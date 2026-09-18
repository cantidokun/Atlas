# Unreal Agent — MRQ Pass-Scoped Failure Attribution Design Review

**Date:** September 17, 2026
**Mode:** READ-ONLY ARCHITECTURE / DESIGN GATE — source audit + previously recorded measurements. No code, no
tests, no editor run, no live gate, no workflow/action-runner execution.
**Published baseline:** `reconcile/unreal-autonomy-origin-20c6d10` @
`1daa574` (MRQ artifact attribution Slice 1/2 + Slice D, submission outcome propagation, and the queue-isolation
review are all published; the observed base commit for the code citations below is `4b61d8f`, whose transport
sources are unchanged since).
**Question:** can a healthy Atlas render be reported as failed because a *different* queued MRQ job fails?
**Verdict:** **CLEAR WITH MINOR FINDINGS** (§8). Nothing is authorized by this document.

```text
Explicitly NOT done here: no production code, no tests, no engine run, no queue isolation, no queue
consumption/deletion, no protocol change, no new authority, no retry, no registry pruning, no receipt,
identity, continuity or attribution change, no Blender change. Nothing committed.
```

---

## 1. Exact mechanics (source-anchored)

Two different callbacks with two different scopes are both written into the same registry entry, in this order.

### 1.1 Job-scoped truth: `OnIndividualJobWorkFinished` (Atlas, `AtlasTransportServer.cpp:1404-1468`)

```cpp
            UMoviePipelineExecutorJob* RegisteredJob=(*Found)->Job.Get();
            UMoviePipelineExecutorJob* PayloadJob=InOutputData.Job.Get();          // :1431-1432
            if(!RegisteredJob || PayloadJob!=RegisteredJob) { ...discard... return; } // :1434-1442
            (*Found)->Status=TEXT("finished");          // :1444   NOTE: set even when bSuccess is false
            (*Found)->StatusMessage=TEXT("Render job finished");
            (*Found)->Progress=1.0;
            (*Found)->bFinished=true;                   // :1447
            (*Found)->bSuccess=InOutputData.bSuccess;   // :1448   OUR job's own pipeline outcome
            (*Found)->bFailed=!InOutputData.bSuccess;   // :1449
            if(InOutputData.bSuccess && InOutputData.ShotData.Num()>0) { ...AddUnique(FilePath)... }  // :1451-1467
```

This payload is per job and identity-guarded (Slice 1): it carries **our** job's outcome and **our** artifacts,
and it is emitted for every job the executor actually processed, including a failing one
(`MoviePipelinePIEExecutor::DelayedFinishNotification` -> `OnIndividualJobFinishedImpl` ->
`OnIndividualJobWorkFinishedDelegate.Broadcast(InOutputData)`, `MoviePipelinePIEExecutor.cpp:451-476`).

### 1.2 Pass-scoped signal: `OnExecutorFinished` (engine broadcast, Atlas, `AtlasTransportServer.cpp:1470-1491`)

```cpp
virtual void OnExecutorFinishedImpl()                                        // MoviePipelineExecutor.h:216-220
{
    OnExecutorFinishedDelegateNative.Broadcast(this, !bAnyJobHadFatalError);  // PASS-scoped aggregate
    OnExecutorFinishedDelegate.Broadcast(this, !bAnyJobHadFatalError);
}
virtual void OnExecutorErroredImpl(UMoviePipeline* ErroredPipeline, bool bFatal, FText ErrorReason)  // :224-234
{
    if (bFatal) { bAnyJobHadFatalError = true; }
    OnExecutorFinishedDelegateNative.Broadcast(this, !bAnyJobHadFatalError);  // also broadcasts "finished"
    OnExecutorFinishedDelegate.Broadcast(this, !bAnyJobHadFatalError);
}
```

Atlas consumes that boolean as if it were our job's verdict:

```cpp
    Executor->OnExecutorFinished().AddLambda(
        [JobId](UMoviePipelineExecutorBase* InExecutor,bool bSuccess)             // :1470-1471
        {
            ... if(Found && Found->IsValid()) {
                (*Found)->bFinished=true;                                        // :1480
                (*Found)->bSuccess=bSuccess;      // <-- CLOBBERS the job-scoped verdict  :1481
                (*Found)->bFailed=!bSuccess;      // <--                                :1482
                (*Found)->Progress=1.0;           //                                    :1483
                (*Found)->Status= bSuccess ? TEXT("finished") : TEXT("failed");   // :1484-1485
                (*Found)->StatusMessage= bSuccess
                    ? TEXT("Render executor finished successfully")
                    : TEXT("Render executor finished with failure");              // :1486-1489
            } });
```

### 1.3 The pass continues after a failing job, so both verdicts really do coexist

