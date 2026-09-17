# Unreal Agent — MRQ Queue Lifecycle & Provenance Design Review

**Date:** September 17, 2026
**Mode:** READ-ONLY ARCHITECTURE/DESIGN GATE (source audit + recorded measurements; no code, no tests, no live engine run)
**Published baseline:** `reconcile/unreal-autonomy-origin-20c6d10` = `8ecf7db4e511e252d10d34593fa6b01fde241302`
  (MRQ artifact attribution Slice 1 + Slice 2 — COMPLETE + LIVE-PROVEN)
**Scope of the review:** the *remaining* MRQ boundary as ONE provenance/lifecycle question — queue lifecycle,
`OnIndividualJobStarted` identity, queue retention/consumption, optional queue isolation.
**Verdict:** see §12. **Nothing is authorized for implementation by this document.**

```text
do-not-touch : planning/**, tests/**, unreal/**, Blender checkout
not run      : pytest, workflow/action-runner tests, Unreal editor, any live gate
used         : UE 5.6.1 engine sources (MovieRenderPipeline plugin), this repo's transport + Python planning
               layer, and the engine logs recorded by the Slice 1/2 publication round
```

---

## 1. The question this gate had to answer

```text
After Slice 1 (job-scoped artifact provenance) and Slice 2 (authorized-directory containment),
does MRQ queue accumulation still create a CORRECTNESS risk,
or is it now only an efficiency/operator concern?
```

**Answer: it is no longer a provenance correctness risk. It remains (a) an efficiency cost, (b) a
fail-closed availability coupling, and (c) a monitoring-state fidelity gap — and it is the reason a
structural isolation option exists at all.**

The distinction matters because Slice 1 already removed the only path by which queue contents could
contaminate *evidence*. Queue cleanup must therefore be justified on other grounds, if at all.

---

## 2. Exact MRQ job ownership (measured from source)

| Fact | Anchor (UE 5.6.1 unless stated) |
| --- | --- |
| Atlas allocates its job into the editor's **current** queue and the queue takes ownership (outer = queue) | transport `SubmitRender` `Queue->AllocateNewJob(UMoviePipelineExecutorJob::StaticClass())`; engine `MoviePipelineQueue.cpp:41-47` (`NewObject<UMoviePipelineExecutorJob>(this, InJobType)`, `Jobs.Add`) |
| The job's identity is engine-minted and stored by the transport | transport `FGuid::NewGuid()` → `FRenderJobState::JobId`; `JobState->Job=Job` |
| **Each job owns its own configuration snapshot** | `UMoviePipelineExecutorJob::SetConfiguration(InPreset)` → `Configuration->CopyFrom(InPreset)` (`MoviePipelineQueue.cpp:322-329`); header: "the configuration was originally based on no longer exists, this configuration will still be valid" |
| The Atlas preset asset is only a *source*: mutating it later cannot retroactively change queued jobs | `LoadAtlasRenderConfig` → `LoadObject<UMoviePipelinePrimaryConfig>` returns the shared asset object, but jobs copied from it at submission time |
| Retained jobs therefore re-render with **their own** latest-at-submission range and directory | **measured**: attribution session log shows per-job registrations `[800,2400)` (1–2), `[800,4800)` (1–5), `[800,2400)`, `[800,2400)` across a 4-job re-render, i.e. each retained job kept its own authorized range even after the shared preset asset had been rewritten twice |

Consequence: ownership is unambiguous at every layer (one engine job per Atlas job id; one configuration
snapshot per job; one registry entry per job id). Nothing in the retained-queue path can make one job's
configuration or artifacts masquerade as another's *by configuration*.

## 3. Callback lifecycle (measured from source)

Three callbacks are registered on the executor created for ONE Atlas submission:

| Callback | Fires | Writes (per Atlas entry) | Identity-guarded? |
| --- | --- | --- | --- |
| `OnIndividualJobStarted(UMoviePipelineExecutorJob*)` | once per job the executor begins | `Status="rendering"`, `StatusMessage`, `Progress=0.0` | **no** (fires for foreign jobs too) |
| `OnIndividualJobWorkFinished(FMoviePipelineOutputData)` | once per job, one tick after that job's PIE session ends (`PIEExecutor.cpp:447-456`) | `Status/Progress/bFinished/bSuccess/bFailed` + artifacts when `InOutputData.bSuccess` | **yes (Slice 1)** |
| `OnExecutorFinished(UMoviePipelineExecutorBase*, bool)` | at the end **and** on every error (`MoviePipelineExecutor.h:224-234`) | `bFinished/bSuccess/bFailed/Status` from `!bAnyJobHadFatalError` | **no** (executor-scoped, not job-scoped) |

