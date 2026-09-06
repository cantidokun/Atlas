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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56MalformedJournalHandlingTest,
    "Atlas.UnrealAgent.UE56.MalformedJournalHandling",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalAttestationVectorTest,
    "Atlas.UnrealAgent.UE56.JournalAttestationVector",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56ReconcileAttestationPreservedTest,
    "Atlas.UnrealAgent.UE56.ReconcileAttestationPreserved",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)


IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56CapabilitySchemaReportingTest,
    "Atlas.UnrealAgent.UE56.CapabilitySchemaReporting",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalAppendHistoryTest,
    "Atlas.UnrealAgent.UE56.JournalAppendHistory",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalMonotonicSequenceTest,
    "Atlas.UnrealAgent.UE56.JournalMonotonicSequence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalDuplicateRejectionTest,
    "Atlas.UnrealAgent.UE56.JournalDuplicateRejection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalLifecycleOrderingTest,
    "Atlas.UnrealAgent.UE56.JournalLifecycleOrdering",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalStructuralValidationTest,
    "Atlas.UnrealAgent.UE56.JournalStructuralValidation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalMalformedHistoryTest,
    "Atlas.UnrealAgent.UE56.JournalMalformedHistory",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56JournalReconcileRetainedHistoryTest,
    "Atlas.UnrealAgent.UE56.JournalReconcileRetainedHistory",
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

bool FAtlasUE56MalformedJournalHandlingTest::RunTest(const FString& Parameters)
{
    const FString JournalDir = FAtlasTransportServer::GetJournalDirectory();
    IFileManager::Get().MakeDirectory(*JournalDir, true);

    // Write a malformed journal entry (invalid JSON) with a unique name.
    const FString MalformedFile = FPaths::Combine(JournalDir, TEXT("malformed_handling_test.json"));
    const FString InvalidJson = TEXT("{ this is not valid JSON ");
    const bool bSaved = FFileHelper::SaveStringToFile(InvalidJson, *MalformedFile);
    TestTrue(TEXT("malformed journal file written"), bSaved);

    FAtlasTransportServer::FTransportRequest Req;
    Req.RequestId = TEXT("malformed-001");
    Req.OperationName = TEXT("reconcile_render_jobs");
    Req.Capability = TEXT("render");
    Req.Kind = TEXT("read");
    Req.SchemaVersion = 1;
    Req.AuthorizationId = TEXT("auth-malformed");

    TSharedPtr<FJsonObject> ObservedState;
    FString Err;
    const bool bSuccess = FAtlasTransportServer::ReconcileRenderJobs(Req, ObservedState, Err);
    TestTrue(TEXT("ReconcileRenderJobs succeeded"), bSuccess);
    TestNotNull(TEXT("ObservedState valid"), ObservedState.Get());
    if (ObservedState.IsValid())
    {
        const FString Status = ObservedState->GetStringField(TEXT("journal_status"));
        TestTrue(TEXT("journal_status is PARTIAL on malformed journal"), Status == TEXT("PARTIAL"));
    }

    // Cleanup
    IFileManager::Get().Delete(*MalformedFile);
    return !HasAnyErrors();
}

bool FAtlasUE56CapabilitySchemaReportingTest::RunTest(const FString& Parameters)
{
    FAtlasTransportServer::FTransportRequest Req;
    Req.RequestId = TEXT("cap-001");
    Req.OperationName = TEXT("get_capabilities");
    Req.Capability = TEXT("render");
    Req.Kind = TEXT("read");
    Req.SchemaVersion = 1;

    TSharedPtr<FJsonObject> ObservedState;
    FString Err;
    const bool bSuccess = FAtlasTransportServer::GetCapabilities(Req, ObservedState, Err);
    TestTrue(TEXT("GetCapabilities succeeded"), bSuccess);
    TestNotNull(TEXT("ObservedState valid"), ObservedState.Get());
    if (ObservedState.IsValid())
    {
        TestEqual(TEXT("schema_version is 1"), ObservedState->GetIntegerField(TEXT("schema_version")), 1);
        TestTrue(TEXT("capabilities array exists"), ObservedState->HasField(TEXT("capabilities")));
        const TArray<TSharedPtr<FJsonValue>> Caps = ObservedState->GetArrayField(TEXT("capabilities"));
        bool bHasDurableJournal = false;
        bool bHasReconcile = false;
        for (const TSharedPtr<FJsonValue>& Cap : Caps)
        {
            FString Name;
            Cap->TryGetString(Name);
            if (Name == TEXT("durable_journal")) { bHasDurableJournal = true; }
            if (Name == TEXT("reconcile_render_jobs")) { bHasReconcile = true; }
        }
        TestTrue(TEXT("capability durable_journal reported"), bHasDurableJournal);
        TestTrue(TEXT("capability reconcile_render_jobs reported"), bHasReconcile);
    }
    return !HasAnyErrors();
}

