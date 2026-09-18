// Copyright Epic Games, Inc. All Rights Reserved.
//
// Unreal State Extraction Fidelity v1 — read-only extraction core.
//
// Contract: docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md, Revision 3.1.
// Section references in comments are to that document.
//
// Read-only by construction (§10.2): this translation unit performs reads only. It
// contains no package dirtying, no transaction, no object creation, no actor mutation,
// no level load/unload, and no write accessor of any kind. The source-level
// forbidden-token test of §10.2 item 3 is asserted by
// tests/test_unreal_state_extraction_readonly_source.py.
//
// Deliberate non-uses required by the contract:
//   * no TActorIterator (§3.2.1.4) — the scan walks ULevel::Actors explicitly;
//   * no StreamingLevelsToConsider, no UActorContainer::Acts (§3.2.1.4);
//   * no FLevelCollection::GetLevels (TSet) and no UWorld::GetLevels (arrival order);
//   * no GetActiveEditorWorld-style fallback (§3.1.1) — one world, one way;
//   * no engine-version branching and no compatibility shim (§3.1.2).

#include "AtlasStateExtraction.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#include "Components/ActorComponent.h"
#include "Components/MeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Containers/StringConv.h"
#include "CoreGlobals.h"
#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/Level.h"
#include "Engine/LevelStreaming.h"
#include "Engine/SkinnedAsset.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/UnrealMemory.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "Misc/FrameRate.h"
#include "MovieScene.h"
#include "UObject/Package.h"

namespace AtlasStateExtraction
{
namespace ErrorCodes
{
const TCHAR* const RequestInvalid = TEXT("ERR_EXTRACTION_REQUEST_INVALID");
const TCHAR* const WorldUnavailable = TEXT("ERR_EXTRACTION_WORLD_UNAVAILABLE");
const TCHAR* const WorldNotEditor = TEXT("ERR_EXTRACTION_WORLD_NOT_EDITOR");
const TCHAR* const WorldPartitionUnsupported = TEXT("ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED");
const TCHAR* const LevelScopeIncomplete = TEXT("ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE");
const TCHAR* const LevelScopeInvalid = TEXT("ERR_EXTRACTION_LEVEL_SCOPE_INVALID");
const TCHAR* const ScopeChanged = TEXT("ERR_EXTRACTION_SCOPE_CHANGED");
const TCHAR* const EntityNotFound = TEXT("ERR_EXTRACTION_ENTITY_NOT_FOUND");
const TCHAR* const EntityAmbiguous = TEXT("ERR_EXTRACTION_ENTITY_AMBIGUOUS");
const TCHAR* const EntityTagConflict = TEXT("ERR_EXTRACTION_ENTITY_TAG_CONFLICT");
const TCHAR* const UnsupportedComponentType = TEXT("ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE");
const TCHAR* const EngineIdentityUnavailable = TEXT("ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE");
const TCHAR* const ParentTagConflict = TEXT("ERR_EXTRACTION_PARENT_TAG_CONFLICT");
const TCHAR* const NonFinite = TEXT("ERR_EXTRACTION_NON_FINITE");
const TCHAR* const MeshCompiling = TEXT("ERR_EXTRACTION_MESH_COMPILING");
const TCHAR* const MeshAssetUnstable = TEXT("ERR_EXTRACTION_MESH_ASSET_UNSTABLE");
const TCHAR* const MaterialUnresolved = TEXT("ERR_EXTRACTION_MATERIAL_UNRESOLVED");
const TCHAR* const UnsupportedMaterialSource = TEXT("ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE");
const TCHAR* const SequenceActorType = TEXT("ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE");
const TCHAR* const SequenceAssetUnresolved = TEXT("ERR_EXTRACTION_SEQUENCE_ASSET_UNRESOLVED");
const TCHAR* const UnsupportedSequenceSource = TEXT("ERR_EXTRACTION_UNSUPPORTED_SEQUENCE_SOURCE");
const TCHAR* const SequenceRangeOpen = TEXT("ERR_EXTRACTION_SEQUENCE_RANGE_OPEN");
const TCHAR* const SequenceRangeInvalid = TEXT("ERR_EXTRACTION_SEQUENCE_RANGE_INVALID");
const TCHAR* const SequenceRateInvalid = TEXT("ERR_EXTRACTION_SEQUENCE_RATE_INVALID");
const TCHAR* const PayloadTooLarge = TEXT("ERR_EXTRACTION_PAYLOAD_TOO_LARGE");
} // namespace ErrorCodes

namespace
{
/** Test-only scope probe storage; null in production (§10.2, §3.2.1a). */
TFunction<void()> GScopeRevalidationProbe;

// ---------------------------------------------------------------------------
// Contract constants
// ---------------------------------------------------------------------------

const FString EntityTagPrefix = TEXT("atlas_entity:");
const TCHAR* const SelectionProvenance = TEXT("g_editor_editor_world_context");
const TCHAR* const WorldTypeEditor = TEXT("editor");
const TCHAR* const LevelKindPersistent = TEXT("persistent");
const TCHAR* const LevelKindStreaming = TEXT("streaming");
const TCHAR* const Binary64 = TEXT("binary64");
const TCHAR* const PlaybackLowerBound = TEXT("inclusive");
const TCHAR* const PlaybackUpperBound = TEXT("exclusive");
const TCHAR* const BooleanOnlyUnrecordedHiddenInput = TEXT("bEditable");
const int32 ExtractionSchemaVersion = 1;
const int32 TransportMessageSizeLimit = 1024 * 1024;

/**
 * Conservative envelope allowance for the §9.3 size check. The value tree plus this
 * headroom must fit the transport bound; the headroom covers the response envelope
 * (identity fields, the session-identity block, the echoed entity_ids and the frame
 * header). Exceeding it fails closed, which is the safe direction: an extraction that
 * passes the check is guaranteed to fit.
 */
const int32 EnvelopeHeadroomBytes = 4096;

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

bool Fail(FString& OutError, FString& OutErrorCode, const TCHAR* Code, const FString& Detail)
{
    OutErrorCode = Code;
    OutError = Detail;
    return false;
}

/** ASCII-only uppercase (§3.3.4): no locale and no Unicode case mapping. */
FString AsciiUpper(const FString& In)
{
    FString Out = In;
    for (int32 Index = 0; Index < Out.Len(); ++Index)
    {
        TCHAR& Character = Out[Index];
        if (Character >= TEXT('a') && Character <= TEXT('z'))
        {
            Character = static_cast<TCHAR>(Character - TEXT('a') + TEXT('A'));
        }
    }
    return Out;
}

/** The canonical entity-ID grammar of §3.3.2, restricted to the canonical form. */
bool IsCanonicalEntityId(const FString& Id)
{
    if (Id.IsEmpty() || Id.Len() > 64)
    {
        return false;
    }
    for (const TCHAR Character : Id)
    {
        const bool bAllowed =
            (Character >= TEXT('A') && Character <= TEXT('Z')) ||
            (Character >= TEXT('0') && Character <= TEXT('9')) ||
            Character == TEXT('_') || Character == TEXT('.') || Character == TEXT('-');
        if (!bAllowed)
        {
            return false;
        }
    }
    return true;
}

/** Canonical integer field. The engine writer emits integral doubles as integers. */
void SetInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, int64 Value)
{
    Object->SetNumberField(Key, static_cast<double>(Value));
}

void SetNull(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key)
{
    Object->SetField(Key, MakeShareable(new FJsonValueNull()));
}

/** A nullable string field: absent values are written as explicit JSON null. */
void SetNullableString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, const FString* Value)
{
    if (Value == nullptr)
    {
        SetNull(Object, Key);
    }
    else
    {
        Object->SetStringField(Key, *Value);
    }
}

