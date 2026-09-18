// Copyright Epic Games, Inc. All Rights Reserved.
//
// Unreal State Extraction Fidelity v1 — dedicated extraction fixture (implementation).
//
// TEST FIXTURE content for the extraction gate. Nothing in this file is production
// extraction code: it creates saved fixture content once, and per-session runtime probes,
// so that the contract's state-space branches can be exercised live. See the header for
// the inventory and for what is deliberately left to the legacy fixtures.

#include "AtlasExtractionFixture.h"

#include "AtlasUnrealTransport.h"
#include "Animation/SkeletalMeshActor.h"
#include "Components/DecalComponent.h"
#include "Components/HeterogeneousVolumeComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Containers/Ticker.h"
#include "Editor.h"
#include "EditorLevelUtils.h"
#include "Engine/DecalActor.h"
#include "Engine/LevelStreamingDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Factories/WorldFactory.h"
#include "FileHelpers.h"
#include "GameFramework/Actor.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "Materials/MaterialInterface.h"
#include "Math/Range.h"
#include "Math/RangeBound.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "MovieScene.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace AtlasExtractionFixture
{
namespace Names
{
const TCHAR* const FixtureMapPackage = TEXT("/Game/AtlasTest/Generated/AtlasExtractionFixture");
const TCHAR* const FixtureMapObjectPath =
    TEXT("/Game/AtlasTest/Generated/AtlasExtractionFixture.AtlasExtractionFixture");
const TCHAR* const SublevelPackage = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSublevel");
const TCHAR* const ValidSequencePackage = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSequenceValid");
const TCHAR* const DegenerateSequencePackage = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSequenceDegenerate");
const TCHAR* const BadRateSequencePackage = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSequenceBadRate");

const TCHAR* const PermutationA = TEXT("IMPL_PERM_A");
const TCHAR* const PermutationB = TEXT("IMPL_PERM_B");
const TCHAR* const CaseLower = TEXT("case_lower");
const TCHAR* const CaseUpper = TEXT("CASE_UPPER");
const TCHAR* const CaseVariantBound = TEXT("CaseVariantBound");
const TCHAR* const NumberedBase = TEXT("CAM");
const TCHAR* const NumberedOne = TEXT("CAM_1");
const TCHAR* const NumberedLeadingZero = TEXT("CAM_01");
const TCHAR* const ParentNone = TEXT("IMPL_PARENT_NONE");
const TCHAR* const ParentUnbound = TEXT("IMPL_PARENT_UNBOUND");
const TCHAR* const ParentBound = TEXT("IMPL_PARENT_BOUND");
const TCHAR* const MaterialOverrideA = TEXT("IMPL_MATERIAL_OVERRIDE_A");
const TCHAR* const MaterialOverrideB = TEXT("IMPL_MATERIAL_OVERRIDE_B");
const TCHAR* const OmittedPrimitive = TEXT("IMPL_OMITTED");
const TCHAR* const NullSkinned = TEXT("IMPL_NULL_SKINNED");
const TCHAR* const UnsupportedComponent = TEXT("IMPL_UNSUPPORTED_COMPONENT");
const TCHAR* const SignedZero = TEXT("IMPL_SIGNED_ZERO");
const TCHAR* const QuaternionPositive = TEXT("IMPL_Q_POS");
const TCHAR* const QuaternionNegative = TEXT("IMPL_Q_NEG");
const TCHAR* const SequenceValid = TEXT("IMPL_SEQUENCE_VALID");
const TCHAR* const SequenceDegenerate = TEXT("IMPL_SEQUENCE_DEGENERATE");
const TCHAR* const SequenceBadRate = TEXT("IMPL_SEQUENCE_BAD_RATE");
const TCHAR* const RuntimeMesh = TEXT("IMPL_RUNTIME_MESH");
} // namespace Names

namespace
{
using namespace Names;

const TCHAR* const EntityTagPrefix = TEXT("atlas_entity:");

// Saved asset paths used by the fixture (engine content, all stable top-level assets).
const TCHAR* const CubeMeshPath = TEXT("/Engine/BasicShapes/Cube.Cube");
const TCHAR* const SphereMeshPath = TEXT("/Engine/BasicShapes/Sphere.Sphere");
const TCHAR* const BasicShapeMaterialPath = TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial");
const TCHAR* const DefaultMaterialPath = TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial");
const TCHAR* const WorldGridMaterialPath = TEXT("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial");

FTSTicker::FDelegateHandle GTickerHandle;
bool GSavedContentReady = false;
int32 GSavedContentAttempts = 0;
bool GRuntimeProbesEnsured = false;

/** Bumped whenever the generated fixture content changes shape. */
constexpr int32 FixtureContentVersion = 3;

FName TagName(const TCHAR* EntityId)
{
    return FName(*FString::Printf(TEXT("%s%s"), EntityTagPrefix, EntityId));
}

AActor* SpawnTaggedActor(UWorld* World, const TCHAR* ActorName, const TCHAR* EntityId)
{
    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = FName(ActorName);
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

    AActor* Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, SpawnParameters);
    if (Actor == nullptr)
    {
        return nullptr;
    }

    USceneComponent* RootComponent = NewObject<USceneComponent>(
        Actor, FName(*FString::Printf(TEXT("%sRoot"), ActorName)));
    if (RootComponent == nullptr)
    {
        return nullptr;
    }
    Actor->SetRootComponent(RootComponent);
    RootComponent->RegisterComponent();
    Actor->Tags.AddUnique(TagName(EntityId));
    return Actor;
}

UStaticMeshComponent* AddStaticMeshComponent(
    AActor* Actor,
    const TCHAR* ComponentName,
    const TCHAR* MeshPath,
    const TCHAR* OverrideMaterialPath)
{
    UStaticMeshComponent* Component = NewObject<UStaticMeshComponent>(Actor, FName(ComponentName));
    if (Component == nullptr)
    {
        return nullptr;
    }
    // A runtime-created component must join the actor's instance-component list, otherwise
    // it is not part of the saved actor (this is what made the first fixture generation
    // lose every child component).
    Actor->AddInstanceComponent(Component);
    Component->SetupAttachment(Actor->GetRootComponent());
    if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, MeshPath))
    {
        Component->SetStaticMesh(Mesh);
    }
    if (OverrideMaterialPath != nullptr)
    {
        if (UMaterialInterface* Override = LoadObject<UMaterialInterface>(nullptr, OverrideMaterialPath))
        {
            // A component-level override: the assignment fact the contract records beside
            // the asset slot and the engine's resolved value.
            Component->SetMaterial(0, Override);
        }
    }
    Component->RegisterComponent();
    return Component;
}