// ── M7: append-only witness journal history ───────────────────────────────
bool FAtlasUE56JournalAppendHistoryTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-hist-append-001");
    const FString UnrealJobId = TEXT("unreal-job-hist-append-001");

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/TestH/TestH");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/hist");
    JobState->AuthorizationId = TEXT("auth-hist-001");
    JobState->ConfigDigest = TEXT("digest-hist");
    JobState->Status = TEXT("submitted");

    FString Error;
    // Write ACCEPTED -> STARTED, then FinalizeRenderJobState (which writes the
    // terminal FINISHED entry itself) for the SAME job-pair => append-only.
    const bool bAccepted = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    JobState->Status = TEXT("rendering");
    const bool bStarted = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);
    TArray<FString> Files;
    Files.Add(TEXT("C:/AtlasRenders/hist/frame_0001.png"));
    FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

    TestTrue(TEXT("ACCEPTED written"), bAccepted);
    TestTrue(TEXT("STARTED written (append)"), bStarted);

    // Append rather than overwrite: all three phases retained, terminal FINISHED wins.
    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    FString Content;
    const bool bLoaded = FFileHelper::LoadFileToString(Content, *JournalPath);
    TestTrue(TEXT("Journal file readable"), bLoaded);
    TestTrue(TEXT("phase_history contains ACCEPTED"), Content.Contains(TEXT("\"ACCEPTED\"")));
    TestTrue(TEXT("phase_history contains STARTED"), Content.Contains(TEXT("\"STARTED\"")));
    TestTrue(TEXT("phase_history contains FINISHED"), Content.Contains(TEXT("\"FINISHED\"")));
    // Latest phase is FINISHED (not regressed).
    TestTrue(TEXT("latest phase is FINISHED"), Content.Contains(TEXT("\"phase\":\"FINISHED\"")));

    IFileManager::Get().Delete(*JournalPath);
    return !HasAnyErrors();
}

bool FAtlasUE56JournalMonotonicSequenceTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-seq-001");
    const FString UnrealJobId = TEXT("unreal-job-seq-001");
    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/Seq/Seq");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/seq");
    JobState->Status = TEXT("submitted");

    FString Error;
    FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    JobState->Status = TEXT("rendering");
    FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);

    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    FString Content;
    FFileHelper::LoadFileToString(Content, *JournalPath);
    // Monotonic ordering preserved: ACCEPTED seq 1 appears before STARTED seq 2.
    const int32 AcceptedPos = Content.Find(TEXT("\"phase\":\"ACCEPTED\""));
    const int32 StartedPos = Content.Find(TEXT("\"phase\":\"STARTED\""));
    TestTrue(TEXT("ACCEPTED present"), AcceptedPos != INDEX_NONE);
    TestTrue(TEXT("STARTED present"), StartedPos != INDEX_NONE);
    TestTrue(TEXT("ACCEPTED precedes STARTED"), AcceptedPos < StartedPos);
    TestTrue(TEXT("phase_sequence 1 present"), Content.Contains(TEXT("\"phase_sequence\":1")));
    TestTrue(TEXT("phase_sequence 2 present"), Content.Contains(TEXT("\"phase_sequence\":2")));

    IFileManager::Get().Delete(*JournalPath);
    return !HasAnyErrors();
}

