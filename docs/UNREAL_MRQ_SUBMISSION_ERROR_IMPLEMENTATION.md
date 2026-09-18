# Unreal Agent — MRQ Submission Outcome Propagation Implementation Record

**Date:** September 17, 2026
**Milestone:** `MRQ submission outcome propagation — COMPLETE + LIVE-PROVEN`
**Authorized slice:** "submission acceptance / rejection identity propagation", on top of the design gate
`docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md` (`CLEAR WITH MINOR FINDINGS`).
**Published baseline:** `9e2c893f1db6b79c77caea3fb4595a6217d3ef1f`.
**Scope change:** one transport source file. No planning/, Blender, protocol, receipt or continuity change.

```text
  - the submission call and its acceptance observation happen in one game-thread task
  - acceptance is proven by GetActiveExecutor() == the exact supplied executor
  - a refused submission fails the operation immediately with a typed error
  - an unprovable outcome fails closed as ambiguous
  - a rejected submission's registry entry is not left readable as "submitted"
  - no new transport operation, response field, status value, queue mutation or timeout change
  - queue consumption and the private queue instance remain unimplemented
  - automatic retry remains prohibited
  - exact job identity unchanged; receipts only from fresh verified terminal evidence
```

---

## 1. The change

One file: `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`
(**+67 / -9**, source blob `1d7d33fd5fc8fe598d3d6ff5e834c5a169025adb`), inside
`FAtlasTransportServer::SubmitRender`.

Before this slice the start was fire-and-forget, so the outcome was unknowable:

```cpp
    AsyncTask(
        ENamedThreads::GameThread,
        [QueueSubsystem, Executor]()
        {
            if (QueueSubsystem && IsValid(QueueSubsystem) &&
                Executor && IsValid(Executor))
            {
                QueueSubsystem->RenderQueueWithExecutorInstance(Executor);
            }
        });
    // ... then the accepted-looking response was built from the pre-start registry state
```

After this slice the call and the identity observation share one game-thread task (`SubmitRender` already runs
inside `ExecuteOnGameThread`, `AtlasTransportServer.cpp:517-533`), and the response is built only on proven
acceptance:

```cpp
    if(!QueueSubsystem || !IsValid(QueueSubsystem) ||
       !Executor || !IsValid(Executor))
    {
        { FScopeLock Lock(&RenderJobRegistryMutex); RenderJobRegistry.Remove(JobId); }
        E=TEXT("render submission failed: the movie pipeline queue subsystem or the render executor was unavailable");
        return false;
    }

    QueueSubsystem->RenderQueueWithExecutorInstance(Executor);

    UMoviePipelineExecutorBase* ObservedActiveExecutor=
        QueueSubsystem->GetActiveExecutor();

    if(ObservedActiveExecutor!=Executor)
    {
        { FScopeLock Lock(&RenderJobRegistryMutex); RenderJobRegistry.Remove(JobId); }

        if(ObservedActiveExecutor!=nullptr)
        {
            E=TEXT("render submission rejected: a render is already active in this editor, so Unreal refused to register the supplied executor");
            UE_LOG(LogAtlasTransport, Error, TEXT("ATLAS MRQ SUBMISSION: rejected; another executor is active; no Atlas job was accepted"));
        }
        else if(JobState->bFinished || JobState->bFailed)
        {
            E=TEXT("render submission rejected: the supplied executor finished or failed without becoming the active executor");
            UE_LOG(LogAtlasTransport, Error, TEXT("ATLAS MRQ SUBMISSION: rejected; the supplied executor reached a terminal state without becoming active"));
        }
        else
        {
            E=TEXT("render submission outcome ambiguous: the supplied executor was not observed as the active executor after the submission call");
            UE_LOG(LogAtlasTransport, Error, TEXT("ATLAS MRQ SUBMISSION: ambiguous; the supplied executor was not observed as the active executor"));
        }

        return false;
    }
    // accepted: the existing response (job_id, status="submitted", status_message="Render submitted", ...)
```

### 1.1 Why this is the whole fix

```text
engine      UMoviePipelineQueueSubsystem::RenderQueueInstanceWithExecutorInstance assigns ActiveExecutor =
            InExecutor synchronously, and on refusal (ensureMsgf(!IsRendering())) returns BEFORE any
            assignment, before Execute() and before any delegate — so a refused submission can only be
            detected by comparing the supplied executor against the observed active executor.
python      no change was needed and none was made: the existing response contract already carries the
            outcome (success=false + error -> UnrealAdapterError -> structured UnrealPlanExecutionError at
            planning/unreal_plan_executor.py:383-388), so a rejection is a hard failure at submit_render with
            no job id exposed, no polling, no receipt and no retry.
```

### 1.2 The three outcomes as implemented

