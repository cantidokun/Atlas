# Unreal Agent — MRQ Submission Rejection / Error Propagation Design Review

**Date:** September 17, 2026
**Mode:** READ-ONLY ARCHITECTURE / DESIGN GATE — source audit + previously recorded measurements. No code, no
tests, no editor run, no live gate, no workflow/action-runner execution.
**Published baseline:** `reconcile/unreal-autonomy-origin-20c6d10` @
`9e2c893f1db6b79c77caea3fb4595a6217d3ef1f` (Slice 1 + Slice 2 + Slice D of MRQ attribution are COMPLETE +
LIVE-PROVEN on top of it).
**Subject:** the concurrent-submission refusal. A render submission made while another render is already active
in the same editor is refused by the engine; the transport cannot see the refusal; the caller observes a poll
timeout instead of a rejection. Carried as finding **F2** of
`docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md`.
**Verdict:** **CLEAR WITH MINOR FINDINGS** (§12). Nothing is authorized by this document.

```text
Explicitly NOT done here: no production code, no tests, no editor session, no live gate, no queue
consumption, no private queue instance, no protocol change, no job-identity change, no receipt/evidence
change, no artifact-attribution change, no shot-continuity change, no Blender change. Nothing committed.
```

---

## 1. The exact path, source-anchored

### 1.1 Atlas side — `FAtlasTransportServer::SubmitRender` (`AtlasTransportServer.cpp:1163-1534`)

```text
1332-1345  mint the job id (FGuid::NewGuid) and initialise the registry entry:
           Status="submitted", StatusMessage="Render submitted", Progress=0.0,
           bSuccess=false, bFinished=false, bFailed=false
1358-1368  allocate UMoviePipelinePIEExecutor + the executor job (SetConfiguration/CopyFrom snapshot);
           store Executor + Job as TWeakObjectPtr in the entry
1369-1402  register OnIndividualJobStarted   (Slice D: identity-guarded)
1404-1468  register OnIndividualJobWorkFinished (Slice 1: artifact guard + terminal flags)
1470-1491  register OnExecutorFinished      (terminal flags + status "finished"/"failed")
1493-1496  RenderJobRegistry.Add(JobId, JobState)
1499-1508  AsyncTask(ENamedThreads::GameThread, [QueueSubsystem, Executor]()
               { ... QueueSubsystem->RenderQueueWithExecutorInstance(Executor); });
           <- the start attempt is DEFERRED and its outcome is never read
1510-1534  build the response from the entry as it stands BEFORE the deferred start:
           job_id, status="submitted", progress=0.0, status_message="Render submitted",
           sequence_asset_path, start_frame, end_frame, end_frame_exclusive; return true
```

The response is therefore always `success=true` with a job id, whether or not the engine will accept the
executor. The refusal happens later, in a game-thread task whose result is discarded.

### 1.2 Engine side — the refusal

`UMoviePipelineQueueSubsystem::RenderQueueInstanceWithExecutorInstance`
(`MovieRenderPipelineEditor/Private/MoviePipelineQueueSubsystem.cpp`, the function Atlas calls through
`RenderQueueWithExecutorInstance(Executor)`, which is a one-line wrapper passing `GetQueue()`):

```cpp
    if (!ensureMsgf(!IsRendering(), TEXT("RenderQueueWithExecutor cannot be called while already rendering!")))
    {
        FFrame::KismetExecutionMessage(TEXT("Render already in progress."), ELogVerbosity::Error);
        return;                                    // REFUSAL: no state change, no Execute, no delegate
    }
    if (!InExecutor) { ... return; }
    ...
    ActiveExecutor = InExecutor;                   // ACCEPTANCE, assigned synchronously
    ActiveExecutor->OnExecutorFinished().AddUObject(this, &UMoviePipelineQueueSubsystem::OnExecutorFinished);
    ActiveExecutor->Execute(InQueue);              // returns as soon as the render is scheduled
```

with `ActiveExecutor` (a `TObjectPtr<UMoviePipelineExecutorBase>`, `MoviePipelineQueueSubsystem.h:106-107`) and

```cpp
    UMoviePipelineExecutorBase* GetActiveExecutor() const { return ActiveExecutor; }   // header:50-52
    bool IsRendering() const { return ActiveExecutor ? ActiveExecutor->IsRendering() : false; }  // header:91-93
```

and the release path, which has **no identity check**:

```cpp
void UMoviePipelineQueueSubsystem::OnExecutorFinished(UMoviePipelineExecutorBase*, bool)
{
    ... ActiveExecutor = nullptr;
}
```

Consequences that matter for this design:

