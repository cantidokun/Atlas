#include "Misc/AutomationTest.h"
#include "AtlasLiveEffectRegistry.h"
#include "AtlasLiveImpactAccentHandler.h"
#include "AtlasLiveSpeedTrailHandler.h"
#include "AtlasLiveImpactFrameHandler.h"
#include "Engine/World.h"
#include "Editor.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/LineBatchComponent.h"
#include "Components/PostProcessComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasLiveEffectDispatchTest,
    "Atlas.Live.Effect.DispatchVerification",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

namespace
{
    AActor* SpawnTestTargetActor(UWorld* World, const FString& EntityId)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.ObjectFlags |= RF_Transient;
        AActor* Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, SpawnParams);
        if (Actor)
        {
            USceneComponent* Root = NewObject<USceneComponent>(Actor, TEXT("TestRoot"));
            Actor->SetRootComponent(Root);
            Root->RegisterComponent();
            Actor->Tags.AddUnique(FName(*FString::Printf(TEXT("atlas_entity:%s"), *EntityId)));
        }
        return Actor;
    }

    FAtlasLiveProductionIntent MakeTestIntent(
        const FString& InIntentId,
        const FString& TargetEntityId,
        EAtlasLiveTreatment Treatment = EAtlasLiveTreatment::ImpactAccent,
        const FString& Preset = TEXT("strike_flash_v1"),
        int32 DurationMs = 200,
        float Intensity = 0.85f)
    {
        FAtlasLiveProductionIntent Intent;
        Intent.IntentId = InIntentId;
        Intent.Treatment = Treatment;
        Intent.SourceEventId = FString::Printf(TEXT("evt-%s"), *InIntentId);
        Intent.TargetEntityIds.Add(TargetEntityId);
        Intent.Intensity = Intensity;
        Intent.DurationMs = DurationMs;
        Intent.Parameters.Add(TEXT("preset"), Preset);
        Intent.ReceiverCycles = FPlatformTime::Cycles64();
        Intent.SequenceNumber = 1;
        return Intent;
    }
}