```text
ACCEPTED    ObservedActiveExecutor == Executor
            -> registry entry stays, existing response shape, existing job identity, existing polling
REJECTED    ObservedActiveExecutor != nullptr (another executor is active)  [engine refused the call]
            -> registry entry removed, operation fails, no job identity exposed, no receipt, no retry
            ObservedActiveExecutor == nullptr and the executor reached a terminal state
            -> same fail-closed handling (reachable only through the engine's synchronous-finish paths)
AMBIGUOUS   ObservedActiveExecutor == nullptr with no terminal state
            -> fail closed with a typed "outcome ambiguous" failure; acceptance is never claimed
```

`IsRendering()` is never consulted for acceptance (it appears in the source only inside the explanatory comment),
and nothing is inferred from logs, queue position, timing, callback order, output files, filesystem state or the
existence of the newly minted GUID.

## 2. Deterministic test matrix

`tests/test_unreal_mrq_submission_outcome_contract.py` (NEW, 18 tests, blob
`a122022a3dbe63a5c69911845a9592d227b8aba34bd01a724352d34dabd2a8ef`):

```text
transport source contract
  call and identity observation share one task (no AsyncTask; only the call, the declaration and the
    observation between them, with no branch or deferral interposed)
  acceptance requires the exact supplied executor identity, and the response is built only after it
  IsRendering() is never used as the acceptance proof
  rejection and ambiguity fail the operation with typed, distinguished messages
  a rejected submission's registry entry is removed (not left readable as "submitted")
  the failure path emits no observed state and no job id
  no new transport operation (frozen 21-name set) and no new response field (frozen 7-field set)
  no queue mutation added (no DeleteJob/DeleteAllJobs/SetConsumed/DeleteQueue/EmptyQueue on the failure path)
  no sleep/timer inference in the submission path
  Slice 1 artifact identity guard intact (payload job compared to the registered job before AddUnique)
  Slice D start-callback identity guard intact (payload job compared before Status/StatusMessage/Progress)
outcome propagation through the real adapter + plan executor + workflow
  accepted submission yields the existing job identity and runs the authorized verify step
  rejected / ambiguous submissions fail closed: exactly one submit attempt, no polling, no wait, no receipt,
    UnrealPlanExecutionFailure carries the failing operation and no completed operations
  GUID generation alone does not imply acceptance (a failed response carrying a job payload still fails)
  job identity verification unchanged (exact expected_job_id, mismatch fails)
  no timeout inflation and no elapsed time (300.0 s unchanged, clock advanced by 0.0, no sleeps)
  the submission plan is still exactly [submit_render, verify_render_job]
```

Baseline RED proof (throwaway worktree at `9e2c893`): **8 of 18 FAIL** — all eight transport-outcome
assertions. The ten that pass at baseline are the invariants this slice must not change plus the Python
plumbing that already carried a failed response; that split is exactly the discrimination expected.

```text
focused set (new slice + attribution + continuity + workflow + verifier + receipt + executor + adapter)
                                                                185 passed, 1 skipped
broad sweep, identical selection as the previous milestones    1216 passed, 7 skipped   (baseline 1198 + 18)
```

## 3. Live UE 5.6.1 gate

`tests/test_unreal_mrq_submission_outcome_real_integration.py` (NEW, blob
`5260129fb60ccdd61a4d2504b7a22455674eb78b054711945bd8ee055e9eab49`) — **2 passed in 22.80 s in ONE fresh
editor session** (session log opened 20:10:33). Four submission attempts.

```text
A  accepted while idle      job CE3199F4-4F8C-B778-F093-859122F47768 (1-24)
                            accepted response kept status/status_message contract; the job then reached its
                            own "rendering" state (watch samples: submitted -> rendering)
B  attempted while A was    REJECTED in 1.50 s
   genuinely rendering      error text: "render submission rejected: a render is already active in this
                            editor, so Unreal refused to register the supplied executor"; the message is not
                            a timeout; elapsed far below the 300 s poll timeout
C  no receipt for B         receipt file for the rejected submission was never created
F  A unaffected             24 artifacts, exact 1-24 frame set inside its own directory, exact job id,
                            continuity completeness verified, receipt coherent
D  multi-job queue          accepted job 2B55DA72-4114-FDBC-36C5-BAA2BFCD6EBA -> exactly 2 PNGs in its own
                            directory, exact job id, receipt coherent
E  same range (1-2 twice)   accepted job 6DA54FB0-4FFF-BCF5-32C1-A6B263FE2D27 -> exactly 2 PNGs in its own
                            directory, disjoint from the other job's artifacts, predecessor unchanged
                            receipts present: exactly the two accepted submissions' receipts
```

Engine-side corroboration from that session's log (independently of the test assertions):