```text
job A fails (fatal)  -> UMoviePipelinePIEExecutor::OnPIEMoviePipelineFinished -> OnPipelineErrored(..., true, ...)
                        (MoviePipelinePIEExecutor.cpp:367-375; MoviePipelineLinearExecutor.cpp:93-96 ->
                         OnExecutorErroredImpl sets bAnyJobHadFatalError, broadcasts "finished")
                     -> RequestEndPlayMap -> OnPIEEnded -> timer -> DelayedFinishNotification (:451-458)
                        -> OnIndividualJobFinishedImpl (per-job payload for A, bSuccess=false)
                        -> OnIndividualPipelineFinished(nullptr)
                        -> bNoMoreJobs = CurrentPipelineIndex >= GetJobs().Num()-1 (LinearExecutor.cpp:81)
                           false  =>  StartPipelineByIndex(CurrentPipelineIndex+1)   // pass CONTINUES
job B (Atlas) renders -> its own per-job payload fires with ITS outcome, artifacts recorded
                        => at this instant the registry holds a healthy job-scoped verdict for B
executor finished    -> bAnyJobHadFatalError is still true  =>  Atlas pass lambda CLOBBERS B's verdict
```

Only cancellation (`CancelAllJobs_Implementation`, `MoviePipelineLinearExecutor.cpp:146-150`) stops the pass; a
fatal error does not.

### 1.4 The clobbered state is denied at two independent gates

```text
unreal_render_workflow.py:201-204   if state.get("failed") is True: raise UnrealRenderWorkflowError(
                                        "render job failed: status=...")       <-- checked BEFORE "finished"
unreal_render_workflow.py:207-231   elif finished -> verify_render_job_completion(require_artifacts=True)
                                        -> continuity -> receipt -> persist
unreal_render_job_verifier.py       verify_render_job_completion itself raises on state["failed"] is True
                                        ("render job reports failed=True: status=...") before any success check
```

So a healthy Atlas job is denied a receipt twice over, even though in the same `inspect_render_job` record it
carries `success=false, finished=true, failed=true, status="failed"` **together with its own complete, already
recorded `output_files`** — a state combination no fixture in this repository exercises (the existing failure
fixture is `finished=False, failed=True, output_files=[]`, `tests/test_unreal_render_workflow.py:254-262`), which
is part of why the defect has stayed invisible.

## 2. The nine audit questions

### Q1. `OnExecutorFinished` semantics and ownership

It is a **queue-pass aggregate**, not a job event: the delegate signature is
`(UMoviePipelineExecutorBase*, bool)` and the boolean is `!bAnyJobHadFatalError` over the whole pass
(`MoviePipelineExecutor.h:216-234`). It is broadcast twice per pass in the error case (once from
`OnExecutorErroredImpl`, once from the terminal `OnExecutorFinishedImpl`). It is owned by the executor instance,
which is exactly what Atlas's registry stores as a `TWeakObjectPtr` (`Public/AtlasTransportServer.h:53-54`).
Atlas subscribed to it to learn "the render is over", which is a legitimate use; the defect is only that it
overwrites fields it does not own.

### Q2. Relationship between per-job completion and queue-level completion

```text
per job      OnIndividualJobWorkFinished(FMoviePipelineOutputData) -> identity-guarded, job-scoped
per pass     OnExecutorFinished(executor, !bAnyJobHadFatalError)   -> unguarded by construction (no job in scope)
ordering     one pass-level signal per pass, always AFTER every job-level signal of that pass
consequence  the pass signal is strictly the weaker/later information and must never overwrite the stronger
             job-scoped information that already exists for our job
```

### Q3. Can Atlas distinguish the three cases today?

**No, not with the current code** - the pass write destroys the distinction. But the information needed is
present in the registry at the moment the pass signal fires:

```text
case 1  THIS Atlas job failed          job-scoped payload fired with bSuccess=false => our entry already says
                                       failed, with a job-specific StatusMessage. The pass signal then agrees;
                                       no information is lost today.
case 2  another queue job failed       our payload fired with bSuccess=true and artifacts recorded, then the pass
                                       signal overwrites everything => WRONG (the defect under review).
case 3  the pass failed but our own     identical to case 2 from our entry's point of view; the engine gives Atlas
        evidence is healthy            no per-mate error detail (the broadcast carries only one bool), so a
                                       precise "which mate failed" distinction is NOT achievable without new engine
                                       hooks - out of scope and unnecessary.
achievable contract                    a TWO-way distinction: "our job has its own verdict" vs "our job has none".
                                       Case 2 and case 3 are correct by the same rule; case 1 is unaffected.
```

### Q4. Existing `InspectRenderJob` evidence

`AtlasTransportServer.cpp:1536-1610` already exposes everything the correction needs: `job_id`, `status`,
`status_message`, `progress`, `success`, `finished`, `failed`, `sequence_asset_path`, `output_directory`,
`output_format`, `start_frame`, `end_frame`, `end_frame_exclusive`, `output_files`. The job-scoped fields
(`finished`/`success`/`failed`/`output_files`) are precisely the ones the pass callback clobbers, so the fix
requires no new field and no new operation.

### Q5. Receipt issuance requirements

A receipt requires: fresh evidence whose `job_id` equals the authorized identity, `finished=true`,
`success=true`, the exact authorized PNG frame set inside the authorized directory, plus continuity completeness
(`unreal_render_workflow.py:207-231` -> `verify_render_job_completion(require_artifacts=True)` ->
`verify_shot_continuity_completeness` -> `UnrealRenderReceipt.issue` -> store). A pass-scoped failure makes
`failed=true`, which is denied before any of that is evaluated. The receipt contract itself does not need to
change; it is simply never reached.