1. The refusal returns **before** `ActiveExecutor` is assigned and before `Execute`, so Atlas's three lambdas
   (registered on that executor instance in §1.1) **never fire**: there is no callback, no delegate, no
   terminal flag, no status change. The only engine-side symptom is
   `FFrame::KismetExecutionMessage("Render already in progress.", Error)`, i.e. a log line (and an on-screen
   message in interactive PIE). It is operator-visible, not machine-observable through the transport.
2. Acceptance is **synchronous and exact**: `ActiveExecutor` is assigned before `Execute` is called, and it stays
   equal to our executor until that executor broadcasts finished/errored (which the subsystem handles by
   clearing the pointer). So immediately after the call returns on the game thread,
   `GetActiveExecutor() == Executor` is a pointer-identity proof that the engine registered *our* submission.
3. `IsRendering()` is **not** a synonym for "an executor is registered": it delegates to the executor's own
   `IsRendering_Implementation()`, whose timing is executor-specific (see §3 Q5/Q7).
4. `ensureMsgf` is an *ensure*, not a contract: on failure it reports (log/blueprint message) and returns false
   so the caller's `return` executes. Atlas must not depend on the ensure's side effects, and must not depend on
   crash-on-ensure being enabled.
5. The same shape exists in the runtime subsystem used by non-editor rendering,
   `UMoviePipelineQueueEngineSubsystem::RenderQueueWithExecutorInstance`
   (`MovieRenderPipelineCore/Private/MoviePipelineQueueEngineSubsystem.cpp:23-33`: same
   `ensureMsgf(!IsRendering(), ...)`, same `KismetExecutionMessage`, same `return`), and it also exposes
   `GetActiveExecutor()` (`MoviePipelineQueueEngineSubsystem.h:44-46`) and `IsRendering()` (`.h:77-79`). Its
   class-type entry point even returns `ActiveExecutor` to its caller (`.cpp:19`) — the engine itself treats
   "read the subsystem's ActiveExecutor at the call site" as the way to learn what happened.

### 1.3 Atlas side — registry, polling, workflow result

```text
InspectRenderJob (AtlasTransportServer.cpp:1536-1610)
    registry lookup by exact job id only (no enumeration, no discovery)
    failure => "Render job not found: <id>" (success=false)
    success => job_id, status, status_message, progress, success, finished, failed,
              sequence_asset_path, output_directory, output_format,
              start_frame, end_frame, end_frame_exclusive, output_files
    NO liveness field, NO executor field, NO notion of "was this ever started"
RenderJobRegistry (Public/AtlasTransportServer.h:94-95, Private:42-43)
    static TMap<FString, TSharedPtr<FRenderJobState>> managed by a static FCriticalSection;
    entries are Added (1495) and only ever Found (1375, 1410, 1476, 1567) — never removed, never pruned
unreal_adapter_production.py::_execute
    if not response.success: raise UnrealAdapterError("Unreal operation '<name>' ... failed: <error>")
unreal_plan_executor.py:383-388
    catches the adapter error, builds UnrealPlanExecutionFailure(intent, index, operation, ledger,
    message, entity_ids, failure_context, completed) and raises UnrealPlanExecutionError(message, failure=...)
unreal_render_workflow.py:99-108 / 187-245
    submit() == plan + authorize + execute; wait_for_completion() polls inspect_job:
      state["failed"] is True            -> UnrealRenderWorkflowError("render job failed: status=...")
      state["finished"] is True          -> verify_render_job_completion (+ continuity) -> receipt -> persist
      status not in {submitted,queued,rendering} -> "... unsupported terminal state: ..."
      elapsed >= timeout_seconds (default 300)   -> "render job did not complete within 300 seconds"
```

## 2. Today's failure mode, precisely

```text
t0   caller submits                 -> transport returns success=true, job_id=<GUID>, status="submitted"
t0+  scheduled task runs
       refused (another render active)  -> engine logs "Render already in progress."; nothing else changes
       accepted                         -> ActiveExecutor=ours; render proceeds; callbacks fire as usual
t0.. polling inspect_render_job (job_id) for a refused submission:
       reports status="submitted", finished=false, failed=false, progress=0.0, output_files=[]
       ... indefinitely (the registry entry is never pruned and never terminalised)
t0+300 s  UnrealRenderWorkflowError("render job did not complete within 300 seconds")
```

So a refusal is reported to the caller as a **timeout with a misleading message**: it is indistinguishable from a
slow render, it costs the full configured timeout, it consumes polling requests for the whole window, and the
error text names the wrong cause. It never produces a false success (no receipt is issued: receipts require
`finished` + fresh verified evidence with exact job identity), so the defect is a **diagnosis/availability**
defect, not a false-evidence defect. The refused submission also leaves a permanently readable
`status="submitted"` registry entry, which is a second, quieter hazard: any later reader of that exact job id
sees what looks like a live submission.