Two lifecycle facts that matter for everything below:

1. **The per-job payload is per job and carries the owning job** (`Params.Job = GetCurrentJob()`), which is
   exactly what Slice 1 now requires to match `FRenderJobState::Job`.
2. **`OnExecutorFinished` is a queue-aggregate signal.** `OnExecutorErroredImpl(..., bFatal, ...)` sets
   `bAnyJobHadFatalError` when the error is fatal and *rebroadcasts the finished delegate immediately*; the
   final `OnExecutorFinishedImpl` broadcasts `!bAnyJobHadFatalError`. Any fatal error from **any job in the
   queue** therefore reaches the newest job's registry entry.

## 4. Failed / partial jobs (source-derived, not yet measured live)

* A pipeline that finishes with `bSuccess == false` is reported to the executor as **fatal**
  (`PIEExecutor.cpp:372-375`: `OnPipelineErrored(..., true, ...)`), so `bAnyJobHadFatalError = true`.
* The executor's finished broadcast then writes `bSuccess=false, bFailed=true, Status="failed"` into **our**
  entry — including when the failing job was an earlier, retained job that Atlas does not own.
* A failed job's own payload carries `bSuccess=false`, so its artifacts are never recorded (Slice 1 keeps
  that gate intact), i.e. the failure is *visible* but never produces artifacts.
* Consequence: a stale/failed queue entry can (i) abort our poll with `failed=True` even though our own job
  rendered (a false negative → no receipt), and (ii) mark our entry failed after our job succeeded if the
  failing job ran later in the same executor pass. **Direction is always fail-closed**; the accept path
  requires `finished && success && non-empty artifacts`, and artifacts only come from our own successful
  payload.

Residual load-bearing invariant to state explicitly: *"no artifacts from our own successful payload ⇒ no
receipt"*. Today that invariant is what keeps the executor-level overwrite from becoming a false accept.
Any future change that records artifacts outside `InOutputData.bSuccess` on the owning job would break it.

## 5. Editor restart

* The editor queue is **transient**: `UMoviePipelineQueueSubsystem()` constructs
  `CurrentQueue = CreateDefaultSubobject<UMoviePipelineQueue>("EditorMoviePipelineQueue")`; explicit
  `SaveQueue`/`LoadQueue` are required for persistence (with `QueueOrigin`/dirty bookkeeping).
* Measured three times in the Slice 1/2 round: every fresh editor session started with **0** MRQ jobs
  (`MoviePipelineLinearExecutorBase starting` count = 0 before the gate), while the previous session had left
  2–4 jobs in the queue.
* The transport's `RenderJobRegistry` is a session-scoped static map, so a previously issued job id fails
  closed after a restart (`Render job not found: <id>`).

Conclusion: restart clears both the accumulation and the provenance registry; there is no cross-session
lifecycle hazard, and no persisted queue state for Atlas to reason about.

## 6. Multiple Atlas submissions

Measured (one editor session, four submissions, attribution gate):

```text
submission 1 -> starting 1 jobs   (queue: [A1])                 A1 rendered with its own 1-2
submission 2 -> starting 2 jobs   (queue: [A1, A2])              A1 re-rendered 1-2, A2 rendered 1-5
submission 3 -> starting 3 jobs   (queue: [A1, A2, A3])          all three re-rendered with their own ranges
submission 4 -> starting 4 jobs   (queue: [A1..A4])              all four re-rendered with their own ranges
6 x "ATLAS MRQ ATTRIBUTION: discarded" (1+2+3 = N-1 foreign payloads per submission)
```

* Evidence stayed exact for every job (`output_files` = own frames, inside own authorized directory).
* Cost is multiplicative: the k-th submission in a session renders `1+2+...+k` job-runs; the measured
  four-submission session executed 10 job-runs for 4 authorized shots.
* Atlas never re-uses another submission's job id, and each submission's poll is bound to its own id.

## 7. Non-Atlas MRQ jobs

* A human-created job in the editor queue renders inside **our** executor pass (queue order, ascending).
* Effects we measured or can derive: it consumes render time; its own payload is discarded by Slice 1; a
  fatal error from it surfaces through the executor-level callback (§4) and can fail/abort our poll; it never
  contributes artifacts to our entry.
* Atlas currently neither sees nor mutates those jobs. Under candidate A/B they remain in the queue
  afterwards (B only touches Atlas-owned jobs); under candidate C they would not render during our
  submission at all.

## 8. Queue visibility / UI behavior