### Q6. Recovery behaviour

Unchanged and unaffected: the failure surfaces as `UnrealRenderWorkflowError` and, in the production path, as
`UnrealProductionWorkflowError` from `submit`/`wait_for_completion`; there is no automatic retry, recovery
requires fresh evidence and a new exact authorization. The cost of the defect is that the operator must
re-authorize and re-render work that already succeeded - a real availability loss, not a correctness hole.

### Q7. Does fresh job-scoped evidence already provide a safe correction?

**Yes.** The evidence needed is already (a) job-scoped, (b) identity-guarded, (c) recorded before the pass signal
fires, and (d) re-read freshly on every poll (`wait_for_completion` -> `inspect_job` per iteration). Removing the
clobber is therefore sufficient: on the next poll our job reports `finished=true, success=true, failed=false`
with its own artifacts, and the existing verification path issues the receipt. No new evidence, no re-render, no
new authority.

### Q8. Monitoring/reporting only, or does it affect the terminal execution contract?

It **does** affect the terminal contract, in the fail-closed direction:

```text
not affected  no false receipt, no mis-attributed artifact, no false success, no weakened identity or continuity
affected      a healthy, evidence-complete render is denied its receipt, and under "no automatic mutation retry"
              the only way to obtain it is a NEW authorization and a NEW render (wasted engine work and operator
              time)
classification availability + terminal-contract precision (fail-closed false negative), NOT a correctness or
              false-accept risk
```

### Q9. Can the solution remain inside the existing transport, without a new protocol operation or authority?

**Yes.** The correction is confined to the existing `OnExecutorFinished` lambda: apply the pass verdict only when
our registry entry has no job-scoped terminal verdict of its own. It uses only registry fields that already
exist, the existing job-scoped callback, and the existing response/evidence surface. No new field, no new
operation, no protocol change, no second authority, no queue interaction, no retry.

```text
recommended shape (design only, NOT authorized)
    on pass-finished, under the registry lock:
      if the entry has no job-scoped terminal verdict (bFinished == false):
          apply the pass verdict as today (our job was never processed: the pass died before it ran)  [fail closed]
      else:
          leave Status / StatusMessage / Progress / bFinished / bSuccess / bFailed untouched  [do not clobber]
          record the pass outcome as a transport log line only (operator-visible, not evidence)
why the second branch cannot mask our OWN failure: our own job's failure always arrives through its own job-scoped
payload (bSuccess=false) BEFORE the pass signal, so the entry is already failed and stays failed.
why the first branch keeps fail-closed behaviour: an executor that ends without ever processing our job leaves the
entry non-terminal; the pass verdict then still marks it failed, so no healthy claim can be fabricated.
```

Explicitly rejected alternatives:

```text
reading the deprecated per-job delegate OnIndividualJobFinished(Job, !IsAnyJobErrored())
    it carries the SAME pass-scoped aggregate (MoviePipelinePIEExecutor.cpp:470-471), so it would reintroduce
    the defect; Atlas correctly does not subscribe to it.
inferring from artifacts/timing/queue position
    forbidden by the standing rules, and unnecessary: the job-scoped verdict is explicit.
adding a per-mate error field / a new operation / a new status value
    a protocol change that this gate does not show to be unavoidable.
serialising "our job finished" into the receipt or evidence chain
    changes nothing about the defect and would touch frozen contracts.
```

## 3. Classification against the standing cost classes

```text
correctness      no risk (the defect is a false NEGATIVE; nothing false is ever accepted or receipted)
availability     YES - a valid render can be lost and must be re-rendered under a new authorization
efficiency       indirect - the lost render is pure waste; amplified because every retained queue job is
                 re-rendered on the retry (see the queue-isolation review)
visibility       mild - the reported message ("Render executor finished with failure") names the pass, not the
                 failing job, so an operator cannot tell whose failure it was
hygiene          none
```

## 4. Why this is the right surface to fix (and why not the alternatives)

```text
fix the transport's pass write            smallest possible change; makes the registry entry reflect the job that
                                          Atlas actually submitted; keeps receipts/identity/continuity frozen
relax the workflow's failed-check order    would weaken a defence-in-depth gate for a real job-scoped failure; NOT
                                          acceptable
relax the verifier's failed=True rule      same objection, and it is the verifier that protects the receipt
queue isolation (previous review)          removes the CAUSE (no foreign jobs in the pass) but was explicitly
                                          deferred behind triggers; this fix removes the SYMPTOM regardless of
                                          queue contents, and the two are compatible
registry pruning / consumption             unrelated to attribution
```

## 5. Evidence plan for a future implementation gate (NOT authorized, NOT written)