## 3. The seven questions

### Q1. Where, exactly, can the refusal be observed?

Three candidate locations, in decreasing exactness:

```text
L1  in-process, at the call site (exact)
      the caller of RenderQueueWithExecutorInstance owns the subsystem and the executor pointer;
      immediately after the call on the same game thread:  GetActiveExecutor() == Executor  => accepted
                                                            GetActiveExecutor() != Executor  => refused
      This is the ONLY location that can distinguish the two outcomes without inference. It requires the start
      call and the read to be in the same task (today they are split by the AsyncTask, §1.1).
L2  engine log (inexact, out-of-band)
      "Render already in progress." (KismetExecutionMessage) / the ensure report. Machine-readable only by log
      scraping — a new, out-of-band observation channel with its own authority problems, and not permitted by the
      frozen constraints (no new authority, no new transport primitive, no filesystem/log discovery).
L3  polling (not observable at all)
      inspect_render_job reports registry fields only; a refused job is "submitted" forever (§2).
```

### Q2. Can it be surfaced using an existing engine-visible state or callback?

**State: yes.** `UMoviePipelineQueueSubsystem::GetActiveExecutor()` is a public, BlueprintPure accessor, and
`ActiveExecutor` is assigned synchronously by the very function that can refuse. `IsRendering()` is also public but
is an executor-implementation-dependent projection (§3 Q5/Q7), so it is usable as a *pre-check* only.
Both subsystems (editor and runtime) expose the same accessor.

**Callback: no.** The refusal path returns before `Execute` and before any executor delegate exists; the
subsystem declares no refusal delegate (`FOnMoviePipelineQueueLoaded` is the only one, and it concerns queue
loading). Atlas's `OnIndividualJobStarted` / `OnIndividualJobWorkFinished` / `OnExecutorFinished` lambdas are
registered on the executor instance and therefore cannot fire for a submission that never started. There is no
existing engine event to subscribe to.

### Q3. Can the existing transport response/result contract represent the distinction without a Named Pipe protocol change?

**Yes — entirely within existing fields, and the plumbing already exists end to end.**

```text
wire    FTransportResponse already carries success (bool), error (string), source, observed_state
        (AtlasTransportServer.cpp:241-248 serialisation; planning/unreal_transport_contract.py:59-73 dataclass)
        No new operation, no new field, no new argument, no new status value is required.
python  unreal_adapter_production.py::_execute already raises UnrealAdapterError on success==false
        unreal_plan_executor.py:383-388 already converts that into a structured UnrealPlanExecutionFailure
        (intent, failing operation index/name, evidence ledger so far, completed operations, failure context)
        unreal_render_workflow.submit() propagates it; wait_for_completion() is never entered
```