TSharedPtr<FJsonObject> MakeObject()
{
    return MakeShareable(new FJsonObject());
}

/** Ordinal, case-sensitive, code-unit comparison (§7.3). Never FString's operator<. */
bool OrdinalLess(const FString& Left, const FString& Right)
{
    return Left.Compare(Right, ESearchCase::CaseSensitive) < 0;
}

FString ObjectPathOf(const UObject* Object)
{
    return Object != nullptr ? Object->GetPathName() : FString();
}

/**
 * Canonical scalar: the binary64 bit pattern as 16 lowercase hex digits (§5.2).
 *
 * The mapping is defined over the pattern, not over memory: the double is reinterpreted
 * as an unsigned 64-bit integer and rendered as hex, so no byte order or host property
 * participates. Non-finite values are refused before encoding (§5.5).
 */
bool PatternOf(double Value, FString& OutPattern, FString& OutError, FString& OutErrorCode)
{
    if (!FMath::IsFinite(Value))
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::NonFinite,
            TEXT("non-finite transform scalar refused before encoding"));
    }
    uint64 Bits = 0;
    static_assert(sizeof(double) == sizeof(uint64), "binary64 canonical form requires a 64-bit double");
    FMemory::Memcpy(&Bits, &Value, sizeof(uint64));
    OutPattern = FString::Printf(TEXT("%016llx"), Bits);
    return true;
}

/** True when the object identity is stable: not transient and not runtime-generated. */
bool IsStableObjectIdentity(const UObject* Object)
{
    return Object != nullptr &&
        Object->GetOutermost() != GetTransientPackage() &&
        !Object->HasAnyFlags(RF_Transient);
}

/**
 * Asset identity for the mesh-asset stability rule (§3.8.3 rule 7): a saved, top-level
 * package asset, with none of the runtime-regenerated markers.
 */
bool IsStablePackageAsset(const UObject* Asset)
{
    if (!IsStableObjectIdentity(Asset))
    {
        return false;
    }
    if (Asset->HasAnyFlags(RF_TextExportTransient | RF_NonPIEDuplicateTransient))
    {
        return false;
    }
    return Cast<UPackage>(Asset->GetOuter()) != nullptr;
}

/**
 * Candidate probe for an `atlas_entity:` tag.
 *
 * Unreal exposes no FName-level prefix query (its own validation helper takes a string),
 * so candidacy is probed on the rendered name with a case-insensitive prefix test, which
 * agrees with FName's case folding over the ASCII prefix. Candidacy is never identity:
 * every binding decision below is made by FName equality (§3.3.3, §3.3.5).
 */
bool IsEntityTagCandidate(const FName& Tag, FString& OutIdPart)
{
    const FString Rendered = Tag.ToString();
    if (!Rendered.StartsWith(EntityTagPrefix, ESearchCase::IgnoreCase))
    {
        return false;
    }
    OutIdPart = Rendered.Mid(EntityTagPrefix.Len());
    return true;
}

/** The canonical IDs a tag set carries, deduplicated by FName (case variants collapse). */
void CollectCanonicalTagIds(const AActor* Actor, TArray<FName>& OutNames, TArray<FString>& OutIds)
{
    for (const FName& Tag : Actor->Tags)
    {
        FString IdPart;
        if (!IsEntityTagCandidate(Tag, IdPart))
        {
            continue;
        }
        // §3.3.5.5: a tag whose ID does not match the canonical grammar is not
        // addressable; it is not a binding and not a conflict.
        const FString CanonicalId = AsciiUpper(IdPart);
        if (!IsCanonicalEntityId(CanonicalId))
        {
            continue;
        }
        if (OutNames.Contains(Tag))
        {
            continue;
        }
        OutNames.Add(Tag);
        OutIds.Add(CanonicalId);
    }
}

// ---------------------------------------------------------------------------
// Level scope (§3.2.1)
// ---------------------------------------------------------------------------

struct FScopeLevel
{
    const ULevel* Level = nullptr;
    FString PackagePath;
    bool bPersistent = false;
};

/** Re-evaluates the scope predicate and re-queries the level set (§3.2.1.4b). */
bool SnapshotScope(
    const UWorld* World,
    TArray<FScopeLevel>& OutScope,
    FString& OutError,
    FString& OutErrorCode)
{
    OutScope.Reset();

    // §3.2.1.4 requires the persistent level in scope. UE 5.6 keeps UWorld's
    // ``PersistentLevel`` member private and offers no public getter for it, so the level
    // is identified by *identity*, not by position: for a non-partitioned world -- the
    // only worlds v1 extracts -- the persistent level is the level whose package is the
    // world's own package, which is exactly the equivalence §4.4 states. Arrival order is
    // never used, so §7.2's prohibition on using the level list as a scope *order* is
    // respected: the list is only the candidate set for this identity test.
    const FString WorldPackage = World->GetOutermost()->GetName();
    const ULevel* PersistentLevel = nullptr;
    int32 PersistentMatches = 0;
    for (const ULevel* Candidate : World->GetLevels())
    {
        if (Candidate != nullptr && Candidate->GetOutermost()->GetName() == WorldPackage)
        {
            PersistentLevel = Candidate;
            ++PersistentMatches;
        }
    }
    if (PersistentLevel == nullptr || PersistentMatches != 1)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::LevelScopeInvalid,
            FString::Printf(
                TEXT("the world package %s identifies %d persistent levels (expected exactly 1)"),
                *WorldPackage,
                PersistentMatches));
    }

    FScopeLevel Persistent;
    Persistent.Level = PersistentLevel;
    Persistent.PackagePath = PersistentLevel->GetOutermost()->GetName();
    Persistent.bPersistent = true;
    OutScope.Add(Persistent);

    for (const ULevelStreaming* Streaming : World->GetStreamingLevels())
    {
        if (Streaming == nullptr)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::LevelScopeInvalid,
                TEXT("the streaming-level array contains a null entry"));
        }
        if (!Streaming->IsLevelLoaded() || !Streaming->IsLevelVisible())
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::LevelScopeIncomplete,
                FString::Printf(
                    TEXT("streaming level %s is not loaded and visible"),
                    *Streaming->GetWorldAssetPackageFName().ToString()));
        }
        const ULevel* LoadedLevel = Streaming->GetLoadedLevel();
        if (LoadedLevel == nullptr)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::LevelScopeInvalid,
                TEXT("a streaming level reports loaded without a level object"));
        }
        FScopeLevel Entry;
        Entry.Level = LoadedLevel;
        Entry.PackagePath = Streaming->GetWorldAssetPackageFName().ToString();
        Entry.bPersistent = false;
        OutScope.Add(Entry);
    }

    return true;
}