```text
deterministic
  - a healthy job-scoped verdict followed by a failed pass verdict must NOT produce a failed entry
    (the exact clobber case; no existing test pins it today)
  - a failed job-scoped verdict followed by an agreeing pass verdict must stay failed
  - a pass verdict with no job-scoped verdict must still fail closed (our job never ran)
  - the response field set, operation set, status vocabulary, receipt fields and evidence contract are unchanged
    (source-shape assertions, in the style of the Slice E contract module)
live UE 5.6.1
  - a pass containing a deliberately failing QUEUE-MATE and a healthy Atlas job: the Atlas job must still obtain
    its receipt with exact identity, exact authorized frame set and coherent continuity, while the engine log
    shows the pass failing. OPEN PRECONDITION: arranging a deterministically failing queue-mate without queue
    mutation, without a new transport operation and without damaging tracked fixtures. Candidate mechanisms to be
    settled before implementation: (a) an operator-side broken job added in the editor MRQ UI before the gate
    (outside the transport's authority, documented as a gate precondition - closest to the real-world trigger);
    (b) a retained job whose configured output directory is made invalid/unwritable before the next submission
    (requires the existing configure path to accept that value); (c) a retained job produced by an interrupted
    render. The gate must also re-prove: our OWN failing job still fails, a rejected submission still fails
    truthfully, and Slice 1/Slice D attribution behaviour is unchanged.
```

## 6. Frozen invariants preserved (nothing in this list changes)

Named Pipe protocol and its operation/argument/response field sets; authorization model and sequence binding;
engine-minted exact render-job identity; receipt architecture and the "fresh verified terminal evidence" gate;
`UnrealShotContinuity` as the single continuity authority; inclusive Atlas frame semantics and the single MRQ
end-frame translation; shot continuity and PNG containment/frame-set verification; MRQ artifact attribution
(Slice 1 + Slice D); submission outcome propagation (Slice E); shared queue semantics (no isolation, no
consumption, no deletion); no automatic mutation retry; no registry pruning; no entity discovery/cache; no
distributed rendering; no generic workflow engine; no model-derived authority; Blender untouched.

## 7. Findings register

```text
F1  The pass-scoped boolean `!bAnyJobHadFatalError` is written into job-scoped fields
    (AtlasTransportServer.cpp:1480-1489), overwriting a healthy verdict that our own job already produced
    (AtlasTransportServer.cpp:1444-1449). The job-scoped truth exists at the moment of the clobber.
F2  The resulting state (finished=true, failed=true, success=false, with complete output_files) is denied at two
    layers (workflow failed-check before finished-check, and the verifier's failed=True rule) and is pinned by no
    fixture - the existing failure fixture is finished=false/failed=true/output_files=[].
F3  Classification: availability + terminal-contract precision. Never a false accept, never a false receipt.
F4  The precise identity of the failing queue-mate is NOT observable through the existing engine broadcasts
    (one boolean per pass); the achievable contract is two-way ("our job has its own verdict" vs "it does not"),
    which is sufficient for the correction.
F5  The fix is confined to the existing transport and needs no protocol, field, operation or authority change.
F6  CLOSED ON MEASURED GROUNDS (B1 + B2), receipt impact UNPROVEN — see §8.8-§8.10. Both retained-mate
    mechanisms produce a GENUINE fatal failure but abort the pass at that job, so neither can reach the
    hypothesised healthy-job-then-pass-failure clobber; the earlier source claim that the pass advances after
    such a fatal class is superseded by engine observation. Mechanisms A and C remain rejected as gate
    mechanisms. What survives is a STATE-FIDELITY invariant only: a job-scoped terminal verdict must not be
    overwritten by a weaker, later pass-scoped aggregate. No receipt-correctness claim is made.
F7  Ordering safety: our own job's failure always reaches its entry through its own payload before the pass
    signal, so "trust the job-scoped verdict" cannot mask an Atlas job's real failure.
F8  MEASURED CORRECTION (§8.8): B1 fails the mate genuinely but aborts the pass before any later queued job
    executes, so it cannot reach the hypothesised healthy-job-then-pass-failure clobber; the pass-continues
    reading is superseded by engine observation.
F9  Separate follow-up (not this slice): `inspect_render_job` rejects failed jobs through the product path, so a
    failed job cannot be read at all through the authorised surface - only the error text is visible.
```

---

## 8. F6 closure — deterministic live-gate test design (read-only resolution)

F6 asked how a live gate can produce, deterministically and under the frozen constraints, a single MRQ executor
pass in which an Atlas job succeeds while a queue-mate genuinely fails. This section closes it as a **test-design
question**: it inventories what can genuinely fail a job in UE 5.6.1, evaluates the three candidate mechanisms
against the eight required criteria, selects the smallest repeatable setup, and specifies the gate. No code, no
queue mutation, no new operation and no engine run is involved in this resolution.

### 8.1 The target scenario as observable assertions

```text
required  one editor session, one MRQ executor pass containing BOTH:
            - the Atlas job under test, whose own identity-guarded per-job payload reports success
            - a queue-mate whose render genuinely fails (engine-reported fatal), so the pass-level broadcast
              reports failure
          on the CURRENT (unfixed) build  -> the Atlas entry is reported failed ("clobber") and no receipt issues
          on the CORRECTED build          -> the Atlas entry keeps its own verdict and its receipt issues with the
                                             exact job id, the exact authorized frame set and coherent continuity
must not  modify production code to create the scenario, mutate the MRQ queue, add a transport operation, add a
          permanent fixture, change the Named Pipe protocol, weaken verification, synthesise success/failure, or
          retry automatically
```