/** Spawns a tagged AStaticMeshActor: its mesh component is engine-owned, so it persists. */
AActor* SpawnStaticMeshActor(
    UWorld* World,
    const TCHAR* ActorName,
    const TCHAR* EntityId,
    const TCHAR* MeshPath,
    const TCHAR* OverrideMaterialPath)
{
    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = FName(ActorName);
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

    AStaticMeshActor* MeshActor =
        World->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FTransform::Identity, SpawnParameters);
    if (MeshActor == nullptr)
    {
        return nullptr;
    }
    MeshActor->Tags.AddUnique(TagName(EntityId));
    MeshActor->SetActorLabel(ActorName);

    UStaticMeshComponent* Component = MeshActor->GetStaticMeshComponent();
    if (Component == nullptr)
    {
        return nullptr;
    }
    if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, MeshPath))
    {
        Component->SetStaticMesh(Mesh);
    }
    if (OverrideMaterialPath != nullptr)
    {
        if (UMaterialInterface* Override = LoadObject<UMaterialInterface>(nullptr, OverrideMaterialPath))
        {
            Component->SetMaterial(0, Override);
        }
    }
    return MeshActor;
}

/** Creates (if missing) and saves the empty world package used as a map. */
UWorld* EnsureEmptyMapWorld(const TCHAR* PackageName, const TCHAR* WorldName, FString& OutError)
{
    if (UWorld* Existing = LoadObject<UWorld>(nullptr, *(FString(PackageName) + TEXT(".") + WorldName)))
    {
        return Existing;
    }

    UPackage* Package = CreatePackage(PackageName);
    if (Package == nullptr)
    {
        OutError = FString::Printf(TEXT("unable to create package %s"), PackageName);
        return nullptr;
    }

    UWorldFactory* Factory = NewObject<UWorldFactory>();
    if (Factory == nullptr)
    {
        OutError = TEXT("unable to create UWorldFactory");
        return nullptr;
    }
    Factory->WorldType = EWorldType::Editor;
    Factory->bCreateWorldPartition = false;
    Factory->bInformEngineOfWorld = true;

    UWorld* World = Cast<UWorld>(Factory->FactoryCreateNew(
        UWorld::StaticClass(),
        Package,
        FName(WorldName),
        RF_Public | RF_Standalone,
        nullptr,
        GWarn));
    if (World == nullptr)
    {
        OutError = FString::Printf(TEXT("unable to create world %s"), WorldName);
        return nullptr;
    }
    World->UpdateWorldComponents(true, true);
    return World;
}