/** Compares a re-queried scope against the snapshot (§3.2.1.4b). */
bool ScopeMatches(const TArray<FScopeLevel>& Left, const TArray<FScopeLevel>& Right)
{
    if (Left.Num() != Right.Num())
    {
        return false;
    }
    for (int32 Index = 0; Index < Left.Num(); ++Index)
    {
        if (Left[Index].Level != Right[Index].Level ||
            Left[Index].bPersistent != Right[Index].bPersistent ||
            Left[Index].PackagePath != Right[Index].PackagePath)
        {
            return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Material source state machine (§3.8)
// ---------------------------------------------------------------------------

/** Resolves one material slot value to a stable asset path (§3.8.3 rules 2-3). */
bool MaterialPath(
    const UMaterialInterface* Material,
    bool& bOutHasValue,
    FString& OutPath,
    FString& OutError,
    FString& OutErrorCode)
{
    if (Material == nullptr)
    {
        bOutHasValue = false;
        OutPath.Reset();
        return true;
    }
    if (Material->IsA<UMaterialInstanceDynamic>() ||
        Material->HasAnyFlags(RF_Transient) ||
        Material->GetOutermost() == GetTransientPackage())
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::UnsupportedMaterialSource,
            FString::Printf(
                TEXT("transient or dynamic material instance at %s"),
                *ObjectPathOf(Material)));
    }
    const FString Path = ObjectPathOf(Material);
    if (Path.IsEmpty())
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::MaterialUnresolved,
            TEXT("a non-null material has no stable object path"));
    }
    bOutHasValue = true;
    OutPath = Path;
    return true;
}

struct FMaterialComponentRecord
{
    FString ComponentObjectPath;
    FString ComponentClass;
    bool bHasMesh = false;
    FString MeshAssetPath;
    int32 SlotCount = 0;
    TArray<TSharedPtr<FJsonValue>> Slots;
};

/**
 * Builds the component records for one actor and the omitted-component inventory.
 *
 * Class ordering (§3.8.1a) is explicit: candidates come only from
 * GetComponents<UMeshComponent>; an unregistered component is excluded entirely (it does
 * not participate in the world, §3.8.1 item 2); a registered component outside the two
 * supported families fails the whole extraction (§3.8.1 item 3) and is never inventoried;
 * the inventory covers registered non-mesh primitives only.
 */