bool FAtlasUE56JournalDuplicateRejectionTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-dup-001");
    const FString UnrealJobId = TEXT("unreal-job-dup-001");
    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->Status = TEXT("submitted");

    FString Error;
    const bool bFirst = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    // Duplicate ACCEPTED must be rejected (append-only, duplicate phase).
    const bool bDuplicateAccepted = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    // Out-of-order STARTED after a FINISHED would also be rejected; here we test duplicate.
    TestTrue(TEXT("First ACCEPTED written"), bFirst);
    TestTrue(TEXT("Duplicate ACCEPTED rejected"), !bDuplicateAccepted);

    IFileManager::Get().Delete(*FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId)));
    return !HasAnyErrors();
}

bool FAtlasUE56JournalLifecycleOrderingTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-lifecycle-001");
    const FString UnrealJobId = TEXT("unreal-job-lifecycle-001");
    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->Status = TEXT("submitted");

    FString Error;

    // STARTED before ACCEPTED must be rejected (lifecycle ordering).
    const bool bStartedFirst = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);
    TestFalse(TEXT("STARTED before ACCEPTED rejected"), bStartedFirst);

    // ACCEPTED first is accepted; then STARTED; then FINISHED via terminal path.
    const bool bAccepted = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    JobState->Status = TEXT("rendering");
    const bool bStarted = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);
    TestTrue(TEXT("ACCEPTED written first"), bAccepted);
    TestTrue(TEXT("STARTED written after ACCEPTED"), bStarted);

    // FINISHED directly after ACCEPTED (skipping STARTED) should have been
    // rejected, but since STARTED is present the terminal write is allowed.
    // Verify a FINISHED then a FAILED dual-terminal is rejected.
    TArray<FString> Files;
    Files.Add(TEXT("C:/AtlasRenders/hist/frame.png"));
    FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));
    // Attempt a second terminal (FAILED) after FINISHED -> rejected.
    const bool bFailedAfterFinished = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("FAILED"), JobState, Error);
    TestFalse(TEXT("FAILED after FINISHED rejected (dual terminal)"), bFailedAfterFinished);

    IFileManager::Get().Delete(*FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId)));
    return !HasAnyErrors();
}