enum class ESequenceMode
{
    Valid,
    DegenerateRange,
    BadRate
};

/** Creates (if missing) and saves one sequence asset in the requested validity state. */
bool EnsureSequenceAsset(const TCHAR* PackageName, ESequenceMode Mode, FString& OutError)
{
    const FString AssetName = FPackageName::GetShortName(PackageName);
    UPackage* Package = LoadPackage(nullptr, PackageName, LOAD_None);
    if (Package == nullptr)
    {
        Package = CreatePackage(PackageName);
    }
    if (Package == nullptr)
    {
        OutError = FString::Printf(TEXT("unable to create package %s"), PackageName);
        return false;
    }

    ULevelSequence* Sequence = LoadObject<ULevelSequence>(Package, *AssetName);
    if (Sequence == nullptr)
    {
        Sequence = NewObject<ULevelSequence>(Package, *AssetName, RF_Public | RF_Standalone);
        if (Sequence == nullptr)
        {
            OutError = FString::Printf(TEXT("unable to create sequence %s"), *AssetName);
            return false;
        }
        Sequence->Initialize();
    }

    UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (MovieScene == nullptr)
    {
        OutError = FString::Printf(TEXT("sequence %s has no MovieScene"), *AssetName);
        return false;
    }

    switch (Mode)
    {
    case ESequenceMode::Valid:
        MovieScene->SetTickResolutionDirectly(FFrameRate(24000, 1));
        MovieScene->SetDisplayRate(FFrameRate(30, 1));
        MovieScene->SetPlaybackRange(FFrameNumber(0), 100);
        break;
    case ESequenceMode::DegenerateRange:
        MovieScene->SetTickResolutionDirectly(FFrameRate(24000, 1));
        MovieScene->SetDisplayRate(FFrameRate(30, 1));
        MovieScene->SetPlaybackRange(FFrameNumber(0), 0);
        break;
    case ESequenceMode::BadRate:
        // The "Directly" setter bypasses the engine's own rate validation, which is what
        // makes the invalid-rate state reachable at all.
        MovieScene->SetTickResolutionDirectly(FFrameRate(0, 1));
        MovieScene->SetDisplayRate(FFrameRate(30, 1));
        MovieScene->SetPlaybackRange(FFrameNumber(0), 100);
        break;
    }

    const FString PackageFilename =
        FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(PackageFilename), true);
    Package->MarkPackageDirty();

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;
    if (!UPackage::SavePackage(Package, Sequence, *PackageFilename, SaveArgs))
    {
        OutError = FString::Printf(TEXT("unable to save sequence asset %s"), PackageName);
        return false;
    }
    return true;
}

/** Attaches `Child` to `Parent`, which is the fixture's parent-state mechanism. */
void AttachTo(AActor* Child, AActor* Parent)
{
    if (Child != nullptr && Parent != nullptr)
    {
        Child->AttachToActor(Parent, FAttachmentTransformRules::KeepRelativeTransform);
    }
}