bool BuildMaterialState(
    AActor* Actor,
    TArray<FMaterialComponentRecord>& OutComponents,
    int32& OutOmittedCount,
    TArray<FString>& OutOmittedClasses,
    FString& OutError,
    FString& OutErrorCode)
{
    OutComponents.Reset();
    OutOmittedCount = 0;
    OutOmittedClasses.Reset();

    TArray<UMeshComponent*> MeshComponents;
    Actor->GetComponents<UMeshComponent>(MeshComponents, /*bIncludeFromChildActors=*/false);

    for (UMeshComponent* Component : MeshComponents)
    {
        if (Component == nullptr || !Component->IsRegistered())
        {
            continue;
        }
        UStaticMeshComponent* StaticComponent = Cast<UStaticMeshComponent>(Component);
        USkinnedMeshComponent* SkinnedComponent = Cast<USkinnedMeshComponent>(Component);
        if (StaticComponent == nullptr && SkinnedComponent == nullptr)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::UnsupportedComponentType,
                FString::Printf(
                    TEXT("registered component %s (%s) is outside the two supported "
                         "material component families"),
                    *ObjectPathOf(Component),
                    *Component->GetClass()->GetName()));
        }

        FMaterialComponentRecord Record;
        Record.ComponentObjectPath = ObjectPathOf(Component);
        Record.ComponentClass = Component->GetClass()->GetName();

        const UObject* MeshAsset = StaticComponent != nullptr
            ? static_cast<const UObject*>(StaticComponent->GetStaticMesh())
            : static_cast<const UObject*>(SkinnedComponent->GetSkinnedAsset());

        if (MeshAsset != nullptr)
        {
            if (!IsStablePackageAsset(MeshAsset))
            {
                return Fail(
                    OutError,
                    OutErrorCode,
                    ErrorCodes::MeshAssetUnstable,
                    FString::Printf(
                        TEXT("mesh asset %s is not a saved top-level package asset"),
                        *ObjectPathOf(MeshAsset)));
            }
        }

        const bool bCompiling = StaticComponent != nullptr
            ? (StaticComponent->GetStaticMesh() != nullptr && StaticComponent->GetStaticMesh()->IsCompiling())
            : (SkinnedComponent->GetSkinnedAsset() != nullptr && SkinnedComponent->GetSkinnedAsset()->IsCompiling());
        if (bCompiling)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::MeshCompiling,
                FString::Printf(TEXT("mesh asset of %s is compiling"), *Record.ComponentObjectPath));
        }

        Record.bHasMesh = MeshAsset != nullptr;
        Record.MeshAssetPath = ObjectPathOf(MeshAsset);
        Record.SlotCount = Component->GetNumMaterials();

        for (int32 SlotIndex = 0; SlotIndex < Record.SlotCount; ++SlotIndex)
        {
            const UMaterialInterface* AssetSlotMaterial = nullptr;
            if (StaticComponent != nullptr && StaticComponent->GetStaticMesh() != nullptr)
            {
                AssetSlotMaterial = StaticComponent->GetStaticMesh()->GetMaterial(SlotIndex);
            }
            else if (SkinnedComponent != nullptr && SkinnedComponent->GetSkinnedAsset() != nullptr)
            {
                const USkinnedAsset* SkinnedAsset = SkinnedComponent->GetSkinnedAsset();
                if (!SkinnedAsset->IsCompiling() && SkinnedAsset->GetMaterials().IsValidIndex(SlotIndex))
                {
                    AssetSlotMaterial = SkinnedAsset->GetMaterials()[SlotIndex].MaterialInterface;
                }
            }

            const UMaterialInterface* OverrideMaterial =
                Component->OverrideMaterials.IsValidIndex(SlotIndex)
                ? Component->OverrideMaterials[SlotIndex].Get()
                : nullptr;

            // §3.8.2 (Revision 3.3): resolved_material_asset_path is the deterministic
            // source-side projection of the two saved source facts above — the override when
            // it exists and is non-null, otherwise the mesh asset's own slot material. It is
            // computed here from those facts and nothing else: the component's material
            // accessor is deliberately NOT called, because its material-level Nanite step is
            // session/configuration gated (shader platform, r.Nanite.MaterialOverrides, view
            // state) and a digested field may not depend on the session.
            const UMaterialInterface* ResolvedMaterial =
                OverrideMaterial != nullptr ? OverrideMaterial : AssetSlotMaterial;

            FString AssetSlotPath;
            FString OverridePath;
            FString ResolvedPath;
            bool bHasAssetSlot = false;
            bool bHasOverride = false;
            bool bHasResolved = false;
            if (!MaterialPath(AssetSlotMaterial, bHasAssetSlot, AssetSlotPath, OutError, OutErrorCode) ||
                !MaterialPath(OverrideMaterial, bHasOverride, OverridePath, OutError, OutErrorCode) ||
                !MaterialPath(ResolvedMaterial, bHasResolved, ResolvedPath, OutError, OutErrorCode))
            {
                return false;
            }

            TSharedPtr<FJsonObject> Slot = MakeObject();
            SetInt(Slot, TEXT("slot_index"), SlotIndex);
            SetNullableString(Slot, TEXT("asset_slot_material_asset_path"), bHasAssetSlot ? &AssetSlotPath : nullptr);
            SetNullableString(Slot, TEXT("override_material_asset_path"), bHasOverride ? &OverridePath : nullptr);
            SetNullableString(Slot, TEXT("resolved_material_asset_path"), bHasResolved ? &ResolvedPath : nullptr);
            Record.Slots.Add(MakeShareable(new FJsonValueObject(Slot)));
        }

        // §3.8.3 rule 8: the slot read must be coherent with one asset state.
        const bool bCompilingAfter = StaticComponent != nullptr
            ? (StaticComponent->GetStaticMesh() != nullptr && StaticComponent->GetStaticMesh()->IsCompiling())
            : (SkinnedComponent->GetSkinnedAsset() != nullptr && SkinnedComponent->GetSkinnedAsset()->IsCompiling());
        if (bCompilingAfter || Component->GetNumMaterials() != Record.SlotCount)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::MeshCompiling,
                FString::Printf(
                    TEXT("the material slot state of %s changed while it was being read"),
                    *Record.ComponentObjectPath));
        }

        OutComponents.Add(MoveTemp(Record));
    }

    TArray<UPrimitiveComponent*> PrimitiveComponents;
    Actor->GetComponents<UPrimitiveComponent>(PrimitiveComponents, /*bIncludeFromChildActors=*/false);
    for (UPrimitiveComponent* Primitive : PrimitiveComponents)
    {
        if (Primitive == nullptr || !Primitive->IsRegistered())
        {
            continue;
        }
        if (Primitive->IsA<UMeshComponent>())
        {
            continue; // already represented (or already refused) above
        }
        ++OutOmittedCount;
        const FString ClassName = Primitive->GetClass()->GetName();
        if (!OutOmittedClasses.Contains(ClassName))
        {
            OutOmittedClasses.Add(ClassName);
        }
    }
    OutOmittedClasses.Sort(OrdinalLess);

    OutComponents.Sort([](const FMaterialComponentRecord& Left, const FMaterialComponentRecord& Right)
    {
        return Left.ComponentObjectPath.Compare(Right.ComponentObjectPath, ESearchCase::CaseSensitive) < 0;
    });

    return true;
}

// ---------------------------------------------------------------------------
// Actor record (§3.4-§3.7)
// ---------------------------------------------------------------------------

bool BuildParentRecord(
    const AActor* Actor,
    TSharedPtr<FJsonObject>& OutParent,
    FString& OutError,
    FString& OutErrorCode)
{
    OutParent = MakeObject();
    const AActor* Parent = Actor->GetAttachParentActor();
    if (Parent == nullptr)
    {
        OutParent->SetStringField(TEXT("binding"), TEXT("none"));
        SetNull(OutParent, TEXT("entity_id"));
        SetNull(OutParent, TEXT("actor_object_path"));
        return true;
    }

    TArray<FName> CandidateNames;
    TArray<FString> CandidateIds;
    CollectCanonicalTagIds(Parent, CandidateNames, CandidateIds);
    if (CandidateIds.Num() >= 2)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::ParentTagConflict,
            FString::Printf(
                TEXT("attach parent %s carries %d distinct atlas_entity bindings"),
                *ObjectPathOf(Parent),
                CandidateIds.Num()));
    }

    const FString ParentPath = ObjectPathOf(Parent);
    if (CandidateIds.Num() == 0)
    {
        OutParent->SetStringField(TEXT("binding"), TEXT("unbound"));
        SetNull(OutParent, TEXT("entity_id"));
        OutParent->SetStringField(TEXT("actor_object_path"), ParentPath);
        return true;
    }

    OutParent->SetStringField(TEXT("binding"), TEXT("bound"));
    OutParent->SetStringField(TEXT("entity_id"), CandidateIds[0]);
    OutParent->SetStringField(TEXT("actor_object_path"), ParentPath);
    return true;
}

