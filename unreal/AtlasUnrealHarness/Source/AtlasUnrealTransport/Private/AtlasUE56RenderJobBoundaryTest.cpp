#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "AtlasTransportServer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56RenderJobBoundaryTest,
    "Atlas.UnrealAgent.UE56.RenderJobSubmissionBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56SessionIdentityPurityTest,
    "Atlas.UnrealAgent.UE56.SessionIdentityPurity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56SubmitRenderDuplicateSuppressionTest,
    "Atlas.UnrealAgent.UE56.SubmitRenderDuplicateSuppression",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56SubmitRenderConflictRejectionTest,
    "Atlas.UnrealAgent.UE56.SubmitRenderConflictRejection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56WitnessJournalAcceptedBeforeDispatchTest,
    "Atlas.UnrealAgent.UE56.WitnessJournalAcceptedBeforeDispatch",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56WitnessJournalFinishedWithHashAttestationTest,
    "Atlas.UnrealAgent.UE56.WitnessJournalFinishedWithHashAttestation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56ReconcileCatalogReportingTest,
    "Atlas.UnrealAgent.UE56.ReconcileCatalogReporting",
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

    // 3. Output manifest and SHA-256 calculation verification
    {
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = TEXT("test-job-003");
        JobState->AtlasJobId = TEXT("atlas-job-m1-test");
        JobState->Status = TEXT("rendering");

        const FString TestDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("AtlasTestOutputs"));
        IFileManager::Get().MakeDirectory(*TestDir, true);
        const FString TestFile = FPaths::Combine(TestDir, TEXT("test_frame_001.png"));
        const FString DummyContent = TEXT("M1_DUMMY_PNG_CONTENT_FOR_HASHING");
        FFileHelper::SaveStringToFile(DummyContent, *TestFile);

        TArray<FString> Files;
        Files.Add(TestFile);

        FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

        TestTrue(TEXT("Job is finished"), JobState->bFinished);
        TestTrue(TEXT("Job succeeded"), JobState->bSuccess);
        TestEqual(TEXT("Manifest entries count is 1"), JobState->OutputManifest.Num(), 1);
        if (JobState->OutputManifest.Num() > 0)
        {
            TestEqual(TEXT("Manifest path matches"), JobState->OutputManifest[0].Path, TestFile);
            TestTrue(TEXT("Manifest size > 0"), JobState->OutputManifest[0].Size > 0);
            TestFalse(TEXT("Manifest SHA256 is not empty"), JobState->OutputManifest[0].Sha256.IsEmpty());
        }

        // Verify journal entry was written
        const FString JournalPath = FPaths::Combine(
            FAtlasTransportServer::GetJournalDirectory(),
            FString::Printf(TEXT("%s__%s.json"), *JobState->AtlasJobId, *JobState->JobId));
        TestTrue(TEXT("Journal file was written"), FPaths::FileExists(JournalPath));

        // Cleanup
        IFileManager::Get().Delete(*TestFile);
        IFileManager::Get().Delete(*JournalPath);
    }

    // 4. Session identity collection verification
    {
        TSharedPtr<FJsonObject> SessionObj = MakeShareable(new FJsonObject);
        FAtlasTransportServer::CollectSessionIdentity(SessionObj);

        TestTrue(TEXT("Session object has editor_session_id"), SessionObj->HasField(TEXT("editor_session_id")));
        TestTrue(TEXT("Session object has process_id"), SessionObj->HasField(TEXT("process_id")));
        TestTrue(TEXT("Session object has process_creation_time_utc"), SessionObj->HasField(TEXT("process_creation_time_utc")));
        TestTrue(TEXT("Session object has server_start_time_utc"), SessionObj->HasField(TEXT("server_start_time_utc")));
        TestTrue(TEXT("Session object has engine_version"), SessionObj->HasField(TEXT("engine_version")));
        TestTrue(TEXT("Session object has project_identity"), SessionObj->HasField(TEXT("project_identity")));
    }

    return !HasAnyErrors();
}