bool PopulateFixtureMap(UWorld* MapWorld, TArray<ULevelSequence*>& OutSequences, FString& OutError)
{
    // Permutation pair: two independently tagged actors.
    AActor* PermutationAActor =
        SpawnStaticMeshActor(MapWorld, TEXT("ImplPermA"), PermutationA, CubeMeshPath, nullptr);
    AActor* PermutationBActor =
        SpawnStaticMeshActor(MapWorld, TEXT("ImplPermB"), PermutationB, SphereMeshPath, nullptr);
    if (PermutationAActor == nullptr || PermutationBActor == nullptr)
    {
        OutError = TEXT("unable to spawn the permutation fixture actors");
        return false;
    }

    // Case variants that must collapse to one FName binding.
    SpawnTaggedActor(MapWorld, TEXT("ImplCaseLower"), CaseLower);
    SpawnTaggedActor(MapWorld, TEXT("ImplCaseUpper"), CaseUpper);
    SpawnTaggedActor(MapWorld, TEXT("ImplCaseVariantBound"), CaseVariantBound);

    // Numbered identities: three distinct FName classes.
    SpawnTaggedActor(MapWorld, TEXT("ImplNumberedBase"), NumberedBase);
    SpawnTaggedActor(MapWorld, TEXT("ImplNumberedOne"), NumberedOne);
    SpawnTaggedActor(MapWorld, TEXT("ImplNumberedLeadingZero"), NumberedLeadingZero);

    // Parent states: none, unbound (untagged parent), bound (tagged parent).
    SpawnTaggedActor(MapWorld, TEXT("ImplParentNone"), ParentNone);
    AActor* UntaggedParent = MapWorld->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
    if (UntaggedParent != nullptr)
    {
        USceneComponent* UntaggedRoot = NewObject<USceneComponent>(UntaggedParent, TEXT("UntaggedParentRoot"));
        UntaggedParent->SetRootComponent(UntaggedRoot);
        UntaggedRoot->RegisterComponent();
    }
    AActor* UnboundChild = SpawnTaggedActor(MapWorld, TEXT("ImplParentUnbound"), ParentUnbound);
    AActor* BoundChild = SpawnTaggedActor(MapWorld, TEXT("ImplParentBound"), ParentBound);
    AttachTo(UnboundChild, UntaggedParent);
    AttachTo(BoundChild, PermutationAActor);

    // Material assignment versus resolution. The engine content's own slot materials are
    // WorldGridMaterial on the cube and DefaultMaterial on the sphere, so the overrides are
    // chosen to differ from each asset's own slot (otherwise the three material facts
    // collapse and the arm proves nothing).
    AActor* OverrideA = SpawnStaticMeshActor(
        MapWorld, TEXT("ImplMaterialOverrideA"), MaterialOverrideA, CubeMeshPath, DefaultMaterialPath);
    AActor* OverrideB = SpawnStaticMeshActor(
        MapWorld, TEXT("ImplMaterialOverrideB"), MaterialOverrideB, SphereMeshPath, WorldGridMaterialPath);
    if (OverrideA == nullptr || OverrideB == nullptr)
    {
        OutError = TEXT("unable to spawn the material override fixture actors");
        return false;
    }
    // A second mesh component on one actor with a different override: two assignment states
    // inside one actor, both distinct from the cube's own slot material.
    AddStaticMeshComponent(OverrideA, TEXT("OverlayMesh"), CubeMeshPath, BasicShapeMaterialPath);

    // A registered non-mesh primitive: the omitted-material-component inventory arm.
    FActorSpawnParameters DecalSpawnParameters;
    DecalSpawnParameters.Name = FName(TEXT("ImplOmitted"));
    DecalSpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ADecalActor* OmittedActor = MapWorld->SpawnActor<ADecalActor>(
        ADecalActor::StaticClass(), FTransform::Identity, DecalSpawnParameters);
    if (OmittedActor == nullptr)
    {
        OutError = TEXT("unable to spawn the omitted-inventory fixture actor");
        return false;
    }
    OmittedActor->Tags.AddUnique(TagName(OmittedPrimitive));
    OmittedActor->SetActorLabel(TEXT("ImplOmitted"));

    // A skinned-family component with no skinned asset (null-mesh arm of that family).
    FActorSpawnParameters SkinnedSpawnParameters;
    SkinnedSpawnParameters.Name = FName(TEXT("ImplNullSkinned"));
    SkinnedSpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    ASkeletalMeshActor* SkinnedActor = MapWorld->SpawnActor<ASkeletalMeshActor>(
        ASkeletalMeshActor::StaticClass(), FTransform::Identity, SkinnedSpawnParameters);
    if (SkinnedActor == nullptr || SkinnedActor->GetSkeletalMeshComponent() == nullptr)
    {
        OutError = TEXT("unable to spawn the null-mesh skinned fixture actor");
        return false;
    }
    SkinnedActor->Tags.AddUnique(TagName(NullSkinned));
    SkinnedActor->SetActorLabel(TEXT("ImplNullSkinned"));

    // A registered UMeshComponent outside the two supported families: refusal arm.
    AActor* Unsupported = SpawnTaggedActor(MapWorld, TEXT("ImplUnsupportedComponent"), UnsupportedComponent);
    if (Unsupported != nullptr)
    {
        UHeterogeneousVolumeComponent* UnsupportedComponent_ =
            NewObject<UHeterogeneousVolumeComponent>(Unsupported, TEXT("UnsupportedVolume"));
        Unsupported->AddInstanceComponent(UnsupportedComponent_);
        UnsupportedComponent_->SetupAttachment(Unsupported->GetRootComponent());
        UnsupportedComponent_->RegisterComponent();
    }

    // Signed zero. Two surfaces are set deliberately: the world location goes through the
    // engine's transform composition (which may normalise the sign), while the relative
    // scale is a stored source value. The gate records which surface preserves the sign
    // instead of assuming one does.
    AActor* SignedZeroActor = SpawnTaggedActor(MapWorld, TEXT("ImplSignedZero"), SignedZero);
    if (SignedZeroActor != nullptr && SignedZeroActor->GetRootComponent() != nullptr)
    {
        const double NegativeZero = -1.0 * 0.0;
        SignedZeroActor->GetRootComponent()->SetRelativeLocation(FVector(NegativeZero, 0.0, 0.0));
        SignedZeroActor->GetRootComponent()->SetRelativeScale3D(FVector(NegativeZero, 1.0, 1.0));
    }

    // Quaternion sign: +q and -q for the same 90-degree rotation about Z.
    const double HalfSqrt = 0.70710678118654752440;
    AActor* QuaternionPositiveActor = SpawnTaggedActor(MapWorld, TEXT("ImplQuaternionPositive"), QuaternionPositive);
    if (QuaternionPositiveActor != nullptr && QuaternionPositiveActor->GetRootComponent() != nullptr)
    {
        QuaternionPositiveActor->GetRootComponent()->SetRelativeRotation(FQuat(0.0, 0.0, HalfSqrt, HalfSqrt));
    }
    AActor* QuaternionNegativeActor = SpawnTaggedActor(MapWorld, TEXT("ImplQuaternionNegative"), QuaternionNegative);
    if (QuaternionNegativeActor != nullptr && QuaternionNegativeActor->GetRootComponent() != nullptr)
    {
        QuaternionNegativeActor->GetRootComponent()->SetRelativeRotation(FQuat(0.0, 0.0, -HalfSqrt, -HalfSqrt));
    }

    // Sequencer arms: one entity-tagged ALevelSequenceActor per reachable validity state.
    OutSequences.Reset();
    for (const TPair<const TCHAR*, const TCHAR*>& Pair :
         {TPair<const TCHAR*, const TCHAR*>(SequenceValid, ValidSequencePackage),
          TPair<const TCHAR*, const TCHAR*>(SequenceDegenerate, DegenerateSequencePackage),
          TPair<const TCHAR*, const TCHAR*>(SequenceBadRate, BadRateSequencePackage)})
    {
        ULevelSequence* Sequence =
            LoadObject<ULevelSequence>(nullptr, *(FString(Pair.Value) + TEXT(".") + FPackageName::GetShortName(Pair.Value)));
        if (Sequence == nullptr)
        {
            OutError = FString::Printf(TEXT("sequence asset %s is missing"), Pair.Value);
            return false;
        }
        FActorSpawnParameters SpawnParameters;
        SpawnParameters.Name = FName(*FString::Printf(TEXT("ImplSequenceActor_%s"), Pair.Key));
        ALevelSequenceActor* SequenceActor = MapWorld->SpawnActor<ALevelSequenceActor>(
            ALevelSequenceActor::StaticClass(), FTransform::Identity, SpawnParameters);
        if (SequenceActor == nullptr)
        {
            OutError = TEXT("unable to spawn a level sequence actor");
            return false;
        }
        SequenceActor->Tags.AddUnique(TagName(Pair.Key));
        SequenceActor->SetSequence(Sequence);
        OutSequences.Add(Sequence);
    }

    // Negative control: an actor with no entity tag at all, so it must never appear in a
    // payload no matter which entity is requested.
    AActor* NegativeControlActor =
        MapWorld->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
    if (NegativeControlActor == nullptr)
    {
        OutError = TEXT("unable to spawn the negative control actor");
        return false;
    }
    USceneComponent* NegativeControlRoot =
        NewObject<USceneComponent>(NegativeControlActor, TEXT("ImplNegativeControlRoot"));
    if (NegativeControlRoot == nullptr)
    {
        OutError = TEXT("unable to create the negative control root component");
        return false;
    }
    NegativeControlActor->SetRootComponent(NegativeControlRoot);
    NegativeControlRoot->RegisterComponent();
    NegativeControlActor->SetActorLabel(TEXT("Impl Negative Control (untagged)"));

    MapWorld->UpdateWorldComponents(true, true);
    return true;
}
} // namespace