### 8.2 What can genuinely fail a job in UE 5.6.1 (source-anchored fatal inventory)

A job's outcome reaches Atlas as `FMoviePipelineOutputData.bSuccess`, which is literally `!bFatalError`
(`MoviePipeline.cpp:1101,1627,1639`), and `bFatalError` is set in only two places - both
`RequestShutdown(true)` / `Shutdown(true)`. So a job fails only when something calls shutdown **as an error**:

```text
Initialize-time fatal (deterministic, instant, config/world driven)
  MoviePipeline.cpp:116-120  null job
  MoviePipeline.cpp:122-126  null configuration     <- unreachable for an Atlas job (SetConfiguration always runs)
  MoviePipeline.cpp:151-155  pipeline reused
  MoviePipeline.cpp:158-162  no world in outer
  MoviePipeline.cpp:166-171  the job's Sequence asset failed to load
Render-time fatal (deterministic, config driven)
  MoviePipelineRendering.cpp:113-124  backbuffer resolution exceeds the engine's max 2D texture dimension
  MoviePipelineRendering.cpp:125-130  resolution <= 0 in either dimension
  MoviePipelineDeferredPasses.cpp:226,1253  pass-level errors (deferred pass setup)
Export-time fatal (deterministic, filesystem driven)
  MoviePipelineTiming.cpp:66-71  an image write returned false ("Error exporting frame, canceling movie export");
                                 the future is TFuture<bool> (MoviePipelineRendering.cpp:549-552), so this is the
                                 write's own success value, not a validity check
Interrupt fatal (deterministic only if something can interrupt)
  MoviePipelinePIEExecutor.cpp:414-422  PIE ended while the pipeline was still active -> Shutdown(true)
  MoviePipelineLinearExecutor.cpp:137-152  CancelCurrentJob / CancelAllJobs -> Shutdown(true)  (cancels are fatal by design)
pass-level, ends the pass instead of failing a job (NOT usable)
  MoviePipelineLinearExecutor.cpp:20-31  null queue / empty queue -> OnExecutorFinishedImpl
  MoviePipelinePIEExecutor.cpp:238-241  no PIE UWorld after startup -> OnExecutorFinishedImpl
  MoviePipelinePIEExecutor.cpp:252-258  pipeline class load failure -> OnExecutorFinishedImpl
```

Two consequences that shape the gate:

```text
(a) Atlas's own configure_render validation closes the easiest door: AtlasTransportServer.cpp:1105 rejects
    `Width<=0 || Height<=0 || StartFrame>EndFrame`, and planning/unreal_render_contract.py enforces the same
    positive-resolution / ordered-range rules. A job therefore cannot be made to fail by a zero resolution or an
    inverted range. There is, however, NO upper bound on resolution in either layer.
(b) A retained job always keeps its OWN configuration snapshot (Configuration->CopyFrom at job build time,
    AtlasTransportServer.cpp:1261), so a later submission with a valid config cannot repair an earlier broken one,
    and a broken retained job fails again in every later pass.
```

### 8.3 The three candidate mechanisms against the eight required criteria

```text
criterion                                                              A   B1  B2  C
1  can it fail reliably on UE 5.6.1                                    ~   Y   Y~  Y
2  can Atlas's job remain healthy                                      Y   Y   Y   Y
3  does it occur in the same executor pass                             Y   Y   Y   Y
4  does it avoid mutating Atlas fixtures                               Y   Y   Y   Y
5  reproducible without fragile editor timing                           N   Y   Y   N
6  can the identity guards prove which result belongs to Atlas          Y   Y   Y   Y
7  can the old baseline be shown to exhibit the clobber                 Y   Y   Y   Y
8  can the corrected implementation be shown to preserve the verdict    Y   Y   Y   Y
   (Y = yes from the sources; Y~ = yes contingent on one live confirmation; ~ = only as reliable as a human
    action; N = no automatable path exists under the frozen constraints)
```