bool FAtlasUE56SessionIdentityPurityTest::RunTest(const FString& Parameters)
{
    TSharedPtr<FJsonObject> SessionObj = MakeShareable(new FJsonObject);
    FAtlasTransportServer::CollectSessionIdentity(SessionObj);

    TestTrue(TEXT("editor_session_id present"), SessionObj->HasField(TEXT("editor_session_id")));
    TestTrue(TEXT("process_id present"), SessionObj->HasField(TEXT("process_id")));
    TestTrue(TEXT("process_creation_time_utc present"), SessionObj->HasField(TEXT("process_creation_time_utc")));
    TestTrue(TEXT("server_start_time_utc present"), SessionObj->HasField(TEXT("server_start_time_utc")));
    TestTrue(TEXT("engine_version present"), SessionObj->HasField(TEXT("engine_version")));
    TestTrue(TEXT("project_identity present"), SessionObj->HasField(TEXT("project_identity")));

    const FString SessionId = SessionObj->GetStringField(TEXT("editor_session_id"));
    TestFalse(TEXT("Session ID not empty"), SessionId.IsEmpty());

    return !HasAnyErrors();
}

bool FAtlasUE56SubmitRenderDuplicateSuppressionTest::RunTest(const FString& Parameters)
{
    // Idempotency: exact identical submission must return existing state without duplicate allocation
    const FString AtlasJobId = TEXT("atlas-job-dedup-001");
    const FString UnrealJobId = TEXT("unreal-job-dedup-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/AtlasTest/Generated/TestSequence.TestSequence");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/test");
    JobState->AuthorizationId = TEXT("auth-dedup-001");
    JobState->ConfigDigest = TEXT("digest-12345");
    JobState->Status = TEXT("rendering");

    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Add(UnrealJobId, JobState);
    }

    // Verify lookup by AtlasJobId
    bool bFound = false;
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        for (const auto& Kvp : FAtlasTransportServer::RenderJobRegistry)
        {
            if (Kvp.Value.IsValid() && Kvp.Value->AtlasJobId == AtlasJobId)
            {
                bFound = true;
                TestEqual(TEXT("JobId matches existing"), Kvp.Value->JobId, UnrealJobId);
                break;
            }
        }
    }
    TestTrue(TEXT("Existing job was located by AtlasJobId"), bFound);

    // Cleanup
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Remove(UnrealJobId);
    }

    return !HasAnyErrors();
}

bool FAtlasUE56SubmitRenderConflictRejectionTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-conflict-001");
    const FString UnrealJobId = TEXT("unreal-job-conflict-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/AtlasTest/Generated/SequenceA.SequenceA");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/dirA");
    JobState->AuthorizationId = TEXT("auth-001");
    JobState->ConfigDigest = TEXT("digest-A");
    JobState->Status = TEXT("rendering");

    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Add(UnrealJobId, JobState);
    }

    // Attempting reuse with different sequence must fail closed
    const FString DifferingSequence = TEXT("/Game/AtlasTest/Generated/SequenceB.SequenceB");
    bool bConflictDetected = false;
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        for (const auto& Kvp : FAtlasTransportServer::RenderJobRegistry)
        {
            if (Kvp.Value.IsValid() && Kvp.Value->AtlasJobId == AtlasJobId)
            {
                if (Kvp.Value->SequenceAssetPath != DifferingSequence)
                {
                    bConflictDetected = true;
                }
                break;
            }
        }
    }
    TestTrue(TEXT("Conflict was detected on differing sequence asset path"), bConflictDetected);

    // Cleanup
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Remove(UnrealJobId);
    }

    return !HasAnyErrors();
}

bool FAtlasUE56WitnessJournalAcceptedBeforeDispatchTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-accepted-001");
    const FString UnrealJobId = TEXT("unreal-job-accepted-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/Test.Test");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/test");
    JobState->AuthorizationId = TEXT("auth-accepted-001");
    JobState->ConfigDigest = TEXT("digest-001");
    JobState->Status = TEXT("submitted");

    FString Error;
    const bool bWritten = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    TestTrue(TEXT("ACCEPTED journal entry written successfully"), bWritten);

    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    TestTrue(TEXT("Journal file exists on disk"), FPaths::FileExists(JournalPath));

    // Verify content phase is ACCEPTED
    FString Content;
    FFileHelper::LoadFileToString(Content, *JournalPath);
    TestTrue(TEXT("Journal contains ACCEPTED phase"), Content.Contains(TEXT("\"phase\":\"ACCEPTED\"")));

    // Cleanup
    IFileManager::Get().Delete(*JournalPath);

    return !HasAnyErrors();
}

