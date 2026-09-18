// Copyright Epic Games, Inc. All Rights Reserved.
//
// Unreal State Extraction Fidelity v1 — extraction gate automation tests.
//
// These tests exist for the contract branches that a transport request cannot reach
// without either expanding production authority or flaking:
//
//   * ERR_EXTRACTION_SCOPE_CHANGED — the world must change between the scope snapshot and
//     the re-query. The extractor is forbidden to cause that, and no production read can,
//     so the extractor's null-by-default test seam is used here (and only here).
//   * the dynamic read-only proof — package dirty state measured immediately before and
//     immediately after an extraction, read directly through the extractor rather than
//     through a new transport operation.
//   * the exact refusal vocabulary for the runtime-generated-mesh, unsupported-component
//     and sequencer validity arms, plus the signed-zero and quaternion-sign source facts,
//     measured in-process.
//
// They run against the fixture world (AtlasExtractionFixture) in the editor session; every
// actor they touch is fixture content, never production scene state.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "AtlasStateExtraction.h"
#include "Editor.h"
#include "Engine/LevelStreaming.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "FileHelpers.h"
#include "GameFramework/Actor.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"

namespace
{
const TCHAR* const SublevelPackageName = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSublevel");
const TCHAR* const ValidSequenceAsset = TEXT("/Game/AtlasTest/Generated/AtlasExtractionSequenceValid");

UWorld* EditorWorld()
{
    return GEditor != nullptr ? GEditor->GetEditorWorldContext().World() : nullptr;
}

AActor* FindTaggedActor(UWorld* World, const TCHAR* EntityId)
{
    if (World == nullptr)
    {
        return nullptr;
    }
    const FName Tag(*FString::Printf(TEXT("atlas_entity:%s"), EntityId));
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        if (*It != nullptr && IsValid(*It) && It->ActorHasTag(Tag))
        {
            return *It;
        }
    }
    return nullptr;
}

FString SerializeTree(const TSharedPtr<FJsonObject>& Object)
{
    FString Out;
    const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
    if (Object.IsValid())
    {
        FJsonSerializer::Serialize(Object.ToSharedRef(), Writer);
    }
    return Out;
}

TSharedPtr<FJsonObject> GetObjectField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
{
    const TSharedPtr<FJsonObject>* Found = nullptr;
    if (Object.IsValid() && Object->TryGetObjectField(Field, Found) && Found != nullptr)
    {
        return *Found;
    }
    return nullptr;
}

/** Extracts one entity and returns the single actor record. */
bool ExtractActorRecord(
    const TCHAR* EntityId,
    TSharedPtr<FJsonObject>& OutActorRecord,
    FString& OutError,
    FString& OutErrorCode)
{
    TSharedPtr<FJsonObject> Tree;
    if (!AtlasStateExtraction::ExtractActorState({FString(EntityId)}, Tree, OutError, OutErrorCode))
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Actors = nullptr;
    if (!Tree.IsValid() || !Tree->TryGetArrayField(TEXT("actors"), Actors) || Actors == nullptr ||
        Actors->Num() != 1)
    {
        OutError = TEXT("expected exactly one actor record");
        OutErrorCode = TEXT("TEST_SHAPE_MISMATCH");
        return false;
    }
    OutActorRecord = (*Actors)[0]->AsObject();
    return OutActorRecord.IsValid();
}

bool ExtractSequencerRecord(
    const TCHAR* EntityId,
    TSharedPtr<FJsonObject>& OutSequenceRecord,
    FString& OutError,
    FString& OutErrorCode)
{
    TSharedPtr<FJsonObject> Tree;
    if (!AtlasStateExtraction::ExtractSequencerState({FString(EntityId)}, Tree, OutError, OutErrorCode))
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Sequences = nullptr;
    if (!Tree.IsValid() || !Tree->TryGetArrayField(TEXT("sequences"), Sequences) || Sequences == nullptr ||
        Sequences->Num() != 1)
    {
        OutError = TEXT("expected exactly one sequence record");
        OutErrorCode = TEXT("TEST_SHAPE_MISMATCH");
        return false;
    }
    OutSequenceRecord = (*Sequences)[0]->AsObject();
    return OutSequenceRecord.IsValid();
}

