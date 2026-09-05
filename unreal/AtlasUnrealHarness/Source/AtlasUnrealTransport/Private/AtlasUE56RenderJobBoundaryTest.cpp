#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "AtlasTransportServer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56RenderJobBoundaryTest,
    "Atlas.UnrealAgent.UE56.RenderJobSubmissionBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasUE56RenderJobBoundaryTest::RunTest(const FString& Parameters)
{
    TestTrue(
        TEXT("UE 5.6 render-job boundary test is executing inside the editor automation framework"),
        GEngine != nullptr);

    // Verify FinalizeRenderJobState invariants
    // 1. Success with output files -> finished=true, status=finished, progress=1.0, success=true, failed=false
    {
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = TEXT("test-job-001");
        JobState->Status = TEXT("rendering");

        TArray<FString> Files;
        Files.Add(TEXT("C:/test/render_0001.png"));

        FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

        TestTrue(TEXT("Job is finished"), JobState->bFinished);
        TestTrue(TEXT("Job succeeded"), JobState->bSuccess);
        TestFalse(TEXT("Job not failed"), JobState->bFailed);
        TestEqual(TEXT("Job status is finished"), JobState->Status, FString(TEXT("finished")));
        TestEqual(TEXT("Job progress is 1.0"), JobState->Progress, 1.0);
        TestEqual(TEXT("Output files count is 1"), JobState->OutputFiles.Num(), 1);

        // Terminal job cannot be re-finalized (idempotent / no-op)
        FAtlasTransportServer::FinalizeRenderJobState(JobState, false, TArray<FString>(), TEXT("failure"));
        TestTrue(TEXT("Job remains finished"), JobState->bFinished);
        TestTrue(TEXT("Job remains succeeded"), JobState->bSuccess);
    }

    // 2. Reported success but 0 output files -> fails closed (status=failed, success=false, failed=true)
    {
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = TEXT("test-job-002");
        JobState->Status = TEXT("rendering");

        TArray<FString> Files;
        FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

        TestTrue(TEXT("Job is finished"), JobState->bFinished);
        TestFalse(TEXT("Job failed closed on empty output files"), JobState->bSuccess);
        TestTrue(TEXT("Job failed flag set"), JobState->bFailed);
        TestEqual(TEXT("Job status is failed"), JobState->Status, FString(TEXT("failed")));
        TestEqual(TEXT("Job progress is 1.0"), JobState->Progress, 1.0);
    }

    return !HasAnyErrors();
}