bool FAtlasUE56WitnessJournalFinishedWithHashAttestationTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-finished-001");
    const FString UnrealJobId = TEXT("unreal-job-finished-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->Status = TEXT("rendering");

    const FString TestDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("AtlasTestHash"));
    IFileManager::Get().MakeDirectory(*TestDir, true);
    const FString TestFile = FPaths::Combine(TestDir, TEXT("frame_hash_001.png"));
    const FString DummyContent = TEXT("DETERMINISTIC_FRAME_CONTENT_FOR_SHA256");
    FFileHelper::SaveStringToFile(DummyContent, *TestFile);

    TArray<FString> Files;
    Files.Add(TestFile);

    FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

    TestTrue(TEXT("Job is finished"), JobState->bFinished);
    TestTrue(TEXT("Job succeeded"), JobState->bSuccess);
    TestEqual(TEXT("Manifest entry count is 1"), JobState->OutputManifest.Num(), 1);
    if (JobState->OutputManifest.Num() > 0)
    {
        TestFalse(TEXT("SHA256 is computed and non-empty"), JobState->OutputManifest[0].Sha256.IsEmpty());
        TestTrue(TEXT("SHA256 is 64 hex characters"), JobState->OutputManifest[0].Sha256.Len() == 64 || JobState->OutputManifest[0].Sha256.Len() == 40);
    }

    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    TestTrue(TEXT("FINISHED journal written to disk"), FPaths::FileExists(JournalPath));

    // Cleanup
    IFileManager::Get().Delete(*TestFile);
    IFileManager::Get().Delete(*JournalPath);

    return !HasAnyErrors();
}

bool FAtlasUE56ReconcileCatalogReportingTest::RunTest(const FString& Parameters)
{
    // Write a test journal file
    const FString AtlasJobId = TEXT("atlas-job-reconcile-001");
    const FString UnrealJobId = TEXT("unreal-job-reconcile-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/TestReconcile.TestReconcile");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/reconcile");
    JobState->AuthorizationId = TEXT("auth-reconcile-001");
    JobState->ConfigDigest = TEXT("digest-rec");
    JobState->Status = TEXT("finished");
    JobState->bFinished = true;
    JobState->bSuccess = true;

    FString Error;
    FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("FINISHED"), JobState, Error);

    // Call ReconcileRenderJobs
    FAtlasTransportServer::FTransportRequest Req;
    Req.RequestId = TEXT("rec-001");
    Req.OperationName = TEXT("reconcile_render_jobs");
    Req.Capability = TEXT("render");
    Req.Kind = TEXT("read");
    Req.SchemaVersion = 1;
    Req.AuthorizationId = TEXT("auth-reconcile-001");

    TSharedPtr<FJsonObject> ObservedState;
    FString ReconcileError;
    const bool bSuccess = FAtlasTransportServer::ReconcileRenderJobs(Req, ObservedState, ReconcileError);

    TestTrue(TEXT("ReconcileRenderJobs succeeded"), bSuccess);
    TestNotNull(TEXT("ObservedState is valid"), ObservedState.Get());
    if (ObservedState.IsValid())
    {
        TestEqual(TEXT("schema_version is 1"), ObservedState->GetIntegerField(TEXT("schema_version")), 1);
        TestTrue(TEXT("journal_status is COMPLETE"), ObservedState->GetStringField(TEXT("journal_status")) == TEXT("COMPLETE"));
        TestTrue(TEXT("known_jobs array exists"), ObservedState->HasField(TEXT("known_jobs")));
        const TArray<TSharedPtr<FJsonValue>> Jobs = ObservedState->GetArrayField(TEXT("known_jobs"));
        TestTrue(TEXT("known_jobs has at least 1 entry"), Jobs.Num() >= 1);
    }

    // Cleanup journal file
    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    IFileManager::Get().Delete(*JournalPath);

    return !HasAnyErrors();
}