bool BuildTransformRecord(
    const AActor* Actor,
    TSharedPtr<FJsonObject>& OutTransform,
    FString& OutError,
    FString& OutErrorCode)
{
    // §4.3 item 2: the precision premise is a compile-time property, asserted here so
    // the literal cannot become a lie.
    static_assert(sizeof(FVector::FReal) == 8, "v1 requires binary64 vector components");
    static_assert(sizeof(FQuat::FReal) == 8, "v1 requires binary64 quaternion components");

    const FVector Location = Actor->GetActorLocation();
    const FQuat Rotation = Actor->GetActorQuat();
    const FVector Scale = Actor->GetActorScale3D();

    FString LocationX, LocationY, LocationZ, RotationX, RotationY, RotationZ, RotationW, ScaleX, ScaleY, ScaleZ;
    if (!PatternOf(Location.X, LocationX, OutError, OutErrorCode) ||
        !PatternOf(Location.Y, LocationY, OutError, OutErrorCode) ||
        !PatternOf(Location.Z, LocationZ, OutError, OutErrorCode) ||
        !PatternOf(Rotation.X, RotationX, OutError, OutErrorCode) ||
        !PatternOf(Rotation.Y, RotationY, OutError, OutErrorCode) ||
        !PatternOf(Rotation.Z, RotationZ, OutError, OutErrorCode) ||
        !PatternOf(Rotation.W, RotationW, OutError, OutErrorCode) ||
        !PatternOf(Scale.X, ScaleX, OutError, OutErrorCode) ||
        !PatternOf(Scale.Y, ScaleY, OutError, OutErrorCode) ||
        !PatternOf(Scale.Z, ScaleZ, OutError, OutErrorCode))
    {
        return false;
    }

    TSharedPtr<FJsonObject> LocationObject = MakeObject();
    LocationObject->SetStringField(TEXT("x"), LocationX);
    LocationObject->SetStringField(TEXT("y"), LocationY);
    LocationObject->SetStringField(TEXT("z"), LocationZ);

    TSharedPtr<FJsonObject> CoordinateFrame = MakeObject();
    CoordinateFrame->SetStringField(TEXT("handedness"), TEXT("left"));
    CoordinateFrame->SetStringField(TEXT("up_axis"), TEXT("Z"));
    CoordinateFrame->SetStringField(TEXT("positive_x"), TEXT("forward"));
    CoordinateFrame->SetStringField(TEXT("positive_y"), TEXT("right"));
    CoordinateFrame->SetStringField(TEXT("positive_z"), TEXT("up"));

    TSharedPtr<FJsonObject> RotationObject = MakeObject();
    RotationObject->SetObjectField(TEXT("coordinate_frame"), CoordinateFrame);
    RotationObject->SetStringField(TEXT("representation"), TEXT("quaternion"));
    RotationObject->SetStringField(TEXT("component_order"), TEXT("x,y,z,w"));
    RotationObject->SetStringField(TEXT("unit"), TEXT("unitless"));
    RotationObject->SetStringField(TEXT("source"), TEXT("actor_world_quaternion"));
    RotationObject->SetStringField(TEXT("x"), RotationX);
    RotationObject->SetStringField(TEXT("y"), RotationY);
    RotationObject->SetStringField(TEXT("z"), RotationZ);
    RotationObject->SetStringField(TEXT("w"), RotationW);

    TSharedPtr<FJsonObject> ScaleObject = MakeObject();
    ScaleObject->SetStringField(TEXT("x"), ScaleX);
    ScaleObject->SetStringField(TEXT("y"), ScaleY);
    ScaleObject->SetStringField(TEXT("z"), ScaleZ);

    OutTransform = MakeObject();
    OutTransform->SetStringField(TEXT("source_component_type"), Binary64);
    OutTransform->SetObjectField(TEXT("location_cm"), LocationObject);
    OutTransform->SetObjectField(TEXT("rotation"), RotationObject);
    OutTransform->SetObjectField(TEXT("scale"), ScaleObject);
    return true;
}

bool BuildActorRecord(
    AActor* Actor,
    const FString& CanonicalId,
    const FString& LevelPackagePath,
    TSharedPtr<FJsonObject>& OutRecord,
    FString& OutError,
    FString& OutErrorCode)
{
    TSharedPtr<FJsonObject> Parent;
    if (!BuildParentRecord(Actor, Parent, OutError, OutErrorCode))
    {
        return false;
    }

    TSharedPtr<FJsonObject> Transform;
    if (!BuildTransformRecord(Actor, Transform, OutError, OutErrorCode))
    {
        return false;
    }

    TArray<FMaterialComponentRecord> MaterialComponents;
    int32 OmittedCount = 0;
    TArray<FString> OmittedClasses;
    if (!BuildMaterialState(Actor, MaterialComponents, OmittedCount, OmittedClasses, OutError, OutErrorCode))
    {
        return false;
    }

    TArray<TSharedPtr<FJsonValue>> MaterialArray;
    for (const FMaterialComponentRecord& Component : MaterialComponents)
    {
        TSharedPtr<FJsonObject> ComponentObject = MakeObject();
        ComponentObject->SetStringField(TEXT("component_object_path"), Component.ComponentObjectPath);
        ComponentObject->SetStringField(TEXT("component_class"), Component.ComponentClass);
        if (Component.bHasMesh)
        {
            ComponentObject->SetStringField(TEXT("mesh_asset_path"), Component.MeshAssetPath);
        }
        else
        {
            SetNull(ComponentObject, TEXT("mesh_asset_path"));
        }
        ComponentObject->SetStringField(
            TEXT("mesh_state"),
            Component.bHasMesh ? TEXT("mesh_asset_present") : TEXT("no_mesh_asset"));
        SetInt(ComponentObject, TEXT("slot_count"), Component.SlotCount);
        ComponentObject->SetArrayField(TEXT("slots"), Component.Slots);
        MaterialArray.Add(MakeShareable(new FJsonValueObject(ComponentObject)));
    }

    TArray<TSharedPtr<FJsonValue>> UnrecordedHiddenInputs;
    UnrecordedHiddenInputs.Add(MakeShareable(new FJsonValueString(BooleanOnlyUnrecordedHiddenInput)));

    TSharedPtr<FJsonObject> Visibility = MakeObject();
    Visibility->SetBoolField(TEXT("hidden_in_editor"), Actor->IsHiddenEd());
    Visibility->SetBoolField(TEXT("derived_from_gis_editor"), GIsEditor != 0);
    Visibility->SetBoolField(TEXT("hidden_ed_at_startup"), Actor->IsHiddenEdAtStartup());
    Visibility->SetBoolField(TEXT("temporarily_hidden_in_editor"), Actor->IsTemporarilyHiddenInEditor(false));
    Visibility->SetBoolField(TEXT("hidden_ed_layer"), Actor->bHiddenEdLayer != 0);
    Visibility->SetBoolField(TEXT("hidden_ed_level"), Actor->bHiddenEdLevel != 0);
    Visibility->SetArrayField(TEXT("unrecorded_hidden_inputs"), UnrecordedHiddenInputs);

    TSharedPtr<FJsonObject> Omitted = MakeObject();
    SetInt(Omitted, TEXT("count"), OmittedCount);
    TArray<TSharedPtr<FJsonValue>> OmittedClassArray;
    for (const FString& ClassName : OmittedClasses)
    {
        OmittedClassArray.Add(MakeShareable(new FJsonValueString(ClassName)));
    }
    Omitted->SetArrayField(TEXT("classes"), OmittedClassArray);

    OutRecord = MakeObject();
    OutRecord->SetStringField(TEXT("entity_id"), CanonicalId);
    OutRecord->SetStringField(TEXT("actor_name"), Actor->GetName());
    OutRecord->SetStringField(TEXT("actor_object_path"), ObjectPathOf(Actor));
    OutRecord->SetStringField(TEXT("actor_class"), Actor->GetClass()->GetName());
    OutRecord->SetStringField(TEXT("level_package_path"), LevelPackagePath);
    OutRecord->SetObjectField(TEXT("parent"), Parent);
    OutRecord->SetObjectField(TEXT("editor_visibility"), Visibility);
    OutRecord->SetObjectField(TEXT("transform"), Transform);
    OutRecord->SetArrayField(TEXT("materials"), MaterialArray);
    OutRecord->SetObjectField(TEXT("omitted_material_components"), Omitted);
    return true;
}