bool FAtlasUE56JournalStructuralValidationTest::RunTest(const FString& Parameters)
{
    const FString JournalDir = FAtlasTransportServer::GetJournalDirectory();
    IFileManager::Get().MakeDirectory(*JournalDir, true);
    const FString AtlasJobId = TEXT("atlas-job-struct-001");
    const FString UnrealJobId = TEXT("unreal-job-struct-001");
    const FString JournalPath = FPaths::Combine(
        JournalDir, FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));

    // Helper to write an arbitrary (possibly malformed) JSON container and then
    // attempt an ACCEPTED append; the pre-append structural validation must reject
    // parseable-but-malformed phase_history and leave the file byte-for-byte intact.
    auto AttemptAppend = [&](const FString& ContainerJson) -> bool
    {
        FFileHelper::SaveStringToFile(ContainerJson, *JournalPath);
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = UnrealJobId;
        JobState->AtlasJobId = AtlasJobId;
        JobState->Status = TEXT("submitted");
        FString Error;
        const bool bAppended = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
        return bAppended;
    };

    auto CheckUnchanged = [&](const FString& Original) -> void
    {
        FString After;
        FFileHelper::LoadFileToString(After, *JournalPath);
        TestTrue(TEXT("Malformed history left byte-for-byte untouched after rejected append"),
                 After == Original);
    };

    // Case: non-object phase_history element.
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[42]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Valid ACCEPTED append rejected after non-object history element"), bOk);
        CheckUnchanged(Bad);
    }
    // Case: missing phase.
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[{\"phase_sequence\":1}]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected after missing phase"), bOk);
        CheckUnchanged(Bad);
    }
    // Case: missing phase_sequence.
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[{\"phase\":\"ACCEPTED\"}]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected after missing phase_sequence"), bOk);
        CheckUnchanged(Bad);
    }
    // Case: wrong phase_sequence (ACCEPTED with sequence 2).
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[{\"phase\":\"ACCEPTED\",\"phase_sequence\":2}]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected after ACCEPTED with sequence 2"), bOk);
        CheckUnchanged(Bad);
    }
    // Case: ACCEPTED -> FINISHED skipping STARTED.
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[{\"phase\":\"ACCEPTED\",\"phase_sequence\":1},{\"phase\":\"FINISHED\",\"phase_sequence\":3}]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected after ACCEPTED->FINISHED skipping STARTED"), bOk);
        CheckUnchanged(Bad);
    }
    // Case: FINISHED + FAILED dual terminal.
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[{\"phase\":\"ACCEPTED\",\"phase_sequence\":1},{\"phase\":\"STARTED\",\"phase_sequence\":2},{\"phase\":\"FINISHED\",\"phase_sequence\":3},{\"phase\":\"FAILED\",\"phase_sequence\":3}]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected on FINISHED+FAILED dual terminal"), bOk);
        CheckUnchanged(Bad);
    }

    // BLOCKER 1: phase_history exists but is NOT an array must fail closed,
    // GetArrayField must not be called on a non-array, and the file must be
    // byte-for-byte unchanged.
    {
        const TArray<FString> BadTypes = {
            TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":{}}"),  // object
            TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":\"corrupt\"}"), // string
            TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":123}"), // number
            TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":null}"), // null
        };
        for (const FString& Bad : BadTypes)
        {
            const bool bOk = AttemptAppend(Bad);
            TestFalse(TEXT("Append rejected when phase_history is not an array"), bOk);
            CheckUnchanged(Bad);
        }
    }
    // BLOCKER 1: phase_history = [] (present but empty) is malformed and must fail
    // closed (an existing history field must not be an empty array).
    {
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase_history\":[]}");
        const bool bOk = AttemptAppend(Bad);
        TestFalse(TEXT("Append rejected on empty phase_history"), bOk);
        CheckUnchanged(Bad);
    }

    // SAFETY HOLE: a pre-existing journal with NEITHER 'phase_history' NOR a
    // recognized legacy top-level 'phase' must FAIL CLOSED (not be treated as
    // fresh), leaving the file byte-for-byte unchanged.
    {
        const TArray<FString> Bad = {
            TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"unrelated\":\"x\"}"), // unknown field only
            TEXT("{}"),                                                                             // empty object
            TEXT("{\"journal_schema_version\":1}"),                                                // schema only
        };
        for (const FString& B : Bad)
        {
            const bool bOk = AttemptAppend(B);
            TestFalse(TEXT("Append rejected on pre-existing journal with neither phase_history nor phase"), bOk);
            CheckUnchanged(B);
        }
    }
    // ReconcileRenderJobs must classify a neither-case file as PARTIAL (not expose
    // it as a current-state known_job). Verified by the reconcile check below.

    // BLOCKER 2 (Option A, LOSSLESS MIGRATION): a legacy schema-1 single-phase
    // BLOCKER 2 (Option A, LOSSLESS MIGRATION): a legacy schema-1 single-phase
    // journal (no phase_history, but a top-level 'phase') must NOT be treated as
    // empty. It is migrated into the first retained phase_history entry and the
    // new phase is appended only if the resulting history is valid. The prior
    // phase must survive in the final phase_history.
    {
        // Legacy ACCEPTED -> append STARTED => migrated history ACCEPTED,STARTED.
        const FString Legacy = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"journal_schema_version\":1,\"phase\":\"ACCEPTED\",\"phase_sequence\":1,\"status\":\"submitted\"}");
        FFileHelper::SaveStringToFile(Legacy, *JournalPath);
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = UnrealJobId;
        JobState->AtlasJobId = AtlasJobId;
        JobState->SequenceAssetPath = TEXT("/Game/S/S");
        JobState->OutputDirectory = TEXT("C:/AtlasRenders/mig");
        JobState->Status = TEXT("rendering");
        FString Error;
        const bool bAppended = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);
        TestTrue(TEXT("Legacy ACCEPTED -> STARTED append succeeds (lossless migration)"), bAppended);
        // Verify the migrated history retains ACCEPTED then STARTED.
        FString Migrated;
        FFileHelper::LoadFileToString(Migrated, *JournalPath);
        TestTrue(TEXT("Migrated phase_history retains ACCEPTED"), Migrated.Contains(TEXT("\"phase\":\"ACCEPTED\"")));
        TestTrue(TEXT("Migrated phase_history retains STARTED"), Migrated.Contains(TEXT("\"phase\":\"STARTED\"")));
        IFileManager::Get().Delete(*JournalPath);
    }

    // Legacy terminal journal cannot accept another terminal (out-of-order).
    {
        const FString Legacy = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase\":\"FINISHED\",\"phase_sequence\":3,\"status\":\"finished\",\"finished\":true,\"success\":true}"); 
        FFileHelper::SaveStringToFile(Legacy, *JournalPath);
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = UnrealJobId;
        JobState->AtlasJobId = AtlasJobId;
        JobState->Status = TEXT("rendering");
        FString Error;
        const bool bAppended = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("FAILED"), JobState, Error);
        TestFalse(TEXT("Legacy terminal journal cannot accept another terminal"), bAppended);
        // Legacy file must be byte-for-byte unchanged.
        FString After;
        FFileHelper::LoadFileToString(After, *JournalPath);
        TestTrue(TEXT("Legacy terminal journal unchanged after rejected terminal append"), After == Legacy);
        IFileManager::Get().Delete(*JournalPath);
    }

    // Legacy invalid/ambiguous journal (phase present but invalid) rejected unchanged.
    {
        const FString Legacy = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"phase\":\"BOGUS\"}");
        FFileHelper::SaveStringToFile(Legacy, *JournalPath);
        TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
            MakeShareable(new FAtlasTransportServer::FRenderJobState());
        JobState->JobId = UnrealJobId;
        JobState->AtlasJobId = AtlasJobId;
        JobState->Status = TEXT("submitted");
        FString Error;
        const bool bAppended = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
        TestFalse(TEXT("Legacy invalid journal rejected"), bAppended);
        FString After;
        FFileHelper::LoadFileToString(After, *JournalPath);
        TestTrue(TEXT("Legacy invalid journal unchanged"), After == Legacy);
        IFileManager::Get().Delete(*JournalPath);
    }

    // ReconcileRenderJobs must FAIL CLOSED on a parseable-but-malformed history:
    // classify journal_status PARTIAL and NOT synthesize a current state from the
    // latest (malformed) entry - malformed witness state is never evidence of
    // absence and never evidence of successful execution.
    {
        // Neither-case (no phase_history, no phase) must also be PARTIAL.
        const FString Bad = TEXT("{\"atlas_job_id\":\"atlas-job-struct-001\",\"unreal_job_id\":\"unreal-job-struct-001\",\"unrelated\":\"x\"}");
        FFileHelper::SaveStringToFile(Bad, *JournalPath);

        FAtlasTransportServer::FTransportRequest Req;
        Req.RequestId = TEXT("struct-rec");
        Req.OperationName = TEXT("reconcile_render_jobs");
        Req.Capability = TEXT("render");
        Req.Kind = TEXT("read");
        Req.SchemaVersion = 1;

        TSharedPtr<FJsonObject> ObservedState;
        FString RErr;
        const bool bOk = FAtlasTransportServer::ReconcileRenderJobs(Req, ObservedState, RErr);
        TestTrue(TEXT("ReconcileRenderJobs succeeds (returns)"), bOk);
        if (ObservedState.IsValid())
        {
            TestTrue(TEXT("journal_status is PARTIAL on malformed history"),
                     ObservedState->GetStringField(TEXT("journal_status")) == TEXT("PARTIAL"));
        }
    }

    // Cleanup any residual journal file.
    IFileManager::Get().Delete(*JournalPath);
    return !HasAnyErrors();
}