/** Reads the binary64 source pattern the extractor emitted for one scalar. */
FString ScalarPattern(const TSharedPtr<FJsonObject>& Vector, const TCHAR* Axis)
{
    FString Pattern;
    if (Vector.IsValid())
    {
        Vector->TryGetStringField(Axis, Pattern);
    }
    return Pattern;
}

/** Encodes a double exactly as the contract's binary64 pattern mapping does. */
FString PatternOf(double Value)
{
    uint64 Bits = 0;
    FMemory::Memcpy(&Bits, &Value, sizeof(Bits));
    return FString::Printf(TEXT("%016llx"), Bits);
}

FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
{
    FString Value;
    if (Object.IsValid())
    {
        Object->TryGetStringField(Field, Value);
    }
    return Value;
}

bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool& bOutValue)
{
    return Object.IsValid() && Object->TryGetBoolField(Field, bOutValue);
}
} // namespace

// ---------------------------------------------------------------------------
// 1. Scope-change refusal (test seam; production probe is null)
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasExtractionScopeChangeTest,
    "Atlas.StateExtraction.ScopeChangeRefusal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasExtractionScopeChangeTest::RunTest(const FString& Parameters)
{
    UWorld* World = EditorWorld();
    if (World == nullptr)
    {
        AddError(TEXT("no editor world available"));
        return false;
    }

    ULevelStreaming* SublevelStreaming = nullptr;
    int32 SublevelIndex = INDEX_NONE;
    const TArray<ULevelStreaming*>& StreamingLevels = World->GetStreamingLevels();
    for (int32 Index = 0; Index < StreamingLevels.Num(); ++Index)
    {
        // A dynamically loaded level instance is renamed by the engine
        // (`<package>_LevelInstance_<n>`), so the probe is matched by package prefix.
        if (StreamingLevels[Index] != nullptr &&
            StreamingLevels[Index]->GetWorldAssetPackageFName().ToString().StartsWith(SublevelPackageName))
        {
            SublevelStreaming = StreamingLevels[Index];
            SublevelIndex = Index;
            break;
        }
    }

    if (SublevelStreaming == nullptr)
    {
        FString LevelNames;
        for (const ULevelStreaming* Streaming : StreamingLevels)
        {
            LevelNames += Streaming != nullptr
                ? Streaming->GetWorldAssetPackageFName().ToString() + TEXT(" ")
                : FString(TEXT("<null> "));
        }
        AddError(FString::Printf(
            TEXT("the runtime streaming-level probe is missing (looked for %s among [%s]): the "
                 "scope-change arm cannot be exercised without a second loaded scope level"),
            SublevelPackageName,
            *LevelNames));
        return false;
    }

    // Pre-state: a normal extraction succeeds and records both scope levels.
    TSharedPtr<FJsonObject> Tree;
    FString Error;
    FString ErrorCode;
    if (!AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_PERM_A"))}, Tree, Error, ErrorCode))
    {
        AddError(FString::Printf(TEXT("pre-state extraction failed: %s (%s)"), *Error, *ErrorCode));
        return false;
    }
    const TSharedPtr<FJsonObject> WorldRecord = GetObjectField(Tree, TEXT("world"));
    const TSharedPtr<FJsonObject> LevelScope = GetObjectField(WorldRecord, TEXT("level_scope"));
    const TArray<TSharedPtr<FJsonValue>>* Levels = nullptr;
    if (!LevelScope.IsValid() || !LevelScope->TryGetArrayField(TEXT("levels"), Levels) || Levels == nullptr)
    {
        AddError(TEXT("pre-state extraction did not record a level scope"));
        return false;
    }
    TestTrue(
        FString::Printf(TEXT("pre-state scope records both levels (found %d)"), Levels->Num()),
        Levels->Num() == 2);

    // Seam: the probe removes the streaming level after the snapshot and before the
    // re-query. The removal is the test's action, attributed to the test, not to the
    // extractor.
    const int32 LevelsBeforeProbe = StreamingLevels.Num();
    bool bProbeRan = false;
    AtlasStateExtraction::SetScopeRevalidationProbe(
        [World, SublevelIndex, &bProbeRan]()
        {
            bProbeRan = true;
            World->RemoveStreamingLevelAt(SublevelIndex);
        });

    TSharedPtr<FJsonObject> ProbeTree;
    FString ProbeError;
    FString ProbeErrorCode;
    const bool bProbeExtractionSucceeded =
        AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_PERM_A"))}, ProbeTree, ProbeError, ProbeErrorCode);

    AtlasStateExtraction::ClearScopeRevalidationProbe();

    TestTrue(TEXT("the scope probe ran between the snapshot and the re-query"), bProbeRan);
    TestTrue(
        FString::Printf(
            TEXT("the probe actually changed the level set (%d -> %d levels)"),
            LevelsBeforeProbe,
            World->GetStreamingLevels().Num()),
        World->GetStreamingLevels().Num() == LevelsBeforeProbe - 1);

    TestFalse(
        FString::Printf(TEXT("extraction with a changed scope must refuse (got success=%s)"), bProbeExtractionSucceeded ? TEXT("true") : TEXT("false")),
        bProbeExtractionSucceeded);
    TestEqual(
        TEXT("scope change reports ERR_EXTRACTION_SCOPE_CHANGED"),
        ProbeErrorCode,
        FString(TEXT("ERR_EXTRACTION_SCOPE_CHANGED")));

    return true;
}

// ---------------------------------------------------------------------------
// 2. Dynamic read-only proof: package dirty state across an extraction
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasExtractionDirtyStateTest,
    "Atlas.StateExtraction.PackageDirtyInvariance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasExtractionDirtyStateTest::RunTest(const FString& Parameters)
{
    UWorld* World = EditorWorld();
    if (World == nullptr)
    {
        AddError(TEXT("no editor world available"));
        return false;
    }

    UPackage* WorldPackage = World->GetOutermost();
    if (WorldPackage == nullptr)
    {
        AddError(TEXT("the world has no package"));
        return false;
    }

    // (a) With whatever dirty state the session already has: extraction must not change it.
    TArray<UPackage*> DirtyBefore;
    UEditorLoadingAndSavingUtils::GetDirtyMapPackages(DirtyBefore);
    const bool bWorldDirtyBefore = WorldPackage->IsDirty();

    TSharedPtr<FJsonObject> Tree;
    FString Error;
    FString ErrorCode;
    if (!AtlasStateExtraction::ExtractActorState(
            {FString(TEXT("IMPL_PERM_A")), FString(TEXT("IMPL_MATERIAL_OVERRIDE_A"))},
            Tree,
            Error,
            ErrorCode))
    {
        AddError(FString::Printf(TEXT("extraction failed: %s (%s)"), *Error, *ErrorCode));
        return false;
    }

    TArray<UPackage*> DirtyAfter;
    UEditorLoadingAndSavingUtils::GetDirtyMapPackages(DirtyAfter);
    TestEqual(
        TEXT("the number of dirty map packages is unchanged by extraction"),
        DirtyAfter.Num(),
        DirtyBefore.Num());
    TestEqual(
        TEXT("the world package dirty flag is unchanged by extraction"),
        WorldPackage->IsDirty(),
        bWorldDirtyBefore);

    // (b) The stronger form: clean before, clean after.
    WorldPackage->SetDirtyFlag(false);
    TSharedPtr<FJsonObject> CleanTree;
    if (!AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_PERM_A"))}, CleanTree, Error, ErrorCode))
    {
        AddError(FString::Printf(TEXT("clean-state extraction failed: %s (%s)"), *Error, *ErrorCode));
        return false;
    }
    TestFalse(TEXT("extraction of a clean world leaves the package clean"), WorldPackage->IsDirty());

    // (c) The content packages the extraction resolves through (mesh and material) must
    //     also stay clean: resolving a material is a read, not a modification.
    const TArray<FString> ContentPackages = {
        FString(TEXT("/Engine/BasicShapes/Cube")),
        FString(TEXT("/Engine/BasicShapes/BasicShapeMaterial")),
        FString(TEXT("/Engine/EngineMaterials/DefaultMaterial"))};
    for (const FString& PackageName : ContentPackages)
    {
        UPackage* Package = FindPackage(nullptr, *PackageName);
        if (Package == nullptr)
        {
            AddWarning(FString::Printf(TEXT("content package %s is not loaded"), *PackageName));
            continue;
        }
        TestFalse(
            FString::Printf(TEXT("content package %s stays clean across extraction"), *PackageName),
            Package->IsDirty());
    }

    return true;
}

// ---------------------------------------------------------------------------
// 3. Refusal vocabulary, in-process (runtime mesh, unsupported component, sequencer)
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasExtractionRefusalArmsTest,
    "Atlas.StateExtraction.RefusalArms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasExtractionRefusalArmsTest::RunTest(const FString& Parameters)
{
    UWorld* World = EditorWorld();
    if (World == nullptr)
    {
        AddError(TEXT("no editor world available"));
        return false;
    }

    TSharedPtr<FJsonObject> Tree;
    FString Error;
    FString ErrorCode;

    // Runtime-generated mesh asset.
    TestFalse(
        TEXT("a runtime-generated mesh asset is refused"),
        AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_RUNTIME_MESH"))}, Tree, Error, ErrorCode));
    TestEqual(
        TEXT("runtime mesh refusal code"),
        ErrorCode,
        FString(TEXT("ERR_EXTRACTION_MESH_ASSET_UNSTABLE")));

    // Unsupported UMeshComponent family.
    const bool bUnsupportedAccepted =
        AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_UNSUPPORTED_COMPONENT"))}, Tree, Error, ErrorCode);
    if (bUnsupportedAccepted)
    {
        AddInfo(FString::Printf(
            TEXT("the unsupported-component fixture was accepted; its payload is: %s"),
            *SerializeTree(Tree)));
    }
    TestFalse(TEXT("an unsupported material-bearing component family is refused"), bUnsupportedAccepted);
    TestEqual(
        TEXT("unsupported component refusal code"),
        ErrorCode,
        FString(TEXT("ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE")));

    // Sequencer validity arms.
    TSharedPtr<FJsonObject> SequenceRecord;
    TestTrue(
        TEXT("the valid sequence extracts"),
        ExtractSequencerRecord(TEXT("IMPL_SEQUENCE_VALID"), SequenceRecord, Error, ErrorCode));
    TestEqual(
        TEXT("the valid sequence asset path is the saved asset"),
        ReadString(SequenceRecord, TEXT("sequence_asset_object_path")),
        FString(ValidSequenceAsset) + TEXT(".AtlasExtractionSequenceValid"));

    TestFalse(
        TEXT("a degenerate playback range is refused"),
        ExtractSequencerRecord(TEXT("IMPL_SEQUENCE_DEGENERATE"), SequenceRecord, Error, ErrorCode));
    TestEqual(
        TEXT("degenerate range refusal code"),
        ErrorCode,
        FString(TEXT("ERR_EXTRACTION_SEQUENCE_RANGE_INVALID")));

    // The open-bound range arm has no fixture on purpose: `UMovieScene::SetPlaybackRange`
    // documents finite bounds only and asserts closed bounds (MovieScene.cpp:689), while
    // `PlaybackRange` is private (MovieScene.h:1271/1311). It cannot be provoked through any
    // public engine API, so it stays a defensive contract state, recorded as blocked by
    // engine/API limitation rather than dressed up as a covered arm.

    TestFalse(
        TEXT("a zero-numerator tick resolution is refused"),
        ExtractSequencerRecord(TEXT("IMPL_SEQUENCE_BAD_RATE"), SequenceRecord, Error, ErrorCode));
    TestEqual(
        TEXT("invalid rate refusal code"),
        ErrorCode,
        FString(TEXT("ERR_EXTRACTION_SEQUENCE_RATE_INVALID")));

    return true;
}

// ---------------------------------------------------------------------------
// 4. Transform source facts in-process (signed zero, quaternion sign)
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasExtractionTransformSignTest,
    "Atlas.StateExtraction.TransformSignPreservation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasExtractionTransformSignTest::RunTest(const FString& Parameters)
{
    UWorld* World = EditorWorld();
    if (World == nullptr)
    {
        AddError(TEXT("no editor world available"));
        return false;
    }

    // Fidelity is the assertion that holds regardless of engine canonicalisation: every
    // transform scalar in the payload must equal the engine's own value on that surface,
    // bit for bit. Whether the engine keeps the sign of a negative zero, and whether it
    // keeps a quaternion's sign, are *observations* reported beside it.
    auto CompareTransformToEngine = [this](const TCHAR* EntityId, const AActor* Actor) -> bool
    {
        TSharedPtr<FJsonObject> Record;
        FString Error;
        FString ErrorCode;
        if (!ExtractActorRecord(EntityId, Record, Error, ErrorCode))
        {
            AddError(FString::Printf(TEXT("%s extraction failed: %s (%s)"), EntityId, *Error, *ErrorCode));
            return false;
        }
        const TSharedPtr<FJsonObject> Transform = GetObjectField(Record, TEXT("transform"));
        const TSharedPtr<FJsonObject> LocationCm = GetObjectField(Transform, TEXT("location_cm"));
        const TSharedPtr<FJsonObject> Scale = GetObjectField(Transform, TEXT("scale"));
        const TSharedPtr<FJsonObject> Rotation = GetObjectField(Transform, TEXT("rotation"));

        const FVector EngineLocation = Actor->GetActorLocation();
        const FVector EngineScale = Actor->GetActorScale3D();
        const FQuat EngineRotation = Actor->GetActorQuat();

        const TCHAR* const Axes[] = {TEXT("x"), TEXT("y"), TEXT("z")};
        const double EngineLocations[] = {EngineLocation.X, EngineLocation.Y, EngineLocation.Z};
        const double EngineScales[] = {EngineScale.X, EngineScale.Y, EngineScale.Z};
        for (int32 Index = 0; Index < 3; ++Index)
        {
            TestEqual(
                FString::Printf(TEXT("%s location.%s matches the engine"), EntityId, Axes[Index]),
                ScalarPattern(LocationCm, Axes[Index]),
                PatternOf(EngineLocations[Index]));
            TestEqual(
                FString::Printf(TEXT("%s scale.%s matches the engine"), EntityId, Axes[Index]),
                ScalarPattern(Scale, Axes[Index]),
                PatternOf(EngineScales[Index]));
        }
        const TCHAR* const QuaternionAxes[] = {TEXT("x"), TEXT("y"), TEXT("z"), TEXT("w")};
        const double EngineQuaternions[] = {EngineRotation.X, EngineRotation.Y, EngineRotation.Z, EngineRotation.W};
        for (int32 Index = 0; Index < 4; ++Index)
        {
            TestEqual(
                FString::Printf(TEXT("%s rotation.%s matches the engine"), EntityId, QuaternionAxes[Index]),
                ScalarPattern(Rotation, QuaternionAxes[Index]),
                PatternOf(EngineQuaternions[Index]));
        }
        AddInfo(FString::Printf(
            TEXT("%s: engine location.x=%s scale.x=%s rotation.z=%s rotation.w=%s"),
            EntityId,
            *PatternOf(EngineLocation.X),
            *PatternOf(EngineScale.X),
            *PatternOf(EngineRotation.Z),
            *PatternOf(EngineRotation.W)));
        return true;
    };

    AActor* SignedZeroActor = FindTaggedActor(World, TEXT("IMPL_SIGNED_ZERO"));
    if (SignedZeroActor == nullptr)
    {
        AddError(TEXT("the signed-zero fixture actor is missing"));
        return false;
    }
    if (!CompareTransformToEngine(TEXT("IMPL_SIGNED_ZERO"), SignedZeroActor))
    {
        return false;
    }
    const FString EngineSignedZeroLocation = PatternOf(SignedZeroActor->GetActorLocation().X);
    const FString EngineSignedZeroScale = PatternOf(SignedZeroActor->GetActorScale3D().X);
    const bool bLocationSignPreserved = EngineSignedZeroLocation == TEXT("8000000000000000");
    const bool bScaleSignPreserved = EngineSignedZeroScale == TEXT("8000000000000000");
    AddInfo(FString::Printf(
        TEXT("signed zero: engine location.x=%s preserved=%s; engine scale.x=%s preserved=%s"),
        *EngineSignedZeroLocation,
        bLocationSignPreserved ? TEXT("true") : TEXT("false"),
        *EngineSignedZeroScale,
        bScaleSignPreserved ? TEXT("true") : TEXT("false")));
    TestTrue(
        TEXT("the signed-zero fixture preserves the sign on at least one engine surface "
             "(otherwise the arm is unobservable through an actor transform)"),
        bLocationSignPreserved || bScaleSignPreserved);

    AActor* PositiveQuaternionActor = FindTaggedActor(World, TEXT("IMPL_Q_POS"));
    AActor* NegativeQuaternionActor = FindTaggedActor(World, TEXT("IMPL_Q_NEG"));
    if (PositiveQuaternionActor == nullptr || NegativeQuaternionActor == nullptr)
    {
        AddError(TEXT("the quaternion-sign fixture actors are missing"));
        return false;
    }
    if (!CompareTransformToEngine(TEXT("IMPL_Q_POS"), PositiveQuaternionActor) ||
        !CompareTransformToEngine(TEXT("IMPL_Q_NEG"), NegativeQuaternionActor))
    {
        return false;
    }
    const FQuat PositiveEngineQuaternion = PositiveQuaternionActor->GetActorQuat();
    const FQuat NegativeEngineQuaternion = NegativeQuaternionActor->GetActorQuat();
    AddInfo(FString::Printf(
        TEXT("quaternion sign: the engine holds +q(z=%s, w=%s) and -q(z=%s, w=%s) for the two "
             "fixtures; sign preserved through AActor: %s"),
        *PatternOf(PositiveEngineQuaternion.Z),
        *PatternOf(PositiveEngineQuaternion.W),
        *PatternOf(NegativeEngineQuaternion.Z),
        *PatternOf(NegativeEngineQuaternion.W),
        (PatternOf(PositiveEngineQuaternion.Z) != PatternOf(NegativeEngineQuaternion.Z))
            ? TEXT("true")
            : TEXT("false (the engine canonicalises the sign for this input)")));
    return true;
}

// ---------------------------------------------------------------------------
// 5. Negative control: an untagged actor is never returned
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasExtractionNegativeControlTest,
    "Atlas.StateExtraction.UntaggedActorExcluded",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasExtractionNegativeControlTest::RunTest(const FString& Parameters)
{
    UWorld* World = EditorWorld();
    if (World == nullptr)
    {
        AddError(TEXT("no editor world available"));
        return false;
    }

    TSharedPtr<FJsonObject> Tree;
    FString Error;
    FString ErrorCode;
    if (!AtlasStateExtraction::ExtractActorState({FString(TEXT("IMPL_PERM_A"))}, Tree, Error, ErrorCode))
    {
        AddError(FString::Printf(TEXT("extraction failed: %s (%s)"), *Error, *ErrorCode));
        return false;
    }

    const FString Serialized = SerializeTree(Tree);
    TestFalse(TEXT("the untagged negative-control actor is absent from the payload"), Serialized.Contains(TEXT("ImplNegativeControl")));
    TestFalse(TEXT("the untagged parent actor is absent from the payload"), Serialized.Contains(TEXT("UntaggedParent")));
    TestFalse(TEXT("no session identity appears in the payload"), Serialized.Contains(TEXT("session")));
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