// ---------------------------------------------------------------------------
// World, engine identity, scope records (§3.1, §4.4)
// ---------------------------------------------------------------------------

bool ResolveEditorWorld(
    UWorld*& OutWorld,
    FString& OutError,
    FString& OutErrorCode)
{
    if (GEditor == nullptr)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::WorldUnavailable,
            TEXT("no editor instance is available in this process"));
    }
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (World == nullptr || !IsValid(World))
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::WorldUnavailable,
            TEXT("the editor world context holds no valid world"));
    }
    if (World->WorldType != EWorldType::Editor)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::WorldNotEditor,
            FString::Printf(
                TEXT("the selected world is not EWorldType::Editor (got %d)"),
                static_cast<int32>(World->WorldType)));
    }
    if (World->IsPartitionedWorld())
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::WorldPartitionUnsupported,
            TEXT("World Partition worlds are refused in v1"));
    }
    OutWorld = World;
    return true;
}

bool BuildWorldRecord(
    const UWorld* World,
    const TArray<FScopeLevel>& Scope,
    TSharedPtr<FJsonObject>& OutWorldRecord,
    FString& OutError,
    FString& OutErrorCode)
{
    const FString EngineVersion = FEngineVersion::Current().ToString(EVersionComponent::Patch);
    const FString BuildVersion = FApp::GetBuildVersion();
    if (EngineVersion.IsEmpty() || BuildVersion.IsEmpty())
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::EngineIdentityUnavailable,
            TEXT("the engine reported an empty version or build string"));
    }

    TArray<FScopeLevel> OrderedScope = Scope;
    OrderedScope.Sort([](const FScopeLevel& Left, const FScopeLevel& Right)
    {
        return Left.PackagePath.Compare(Right.PackagePath, ESearchCase::CaseSensitive) < 0;
    });

    TArray<TSharedPtr<FJsonValue>> LevelArray;
    for (const FScopeLevel& Level : OrderedScope)
    {
        TSharedPtr<FJsonObject> LevelObject = MakeObject();
        LevelObject->SetStringField(TEXT("level_package_path"), Level.PackagePath);
        LevelObject->SetStringField(
            TEXT("level_kind"),
            Level.bPersistent ? LevelKindPersistent : LevelKindStreaming);
        LevelObject->SetBoolField(TEXT("loaded"), true);
        LevelObject->SetBoolField(TEXT("visible"), true);
        LevelArray.Add(MakeShareable(new FJsonValueObject(LevelObject)));
    }

    TSharedPtr<FJsonObject> LevelScope = MakeObject();
    LevelScope->SetArrayField(TEXT("levels"), LevelArray);

    OutWorldRecord = MakeObject();
    OutWorldRecord->SetStringField(TEXT("world_object_path"), ObjectPathOf(World));
    OutWorldRecord->SetStringField(TEXT("world_package_path"), World->GetOutermost()->GetName());
    OutWorldRecord->SetStringField(TEXT("world_name"), World->GetName());
    OutWorldRecord->SetStringField(TEXT("world_type"), WorldTypeEditor);
    OutWorldRecord->SetStringField(TEXT("engine_version"), EngineVersion);
    OutWorldRecord->SetStringField(TEXT("engine_build_version"), BuildVersion);
    OutWorldRecord->SetStringField(TEXT("selection_provenance"), SelectionProvenance);
    OutWorldRecord->SetBoolField(TEXT("is_partitioned_world"), false);
    OutWorldRecord->SetObjectField(TEXT("level_scope"), LevelScope);
    return true;
}

// ---------------------------------------------------------------------------
// Binding (§3.3.5)
// ---------------------------------------------------------------------------

struct FMatch
{
    AActor* Actor = nullptr;
    FString LevelPackagePath;
};

/** Scans the snapshot levels for every requested canonical ID in one pass. */
void ScanScope(
    const TArray<FScopeLevel>& Scope,
    const TArray<FName>& ExpectedNames,
    TArray<TArray<FMatch>>& OutMatches)
{
    OutMatches.Reset();
    OutMatches.SetNum(ExpectedNames.Num());

    for (const FScopeLevel& ScopeLevel : Scope)
    {
        for (const TObjectPtr<AActor>& Entry : ScopeLevel.Level->Actors)
        {
            AActor* Actor = Entry.Get();
            if (!IsValid(Actor))
            {
                continue; // null slot or pending-kill actor (§3.2.1.5)
            }
            for (int32 Index = 0; Index < ExpectedNames.Num(); ++Index)
            {
                if (Actor->Tags.Contains(ExpectedNames[Index]))
                {
                    FMatch Match;
                    Match.Actor = Actor;
                    Match.LevelPackagePath = ScopeLevel.PackagePath;
                    OutMatches[Index].Add(Match);
                }
            }
        }
    }
}

bool PrepareCanonicalRequest(
    const TArray<FString>& EntityIds,
    TArray<FString>& OutCanonicalIds,
    TArray<FName>& OutExpectedNames,
    FString& OutError,
    FString& OutErrorCode)
{
    OutCanonicalIds.Reset();
    OutExpectedNames.Reset();
    TSet<FString> Seen;
    for (const FString& RawId : EntityIds)
    {
        const FString CanonicalId = AsciiUpper(RawId);
        if (!IsCanonicalEntityId(CanonicalId))
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::RequestInvalid,
                FString::Printf(TEXT("entity id [%s] is not canonical"), *RawId));
        }
        if (Seen.Contains(CanonicalId))
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::RequestInvalid,
                FString::Printf(TEXT("duplicate entity id after case folding: [%s]"), *RawId));
        }
        Seen.Add(CanonicalId);
        OutCanonicalIds.Add(CanonicalId);
    }
    if (OutCanonicalIds.Num() == 0)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::RequestInvalid,
            TEXT("the request carries no entity ids"));
    }

    // Canonical order by entity_id (§7.3), and the expected names are derived from the
    // sorted list in the same order. The two arrays are therefore index-aligned by
    // construction; sorting the names independently would be unsound, because an FName's
    // rendered spelling follows the process name table's display casing.
    OutCanonicalIds.Sort(OrdinalLess);
    for (const FString& CanonicalId : OutCanonicalIds)
    {
        OutExpectedNames.Add(FName(*(EntityTagPrefix + CanonicalId)));
    }
    return true;
}