```text
"Render already in progress." (the engine's own refusal, KismetExecutionMessage)         1 occurrence
"ATLAS MRQ SUBMISSION: rejected; another executor is active; no Atlas job was accepted"   1 occurrence
"MoviePipelineLinearExecutorBase starting N jobs"      3 occurrences: 1, 3, 4  (four attempts)
"MoviePipelineLinearExecutorBase finished"             3 occurrences
"ATLAS MRQ ATTRIBUTION: discarded per-job output data" 6 occurrences (Slice 1 still discarding foreign payloads)
```

The three-versus-four count is the decisive evidence: the rejected attempt never registered an executor, so no
executor was started for it, no callback fired, and no job identity was ever exposed to Atlas. The growth
`1 -> 3 -> 4` also shows the residual documented in §5.1.

## 4. DLL provenance

```text
source mtime   2026-09-17 20:05:12   AtlasTransportServer.cpp   blob 1d7d33fd5fc8fe598d3d6ff5e834c5a169025adb
build          [1/4] Compile [x64] AtlasTransportServer.cpp
               [3/4] Link [x64] UnrealEditor-AtlasUnrealTransport.dll
               build end 2026-09-17T20:05:35-04:00 (exit 0)
DLL            2026-09-17 20:05:34   364,544 bytes
               sha256 4b7dc0a8a604570600c664710adcc3088b4b78556892fc8a6409734718fc46a5
session opened 2026-09-17 20:10:33   `Loading module ... UnrealEditor-AtlasUnrealTransport.dll (0.348 MB)`
```

Two independent discriminators: the DLL grew from the previous slice's 361,984 bytes (0.345 MB) to 364,544 bytes
(0.348 MB, matching the session's own module-load line), and the observed behaviour — an immediate typed
rejection instead of a 300 s timeout — is impossible with the previous binary.

## 5. Non-claims and residual findings

### 5.1 A rejected submission leaves its allocated MRQ job in the queue

The queue is deliberately not mutated (frozen: no queue consumption, no queue semantics change), so the job
that `SubmitRender` allocated and configured before the refusal stays in the editor's queue. Measured in the live
gate: the first accepted submission after the rejection reported `starting 3 jobs` (the abandoned job plus the
new one plus the earlier long job), and two orphan PNGs appeared in the rejected job's configured output
directory. They are **not evidence**: no receipt exists for that submission, Atlas never saw a job identity for
it, and Slice 1 discarded its payload (the 6 discards above), so it never entered any accepted job's evidence.
This is the existing accumulation behaviour of the shared queue combined with the deliberate no-queue-mutation
rule, now with a measured example; it is recorded, not fixed.

### 5.2 Registry entries for accepted jobs are still never pruned

This slice removes the entry of a *rejected* submission. Entries for accepted jobs are still retained for the
life of the editor process (pre-existing; registry pruning and consumption are out of scope).

### 5.3 Engine mutual exclusion is still best-effort

Finding F2 of the design review stands unchanged: the PIE executor sets `bIsRendering` only in
`OnPIEStartupFinished`, so a submission during that window can still be *accepted* by the engine and overwrite
`ActiveExecutor`. This slice makes the outcome truthful for the submission Atlas makes; it does not and cannot
make the engine's exclusion sound.

### 5.4 No deterministic execution cover for the C++

As for Slice 1 and Slice D: the transport's behaviour is covered by source-shape assertions plus the live gate.
There is no in-repository harness that executes the transport code.

### 5.5 Harness-only log synchronisation between the two live tests

The second live test needs the editor idle again after the first test's long render, and the only signal that
the engine has released the executor is the executor-finished log line. The test waits for it, with a bounded
timeout, purely to establish that precondition. No product code reads a log at any point, and the acceptance
decision remains identity-based; the design review's F3 (log is not an authority) is unaffected.

### 5.6 Earlier attempt during development

The first live run of the module failed its second test because the previous executor had not finished
releasing; the fix was the harness synchronisation in §5.5, applied to the test only. No production code was
changed in response to a test failure, and the gate was then re-run on a fresh editor session whose log
contains exactly one run's evidence.

## 6. Frozen invariants preserved

Named Pipe protocol and its operation/argument/response field sets (21 operations, 7 response fields, both
asserted); authorization model and sequence binding; exact engine-minted render-job identity; receipt
architecture and the "receipt only from fresh verified terminal evidence" gate; `UnrealShotContinuity` as the
single continuity authority; inclusive Atlas frame semantics and the single MRQ end-frame translation; shot
continuity and PNG containment/frame-set verification; MRQ artifact attribution (Slice 1 + Slice D); queue
semantics (no deletion, no consumption, no private queue instance); no automatic mutation retry; no timeout
redesign; no entity discovery/cache; no distributed rendering; no generic workflow engine; no model-derived
authority; Blender untouched.