| Behaviour | Anchor |
| --- | --- |
| Atlas jobs appear in the MRQ queue panel like any other job (no hiding, no badges) | `AllocateNewJob` + queue change notifications (`FCoreUObjectDelegates::OnObjectModified` → `OnAnyObjectModified`; `DeleteJob` calls `Modify()` under `WITH_EDITOR`) |
| `IsConsumed` is **never set to true by the engine** in 5.6.1 — the only write is `SetConsumed(false)` in the queue editor's `ResetStatus()` | grep across the plugin: `SMoviePipelineQueueEditor.cpp:220` only |
| Consumed jobs are excluded from "renderable" sets and from `RenderQueueWithExecutor`-style UI flows | `MoviePipelineLinearExecutor.cpp:58` (skips consumed), `MoviePipelineEditorUtils.cpp:47`, `SMoviePipelineGraphPanel` filters, `SMoviePipelineQueuePanel.cpp:324,518` |
| The `Consumed` flag exists for **remote/farm** executors ("Jobs submitted to remote renders might already be consumed") — not for the local PIE path | `MoviePipelineQueue.h:381-403` comments + `StartPipelineByIndex` skip |

**Measured implication:** the engine's own local UI has the same re-render semantics Atlas has — rendering
the queue twice re-renders the jobs still in it, because nothing marks them consumed. Accumulation is an
engine-model property, not an Atlas defect, and it is *visible to the operator* in the MRQ panel.

## 9. Job deletion semantics

| Aspect | Finding (source) |
| --- | --- |
| `DeleteJob(Job)` | `Jobs.Remove(InJob); QueueSerialNumber++` (+ `Modify()` in editor) — plain removal, no delegate of its own, job object survives until GC |
| `DeleteAllJobs()` | same for the whole list |
| Safe while rendering? | **No.** The linear executor iterates by index: `StartPipelineByIndex` does `check(InPipelineIndex >= 0 && InPipelineIndex < Queue->GetJobs().Num())` and `OnIndividualPipelineFinished` compares `CurrentPipelineIndex >= Queue->GetJobs().Num() - 1`. Mutating the array mid-iteration can trip the `check()` (fatal in Development) or shift the "last job" decision. Any deletion policy must therefore be conditioned on "no executor is iterating this queue" |
| Atlas's existing deletions | only on configuration-failure paths inside `SubmitRender` (before the executor starts) |
| Consumption (`SetConsumed(true)`) | engine-sanctioned, non-destructive, skipped by the executor, but Atlas would be writing a flag the engine's own local path never writes; it changes UI "renderable" lists |
| Who may be touched | Only jobs Atlas explicitly allocated and still holds a `TWeakObjectPtr` to (`FRenderJobState::Job`) — anything else is operator/engine state |

## 10. Recovery / fail-closed behaviour (unchanged by this review)

* Submission failures, timeouts, and failed jobs all raise `UnrealRenderWorkflowError` → the production
  workflow fails → a NEW exact authorization is required; `submit_render` is never retried automatically
  (pinned by the existing recovery tests).
* A silent non-start (see §11, finding F2) also fails closed — via poll timeout, not via an explicit error.
* No lifecycle change proposed here may introduce a retry, a repair, or a second authorization path.

## 11. Findings of this review

**F1 — `OnIndividualJobStarted` is identity-blind (fidelity, not safety).**
A foreign job's start writes `Status="rendering"` and resets `Progress=0.0` into the newest job's entry, so
monitoring fields can describe another job's activity. No acceptance path consumes those fields beyond
"status ∈ {submitted, queued, rendering}" gating, and the terminal flags are written by the other two
callbacks. → candidate D is a small, isolated fidelity fix.

**F2 — A submission can be silently dropped when a render is already in progress.**
`RenderQueueInstanceWithExecutorInstance` begins with
`ensureMsgf(!IsRendering(), "RenderQueueWithExecutor cannot be called while already rendering!")` and returns
without executing. The transport's `AsyncTask` ignores that outcome and `SubmitRender` has already returned
`status="submitted"`, so Atlas discovers the non-start only by poll timeout (measured path: none observed
live; derived from source). Affects A, B and C equally (the guard lives in the shared entry point).

**F3 — Executor-level failure is queue-scoped, not job-scoped.**
Any fatal error from any job in the queue (retained Atlas job or non-Atlas job) is broadcast to our entry as
`failed=true`, aborting the poll or marking our job failed after our own successful render (§4). Fail-closed,
but it is a real coupling between our submission and queue entries we do not own.