/** §3.8.3-style size bound: the response must fit the transport limit (§9.3). */
bool EnforcePayloadBound(
    const TSharedPtr<FJsonObject>& ValueTree,
    FString& OutError,
    FString& OutErrorCode)
{
    FString Serialized;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialized);
    if (!FJsonSerializer::Serialize(ValueTree.ToSharedRef(), Writer))
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::PayloadTooLarge,
            TEXT("the extraction value tree could not be serialized for the size check"));
    }
    const FTCHARToUTF8 Converted(*Serialized);
    const int32 ByteCount = Converted.Length();
    if (ByteCount + EnvelopeHeadroomBytes > TransportMessageSizeLimit)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::PayloadTooLarge,
            FString::Printf(
                TEXT("the extraction payload would exceed the transport bound (%d bytes)"),
                ByteCount));
    }
    return true;
}

/** Shared scope/binding pipeline: world, scope snapshot, scan, revalidation. */
bool ResolveBindings(
    const TArray<FString>& EntityIds,
    TArray<FString>& OutCanonicalIds,
    TArray<TArray<FMatch>>& OutMatches,
    UWorld*& OutWorld,
    TArray<FScopeLevel>& ScopeStorage,
    FString& OutError,
    FString& OutErrorCode)
{
    TArray<FName> ExpectedNames;
    if (!PrepareCanonicalRequest(EntityIds, OutCanonicalIds, ExpectedNames, OutError, OutErrorCode))
    {
        return false;
    }

    UWorld* World = nullptr;
    if (!ResolveEditorWorld(World, OutError, OutErrorCode))
    {
        return false;
    }

    if (!SnapshotScope(World, ScopeStorage, OutError, OutErrorCode))
    {
        return false;
    }

    ScanScope(ScopeStorage, ExpectedNames, OutMatches);

    // Test-only seam: runs between the snapshot and the re-query. Null in production, so
    // this is a no-op there; the extractor performs no mutation and takes no waits, task
    // hops or polling either way (§3.2.1a).
    if (GScopeRevalidationProbe)
    {
        GScopeRevalidationProbe();
    }

    // §3.2.1.4b: re-query the scope and compare it against the snapshot.
    TArray<FScopeLevel> Revalidated;
    if (!SnapshotScope(World, Revalidated, OutError, OutErrorCode))
    {
        return false;
    }
    if (!ScopeMatches(ScopeStorage, Revalidated))
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::ScopeChanged,
            TEXT("the world's level scope changed while it was being extracted"));
    }

    OutWorld = World;
    return true;
}

} // namespace

bool ExtractActorState(
    const TArray<FString>& EntityIds,
    TSharedPtr<FJsonObject>& OutValueTree,
    FString& OutError,
    FString& OutErrorCode)
{
    TArray<FString> CanonicalIds;
    TArray<TArray<FMatch>> Matches;
    UWorld* World = nullptr;
    TArray<FScopeLevel> ScopeStorage;
    if (!ResolveBindings(EntityIds, CanonicalIds, Matches, World, ScopeStorage, OutError, OutErrorCode))
    {
        return false;
    }

    TSharedPtr<FJsonObject> WorldRecord;
    if (!BuildWorldRecord(World, ScopeStorage, WorldRecord, OutError, OutErrorCode))
    {
        return false;
    }

    TArray<TSharedPtr<FJsonValue>> ActorArray;
    for (int32 Index = 0; Index < CanonicalIds.Num(); ++Index)
    {
        const TArray<FMatch>& IndexMatches = Matches[Index];
        if (IndexMatches.Num() == 0)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::EntityNotFound,
                FString::Printf(TEXT("no actor in scope carries %s%s"), *EntityTagPrefix, *CanonicalIds[Index]));
        }
        if (IndexMatches.Num() > 1)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::EntityAmbiguous,
                FString::Printf(
                    TEXT("%d actors in scope carry %s%s"),
                    IndexMatches.Num(),
                    *EntityTagPrefix,
                    *CanonicalIds[Index]));
        }

        AActor* Actor = IndexMatches[0].Actor;

        // §3.3.5 rule 4: two or more distinct canonical identities on the matched actor.
        TArray<FName> CandidateNames;
        TArray<FString> CandidateIds;
        CollectCanonicalTagIds(Actor, CandidateNames, CandidateIds);
        if (CandidateIds.Num() >= 2)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::EntityTagConflict,
                FString::Printf(
                    TEXT("actor %s carries %d distinct atlas_entity bindings"),
                    *ObjectPathOf(Actor),
                    CandidateIds.Num()));
        }

        TSharedPtr<FJsonObject> Record;
        if (!BuildActorRecord(
                Actor,
                CanonicalIds[Index],
                IndexMatches[0].LevelPackagePath,
                Record,
                OutError,
                OutErrorCode))
        {
            return false;
        }
        ActorArray.Add(MakeShareable(new FJsonValueObject(Record)));
    }

    TSharedPtr<FJsonObject> Tree = MakeObject();
    SetInt(Tree, TEXT("extraction_schema_version"), ExtractionSchemaVersion);
    Tree->SetStringField(TEXT("extraction_kind"), TEXT("actor_state"));
    Tree->SetObjectField(TEXT("world"), WorldRecord);
    Tree->SetArrayField(TEXT("actors"), ActorArray);
    Tree->SetArrayField(TEXT("sequences"), TArray<TSharedPtr<FJsonValue>>());

    if (!EnforcePayloadBound(Tree, OutError, OutErrorCode))
    {
        return false;
    }
    OutValueTree = Tree;
    return true;
}