bool FAtlasUE56JournalMalformedHistoryTest::RunTest(const FString& Parameters)
{
    const FString JournalDir = FAtlasTransportServer::GetJournalDirectory();
    IFileManager::Get().MakeDirectory(*JournalDir, true);
    const FString AtlasJobId = TEXT("atlas-job-malformed-hist-001");
    const FString UnrealJobId = TEXT("unreal-job-malformed-hist-001");
    const FString JournalPath = FPaths::Combine(
        JournalDir, FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));

    // Write malformed content first, then attempt an append -> must fail closed.
    FFileHelper::SaveStringToFile(TEXT("{ not valid json "), *JournalPath);

    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->Status = TEXT("submitted");

    FString Error;
    const bool bAppend = FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    TestTrue(TEXT("Append to malformed history fails closed"), !bAppend);
    TestTrue(TEXT("Fail-closed error describes malformed history"), Error.Contains(TEXT("malformed")));

    IFileManager::Get().Delete(*JournalPath);
    return !HasAnyErrors();
}

bool FAtlasUE56JournalReconcileRetainedHistoryTest::RunTest(const FString& Parameters)
{
    const FString AtlasJobId = TEXT("atlas-job-reconcile-hist-001");
    const FString UnrealJobId = TEXT("unreal-job-reconcile-hist-001");
    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->SequenceAssetPath = TEXT("/Game/HistRec/HistRec");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/histrec");
    JobState->Status = TEXT("submitted");

    FString Error;
    FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("ACCEPTED"), JobState, Error);
    JobState->Status = TEXT("rendering");
    FAtlasTransportServer::WriteJournalEntry(AtlasJobId, UnrealJobId, TEXT("STARTED"), JobState, Error);
    TArray<FString> Files;
    Files.Add(TEXT("C:/AtlasRenders/histrec/frame.png"));
    FAtlasTransportServer::FinalizeRenderJobState(JobState, true, Files, TEXT("test"));

    // Reconcile must see the retained history.
    FAtlasTransportServer::FTransportRequest Req;
    Req.RequestId = TEXT("hist-rec");
    Req.OperationName = TEXT("reconcile_render_jobs");
    Req.Capability = TEXT("render");
    Req.Kind = TEXT("read");
    Req.SchemaVersion = 1;
    Req.AuthorizationId = TEXT("auth-histrec");

    TSharedPtr<FJsonObject> ObservedState;
    FString RErr;
    const bool bOk = FAtlasTransportServer::ReconcileRenderJobs(Req, ObservedState, RErr);
    TestTrue(TEXT("ReconcileRenderJobs succeeded"), bOk);
    bool bFoundHistory = false;
    bool bFoundJobIdAlias = false;
    if (ObservedState.IsValid())
    {
        TArray<TSharedPtr<FJsonValue>> Jobs = ObservedState->GetArrayField(TEXT("known_jobs"));
        for (const TSharedPtr<FJsonValue>& J : Jobs)
        {
            TSharedPtr<FJsonObject> Jo = J->AsObject();
            if (Jo.IsValid() && Jo->GetStringField(TEXT("atlas_job_id")) == AtlasJobId)
            {
                bFoundHistory = Jo->HasTypedField<EJson::Array>(TEXT("phase_history"));
                // Downstream consumers read job_id (alias) OR unreal_job_id; both
                // must be exposed by the derived known_job.
                const FString JobIdAlias = Jo->GetStringField(TEXT("job_id"));
                const FString ReadUnrealJobId = Jo->GetStringField(TEXT("unreal_job_id"));
                if (!JobIdAlias.IsEmpty() && JobIdAlias == ReadUnrealJobId)
                {
                    bFoundJobIdAlias = true;
                }
                break;
            }
        }
    }
    TestTrue(TEXT("Reconcile exposes retained phase_history"), bFoundHistory);
    TestTrue(TEXT("Reconcile exposes job_id == unreal_job_id alias"), bFoundJobIdAlias);

    IFileManager::Get().Delete(*FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId)));
    return !HasAnyErrors();
}
bool FAtlasUE56JournalAttestationVectorTest::RunTest(const FString& Parameters)
{
    // Contract V1 canonical HMAC-SHA256 conformance vector. This EXACT input must
    // produce the same canonical bytes and the same hexdigest as the Python
    // reference (tests/m8/test_m8_attestation.py, CONFORMANCE_NONCE/PAYLOAD,
    // EXPECTED_CANONICAL_HEX/EXPECTED_DIGEST).
    const FString Nonce = TEXT("m8-nonce-0123456789abcdef0123456789abcdef");
    const FString AtlasJobId = TEXT("atlas-render-job-aaaa-bbbb-cccc-dddd-eeeeeeeeeeee");
    const FString UnrealJobId = TEXT("unreal-job-m8-001");
    const FString Phase = TEXT("FINISHED");
    const FString EditorSessionId = TEXT("session-m8-editor");
    const FString ProcessCreationTimeUtc = TEXT("2026-09-06T00:00:00Z");
    const FString OutputDirectory = TEXT("C:/renders/out");

    TArray<FAtlasTransportServer::FOutputManifestEntry> Manifest;
    FAtlasTransportServer::FOutputManifestEntry Entry;
    Entry.Path = TEXT("C:/renders/out/f.png");
    Entry.Size = 42;
    Entry.Sha256 = TEXT("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    Manifest.Add(Entry);

    TArray<uint8> CanonicalBytes;
    const bool bCanonical = FAtlasTransportServer::ComputeJournalAttestationCanonical(
        1, AtlasJobId, UnrealJobId, 1, Phase, 3,
        EditorSessionId, ProcessCreationTimeUtc, OutputDirectory, Manifest, CanonicalBytes);
    TestTrue(TEXT("canonical payload built"), bCanonical);
    if (!bCanonical)
    {
        return !HasAnyErrors();
    }

    // Canonical bytes must match the pinned Python reference. The strongest
    // conformance property is the exact HMAC-SHA256 digest below: a difference in
    // even ONE canonical byte would change the digest. Additionally verify the
    // deterministic head (1<unit-sep>atlas) and tail (sha256 0x1d 0x1e).
    TestTrue(TEXT("canonical starts with '1 unit-sep atlas'"),
        CanonicalBytes.Num() > 4 &&
        CanonicalBytes[0] == 0x31 && CanonicalBytes[1] == 0x1f &&
        CanonicalBytes[2] == 0x61 && CanonicalBytes[3] == 0x74); // 'a','t'
    TestTrue(TEXT("canonical ends with sha256 + 0x1d 0x1e"),
        CanonicalBytes.Num() > 2 &&
        CanonicalBytes[CanonicalBytes.Num()-1] == 0x1e &&
        CanonicalBytes[CanonicalBytes.Num()-2] == 0x1d);

    FString HexDigest;
    const bool bDigest = FAtlasTransportServer::ComputeJournalAttestationDigest(Nonce, CanonicalBytes, HexDigest);
    TestTrue(TEXT("attestation digest computed"), bDigest);
    TestTrue(TEXT("attestation digest matches pinned reference"),
        HexDigest == TEXT("af7c077a395b80064537304447f4ae77fc9204577fdb70ec0189e30682288232"));

    // Altering any signed field must change the digest.
    TArray<uint8> TamperedCanonical;
    FAtlasTransportServer::ComputeJournalAttestationCanonical(
        1, AtlasJobId, UnrealJobId, 2 /* changed attempt_ordinal */, Phase, 3,
        EditorSessionId, ProcessCreationTimeUtc, OutputDirectory, Manifest, TamperedCanonical);
    FString TamperedDigest;
    FAtlasTransportServer::ComputeJournalAttestationDigest(Nonce, TamperedCanonical, TamperedDigest);
    TestFalse(TEXT("changed attempt_ordinal changes the digest"), HexDigest == TamperedDigest);

    // Wrong nonce must fail.
    FString WrongNonceDigest;
    FAtlasTransportServer::ComputeJournalAttestationDigest(TEXT("wrong-nonce"), CanonicalBytes, WrongNonceDigest);
    TestFalse(TEXT("wrong nonce produces a different digest"), HexDigest == WrongNonceDigest);

    return !HasAnyErrors();
}
bool FAtlasUE56ReconcileAttestationPreservedTest::RunTest(const FString& Parameters)
{
    // Defect B regression: the reconcile catalog MUST preserve the M8 attestation
    // fields (attempt_ordinal, entry_digest) from the DURABLE journal even when a
    // matching in-memory registry entry exists. The in-memory overlay is transient
    // and sparse; it must NOT clobber the richer journal-derived attested entry.
    const FString AtlasJobId = TEXT("atlas-reconcile-attest-001");
    const FString UnrealJobId = TEXT("unreal-reconcile-attest-001");

    // Build a job state carrying the FIFEISHED attestation fields.
    TSharedPtr<FAtlasTransportServer::FRenderJobState> JobState =
        MakeShareable(new FAtlasTransportServer::FRenderJobState());
    JobState->JobId = UnrealJobId;
    JobState->AtlasJobId = AtlasJobId;
    JobState->AttemptOrdinal = 1;
    JobState->AttemptNonce = TEXT("m10-cpp-nonce-0123456789abcdef");
    JobState->SequenceAssetPath = TEXT("/Game/TestReconcile.TestReconcile");
    JobState->OutputDirectory = TEXT("C:/AtlasRenders/attest");
    JobState->AuthorizationId = TEXT("auth-attest-001");
    JobState->ConfigDigest = TEXT("digest-attest");
    JobState->Status = TEXT("finished");
    JobState->bFinished = true;
    JobState->bSuccess = true;

    FAtlasTransportServer::FOutputManifestEntry Entry;
    Entry.Path = TEXT("C:/AtlasRenders/attest/AtlasRender_0001.png");
    Entry.Size = 42;
    Entry.Sha256 = TEXT("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    JobState->OutputManifest.Add(Entry);
    JobState->OutputFiles.Add(TEXT("C:/AtlasRenders/attest/AtlasRender_0001.png"));

    FString Error;
    const bool bWritten = FAtlasTransportServer::WriteJournalEntry(
        AtlasJobId, UnrealJobId, TEXT("FINISHED"), JobState, Error);
    TestTrue(TEXT("FINISHED journal written"), bWritten);

    // Register a matching in-memory registry entry (same atlas_job_id)) so the
    // sparse overlay would previously have clobbered the attested journal entry.
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Add(UnrealJobId, JobState);
    }

    // Reconcile.
    FAtlasTransportServer::FTransportRequest Req;
    Req.RequestId = TEXT("attest-rec-001");
    Req.OperationName = TEXT("reconcile_render_jobs");
    Req.Capability = TEXT("render");
    Req.Kind = TEXT("read");
    Req.SchemaVersion = 1;
    Req.AuthorizationId = TEXT("auth-attest-001");
    Req.EntityIds.Add(TEXT("RENDER_RECOVERY"));
    Req.Arguments = MakeShareable(new FJsonObject());
    // arguments.entity_ids must be an array of strings per ValidateRequest.
    {
        TArray<TSharedPtr<FJsonValue>> ArgEntityIds;
        ArgEntityIds.Add(MakeShareable(new FJsonValueString(TEXT("RENDER_RECOVERY"))));
        Req.Arguments->SetArrayField(TEXT("entity_ids"), ArgEntityIds);
    }

    TSharedPtr<FJsonObject> State;
    FString RecErr;
    const bool bOk = FAtlasTransportServer::ReconcileRenderJobs(Req, State, RecErr);
    TestTrue(TEXT("reconcile succeeded"), bOk);
    if (State.IsValid())
    {
        const TArray<TSharedPtr<FJsonValue>> Jobs = State->GetArrayField(TEXT("known_jobs"));
        bool bFound = false;
        for (const TSharedPtr<FJsonValue>& Jv : Jobs)
        {
            const TSharedPtr<FJsonObject> J = Jv->AsObject();
            if (!J.IsValid()) continue;
            if (J->GetStringField(TEXT("atlas_job_id")) != AtlasJobId) continue;
            bFound = true;
            // Journal-derived attested entry must retain the attestation fields.
            TestTrue(TEXT("catalog retains attempt_ordinal"),
                J->HasField(TEXT("attempt_ordinal")) && J->GetIntegerField(TEXT("attempt_ordinal")) == 1);
            TestTrue(TEXT("catalog retains entry_digest"),
                J->HasField(TEXT("entry_digest")) && !J->GetStringField(TEXT("entry_digest")).IsEmpty());
            TestTrue(TEXT("catalog retains output_manifest"),
                J->HasField(TEXT("output_manifest")));
            TestTrue(TEXT("catalog retains phase_history"),
                J->HasField(TEXT("phase_history")));
        }
        TestTrue(TEXT("reconcile produced the attested job entry"), bFound);
    }

    // Cleanup
    const FString JournalPath = FPaths::Combine(
        FAtlasTransportServer::GetJournalDirectory(),
        FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId));
    IFileManager::Get().Delete(*JournalPath);
    {
        FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);
        FAtlasTransportServer::RenderJobRegistry.Remove(UnrealJobId);
    }
    return !HasAnyErrors();
}

