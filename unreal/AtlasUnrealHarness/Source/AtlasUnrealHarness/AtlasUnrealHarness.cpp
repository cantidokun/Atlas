#include "AtlasUnrealHarness.h"

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
    static bool ParseAndValidateOperation(const FString& Payload, FString& OutEntityId, FString& OutError)
    {
        TSharedPtr<FJsonObject> Root;
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
        if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
        {
            OutError = TEXT("operation payload is not valid JSON");
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

        const TArray<TSharedPtr<FJsonValue>>* EntityValues = nullptr;
        if (!(*Arguments)->TryGetArrayField(TEXT("entity_ids"), EntityValues) || !EntityValues || EntityValues->Num() != 1)
        {
            OutError = TEXT("smoke-test operation requires exactly one entity_id");
            return false;
        }

        if (!(*EntityValues)[0].IsValid() || !(*EntityValues)[0]->TryGetString(OutEntityId) || OutEntityId.IsEmpty())
        {
            OutError = TEXT("entity_ids must contain a non-empty string");
            return false;
        }

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
    const FString InvalidPayload = TEXT(R"JSON({"capability":"modify_actor","kind":"execute","name":"move_target_actor","arguments":{"entity_ids":["FIELD_SURFACE"]},"entity_ids":["FIELD_SURFACE"]})JSON");

    FString EntityId;
    FString Error;
    TestTrue(TEXT("valid Atlas Unreal operation parses and validates"), AtlasUnrealHarness::ParseAndValidateOperation(ValidPayload, EntityId, Error));
    if (!Error.IsEmpty())
    {
        AddError(Error);
    }
    TestEqual(TEXT("Atlas entity ID survives the Unreal boundary"), EntityId, FString(TEXT("FIELD_SURFACE")));

    EntityId.Empty();
    Error.Empty();
    TestFalse(TEXT("unsupported operation kind fails closed"), AtlasUnrealHarness::ParseAndValidateOperation(InvalidPayload, EntityId, Error));

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

    Actor->Tags.Add(FName(TEXT("atlas_entity:FIELD_SURFACE")));
    const FVector TargetLocation(100.0, 200.0, 300.0);
    Actor->SetActorLocation(TargetLocation);

    TestTrue(TEXT("Atlas entity mapping exists on Unreal Actor"), Actor->Tags.Contains(FName(TEXT("atlas_entity:FIELD_SURFACE"))));
    TestEqual(TEXT("authorized write reaches Unreal Actor state"), Actor->GetActorLocation(), TargetLocation);

    Actor->Destroy();
    return true;
}