The distinction is therefore already representable: *submission rejected* = a failed operation at
`submit_render` (hard error, no job id in evidence, no polling, no receipt); *accepted but not complete* =
`success=true` with a job id and `status in {submitted, queued, rendering}` (pollable). The refusal text can and
should name the cause (the engine's own `"Render already in progress."` is available verbatim).

For completeness, the poll-side is also representable without a protocol change *if* a deferred detection is ever
needed: the registry already has the existing terminal vocabulary (`failed` + `status_message`) which
`wait_for_completion` already converts into `"render job failed: status=..."`. That reuses an existing terminal
state rather than inventing a status value (inventing one would change the job-state/evidence contract consumed
by the verifier, which is out of bounds).

### Q4. If not, what is the narrowest fail-closed contract that distinguishes "rejected" from "accepted but not yet complete"?

"Yes, it is representable" (§3 Q3) is the answer; the narrowest contract that keeps the two outcomes
non-confusable is:

```text
outcome            observation (engine-visible, at the moment of the call)        caller-visible result
--------------------------------------------------------------------------------  ------------------------------
REJECTED           subsystem did not register our executor                        submit_render FAILS:
                   (GetActiveExecutor() != Executor after the call)               success=false,
                                                                                  error mentions the engine refusal
                                                                                  -> UnrealAdapterError ->
                                                                                     structured
                                                                                     UnrealPlanExecutionError
                                                                                  -> no polling, no receipt
ACCEPTED,          GetActiveExecutor() == Executor                                submit_render succeeds with a
NOT YET COMPLETE                                                                  job id; poll until verified
                                                                                  terminal evidence; receipt only
                                                                                  after fresh verification
AMBIGUOUS          ActiveExecutor == nullptr immediately after the call and no    FAIL CLOSED: treated as
                   terminal callback observed on our executor                     rejection, never as acceptance
LOST RESPONSE      pipe error / disconnect before the response was read           FAIL CLOSED: typed transport
                   (NamedPipeTransportDisconnectedError / TimeoutError)           error, no receipt, no retry
```

Invariants that make this fail-closed rather than merely clearer:

1. The **only** path to a receipt stays "fresh verified terminal evidence with exact job identity"
   (`verify_render_job_completion` + `verify_shot_continuity_completeness` + exact job id). A rejection produces
   no artifacts and can never reach a receipt.
2. Acceptance is a **positive** observation (identity equality), never inferred from absence of error, elapsed
   time, queue position, or the absence of artifacts.
3. A refusal is terminal at the submission operation: no retry, no queue mutation, no second submission minted
   behind the caller's back (`no automatic mutation retry`).
4. The job id remains the only render-job identity, and the rejected submission is not reported under any job id
   it did not receive.

### Q5. What happens if the engine is between those states?

The engine has more than two states; enumerating them (source-anchored) matters because it constrains what any
design may infer:

```text
S0  submitted, deferred start not yet run (Atlas AsyncTask queued)
      ActiveExecutor unchanged; entry "submitted". Indistinguishable from S1/S2 by polling.
S1  accepted: ActiveExecutor = our executor, Execute() has returned
      IsRendering() may STILL be false here. In the PIE executor, bIsRendering is set to true only in
      OnPIEStartupFinished (MoviePipelinePIEExecutor.cpp:245), i.e. after RequestPlaySession (:213) completes
      and PostPIEStarted fires (:216). Between S1 and S3 the executor is registered but reports
      IsRendering() == false; the engine's own comment at :243-244 states this is deliberate ("the queue would
      get stuck thinking it's rendering when it's not").
S2  consequence: a submission made during S1/S2 (IsRendering() == false, ActiveExecutor == someone else's
      executor) PASSES the !IsRendering() check and is ACCEPTED: ActiveExecutor is overwritten with no identity
      check, our executor keeps running, and when the displaced executor later finishes, OnExecutorFinished sets
      ActiveExecutor = nullptr unconditionally.
S3  rendering: IsRendering() == true -> the ensure refuses any further submission.
S4  finalize / error / cancel: the executor broadcasts "finished" (OnExecutorFinishedImpl and also
      OnExecutorErroredImpl, MoviePipelineExecutor.h:216-234) -> the subsystem clears ActiveExecutor.
      OnExecutorErroredImpl does not itself reset bIsRendering, but with ActiveExecutor cleared
      IsRendering() is false again, so the state self-heals.
Also: the null-queue / empty-queue paths (MoviePipelineLinearExecutor.cpp:20-31) call
      OnExecutorFinishedImpl synchronously inside Execute, so ActiveExecutor can be cleared within the call.
      Atlas always allocates a job before submitting, so this path is not reachable in practice.
```

Answers implied by that enumeration:

- The refusal is **only** meaningful for the state at the instant of the call, read on the same thread. Reading
  it later (or from another thread) is unsound because S1/S2/S4 can change it.
- "IsRendering() == false" does **not** imply "I will be accepted" (S1/S2), and "IsRendering() == true" does
  imply refusal at that instant (S3) — but it is a *precondition* check, not a proof, because the engine can
  move between the check and the deferred call.
- The only exact per-call signal is the **identity of the active executor immediately after the call**.
- If Atlas is between states *when it inspects*, nothing in the poll can disambiguate (§3 Q1/L3). This is
  exactly why the recommended design puts the outcome on the **submission call**, not on the poll.

### Q6. What happens if the transport dies after submission but before the caller observes job creation?

```text
topology      the transport server is an in-editor module (FAtlasTransportServer is started by the editor
              module); pipe death therefore means the editor process is gone, not just a client
registry      FAtlasTransportServer::RenderJobRegistry is a process-lifetime static TMap (§1.3) -> gone
queue         the MRQ queue is a transient CreateDefaultSubobject on the subsystem, persisted only by an
              explicit SaveQueue; nothing is written on submit -> the job is gone with the process
job identity  the id is an engine-minted FGuid returned only in the submit response; if the caller never read
              the response it holds no job id, and a retry mints a NEW id (GUIDs are not reused), so a retried
              submission can never alias the lost one
receipts      issue-and-save happen in the caller only after verified terminal evidence (§1.3) -> none issued
caller sees   pipe error 2 / 109 / 121 / 231 / 232 / 233 -> NamedPipeTransportError subclass
              (unreal_transport_named_pipe.py:43-65) -> UnrealAdapterError -> structured
              UnrealPlanExecutionError with the completed-operation list
```

So: **fail-closed**, with three honest caveats:

1. A partially rendered orphan job can leave PNGs on disk. They are not evidence — no receipt, no engine job
   identity, and Atlas never enumerates the filesystem to adopt artifacts (frozen: no artifact discovery,
   no filesystem-based authority).
2. The caller learns "the submission outcome is unknown", not "rejected". That is the honest and fail-closed
   answer, and it must not be retried automatically (a retry would create a second job).
3. Nothing about this is made worse or better by the design below; it is recorded so the contract does not
   pretend to know more than the engine does.

### Q7. Does the design remain valid for the existing PIE executor and for a future executor implementation?

```text
both subsystems   UMoviePipelineQueueSubsystem (editor, used by Atlas) and UMoviePipelineQueueEngineSubsystem
                  (runtime/in-process) refuse with the same ensureMsgf(!IsRendering()) and both expose
                  GetActiveExecutor() and IsRendering() (§1.2, item 5). The refusal is a property of the
                  SUBSYSTEM contract, not of any executor class.
both take         UMoviePipelineExecutorBase* (executor-agnostic): ActiveExecutor is assigned by the subsystem
                  for whatever subclass was supplied, before Execute is called.
executor-specific IsRendering() timing: PIE executor sets bIsRendering only in OnPIEStartupFinished
                  (MoviePipelinePIEExecutor.cpp:245); UMoviePipelineInProcessExecutor sets it inside its own
                  start path (MoviePipelineInProcessExecutor.cpp:145) after the pipeline is created; other
                  implementations must define the same overload at their own discretion.
therefore         a design anchored on ACTIVEEXECUTOR IDENTITY is executor-agnostic and survives a future
                  executor implementation; a design anchored on IsRendering() timing or on the position of the
                  bIsRendering assignment inside a particular executor is NOT portable.
residual          the S2 window hazard (§3 Q5) is engine-level and executor-dependent in its width; it is out
                  of scope for Atlas (fixing it would require queue/executor changes, which are frozen).
```

## 4. Candidate evaluation

| # | candidate | verdict | basis |
|---|-----------|---------|-------|
| A | synchronous submission-state observation | **ACCEPT with F** (observation half) | `GetActiveExecutor() == Executor` on the game thread right after the call is the only exact signal (§3 Q1/L1). Observation alone is not enough: the call itself must be in the same task, otherwise there is nothing to observe (§1.1, `AsyncTask`). |
| B | executor state / error observation | **PARTIAL — already used for in-flight errors, not applicable to the refusal** | in-flight success/failure is already observed through the executors' `OnIndividualJobWorkFinished` / `OnExecutorFinished` lambdas with terminal flags; a refused submission never reaches `Execute`, so none of those callbacks fire (§1.2, item 1). No policy change needed for the in-flight case; it simply cannot see the refusal. |
| C | explicit submission outcome in existing result plumbing | **ACCEPT** | The refusal is representable with the existing `success`/`error` response fields and already flows into `UnrealAdapterError` → structured `UnrealPlanExecutionError` → a hard failure from `submit()`. No protocol change, no new status value, no new identity. (§3 Q3/Q4.) |
| D | bounded / typed timeout semantics | **REJECT as the mechanism** | a timeout cannot distinguish "refused" from "slow" — it is the symptom being reported, not the cause. The existing timeout already provides the backstop; changing or inflating it is explicitly forbidden as a way to hide this failure. A "typed" outcome is only legitimate when it derives from engine-visible state, at which point it is C, not D. |
| E | documented operator precondition | **REJECT as the contract; retain as an operational note** | an operator precondition ("do not submit while a render is active") cannot be verified by the caller, and §3 Q5 S2 shows the engine does not enforce mutual exclusion itself. Making it load-bearing would invert the milestone's direction (Slice 1 removed the fresh-session precondition) and would re-introduce an unverifiable assumption into the evidence chain. |
| F | another minimal architecture supported by the existing code | **ACCEPT — recommended** | Make the start call and its outcome read happen in the same game-thread request task: call the subsystem directly (as today's `AsyncTask` does, but inline) and branch the existing response on `GetActiveExecutor() == Executor`. If the implementation gate finds that the direct call is unsafe (unknown rationale for the existing deferral), keep the `AsyncTask` and have it record the outcome in the existing registry terminal state (`failed` + explicit `status_message`) so the poll returns a truthful terminal result instead of hanging to the timeout. Both variants use only existing state, existing fields, existing plumbing. |

## 5. Recommended architecture (narrow, fail-closed, nothing frozen is touched)

```text
primary    In SubmitRender, perform the executor start inside the request's own game-thread task:
             QueueSubsystem->RenderQueueWithExecutorInstance(Executor);        // as today, un-deferred
             UMoviePipelineExecutorBase* Active = QueueSubsystem->GetActiveExecutor();
             if (Active != Executor)                                            // refusal (or ambiguity)
             {
                 response.success = false;
                 response.error   = "render submission refused: a render is already active in this editor
                                     (engine: Render already in progress.)";
                 mark the registry entry terminal-failed with the same message and clear its weak pointers;
                 return false;
             }
             build the normal success response (job_id, status="submitted", ...)  // unchanged shape
fallback   If the implementation gate proves the inline call unsafe, keep the deferred start and put the same
           identity check in that deferred lambda instead: on mismatch, terminalise the entry as failed with an
           explicit message. The caller then sees submit success followed by a truthful terminal failure on the
           first poll (never a timeout, never a success).
constraints the design adds no request field, no response field, no operation, no status value, no engine
           callback, no queue mutation, no second authority, no second identity source, and no new persistence.
           It reuses: the subsystem's public ActiveExecutor accessor, the existing success/error response
           fields, the existing registry terminal flags, the existing adapter/executor error plumbing, and the
           existing verified-completion gate that guards receipts.
```

Two behaviours of the primary variant deserve to be stated as decisions rather than side effects:

- **The registry entry of a refused submission must not remain readable as "submitted".** Either it is not added
  (preferred: no entry exists if the engine never registered the job) or it is terminalised as `failed` with the
  refusal message. Leaving a permanently "submitted" entry (today's behaviour, §1.3) is what turns a refusal
  into a plausible-looking live job.
- **The submitted-job identity stays engine-minted.** The refusal path must not invent, substitute, or reuse a
  job id.

## 6. Rejected or deferred approaches, and why

```text
pre-check only (IsRendering())            insufficient alone: S1/S2 make the precondition check unreliable
                                          and it says nothing about the deferred call's outcome. Usable as an
                                          additional early-out, never as the authority.
new "rejected" status value               changes the job-state/evidence vocabulary the verifier consumes
                                          (receipt/evidence contract) -> out of bounds.
new transport operation (e.g. get_executor_state)  a new Named Pipe primitive -> explicitly frozen.
log scraping for "Render already in progress."     out-of-band channel + a new observation authority, and it
                                          fails exactly when logging changes -> rejected.
polling-based liveness inference          cannot distinguish never-started from slow (§3 Q1/L3). Rejected.
automatic retry on refusal / on lost response      creates a second engine job and violates "no automatic
                                          mutation retry". Rejected.
queue consumption or private-queue instance        does not address this failure and stays unimplemented
                                          (frozen: B and C of the queue-lifecycle review).
timeout inflation / synthetic success              explicitly forbidden as a way to hide the defect.
```

## 7. Deterministic test strategy (for the later implementation gate — NOT run here)

What the deterministic matrix must prove, in the repository's existing test style:

```text
transport source shape     the start call and the ActiveExecutor identity read are in the same task; the
                           success/error branch is driven by identity equality; the response field set is
                           unchanged (job_id, status, progress, status_message, sequence_asset_path,
                           start_frame, end_frame, end_frame_exclusive); no new registry member; no
                           queue/position/path/time/order inference; no new operation name.
response contract          success=false carries a non-empty error and no job-id-bearing evidence; the adapter
                           raises UnrealAdapterError; the plan executor produces UnrealPlanExecutionFailure
                           whose completed-operation list reflects the mutations that did land; the workflow's
                           submit() fails and wait_for_completion() is never entered (fake transport).
fail-closed                a refused submission yields no receipt and no receipt-store write; a lost-response
                           transport (disconnect/timeout) yields a structured failure, no receipt, and no
                           retry; the refusal error is distinguishable from the timeout error by type/message
                           (an explicit "this is not a timeout" assertion).
unchanged behaviour        accept path unchanged: job id bound, poll, verified terminal evidence, receipt,
                           continuity verification, exact PNG frame set; slice-1/slice-D attribution suites
                           untouched and green.
```

## 8. Live UE 5.6.1 gate requirements (for the later implementation gate — NOT run here)

```text
one editor session, no fresh-session precondition for correctness
submit A (long enough to still be rendering) -> wait until it is genuinely rendering
submit B while A renders                -> B must FAIL at submit with the typed refusal error; no polling,
                                           no receipt; A must be unaffected (its evidence, job id, receipts
                                           and artifacts unchanged)
sampling/inspection during the window   -> B's failure must be reported by the submission call, not discovered
                                           by elapsed time (assert the elapsed time is far below the timeout)
same-range / multi-submission           -> re-prove Slice D + Slice 1 properties in the same session
DLL provenance                          -> rebuilt DLL proven as in the Slice 1/Slice D gates (source blob,
                                           compile+link log line, DLL mtime/sha256, session module load, plus a
                                           behavioural discriminator)
fixtures                                -> tracked fixtures byte-identical; editors killed; pipe released
```

## 9. Recovery / fail-closed implications

```text
refusal is a FAILED operation at submit_render, not a partial success. UnrealPlanExecutionFailure already
carries: failing operation index/name, the evidence ledger so far, the completed-operation list (the
configure_render/sequencer/composite mutations that did land), and the failure context. Recovery therefore
follows the existing invariant: reassess from fresh evidence and require a NEW exact authorization; no replay
of the earlier mutations, no automatic retry, no queue cleanup.
a refused submission never produces artifacts, never produces a receipt, and never enters the evidence chain.
the existing timeout remains the last-resort backstop for genuinely slow renders (unchanged, unbounded by this
design).
nothing in this design makes a refusal visible as success, and nothing makes a slow render visible as a refusal.
```

## 10. Frozen invariants preserved (nothing in this list changes)

Named Pipe protocol and its operation/argument/response field sets; authorization model and authorization
sequence binding; exact render-job identity (engine-minted, single source); receipt architecture
(`job_id, sequence_asset_path, evidence_digest`) and the "receipt only from fresh verified terminal evidence"
gate; `UnrealShotContinuity` as the single continuity authority; inclusive Atlas frame semantics and the single
MRQ end-frame translation; shot continuity and PNG containment/frame-set verification; MRQ artifact attribution
(Slice 1 + Slice D); queue semantics (no deletion, no consumption, no private queue instance); no entity
discovery/cache; no distributed rendering; no generic workflow engine; no model-derived authority; fail-closed
recovery with no automatic mutation retry; Blender untouched.

## 11. Uncertainties the implementation gate must resolve before/while implementing

```text
U1  why the start is deferred today (AsyncTask at AtlasTransportServer.cpp:1499-1508) is undocumented in the
    repository. The primary variant removes the deferral; the gate must verify by source + a single-session live
    gate that calling RenderQueueWithExecutorInstance from inside the request's game-thread task preserves the
    observed submission timing and does not introduce re-entrancy (the response is still built after the call
    returns, and Execute() itself returns as soon as the render is scheduled).
U2  whether "ActiveExecutor == nullptr immediately after the call" can occur for a legitimate submission in the
    harness (the engine's null/empty-queue paths clear it synchronously; Atlas always allocates a job first, so
    the expectation is "not reachable"). The contract must fail closed in that case regardless, and may
    additionally cross-check the executor's terminal callbacks.
U3  how the ensure behaves in the exact harness configuration (Development editor, unattended -Cmd). The design
    must not depend on ensure side effects; the identity read alone carries the outcome.
U4  the permanent "submitted" registry entry for a refused job: the gate must decide whether the primary variant
    (which can avoid creating an entry at all, or terminalise it) changes any existing inspection test. This is
    the one place where the design changes observable registry behaviour, and it must be stated in the
    implementation record.
U5  the S2 window (§3 Q5) is engine-level and remains: mutual exclusion is best-effort on the engine side.
    The implementation record must say so rather than implying the design enforces exclusivity.
```

## 12. Findings register and verdict

```text
F1  SILENT REFUSAL -> MISLEADING TIMEOUT (the defect this gate exists to remove)
    refusal is invisible to the transport; a refused submission polls "submitted" until the 300 s default
    timeout and is reported as a slow render. Diagnosis/availability defect; never a false success.
F2  ENGINE MUTUAL EXCLUSION IS NOT SOUND DURING PIE STARTUP (new, source-anchored)
    bIsRendering becomes true only in OnPIEStartupFinished (MoviePipelinePIEExecutor.cpp:245); between
    acceptance and that point IsRendering() is false, so a concurrent submission passes the ensure and
    overwrites ActiveExecutor (no identity check in the subsystem). Consequence for this design: acceptance
    must be proven by identity, never inferred from IsRendering() being false. Out of scope to fix (queue/
    executor changes are frozen); must be documented as a residual engine-level hazard.
F3  NO CALLBACK EXISTS FOR A REFUSAL (confirming candidate B is not applicable)
    the refusal returns before Execute and before any executor delegate; the only symptom is a
    KismetExecutionMessage log line (operator-visible, not an authority).
F4  REGISTRY ENTRIES ARE NEVER PRUNED AND HAVE NO LIVENESS FIELD
    a refused submission is permanently readable as status="submitted"; the recommendation removes or
    terminalises that entry.
F5  THE DEFERRAL IS THE ROOT CAUSE OF THE UNOBSERVABILITY
    the start's outcome is discarded by construction (AsyncTask); observing it requires a scheduling decision,
    which is why this is a design gate and not a one-line fix.
F6  RECOVERY CONTEXT ALREADY EXISTS
    UnrealPlanExecutionFailure.completed already carries the mutations that landed; no new recovery machinery
    is needed for a refused submission.
```

**Verdict: `CLEAR WITH MINOR FINDINGS`.**

The refusal is exactly observable at the call site through an existing public engine accessor
(`GetActiveExecutor()`, identity equality), and exactly representable in the existing transport response and
Python result plumbing (`success`/`error` → `UnrealAdapterError` → structured
`UnrealPlanExecutionError`), so a narrow fail-closed design exists that adds no protocol field, no operation,
no status value, no engine callback, no queue mutation and no second authority. The findings are: the
recommended variant requires a scheduling decision whose safety must be verified at implementation time (U1,
F5); the registry currently leaves a permanently "submitted" entry for a refused job (F4); the engine's own
mutual-exclusion check is unsound during the PIE-startup window, so acceptance must be proven by identity and
exclusivity must not be claimed (F2, U5); and the log-only symptom of a refusal must not be promoted into an
observation channel (F3).

This document **authorizes no implementation**. The next rung is a separate implementation gate, and nothing
before queue consumption or a private-queue migration (both remain unimplemented).

---

*Evidence classes: (a) UE 5.6.1 engine sources with file:line anchors
(`MovieRenderPipelineEditor/Private/MoviePipelineQueueSubsystem.cpp`, `.../Public/MoviePipelineQueueSubsystem.h`,
`MovieRenderPipelineCore/Private/MoviePipelineQueueEngineSubsystem.cpp`, `.../Public/MoviePipelineQueueEngineSubsystem.h`,
`MovieRenderPipelineCore/Public/MoviePipelineExecutor.h`, `MovieRenderPipelineCore/Private/MoviePipelineLinearExecutor.cpp`,
`MovieRenderPipelineEditor/Private/MoviePipelinePIEExecutor.cpp`, `MovieRenderPipelineCore/Private/MoviePipelineInProcessExecutor.cpp`);
(b) this repository's transport and planning sources at `9e2c893`
(`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`,
`Public/AtlasTransportServer.h`, `planning/unreal_render_workflow.py`, `planning/unreal_plan_executor.py`,
`planning/unreal_adapter_production.py`, `planning/unreal_transport_contract.py`,
`planning/unreal_transport_named_pipe.py`); (c) previously recorded live-gate measurements (Slice 1, Slice D).
No engine was run for this review, and nothing is asserted that the sources do not show.*

---

## Addendum (September 17, 2026, later the same session) — implementation status

This review authorized no code. Its recommended architecture was then authorized as the slice
"submission acceptance / rejection identity propagation", implemented, live-proven and recorded in
`docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md` (**MRQ submission outcome propagation — COMPLETE +
LIVE-PROVEN**).

```text
implemented   the submission call and the GetActiveExecutor() identity observation in one game-thread task
              (+67/-9 in AtlasTransportServer.cpp), with rejected / accepted / ambiguous outcomes surfaced
              through the EXISTING success+error response fields (no protocol change)
proof         18 deterministic tests (8 of them fail at the previous baseline) + one clean live UE 5.6.1
              session: accepted while idle, rejected in 1.50 s while rendering, no receipt for the rejection,
              multi-job and same-range attribution still exact
unchanged     F2 (engine mutual exclusion is best-effort during PIE startup) still stands; F3 (log is not an
              authority) still stands - the live-test harness waits on the executor-finished log line only to
              establish an idle precondition and no product code reads logs
new residual  a rejected submission leaves its allocated MRQ job in the queue (queue mutation is frozen), so a
              later accepted submission renders it; the orphan artifacts are discarded by Slice 1 and no receipt
              exists for them
still open    Slice 3 queue consumption, and the private queue instance - the next review evaluates whether
              queue isolation is worth its lifecycle surface
```

Candidates D (bounded/typed timeout) and E (operator precondition) remain rejected, and the prohibited actions
listed above (no timeout inflation, no synthetic success, no automatic retry, no queue mutation) remain binding.