```text
A  an operator-created non-Atlas MRQ job that genuinely fails
   Faithful to the real-world trigger; satisfies criteria 2,3,4,6,7,8. It fails criterion 5: this repository's
   live gates run headless (UnrealEditor-Cmd, no UI), and creating such a job requires either an interactive
   operator or a queue mutation / new transport operation (both frozen).
   VERDICT: rejected as the gate mechanism; retained as the production scenario the defect describes, and usable
   as a documented manual precondition only if the automated mechanisms below fail to confirm.

B1 an intentionally invalid RETAINED Atlas job: output resolution above the engine's maximum
   Submit once with a resolution far above any GPU's max 2D texture dimension: the engine's own check
   (MoviePipelineRendering.cpp:113-124 -> Shutdown(true)) genuinely rejects it at the first frame, so the failure
   is real engine behaviour and nothing is synthesised. Atlas allows any positive value, so no contract or
   validation change is needed. The job is retained in the queue by design (no consumption/deletion), and a
   second, valid submission in the same session renders that mate first (it fails again, deterministically and
   before doing render work) and then Atlas's own job (which succeeds). Criteria 1-8 all hold, and criterion 1
   does not depend on the specific GPU because the value is chosen far above any plausible maximum.
   VERDICT: RECOMMENDED - the smallest deterministic repeatable setup.

B2 an intentionally invalid RETAINED Atlas job: an output path the image write cannot satisfy
   Configure the retained job's output_directory at a path whose write fails (for example a gate-created FILE
   where the directory is expected, inside the disposable Saved/ area). The export-time fatal fires when the image
   write returns false (MoviePipelineTiming.cpp:66-71 with the TFuture<bool> produced at
   MoviePipelineRendering.cpp:549-552). Criteria 2-8 hold; criterion 1 is contingent on that plumbing behaving as
   read (the future must resolve false for an unsatisfiable path) - source-consistent but unconfirmed without an
   engine run.
   VERDICT: FALLBACK - use if B1's fatality does not confirm live, or as B1's cross-check.

C  a deliberately interrupted queue-mate render
   The fatal path exists (PIE ended while the pipeline was active: MoviePipelinePIEExecutor.cpp:414-422; cancels:
   MoviePipelineLinearExecutor.cpp:137-152) and criteria 2,3,4,6,7,8 hold. It fails criterion 5 twice over:
   nothing in the frozen protocol can interrupt a render from outside (there is no cancel operation and the UI is
   unavailable in headless gates), and any external interruption is inherently timing-dependent.
   VERDICT: rejected as the gate mechanism.
```

Note on fidelity: B1 and B2 make the mate an Atlas-allocated job rather than a foreign operator job - a job this
repository created and deliberately broke. That does not weaken the test: the clobber depends only on the
pass-level aggregate originating from a job that is NOT the job under test, which is exactly what the real defect
requires, and Slice 1's identity guard makes the ownership split explicit and observable in the engine log.

### 8.4 The gate specification (for the later implementation gate; nothing authorised)

```text
session      ONE fresh headless UE 5.6.1 editor; no UI; no queue file; no new permanent fixture
S1 (setup,   configure_render: resolution far above the engine max (e.g. 200000x200000), disposable output dir D1,
   EXPECTED  short frame range; then submit and EXPECT the submission to fail (the mate is broken on purpose).
   TO FAIL)  Assert the failure is engine-reported and job-scoped to S1 (S1's own entry terminal-failed) and that
             the engine logged its own resolution error. No retry. The mate is not cleaned up: it stays in the
             queue by design.
S2 (the      after the engine has released the executor, configure_render: the normal valid config (e.g. 320x180,
   MEASURE-  1-2, disposable output dir D2); submit in the SAME session. The pass now renders the retained mate
   MENT)     first (fails) and S2's own job second (succeeds) - one pass, one editor session.
             current build    -> S2's entry is reported failed and no receipt is produced        (the clobber)
             corrected build  -> S2's receipt issues with the exact job id, the exact authorised frame set inside
                                 D2, and coherent continuity                                     (verdict preserved)
assertions   - the pass-level failure genuinely happened (engine log: the mate's fatal error + the executor
               finishing with failure)
             - exactly one payload belongs to S2: the "ATLAS MRQ ATTRIBUTION: discarded per-job output data for
               job <id>" line proves Slice 1 attributed the mate's payload to the mate, not to S2
             - the mate's artifacts exist only in D1 and never appear in S2's evidence or receipt
             - S1's entry stays failed on BOTH builds (its own verdict, unaffected by the correction)
             - tracked fixtures restored byte-identical; D1/D2 removed; editor killed; pipe released; DLL
               provenance proven as in the previous slices
sequencing   STEP 1 runs on the UNMODIFIED build, so the mechanism and the clobber are confirmed BEFORE any
   advantage production code is written - no implementation is needed to validate F6's mechanism. If STEP 1 cannot
             produce the clobber with B1, the gate falls back to B2, then to B1+B2 together; only then is
             implementation worth authorising.
```

### 8.5 What remains open after this closure

```text
O1  the two fatality claims are read from the sources and are the gate's own first deliverable: STEP 1 of §8.4
    confirms them on the unmodified build before any code change. F6 is closed as a test design; its mechanism
    confirmation is deliberately part of the implementation gate's run, not of this read-only review.
O2  the mate is an Atlas-allocated job (B1/B2). A foreign operator job (mechanism A) remains the only way to
    exercise the "non-Atlas" wording literally, and remains a documented manual contingency.
O3  B1 depends on GetMax2DTextureDimension() being below the chosen value on the gate machine; the value is chosen
    far above any plausible maximum, and the engine's own error message is asserted as evidence.
```

### 8.6 Frozen-constraint checklist for this test design

```text
no production code modification      the scenario is created entirely through the existing configure_render and
                                     submit_render operations
no MRQ queue mutation                the mate is the job Atlas itself allocated and deliberately configured; it is
                                     left in place, never deleted, consumed, disabled or reordered
no new transport operation           only configure_render + submit_render + inspect_render_job are used
no permanent fixture                 only disposable Saved/ output directories; the render config asset is restored
                                     by the existing finally arm and the tracked fixtures must end byte-identical
no protocol change                   nothing on the wire changes
no weakened verification             the receipt path, frame-set and continuity verification are untouched
no synthetic success/failure         the mate fails because the ENGINE rejects its configuration; the gate never
                                     writes a failed state itself
no automatic retry                   S1's failure is asserted, not retried; S2 is a separate authorised submission
```