bool ExtractSequencerState(
    const TArray<FString>& EntityIds,
    TSharedPtr<FJsonObject>& OutValueTree,
    FString& OutError,
    FString& OutErrorCode)
{
    if (EntityIds.Num() != 1)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::RequestInvalid,
            TEXT("a sequencer-state extraction targets exactly one entity id"));
    }

    TArray<FString> CanonicalIds;
    TArray<TArray<FMatch>> Matches;
    UWorld* World = nullptr;
    TArray<FScopeLevel> ScopeStorage;
    if (!ResolveBindings(EntityIds, CanonicalIds, Matches, World, ScopeStorage, OutError, OutErrorCode))
    {
        return false;
    }

    const TArray<FMatch>& IndexMatches = Matches[0];
    if (IndexMatches.Num() == 0)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::EntityNotFound,
            FString::Printf(TEXT("no actor in scope carries %s%s"), *EntityTagPrefix, *CanonicalIds[0]));
    }
    if (IndexMatches.Num() > 1)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::EntityAmbiguous,
            FString::Printf(
                TEXT("%d actors in scope carry %s%s"),
                IndexMatches.Num(),
                *EntityTagPrefix,
                *CanonicalIds[0]));
    }

    AActor* Actor = IndexMatches[0].Actor;

    // §3.3.5 rule 4 applies to the matched actor in either extraction kind.
    {
        TArray<FName> CandidateNames;
        TArray<FString> CandidateIds;
        CollectCanonicalTagIds(Actor, CandidateNames, CandidateIds);
        if (CandidateIds.Num() >= 2)
        {
            return Fail(
                OutError,
                OutErrorCode,
                ErrorCodes::EntityTagConflict,
                FString::Printf(
                    TEXT("actor %s carries %d distinct atlas_entity bindings"),
                    *ObjectPathOf(Actor),
                    CandidateIds.Num()));
        }
    }

    ALevelSequenceActor* SequenceActor = Cast<ALevelSequenceActor>(Actor);
    if (SequenceActor == nullptr)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceActorType,
            FString::Printf(TEXT("actor %s is not an ALevelSequenceActor"), *ObjectPathOf(Actor)));
    }

    ULevelSequence* Sequence = SequenceActor->GetSequence();
    if (Sequence == nullptr)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceAssetUnresolved,
            TEXT("the level sequence actor has no sequence asset"));
    }
    UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (MovieScene == nullptr)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceAssetUnresolved,
            TEXT("the sequence asset has no MovieScene"));
    }
    if (!IsStableObjectIdentity(Sequence))
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::UnsupportedSequenceSource,
            FString::Printf(TEXT("sequence asset %s is transient"), *ObjectPathOf(Sequence)));
    }

    const TRange<FFrameNumber> PlaybackRange = MovieScene->GetPlaybackRange();
    if (!PlaybackRange.HasLowerBound() || !PlaybackRange.HasUpperBound())
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceRangeOpen,
            TEXT("the playback range has an open bound"));
    }
    const int32 LowerFrame = PlaybackRange.GetLowerBoundValue().Value;
    const int32 UpperFrame = PlaybackRange.GetUpperBoundValue().Value;
    if (UpperFrame <= LowerFrame)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceRangeInvalid,
            FString::Printf(TEXT("the playback range [%d, %d) is degenerate"), LowerFrame, UpperFrame));
    }

    const FFrameRate TickResolution = MovieScene->GetTickResolution();
    const FFrameRate DisplayRate = MovieScene->GetDisplayRate();
    if (TickResolution.Numerator <= 0 || TickResolution.Denominator <= 0 ||
        DisplayRate.Numerator <= 0 || DisplayRate.Denominator <= 0)
    {
        return Fail(
            OutError,
            OutErrorCode,
            ErrorCodes::SequenceRateInvalid,
            FString::Printf(
                TEXT("non-positive frame rate: tick %d/%d, display %d/%d"),
                TickResolution.Numerator,
                TickResolution.Denominator,
                DisplayRate.Numerator,
                DisplayRate.Denominator));
    }

    TSharedPtr<FJsonObject> PlaybackRangeObject = MakeObject();
    SetInt(PlaybackRangeObject, TEXT("lower_frame"), LowerFrame);
    PlaybackRangeObject->SetStringField(TEXT("lower_bound"), PlaybackLowerBound);
    SetInt(PlaybackRangeObject, TEXT("upper_frame"), UpperFrame);
    PlaybackRangeObject->SetStringField(TEXT("upper_bound"), PlaybackUpperBound);

    TSharedPtr<FJsonObject> TickObject = MakeObject();
    SetInt(TickObject, TEXT("numerator"), TickResolution.Numerator);
    SetInt(TickObject, TEXT("denominator"), TickResolution.Denominator);

    TSharedPtr<FJsonObject> DisplayObject = MakeObject();
    SetInt(DisplayObject, TEXT("numerator"), DisplayRate.Numerator);
    SetInt(DisplayObject, TEXT("denominator"), DisplayRate.Denominator);

    TSharedPtr<FJsonObject> Record = MakeObject();
    Record->SetStringField(TEXT("entity_id"), CanonicalIds[0]);
    Record->SetStringField(TEXT("sequence_actor_object_path"), ObjectPathOf(Actor));
    Record->SetStringField(TEXT("sequence_asset_object_path"), ObjectPathOf(Sequence));
    Record->SetObjectField(TEXT("playback_range"), PlaybackRangeObject);
    Record->SetObjectField(TEXT("tick_resolution"), TickObject);
    Record->SetObjectField(TEXT("display_rate"), DisplayObject);

    TArray<TSharedPtr<FJsonValue>> SequenceArray;
    SequenceArray.Add(MakeShareable(new FJsonValueObject(Record)));

    TSharedPtr<FJsonObject> WorldRecord;
    if (!BuildWorldRecord(World, ScopeStorage, WorldRecord, OutError, OutErrorCode))
    {
        return false;
    }

    TSharedPtr<FJsonObject> Tree = MakeObject();
    SetInt(Tree, TEXT("extraction_schema_version"), ExtractionSchemaVersion);
    Tree->SetStringField(TEXT("extraction_kind"), TEXT("sequencer_state"));
    Tree->SetObjectField(TEXT("world"), WorldRecord);
    Tree->SetArrayField(TEXT("actors"), TArray<TSharedPtr<FJsonValue>>());
    Tree->SetArrayField(TEXT("sequences"), SequenceArray);

    if (!EnforcePayloadBound(Tree, OutError, OutErrorCode))
    {
        return false;
    }
    OutValueTree = Tree;
    return true;
}

void SetScopeRevalidationProbe(FScopeProbe InProbe)
{
    check(IsInGameThread());
    GScopeRevalidationProbe = MoveTemp(InProbe);
}

void ClearScopeRevalidationProbe()
{
    GScopeRevalidationProbe = nullptr;
}

} // namespace AtlasStateExtraction