**F4 — Accumulation is a real, measured cost and an operator-visible side effect.**
10 job-runs for 4 authorized shots (§6); the queue panel accumulates one Atlas job per submission for the
lifetime of the editor session.

**F5 — Provenance is already job-scoped and configuration is already per-job (no action).**
Recorded because the review's premise ("queue retention may still contaminate evidence") is measurably
false after Slice 1 + Slice 2: per-job configuration snapshots (`CopyFrom`), job-scoped artifact collection,
containment against the authorized directory, and exact frame-set equality all hold on retained jobs.

## 12. Candidates and verdict

### A. Retain current shared MRQ queue semantics — **ACCEPTED as the default**

* Matches the engine's own local model (§8): the shared queue accumulates, jobs stay visible and re-render.
* No new state, no new mutation of engine-owned objects, no lifecycle risk (§9).
* Keeps F1–F4 exactly as they are today: fidelity noise, a silent-drop hazard, a fail-closed coupling, and a
  measurable cost.
* Cost is bounded by session length (queue is transient, §5) and is visible to the operator.

### B. Consume/delete only Atlas-owned completed jobs — **REJECTED for now**

* Benefit: removes Atlas's own re-render cost (F4) and the coupling to *Atlas* stale jobs (part of F3).
* But: it does **not** establish provenance (Slice 1 did), does **not** remove the coupling to non-Atlas
  jobs (F3), and does not touch F1/F2.
* Risk: it mutates engine-owned queue state that Atlas does not own semantically (the queue is an
  operator-facing object), and deletion must be gated on "no executor iterating this queue" or it can trip
  the executor's index `check()` (§9). `SetConsumed(true)` is a safer variant but writes a flag the engine's
  local path never writes, changing UI "renderable" semantics.
* Verdict: not justified by the correctness question this gate had to answer; revisit only if the re-render
  cost or the visibility of stale Atlas jobs becomes an operational problem.

### C. Isolate Atlas to its own MRQ queue instance — **SUPPORTED BY THE ENGINE, deferred to its own gate**

* **Engine-proven mechanism.** Epic's own Quick Render code does exactly this shape in UE 5.6.1:
  `MovieGraphQuickRender.cpp:315` creates a transient queue
  (`NewObject<UMoviePipelineQueue>(GetTransientPackage())`), line 198 creates the **same executor class Atlas
  uses** (`NewObject<UMoviePipelinePIEExecutor>(GetTransientPackage())`), registers the same three callbacks,
  and renders it with `Subsystem->RenderQueueInstanceWithExecutorInstance(TemporaryQueue, TemporaryExecutor)`
  (line 226). The subsystem's public `RenderQueueWithExecutor<T>(InQueue, ExecutorType)` wrapper exists for
  the same purpose, and the queue is kept alive during the render because `LinearExecutorBase::Queue` is a
  `UPROPERTY(Transient) TObjectPtr<UMoviePipelineQueue>`.
* What it would buy: F3 disappears (nothing else is in our queue → no foreign payloads, no foreign fatal
  errors), F4 disappears (no accumulation at all), F1/F2 remain (F2 is in the shared entry point), and the
  editor queue becomes fully operator-owned — Atlas stops adding jobs to it.