bool IsFixtureWorld(const UWorld* World)
{
    return World != nullptr && World->GetOutermost() != nullptr &&
        World->GetOutermost()->GetName() == FixtureMapPackage;
}

bool EnsureSavedFixtureContent(FString& OutError)
{
    // Sequence assets first: the map's sequence actors reference them.
    //
    // The open-bound range arm is deliberately absent: `UMovieScene::SetPlaybackRange(const
    // TRange<FFrameNumber>&)` documents "Must not have any open bounds (ie must be a finite
    // range)" and *asserts* it (MovieScene.cpp:689
    // `NewRange.GetLowerBound().IsClosed() && NewRange.GetUpperBound().IsClosed()`), and the
    // `PlaybackRange` storage is private (MovieScene.h:1271/1311). An open-bound playback
    // range is therefore unreachable through any public engine API, so no fixture can hold
    // it; the arm stays a defensive contract state and is reported as such.
    if (!EnsureSequenceAsset(ValidSequencePackage, ESequenceMode::Valid, OutError) ||
        !EnsureSequenceAsset(DegenerateSequencePackage, ESequenceMode::DegenerateRange, OutError) ||
        !EnsureSequenceAsset(BadRateSequencePackage, ESequenceMode::BadRate, OutError))
    {
        return false;
    }

    // The sublevel is only a load target for the runtime scope probe; it stays empty.
    if (EnsureEmptyMapWorld(SublevelPackage, TEXT("AtlasExtractionSublevel"), OutError) == nullptr)
    {
        return false;
    }
    const FString SublevelFilename =
        FPackageName::LongPackageNameToFilename(SublevelPackage, FPackageName::GetMapPackageExtension());
    if (!FPaths::FileExists(SublevelFilename))
    {
        UWorld* Sublevel = LoadObject<UWorld>(nullptr, *(FString(SublevelPackage) + TEXT(".AtlasExtractionSublevel")));
        if (Sublevel != nullptr)
        {
            Sublevel->GetOutermost()->MarkPackageDirty();
        }
        if (Sublevel == nullptr || !UEditorLoadingAndSavingUtils::SaveMap(Sublevel, SublevelPackage))
        {
            OutError = TEXT("unable to save the extraction fixture sublevel map");
            return false;
        }
    }

    if (LoadObject<UWorld>(nullptr, FixtureMapObjectPath) != nullptr)
    {
        // Fixture content is generated once. Bump the version when the fixture source
        // changes and delete Content/AtlasTest/Generated/AtlasExtraction* to regenerate:
        // a stale fixture must be a visible instruction, not a silent difference.
        UE_LOG(
            LogAtlasTransport,
            Log,
            TEXT("Atlas extraction fixture map already exists (content version %d); delete "
                 "Content/AtlasTest/Generated/AtlasExtraction* to regenerate"),
            FixtureContentVersion);
        return true; // already saved
    }

    UWorld* MapWorld = EnsureEmptyMapWorld(FixtureMapPackage, TEXT("AtlasExtractionFixture"), OutError);
    if (MapWorld == nullptr)
    {
        return false;
    }

    TArray<ULevelSequence*> Sequences;
    if (!PopulateFixtureMap(MapWorld, Sequences, OutError))
    {
        return false;
    }

    const FString MapFilename =
        FPackageName::LongPackageNameToFilename(FixtureMapPackage, FPackageName::GetMapPackageExtension());
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(MapFilename), true);
    MapWorld->GetOutermost()->MarkPackageDirty();
    if (!UEditorLoadingAndSavingUtils::SaveMap(MapWorld, FixtureMapPackage))
    {
        OutError = TEXT("unable to save the extraction fixture map");
        return false;
    }
    return true;
}