bool FAtlasLiveEffectDispatchTest::RunTest(const FString& Parameters)
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    TestNotNull(TEXT("Editor world available"), World);
    if (!World)
    {
        return false;
    }

    AActor* BallActor = SpawnTestTargetActor(World, TEXT("test_ball"));
    TestNotNull(TEXT("Ball actor created"), BallActor);
    if (!BallActor)
    {
        return false;
    }

    TSharedPtr<FAtlasLiveEffectRegistry> Registry = MakeShared<FAtlasLiveEffectRegistry>(500.0);
    TSharedPtr<FAtlasLiveImpactAccentHandler> ImpactHandler = MakeShared<FAtlasLiveImpactAccentHandler>();
    TSharedPtr<FAtlasLiveSpeedTrailHandler> TrailHandler = MakeShared<FAtlasLiveSpeedTrailHandler>();
    TSharedPtr<FAtlasLiveImpactFrameHandler> FrameHandler = MakeShared<FAtlasLiveImpactFrameHandler>();

    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactAccent, TEXT("strike_flash_v1"), ImpactHandler);
    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactAccent, TEXT(""), ImpactHandler); // Default fallback

    Registry->RegisterHandler(EAtlasLiveTreatment::SpeedTrail, TEXT("speed_trail_v1"), TrailHandler);
    Registry->RegisterHandler(EAtlasLiveTreatment::SpeedTrail, TEXT(""), TrailHandler);

    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactFrame, TEXT("impact_frame_v1"), FrameHandler);
    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactFrame, TEXT(""), FrameHandler);

    // -------------------------------------------------------------
    // Test 1: Successful IMPACT_ACCENT dispatch and component attachment
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent Intent = MakeTestIntent(TEXT("intent-strike-001"), TEXT("test_ball"));
        bool bDispatched = Registry->DispatchIntent(Intent);

        TestTrue(TEXT("Dispatch returns success"), bDispatched);
        TestTrue(TEXT("Actor has active impact accent tag"), FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(BallActor));
        TestEqual(TEXT("Active intent ID matches"), FAtlasLiveImpactAccentHandler::GetActiveImpactIntentId(BallActor), FString(TEXT("intent-strike-001")));

        TArray<UActorComponent*> Lights = BallActor->GetComponentsByTag(
            UPointLightComponent::StaticClass(),
            FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag);
        TestEqual(TEXT("Attached point light component found"), Lights.Num(), 1);

        UPointLightComponent* Light = Cast<UPointLightComponent>(Lights[0]);
        TestNotNull(TEXT("Light component valid"), Light);
        if (Light)
        {
            TestTrue(TEXT("Light intensity scaled by intent (> 0)"), Light->Intensity > 0.0f);
        }
    }

    // -------------------------------------------------------------
    // Test 2: Preemption / Repeated effect on same target
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent Intent2 = MakeTestIntent(TEXT("intent-strike-002"), TEXT("test_ball"), EAtlasLiveTreatment::ImpactAccent, TEXT("strike_flash_v1"), 300, 0.95f);
        bool bDispatched2 = Registry->DispatchIntent(Intent2);

        TestTrue(TEXT("Second dispatch succeeds and preempts first"), bDispatched2);
        TestEqual(TEXT("Active intent ID updated to intent-strike-002"), FAtlasLiveImpactAccentHandler::GetActiveImpactIntentId(BallActor), FString(TEXT("intent-strike-002")));

        TArray<UActorComponent*> Lights = BallActor->GetComponentsByTag(
            UPointLightComponent::StaticClass(),
            FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag);
        TestEqual(TEXT("Exactly one point light remains after preemption"), Lights.Num(), 1);
    }

    // -------------------------------------------------------------
    // Test 3: Missing Target Rejection
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent IntentMissingTarget = MakeTestIntent(TEXT("intent-missing-target"), TEXT("non_existent_entity"));
        bool bDispatchedMissing = Registry->DispatchIntent(IntentMissingTarget);

        TestFalse(TEXT("Missing target rejected"), bDispatchedMissing);
        TestTrue(TEXT("Telemetry records missing target"), Registry->GetTelemetry().TotalMissingTarget > 0);
    }

    // -------------------------------------------------------------
    // Test 4: Missing Preset Rejection
    // -------------------------------------------------------------
    {
        // Unregistered treatment
        FAtlasLiveProductionIntent IntentMissingPreset = MakeTestIntent(TEXT("intent-missing-preset"), TEXT("test_ball"), EAtlasLiveTreatment::CinematicPunch, TEXT("unknown_punch_v99"));
        bool bDispatchedMissingPreset = Registry->DispatchIntent(IntentMissingPreset);

        TestFalse(TEXT("Missing preset / treatment rejected"), bDispatchedMissingPreset);
        TestTrue(TEXT("Telemetry records missing preset"), Registry->GetTelemetry().TotalMissingPreset > 0);
    }

    // -------------------------------------------------------------
    // Test 5: Visual Deadline Expiration
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent StaleIntent = MakeTestIntent(TEXT("intent-stale"), TEXT("test_ball"));
        // Simulate receive cycles 2 seconds ago (deadline is 500ms)
        uint64 TwoSecCycles = (uint64)(2.0 / FPlatformTime::GetSecondsPerCycle64());
        StaleIntent.ReceiverCycles = FPlatformTime::Cycles64() - TwoSecCycles;

        bool bDispatchedStale = Registry->DispatchIntent(StaleIntent);
        TestFalse(TEXT("Stale intent expired visual deadline and was dropped"), bDispatchedStale);
        TestTrue(TEXT("Telemetry records expired deadline"), Registry->GetTelemetry().TotalExpiredDeadlineCount > 0);

        // Test 5b: Missing ReceiverCycles (ReceiverCycles == 0) fail-safe enforcement
        int64 DeadlineCountBefore = Registry->GetTelemetry().TotalExpiredDeadlineCount;
        FAtlasLiveProductionIntent MissingCyclesIntent = MakeTestIntent(TEXT("intent-missing-cycles"), TEXT("test_ball"));
        MissingCyclesIntent.ReceiverCycles = 0; // Explicitly zero

        bool bDispatchedMissingCycles = Registry->DispatchIntent(MissingCyclesIntent);
        TestFalse(TEXT("Intent with ReceiverCycles == 0 rejected fail-safe"), bDispatchedMissingCycles);
        TestTrue(TEXT("Telemetry records dropped intent for missing ReceiverCycles"),
            Registry->GetTelemetry().TotalExpiredDeadlineCount > DeadlineCountBefore);
    }

    // -------------------------------------------------------------
    // Test 6: Deterministic Cleanup & Expiration
    // -------------------------------------------------------------
    {
        // Cleanup all active effects
        Registry->CleanupAllActiveEffects();
        TestFalse(TEXT("Actor no longer has impact accent tag after cleanup"), FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(BallActor));

        TArray<UActorComponent*> Lights = BallActor->GetComponentsByTag(
            UPointLightComponent::StaticClass(),
            FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag);
        TestEqual(TEXT("Light component destroyed on cleanup"), Lights.Num(), 0);
        TestEqual(TEXT("Registry has 0 active effects"), Registry->GetActiveEffectCount(), 0);
    }

    // -------------------------------------------------------------
    // Test 7: Multiple Intents In Same Frame
    // -------------------------------------------------------------
    {
        AActor* PlayerActor = SpawnTestTargetActor(World, TEXT("test_player"));
        TestNotNull(TEXT("Player actor created"), PlayerActor);

        if (PlayerActor)
        {
            FAtlasLiveProductionIntent IntentBall = MakeTestIntent(TEXT("same-frame-ball"), TEXT("test_ball"));
            FAtlasLiveProductionIntent IntentPlayer = MakeTestIntent(TEXT("same-frame-player"), TEXT("test_player"));

            bool bDispatchedBall = Registry->DispatchIntent(IntentBall);
            bool bDispatchedPlayer = Registry->DispatchIntent(IntentPlayer);

            TestTrue(TEXT("Ball intent dispatched in same frame"), bDispatchedBall);
            TestTrue(TEXT("Player intent dispatched in same frame"), bDispatchedPlayer);
            TestTrue(TEXT("Ball has impact effect"), FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(BallActor));
            TestTrue(TEXT("Player has impact effect"), FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(PlayerActor));
            TestEqual(TEXT("Registry tracks 2 active effects concurrently"), Registry->GetActiveEffectCount(), 2);

            Registry->CleanupAllActiveEffects();
            PlayerActor->Destroy();
        }
    }

    // -------------------------------------------------------------
    // Test 8: SPEED_TRAIL Execution, LineBatch Attachment, and Cleanup
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent TrailIntent = MakeTestIntent(
            TEXT("intent-trail-001"),
            TEXT("test_ball"),
            EAtlasLiveTreatment::SpeedTrail,
            TEXT("speed_trail_v1"),
            250,
            0.9f);
        TrailIntent.Direction = FVector(1.0f, 0.0f, 0.0f);

        bool bDispatchedTrail = Registry->DispatchIntent(TrailIntent);
        TestTrue(TEXT("SpeedTrail dispatched successfully"), bDispatchedTrail);
        TestTrue(TEXT("Ball has active speed trail tag"), FAtlasLiveSpeedTrailHandler::HasActiveSpeedTrail(BallActor));
        TestEqual(TEXT("Ball active speed trail intent ID matches"),
            FAtlasLiveSpeedTrailHandler::GetActiveTrailIntentId(BallActor),
            FString(TEXT("intent-trail-001")));

        TArray<UActorComponent*> Lines = BallActor->GetComponentsByTag(
            ULineBatchComponent::StaticClass(),
            FAtlasLiveSpeedTrailHandler::SpeedTrailComponentTag);
        TestEqual(TEXT("LineBatchComponent attached for speed trail"), Lines.Num(), 1);

        Registry->CleanupAllActiveEffects();
        TestFalse(TEXT("Ball active speed trail tag removed after cleanup"), FAtlasLiveSpeedTrailHandler::HasActiveSpeedTrail(BallActor));
        TArray<UActorComponent*> PostCleanupLines = BallActor->GetComponentsByTag(
            ULineBatchComponent::StaticClass(),
            FAtlasLiveSpeedTrailHandler::SpeedTrailComponentTag);
        TestEqual(TEXT("LineBatchComponent destroyed after cleanup"), PostCleanupLines.Num(), 0);
    }

    // -------------------------------------------------------------
    // Test 9: IMPACT_FRAME Execution, PostProcess Attachment, and Cleanup
    // -------------------------------------------------------------
    {
        FAtlasLiveProductionIntent FrameIntent = MakeTestIntent(
            TEXT("intent-frame-001"),
            TEXT("test_ball"),
            EAtlasLiveTreatment::ImpactFrame,
            TEXT("impact_frame_v1"),
            100, // 100ms flash
            0.85f);

        bool bDispatchedFrame = Registry->DispatchIntent(FrameIntent);
        TestTrue(TEXT("ImpactFrame dispatched successfully"), bDispatchedFrame);
        TestTrue(TEXT("Ball has active impact frame tag"), FAtlasLiveImpactFrameHandler::HasActiveImpactFrame(BallActor));
        TestEqual(TEXT("Ball active impact frame intent ID matches"),
            FAtlasLiveImpactFrameHandler::GetActiveImpactFrameIntentId(BallActor),
            FString(TEXT("intent-frame-001")));

        TArray<UActorComponent*> PPComps = BallActor->GetComponentsByTag(
            UPostProcessComponent::StaticClass(),
            FAtlasLiveImpactFrameHandler::ImpactFrameComponentTag);
        TestEqual(TEXT("PostProcessComponent attached for impact frame"), PPComps.Num(), 1);
        if (PPComps.Num() > 0)
        {
            UPostProcessComponent* PPC = Cast<UPostProcessComponent>(PPComps[0]);
            TestNotNull(TEXT("Valid PostProcessComponent pointer"), PPC);
            if (PPC)
            {
                TestTrue(TEXT("PostProcessComponent is unbound (fullscreen impact)"), PPC->bUnbound);
                TestTrue(TEXT("Color contrast override enabled on impact frame"), PPC->Settings.bOverride_ColorContrast);
            }
        }

        Registry->CleanupAllActiveEffects();
        TestFalse(TEXT("Ball active impact frame tag removed after cleanup"), FAtlasLiveImpactFrameHandler::HasActiveImpactFrame(BallActor));
        TArray<UActorComponent*> PostCleanupPP = BallActor->GetComponentsByTag(
            UPostProcessComponent::StaticClass(),
            FAtlasLiveImpactFrameHandler::ImpactFrameComponentTag);
        TestEqual(TEXT("PostProcessComponent destroyed after cleanup"), PostCleanupPP.Num(), 0);
    }

    // Clean up test actor
    BallActor->Destroy();

    return !HasAnyErrors();
}