* What it would cost / change: the shared queue panel no longer shows Atlas renders (visibility change; the
  subsystem's active-executor progress still works); Atlas would own the private queue's lifetime
  (transient object + explicit null-out, as Quick Render does); the render would need the same map-validity
  path (`SetAllowUsingUnsavedLevels` is *not* required because Atlas sets `Job->Map` explicitly, unlike Quick
  Render which may render unsaved levels); and it is a behavioural change to a proven-live path, so it needs
  its own design gate, its own live gate (same-session multi-submission + foreign-job-present cases), and a
  rollback story.
* Verdict: the only candidate that structurally removes the coupling, and it is engine-native rather than
  invented — but it is *not* required for correctness today, so it is deferred with explicit entry criteria
  (§13) rather than adopted.

### D. Identity-guard `OnIndividualJobStarted` — **RECOMMENDED as the next small slice**

* Symmetric with Slice 1: the callback receives `UMoviePipelineExecutorJob* InJob`; guard it with
  `InJob == (*Found)->Job.Get()` before writing status/progress, exactly as `OnIndividualJobWorkFinished` now
  guards `InOutputData.Job`.
* Removes F1 (monitoring fields stop describing foreign jobs) with no protocol, authority, or contract change
  and no new abstraction; failure direction is unchanged (started-only writes never set terminal flags).
* Does not address F2/F3/F4.

### E. Combinations

| Combination | Effect |
| --- | --- |
| **A + D** | Baseline semantics preserved; F1 removed; F2–F4 unchanged. **Recommended minimum.** |
| A + B + D | Adds cost reduction and removes Atlas-stale-job coupling; introduces engine-queue mutation and its index/UI risks. Not recommended while F3's non-Atlas half remains. |
| C + D | Removes F1, F3, F4 and the queue-visibility coupling entirely; keeps F2. The strongest end state, at the price of a behaviour change to a live-proven path. |
| B + C | Redundant: with an Atlas-owned private queue there is nothing of Atlas's to consume or delete. |

### Verdict

```text
CLEAR WITH MINOR FINDINGS
```

* **The design question is answered:** after Slice 1 + Slice 2, queue accumulation is **not** a provenance or
  evidence-correctness risk (F5). It is an efficiency cost (F4), a state-fidelity gap (F1), a fail-closed
  availability coupling (F3), and a silent-drop hazard (F2).
* **Recommended next step:** candidate **D**, as a small self-contained slice with its own deterministic
  contract tests and a same-session live check — because it is the only finding that is unambiguously a defect
  in Atlas's own code (a foreign job mutating our monitoring state) and it is symmetrical with Slice 1.
* **Recommended retention:** candidate **A** (keep the shared-queue semantics) unless the operational cost of
  F3/F4 becomes material, in which case candidate **C** is the engine-proven structural answer and must go
  through its own design gate first.
* **Rejected:** candidate **B** in its delete form; `SetConsumed(true)` only as a sub-variant if a future gate
  proves a need.
* **Findings carried, none blocking:** F2 (silent non-start → poll timeout) and F3 (executor-level failure
  coupling) are fail-closed and out of scope for a slice; they should be re-examined together with candidate C,
  because C is what makes them disappear.

## 13. If candidate C is ever opened, its entry criteria are

1. A design gate that freezes: private-queue ownership/lifetime, transient-object handling, the executor's
   `Queue` reference, what the operator sees (queue panel vs active-executor progress), and whether the
   editor queue is left untouched in every failure path.
2. A live gate in ONE editor session proving: (a) a submission renders with a private queue while the
   editor queue holds unrelated jobs; (b) those unrelated jobs are neither rendered nor mutated; (c) evidence,
   job identity, continuity, and receipt are unchanged; (d) two sequential Atlas submissions in one session
   do not accumulate; (e) fail-closed behaviour on a deliberately invalid configuration.
3. A rollback statement: reverting to the shared-queue submission must be a one-line change with no state
   migration.

## 14. Frozen invariants (unchanged by this review)

No second authorization authority; no model-derived authority; no new transport primitive; no Named Pipe
protocol or argument change; no entity discovery/cache; no generic workflow engine; no distributed rendering;
no Blender changes; no weakening of exact job identity; no weakening of fresh verification; exact PNG
frame-set verification and authorized-directory containment remain active; recovery stays fail-closed with no
automatic mutation retry. This review authorizes **no code**: candidate D would need its own design gate
(and, per the standing ladder, an implementation authorization) before any edit.

---

*Evidence classes used: (a) UE 5.6.1 engine sources with file:line anchors; (b) this repository's transport
and planning sources at `8ecf7db`; (c) engine logs recorded by the previously completed live gates
(`Saved/Logs/AtlasUnrealHarness-backup-2026.09.17-22.33.20.log`). No new engine run was performed for this
review, and nothing was measured that the review does not cite.*

---

## Addendum (September 17, 2026, later the same session) — implementation status of this review's candidates

This review recommended candidate D (`OnIndividualJobStarted` identity guard) as the next slice and authorized no
code. That slice was subsequently authorized, implemented, live-proven and recorded separately:

```text
D  identity-guard OnIndividualJobStarted      DONE - COMPLETE + LIVE-PROVEN (docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md §7)
   F1 monitoring-state fidelity gap           CLOSED by D
A  retain current shared MRQ queue semantics  unchanged default
C  Atlas-owned private MRQ queue instance     still deferred (entry criteria above unchanged)
B  consume/delete only Atlas-owned jobs       still rejected for now
   F2 silent non-start -> poll timeout        CARRIED, not fixed: next architecture review
   F3 executor-level failure coupling         CARRIED, not fixed
```

The review's central finding is unchanged: after the artifact-provenance guard and the monitoring-state guard,
queue accumulation is not a correctness risk, and the remaining items are efficiency, operator-visibility and
fail-closed availability concerns. F2 is deliberately excluded from Slice D's scope; it must not be masked by
timeout changes or synthetic success.
