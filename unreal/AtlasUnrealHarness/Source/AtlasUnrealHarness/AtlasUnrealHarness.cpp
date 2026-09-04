#include "AtlasUnrealHarness.h"

#include "Components/SceneComponent.h"
#include "Editor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_MODULE(FAtlasUnrealHarnessModule, AtlasUnrealHarness)

void FAtlasUnrealHarnessModule::StartupModule()
{
}

void FAtlasUnrealHarnessModule::ShutdownModule()
{
}

namespace AtlasUnrealHarness
{
    static bool HasExactKeys(const TSharedPtr<FJsonObject>& Object, const TSet<FString>& RequiredKeys)
    {
        if (!Object.IsValid() || Object->Values.Num() != RequiredKeys.Num())
        {
            return false;
        }

        for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Object->Values)
        {
            if (!RequiredKeys.Contains(Pair.Key))
            {
                return false;
            }
        }

        return true;
    }

    static bool ReadSingleEntityIdArray(
        const TArray<TSharedPtr<FJsonValue>>* Values,
        FString& OutEntityId)
    {
        if (!Values || Values->Num() != 1 || !(*Values)[0].IsValid())
        {
            return false;
        }

        FString EntityId;
        if (!(*Values)[0]->TryGetString(EntityId) || EntityId.IsEmpty())
        {
            return false;
        }

        OutEntityId = MoveTemp(EntityId);
        return true;
    }

    static bool ParseAndValidateOperation(
        const FString& Payload,
        FString& OutEntityId,
        FString& OutError)
    {
        TSharedPtr<FJsonObject> Root;
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
        if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
        {
            OutError = TEXT("operation payload is not valid JSON");
            return false;
        }

        const TSet<FString> RequiredOperationKeys = {
            TEXT("capability"),
            TEXT("kind"),
            TEXT("name"),
            TEXT("arguments"),
            TEXT("entity_ids")
        };
        if (!HasExactKeys(Root, RequiredOperationKeys))
        {
            OutError = TEXT("operation must contain exactly the Atlas operation contract keys");
            return false;
        }

        FString Capability;
        FString Kind;
        FString Name;
        if (!Root->TryGetStringField(TEXT("capability"), Capability) ||
            !Root->TryGetStringField(TEXT("kind"), Kind) ||
            !Root->TryGetStringField(TEXT("name"), Name))
        {
            OutError = TEXT("operation is missing required string fields");
            return false;
        }

        if (Capability != TEXT("modify_actor") || Kind != TEXT("write") || Name.IsEmpty())
        {
            OutError = TEXT("operation is outside the smoke-test capability contract");
            return false;
        }

        const TSharedPtr<FJsonObject>* Arguments = nullptr;
        if (!Root->TryGetObjectField(TEXT("arguments"), Arguments) || !Arguments || !Arguments->IsValid())
        {
            OutError = TEXT("operation arguments must be an object");
            return false;
        }

        const TSet<FString> RequiredArgumentKeys = {TEXT("entity_ids")};
        if (!HasExactKeys(*Arguments, RequiredArgumentKeys))
        {
            OutError = TEXT("operation arguments do not match the Atlas argument schema");
            return false;
        }

        const TArray<TSharedPtr<FJsonValue>>* ArgumentEntityValues = nullptr;
        if (!(*Arguments)->TryGetArrayField(TEXT("entity_ids"), ArgumentEntityValues))
        {
            OutError = TEXT("operation arguments must contain entity_ids");
            return false;
        }

        FString ArgumentEntityId;
        if (!ReadSingleEntityIdArray(ArgumentEntityValues, ArgumentEntityId))
        {
            OutError = TEXT("arguments.entity_ids must contain exactly one non-empty string");
            return false;
        }

        const TArray<TSharedPtr<FJsonValue>>* OperationEntityValues = nullptr;
        if (!Root->TryGetArrayField(TEXT("entity_ids"), OperationEntityValues))
        {
            OutError = TEXT("operation must contain entity_ids");
            return false;
        }

        FString OperationEntityId;
        if (!ReadSingleEntityIdArray(OperationEntityValues, OperationEntityId))
        {
            OutError = TEXT("entity_ids must contain exactly one non-empty string");
            return false;
        }

        if (ArgumentEntityId != OperationEntityId)
        {
            OutError = TEXT("operation entity_ids must match arguments.entity_ids");
            return false;
        }

        OutEntityId = MoveTemp(OperationEntityId);
        return true;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUnrealOperationSmokeTest,
    "Atlas.UnrealAgent.OperationBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter
)