### 8.7 Effect on the findings register

```text
F6  CLOSED AS A TEST DESIGN (this section): a deterministic, repeatable, headless live-gate scenario exists
    (B1 recommended, B2 fallback) for a single pass containing a genuinely failing queue-mate and a healthy Atlas
    job, with A and C rejected as gate mechanisms and their reasons recorded. Two live confirmations (O1) belong to
    the implementation gate's first step and require no code change.
```

**Verdict: `CLEAR WITH MINOR FINDINGS`.**

The defect is real, reproducible from the sources without running the engine, and confined to one existing
callback: the pass-scoped `!bAnyJobHadFatalError` aggregate is written into job-scoped fields and clobbers the
healthy verdict our own job already recorded.

**Closure note (measured, §8.8-§8.10):** the two candidate same-pass mechanisms (B1 frame-production rejection,
B2 export-time write failure) were both measured on the unmodified published baseline. Each produces a genuine
fatal failure for the retained mate, but each also aborts the pass before any later queued job executes, so
neither reaches the clobber of a healthy verdict. The correction therefore stands only as a **state-fidelity
invariant**; its receipt impact is **UNPROVEN** and no receipt-correctness claim is made. Whether to implement
it, and its priority, is a decision for the next gate. It is an availability/terminal-contract precision defect in the
fail-closed direction - never a false accept - and it is correctable entirely inside the existing transport using
existing registry fields, with no protocol operation, no new authority, no queue interaction and no change to
receipts, identity, continuity or attribution. The findings are F1-F7 above, of which F6 (how the live gate
arranges a deterministically failing queue-mate under the frozen constraints) must be settled before any
implementation is authorized. This document **authorizes no implementation**.

### 8.8 Amendment (measured, same session) — B1 does NOT produce the target ordering

The first baseline run of the B1 gate (unmodified published code, headless UE 5.6.1) measured the mechanism, and
the result contradicts the design's hypothesis in one decisive respect. Recorded here as an explicit correction.

```text
CONFIRMED  B1 genuinely fails the retained mate in UE 5.6.1, by the engine's own checks:
             "Resolution 200000x200000 exceeds maximum allowed by GPU (16384x16384)"  (4 occurrences)
           the mate's MRQ job terminalised as failed with no artifacts and no receipt
           Atlas's configure_render accepted the value (Atlas validates only width>0/height>0), so the
           scenario was created through existing operations only

CONTRADICTED  the pass does NOT continue past the failing mate, so the subject never executes in that pass:
             pass 1  "starting 1 jobs" + "starting job [1/1]"          -> mate fails; pass never completes
             pass 2  "starting 2 jobs" + "starting job [1/2]"          -> stops at index 0 (the mate);
                                                                        no "starting job [2/2]"
             "MoviePipelineLinearExecutorBase finished"  = 0           (no pass ever finished in the session)
           a submission accepted after the mate's failure (the editor was NOT stuck: ActiveExecutor had been
           released, so the identity-based acceptance path worked) had its own job - index 1 of a two-job pass
           whose index 0 is the retained failing mate - reported failed within ~2 s with ZERO output files:
           it never rendered

MECHANISM  the terminal signal that reaches Atlas for this fatal class is the PASS-LEVEL error broadcast
           (OnExecutorErroredImpl broadcasts the finished delegate, MoviePipelineExecutor.h:224-234), not an
           executor finish. For an entry with no job-scoped verdict of its own this is exactly the fail-closed
           fallback: a job that never ran is reported failed.

SUPERSEDED  the source interpretation recorded earlier in this section (§8.2/§8.4: "the pass continues after a
           fatal job error via OnIndividualPipelineFinished -> StartPipelineByIndex(+1)") is superseded by the
           direct engine observation above. That reading holds for the normal per-job finish path; it does NOT
           hold when a job's pipeline calls Shutdown(true) during frame production, which aborts the pass at
           that job without a next-job start and without an executor finish.

CONSEQUENCE  B1 cannot produce the hypothesised ordering (healthy Atlas job first, pass-level failure after its
           own terminal callback). The baseline clobber proof was therefore NOT established with B1, and no
           implementation was authorised on that basis.

UNCHANGED   the proposed correction stays valid as a STATE-FIDELITY rule (preserve a job-scoped terminal verdict;
           the fallback must still represent failure when no stronger verdict exists). The measured fallback
           behaviour above is exactly what that rule prescribes.

UNPROVEN    whether a pass-level failure can land AFTER a healthy job-scoped verdict in the same pass - i.e.
           whether the receipt impact of the clobber is reachable at all. This is the open question the B2
           experiment (§8.9) exists to answer; nothing is implemented while it is open.
```

Separate follow-up finding, recorded here and deliberately **not** part of this slice:

```text
F9  `inspect_render_job` cannot read a FAILED job through the product path. The executor maps that operation
    onto `verify_render_job_completion`, which raises "render job reports failed=True", so a failed (or
    clobbered) entry is not merely denied a receipt - it is unreadable through the authorised surface, and the
    only caller-visible diagnosis is the error text. Consequence for the gate: the registry state behind a
    failure has to be read at the transport layer (`adapter.inspect`) for evidence capture; that is diagnostics
    only and no product decision changes. Deserves its own design gate (diagnosis quality for failed jobs),
    separate from the pass-failure attribution correction.
```

### 8.9 B2 experiment — measured result (read-only, production code untouched)

Mechanism B2 as originally listed: a retained Atlas job whose output condition makes the image write fail
(`MoviePipelineTiming.cpp:66-71` -> `RequestShutdown(true)`, export-time fatal). The unsatisfiable condition was
created by occupying the mate's configured output-directory path with a FILE inside the untracked `Saved/` area
(no tracked fixture touched, blocker removed afterwards), and the experiment ran on the unmodified published
baseline.

```text
requirement 1  does the retained mate genuinely fail? ............ YES
   engine: "Error: Error exporting frame, canceling movie export."  (LogMovieRenderPipeline +
   MoviePipelinePIEExecutor) - the export-time fatal, exactly the class B2 targets
   mate job: failed=true, finished=true, success=false, output_files=0, no receipt
   status_message = "Render executor finished with failure"  -> the PASS-LEVEL write, not a job-scoped one

requirement 2  does the subsequent Atlas job execute? ........... NO
   submitted after the mate failed, and ACCEPTED (a job id was issued, so ActiveExecutor had been released
   and the editor stayed usable; its production phase succeeded on the first harness attempt)
   samples: submitted, submitted, submitted, failed   (t+0.00 s .. t+1.17 s)
   "starting job [2/..." lines: 0 -> 0   -> its job NEVER STARTED; 0 artifacts produced

requirement 3  pass-level failure AFTER that job's own verdict? . NO
   the subject's terminal message is the pass-level "...finished with failure" and it holds NO job-scoped
   verdict of its own (0 artifacts) -> the FALLBACK branch: fail-closed reporting of a job that never ran

requirement 4  is the clobber state reached? ................... NO
   mate_failed_at_export=true; subject_job_started_in_a_shared_pass=false;
   subject_produced_artifacts=false; clobber_state_reached=false; subject_never_rendered=true;
   pass_finished_at_all=false
   "MoviePipelineLinearExecutorBase finished" = 0 for the whole experiment
   export-time errors 2 -> 4 across the two passes: the retained mate re-rendered in the subject's pass and
   failed again, consistently with the queue-accumulation measurements of the isolation review
```

### 8.10 F6 closure on the measured basis (B1 + B2)

```text
B1  frame-production rejection (resolution above the engine maximum)
      genuine fatal; the pass aborts before any later queued job starts (measured, §8.8)
B2  export-time write failure (unsatisfiable output path)
      genuine fatal; the SAME decisive behaviour (measured, §8.9)
NEITHER retained-mate mechanism can produce the hypothesised healthy-job-then-pass-failure clobber: a fatal
mate failure always aborts the pass at that job, so the pass-level failure broadcast always lands on entries
whose job never ran - the fallback branch - and never on a healthy job-scoped verdict.
RECEIPT IMPACT: UNPROVEN. Nothing in this review shows the clobber denying, corrupting or fabricating a
receipt. The two independent Python gates observed earlier (the workflow's `failed` check, which precedes its
`finished` branch, and the verifier's own `failed=True` rule) remain exactly the defence in depth they already
were, and this review makes no claim that the correction is required for receipt correctness.
THE CORRECTION REMAINS VALID AS A STATE-FIDELITY INVARIANT (nothing more):
      a job-scoped terminal verdict must not be overwritten by a weaker, later pass-scoped aggregate.
EXPLICITLY NOT CLAIMED: receipt correctness depends on this correction.
F9 is recorded separately (a failed job is unreadable through the authorised inspection path) and is not part
of this slice.
CONSEQUENCE FOR THE LADDER: no implementation is authorised by this document. The next architecture /
implementation gate decides separately whether the small state-fidelity correction is worth implementing,
with the receipt impact explicitly treated as UNPROVEN.
```

---

*Evidence classes: (a) UE 5.6.1 engine sources with file:line anchors
(`MovieRenderPipelineCore/Public/MoviePipelineExecutor.h`, `.../Private/MoviePipelineLinearExecutor.cpp`,
`MovieRenderPipelineEditor/Private/MoviePipelinePIEExecutor.cpp`, `MovieRenderPipelineCore/Private/MoviePipeline.cpp`,
`.../Private/MoviePipelineRendering.cpp`, `.../Private/MoviePipelineTiming.cpp`); (b) this repository's transport and planning
sources at `4b61d8f` (`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`,
`Public/AtlasTransportServer.h`, `planning/unreal_render_workflow.py`,
`planning/unreal_render_job_verifier.py`, `tests/test_unreal_render_workflow.py`); (c) live-gate measurements
recorded for Slice 1/2, Slice D and Slice E. No engine was run for this review, and nothing is asserted that the
sources or the recorded measurements do not show.*