bool EnsureRuntimeProbeActors(UWorld* World, FString& OutError)
{
    if (World == nullptr)
    {
        OutError = TEXT("no world to provision runtime probes into");
        return false;
    }

    // 1. A loaded, visible dynamic streaming level: the second scope level the
    //    scope-change seam needs. Loading is asynchronous, so the ticker keeps asking
    //    until the level reports loaded (test-side polling, never inside the extractor).
    bool bHasStreamingLevel = false;
    for (const ULevelStreaming* Streaming : World->GetStreamingLevels())
    {
        if (Streaming != nullptr && Streaming->GetWorldAssetPackageFName().ToString() == SublevelPackage)
        {
            bHasStreamingLevel = true;
            break;
        }
    }
    if (!bHasStreamingLevel)
    {
        bool bCreated = false;
        ULevelStreamingDynamic* StreamingLevel = ULevelStreamingDynamic::LoadLevelInstance(
            World, SublevelPackage, FVector::ZeroVector, FRotator::ZeroRotator, bCreated);
        if (!bCreated || StreamingLevel == nullptr)
        {
            OutError = TEXT("unable to create the runtime streaming level");
            return false;
        }
        StreamingLevel->SetShouldBeLoaded(true);
        StreamingLevel->SetShouldBeVisible(true);
    }
    else
    {
        for (ULevelStreaming* Streaming : World->GetStreamingLevels())
        {
            if (Streaming != nullptr && Streaming->GetWorldAssetPackageFName().ToString() == SublevelPackage)
            {
                Streaming->SetShouldBeLoaded(true);
                Streaming->SetShouldBeVisible(true);
                if (!Streaming->IsLevelLoaded())
                {
                    return false; // keep ticking until the engine reports it loaded
                }
            }
        }
    }

    // 2. The runtime-generated mesh arm: a mesh asset created in memory with the
    //    runtime-regenerated flags and an actor as its outer — the shape the contract
    //    refuses (a shipped water body does the same thing).
    bool bHasRuntimeMeshActor = false;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        if (*It != nullptr && IsValid(*It) && It->ActorHasTag(TagName(RuntimeMesh)))
        {
            bHasRuntimeMeshActor = true;
            break;
        }
    }
    if (!bHasRuntimeMeshActor)
    {
        AActor* RuntimeMeshActor = SpawnTaggedActor(World, TEXT("ImplRuntimeMesh"), RuntimeMesh);
        if (RuntimeMeshActor == nullptr)
        {
            OutError = TEXT("unable to spawn the runtime-mesh probe actor");
            return false;
        }
        UStaticMeshComponent* Component =
            NewObject<UStaticMeshComponent>(RuntimeMeshActor, TEXT("RuntimeGeneratedMesh"));
        Component->SetupAttachment(RuntimeMeshActor->GetRootComponent());
        UStaticMesh* GeneratedMesh = NewObject<UStaticMesh>(
            RuntimeMeshActor,
            MakeUniqueObjectName(RuntimeMeshActor, UStaticMesh::StaticClass(), TEXT("AtlasGeneratedMesh")),
            RF_TextExportTransient | RF_NonPIEDuplicateTransient);
        if (GeneratedMesh == nullptr)
        {
            OutError = TEXT("unable to create the runtime-generated mesh asset");
            return false;
        }
        Component->SetStaticMesh(GeneratedMesh);
        Component->RegisterComponent();
    }

    return true;
}