bool FAtlasUnrealOperationSmokeTest::RunTest(const FString& Parameters)
{
    const FString ValidPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"write","name":"move_target_actor","arguments":{"entity_ids":["FIELD_SURFACE"]},"entity_ids":["FIELD_SURFACE"]})JSON");
    const FString InvalidKindPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"execute","name":"move_target_actor","arguments":{"entity_ids":["FIELD_SURFACE"]},"entity_ids":["FIELD_SURFACE"]})JSON");
    const FString InvalidExtraKeyPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"write","name":"move_target_actor","arguments":{"entity_ids":["FIELD_SURFACE"]},"entity_ids":["FIELD_SURFACE"],"authorization":"approved"})JSON");
    const FString InvalidExtraArgumentPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"write","name":"move_target_actor","arguments":{"entity_ids":["FIELD_SURFACE"],"location":[100,200,300]},"entity_ids":["FIELD_SURFACE"]})JSON");
    const FString InvalidMismatchPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"write","name":"move_target_actor","arguments":{"entity_ids":["OTHER_TARGET"]},"entity_ids":["FIELD_SURFACE"]})JSON");

    FString EntityId;
    FString Error;
    TestTrue(
        TEXT("valid Atlas Unreal operation parses and validates"),
        AtlasUnrealHarness::ParseAndValidateOperation(ValidPayload, EntityId, Error));
    if (!Error.IsEmpty())
    {
        AddError(Error);
    }
    TestEqual(TEXT("Atlas entity ID survives the Unreal boundary"), EntityId, FString(TEXT("FIELD_SURFACE")));

    EntityId.Empty();
    Error.Empty();
    TestFalse(
        TEXT("unsupported operation kind fails closed"),
        AtlasUnrealHarness::ParseAndValidateOperation(InvalidKindPayload, EntityId, Error));

    EntityId.Empty();
    Error.Empty();
    TestFalse(
        TEXT("unknown top-level operation keys fail closed"),
        AtlasUnrealHarness::ParseAndValidateOperation(InvalidExtraKeyPayload, EntityId, Error));

    EntityId.Empty();
    Error.Empty();
    TestFalse(
        TEXT("unknown operation argument keys fail closed"),
        AtlasUnrealHarness::ParseAndValidateOperation(InvalidExtraArgumentPayload, EntityId, Error));

    EntityId.Empty();
    Error.Empty();
    TestFalse(
        TEXT("operation target mismatch fails closed"),
        AtlasUnrealHarness::ParseAndValidateOperation(InvalidMismatchPayload, EntityId, Error));

    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    TestNotNull(TEXT("Unreal editor world is available"), World);
    if (!World)
    {
        return false;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = TEXT("AtlasUnrealHarness_FieldSurface");
    AActor* Actor = World->SpawnActor<AActor>(FVector::ZeroVector, FRotator::ZeroRotator, SpawnParameters);
    TestNotNull(TEXT("Unreal test actor can be created"), Actor);
    if (!Actor)
    {
        return false;
    }

    USceneComponent* RootComponent = NewObject<USceneComponent>(Actor, TEXT("AtlasUnrealHarnessRoot"));
    TestNotNull(TEXT("Unreal test actor has a transform root component"), RootComponent);
    if (!RootComponent)
    {
        Actor->Destroy();
        return false;
    }

    Actor->SetRootComponent(RootComponent);
    RootComponent->RegisterComponent();
    TestTrue(TEXT("Unreal test actor root component is registered"), Actor->HasValidRootComponent());

    Actor->Tags.Add(FName(TEXT("atlas_entity:FIELD_SURFACE")));
    const FVector TargetLocation(100.0, 200.0, 300.0);
    const bool bLocationWriteSucceeded = Actor->SetActorLocation(TargetLocation);

    TestTrue(
        TEXT("Atlas entity mapping exists on Unreal Actor"),
        Actor->Tags.Contains(FName(TEXT("atlas_entity:FIELD_SURFACE"))));
    TestTrue(
        TEXT("authorized write reaches Unreal Actor state"),
        bLocationWriteSucceeded && Actor->GetActorLocation().Equals(TargetLocation, KINDA_SMALL_NUMBER));

    Actor->Destroy();
    return true;
}