void StartRuntimeFixtureTicker()
{
    if (GTickerHandle.IsValid())
    {
        return;
    }
    GTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateLambda([](float DeltaTime) -> bool
        {
            if (!IsInGameThread() || !GEditor)
            {
                return true;
            }

            FString Error;
            if (!GSavedContentReady && GSavedContentAttempts < 20)
            {
                ++GSavedContentAttempts;
                if (EnsureSavedFixtureContent(Error))
                {
                    GSavedContentReady = true;
                    UE_LOG(LogAtlasTransport, Log, TEXT("Atlas extraction fixture content ready"));
                }
                else if (GSavedContentAttempts >= 20)
                {
                    UE_LOG(
                        LogAtlasTransport,
                        Warning,
                        TEXT("Atlas extraction fixture content was not created: %s"),
                        *Error);
                }
            }

            UWorld* World = GEditor->GetEditorWorldContext().World();
            if (!GRuntimeProbesEnsured && IsFixtureWorld(World))
            {
                if (EnsureRuntimeProbeActors(World, Error))
                {
                    GRuntimeProbesEnsured = true;
                    UE_LOG(LogAtlasTransport, Log, TEXT("Atlas extraction runtime probes ready"));
                }
            }
            return true;
        }),
        0.25f);
}

void StopRuntimeFixtureTicker()
{
    if (GTickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(GTickerHandle);
        GTickerHandle.Reset();
    }
}
} // namespace AtlasExtractionFixture
