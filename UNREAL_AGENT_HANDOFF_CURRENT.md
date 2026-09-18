# Atlas Unreal Agent — Current Development Handoff

**Updated:** September 17, 2026 (publication update)
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10` — published at `d582af3`
**Status:** Shot-level production continuity is **COMPLETE + LIVE-PROVEN and PUBLISHED** (d582af3). **MRQ artifact attribution (Slice 1 + Slice 2) is COMPLETE + LIVE-PROVEN** and committed in this milestone's commit on top of `6e63d15`: the per-job callback records artifacts only for the exact executor job this Atlas submission allocated (foreign payloads are discarded), and PNG artifacts must be contained within the authorized output directory. **Slice D (start-callback identity guard) is now COMPLETE + LIVE-PROVEN** on top of that: monitoring state (`Status`/`StatusMessage`/`Progress`) is written only for the exact registered executor job, so a foreign queued job can no longer overwrite the new Atlas job's monitoring state. The queue-lifecycle design review (`docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md`, **CLEAR WITH MINOR FINDINGS**, read-only) concluded that accumulation is no longer a provenance correctness risk, accepted the current shared queue semantics as the default, rejected queue consumption for now, and deferred an Atlas-owned private queue instance. **Slice 3 queue consumption and the private-queue migration remain unimplemented and unauthorized.** **MRQ submission outcome propagation is now COMPLETE + LIVE-PROVEN** (`docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md`): the submission call and its `GetActiveExecutor()` identity observation happen in one game-thread task, so a refused submission is an immediate typed failure (measured 1.50 s) instead of the 300 s poll timeout, an unprovable outcome fails closed as ambiguous, and the rejected job's registry entry is removed. **Queue consumption and the private-queue migration remain unimplemented and unauthorized.** The queue-isolation question has been through a **read-only design gate**: `docs/UNREAL_MRQ_QUEUE_ISOLATION_DESIGN_REVIEW.md` (**verdict CLEAR WITH MINOR FINDINGS** — approved and published) concludes that **no remaining queue cost is a correctness risk**, recommends **keeping the shared queue semantics as the permanent default**, **defers** an Atlas-owned private queue against written triggers (T1-T4), and **rejects** consumption/deletion. The immediately following gate, `docs/UNREAL_MRQ_PASS_FAILURE_ATTRIBUTION_DESIGN_REVIEW.md` (**verdict CLEAR WITH MINOR FINDINGS**), audited the one cost that review left standing: the **pass-scoped executor failure is written into job-scoped fields** (bFinished/bSuccess/bFailed/Status/StatusMessage), which would overwrite a job-scoped verdict recorded by the job's own callback. Its two candidate in-pass mechanisms were then MEASURED on the unmodified baseline: B1 (resolution above the engine maximum) and B2 (unsatisfiable output path -> export-time write failure) both fail the retained mate GENUINELY, but both also **abort the pass at that job** (measured: `starting job [2/...]` = 0, `MoviePipelineLinearExecutorBase finished` = 0, and a later Atlas submission's own job never started - terminalised by the pass-level broadcast with no job-scoped verdict, i.e. the fail-closed fallback). So **a healthy render being reported failed is NOT reachable by either tested mechanism, and no receipt was denied, corrupted or fabricated**. What remains is a **state-fidelity invariant** only: a job-scoped terminal verdict must not be overwritten by a weaker, later pass-scoped aggregate. Its receipt impact is **UNPROVEN** and no receipt-correctness claim is made. **Nothing is authorized.**

## Current milestone chain

```text
Controller trust boundary              COMPLETE + LIVE
Blueprint semantic verification        COMPLETE + LIVE
Render-state semantic verification     COMPLETE + LIVE
Render-job identity verification       COMPLETE + LIVE
Composite actor production             COMPLETE + LIVE
Shot-level production continuity       COMPLETE + LIVE-PROVEN + PUBLISHED (d582af3)
MRQ artifact attribution (Slice 1+2)   COMPLETE + LIVE-PROVEN + PUBLISHED (8ecf7db)
        ↓
MRQ queue lifecycle design review      DONE - CLEAR WITH MINOR FINDINGS (read-only; no code)
        ↓
MRQ start-callback identity (Slice D)  COMPLETE + LIVE-PROVEN
        ↓
MRQ submission-error design review     DONE - CLEAR WITH MINOR FINDINGS (read-only; no code)
        ↓
MRQ submission outcome propagation     COMPLETE + LIVE-PROVEN
        ↓
MRQ queue isolation design review      DONE - CLEAR WITH MINOR FINDINGS (read-only; no code)
        ↓
MRQ pass-failure attribution review    DONE - CLEAR WITH MINOR FINDINGS (read-only; no code)
        ↓
NEXT (not authorized): decide whether the state-fidelity correction is worth
      implementing (receipt impact UNPROVEN - F6 closed on measured B1+B2)
      (standing: shared queue default; isolation only against triggers T1-T4;
       consumption/deletion unimplemented)
```

## MRQ artifact attribution — COMPLETE + LIVE-PROVEN

```text
MRQ artifact attribution   COMPLETE + LIVE-PROVEN
  - job identity guard is live-proven in a multi-submission single-editor session
  - foreign callback artifacts are discarded
  - PNG artifacts must be contained within the authorized output directory
  - exact frame-set verification remains active
  - Slice 3 queue consumption remains separate and unimplemented
```

Evidence: `tests/test_unreal_mrq_attribution_real_integration.py` (2 passed in 26.18 s, ONE editor session, four
submissions; engine log `starting 1 -> 2 -> 3 -> 4 jobs` with 6 `ATLAS MRQ ATTRIBUTION: discarded ...` lines),
plus `tests/test_unreal_mrq_attribution_contract.py` (14 deterministic tests) and the existing continuity live
gate re-run (1 passed in 9.60 s). Details: `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md`.

### Slice D — start-callback identity (COMPLETE + LIVE-PROVEN)

```text
Slice D   COMPLETE + LIVE-PROVEN
  - monitoring state is written only for the exact registered executor job
  - foreign queued jobs can no longer overwrite Status / StatusMessage / Progress
  - the Atlas job still receives its own start transition
  - Slice 1 artifact isolation unchanged; exact PNG frame-set verification unchanged
  - Slice 3 queue consumption and the private-queue migration remain unimplemented
```

Evidence: `tests/test_unreal_mrq_started_identity_real_integration.py` (2 passed in 35.22 s in ONE editor session
whose queue already held two jobs from an aborted harness attempt: after each submission 12/12 and 8/8 state reads
reported `submitted` while a foreign queued job was still rendering, and the Atlas job's own transition to
`rendering` was observed), plus `tests/test_unreal_mrq_started_identity_contract.py` (7 deterministic tests).

## Shot-level production continuity

The shot-continuity implementation is live-proven against real Unreal Engine 5.6.1 and the existing Named Pipe/MRQ path in fresh editor sessions.

Atlas frame semantics remain **inclusive**:

```text
start_frame ... end_frame
expected PNG frame set = every authorized frame in that range
```

The Unreal/MRQ boundary performs the translation exactly once:

```text
CustomStartFrame = Atlas start_frame
CustomEndFrame   = Atlas end_frame + 1
```

Fresh render-job evidence exposes the Atlas semantic range plus `end_frame_exclusive` as the raw engine-boundary diagnostic. Final continuity verification requires exact sequence identity, frame-range identity, output-directory identity, output-format identity, exact job identity, and exact PNG frame-set coverage. Missing, duplicate, unexpected, or frame-number-less artifacts fail closed.

Live proof included:

```text
authorized 1–2 → 2 PNG artifacts
sequence path exact
inclusive frame range exact
output directory/format exact
job ID exact
receipt issued + persisted

full-range diagnostic 1–5 → 5 PNG artifacts
```

Tracked Unreal fixtures were restored and byte-verified identical after the live runs.

## Reconciliation state

The shared branch contained a parallel shot-continuity implementation. A reconciled candidate was assembled locally by explicit semantic decisions and has now been published.

```text
common checkpoint            : 86467ac5
remote parallel lineage      : 2e3d8e8 (published feature branch)
documentation lineage        : 930cc60 (3 docs-only commits after 2e3d8e8)
local closeout lineage       : 0e11d2b
reconciled candidate         : 97487d0 (LIVE CLEAR, fresh UE 5.6.1 gate)
publication merge            : d582af3 (merge of 97487d0 + 930cc60)
published shared-branch tip  : d582af3 (normal fast-forward from 930cc60; no force push)
```

The reconciled contract:

1. `UnrealShotContinuity` is the single continuity authority.
2. Sequence identity is bound through production spec → production plan → authorization.
3. Inclusive Atlas range semantics are preserved.
4. MRQ boundary translation occurs exactly once at the Unreal boundary.
5. Fresh effective frame evidence is authoritative.
6. Exact PNG frame-set verification is retained from the strongest part of the parallel implementation.
7. `verify_render_job_completion` stays continuity-free.
8. Exact job-ID binding remains unchanged.
9. Recovery remains fail-closed and authorization-bound.
10. No new transport primitive, second authorization authority, generic workflow engine, entity cache, or distributed-render architecture is introduced.

### Receipt decision

Keep the existing evidence-bound receipt:

```text
job_id
sequence_asset_path
evidence_digest
receipt_digest
```

The parallel receipt extension containing frame range/output directory/output format was rejected during reconciliation. Those values are already covered by the evidence digest and continuity verification; duplicating them into receipt identity adds churn without an independent integrity property.

No additional `continuity_digest` provenance field was added to the receipt store.

## Publication record (September 17, 2026 — publication gate)

The reconciled implementation is **published** on the shared branch.

```text
published tip (shared + candidate) : d582af3
publication method                 : documented merge, then normal fast-forward push
force push / rebase / reset        : none
```

Proof that publication was documentation-only: `git diff 97487d0 d582af3` contains exactly `README.md`, `UNREAL_AGENT_HANDOFF_CURRENT.md` and `docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md`, and every blob under `planning/`, `tests/` and `unreal/AtlasUnrealHarness/Source/` is byte-identical between `97487d0` and `d582af3` (`git rev-parse 97487d0:<path>` equals `git rev-parse d582af3:<path>`).

Deterministic regression re-run on the merged tree: focused continuity/auth/receipt set 173 passed / 1 skipped; consolidated affected Unreal suite 291 passed / 2 skipped; canonical controller/host suite 160 passed / 2 deselected; broad scoped sweep 1123 passed / 6 skipped — identical to the pre-merge numbers, so no contract break. The UE live gate was not re-run because no executable source changed.

Do not force-push, rebase destructively, or blindly merge the parallel implementation.

## Next step — design gate only (no implementation)

Shot continuity is closed and published, MRQ artifact attribution (Slice 1 + Slice 2) is COMPLETE + LIVE-PROVEN
and published (`8ecf7db`), and the queue-lifecycle design review completed as **CLEAR WITH MINOR FINDINGS**
(`docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md`, read-only; no code, no tests, no live run).

Its recommended slice — **D, identity-guarding `OnIndividualJobStarted`** — has since been implemented and
live-proven: `InJob == FRenderJobState::Job` gates every monitoring-state write, so a foreign queued job cannot
overwrite the new Atlas job's `Status`/`StatusMessage`/`Progress`. The remaining candidates are unchanged:

```text
D  identity-guard OnIndividualJobStarted      DONE - implemented + live-proven
A  retain current shared MRQ queue semantics  accepted as the default
C  Atlas-owned private MRQ queue instance     engine-proven mechanism (Epic Quick Render), deferred with
                                              entry criteria; own design gate required
B  consume/delete only Atlas-owned jobs       rejected for now (engine-queue mutation + index risk)
```

### MRQ submission outcome propagation — COMPLETE + LIVE-PROVEN

When a submission was made while another render was already active, UE refused it inside the subsystem
(`ensureMsgf(!IsRendering())` → `KismetExecutionMessage("Render already in progress.")` → `return`), the
transport could not surface that refusal, and the caller observed a poll timeout. **Closed by this slice.**

```text
MRQ submission outcome propagation   COMPLETE + LIVE-PROVEN
  - the submission call and the GetActiveExecutor() identity observation share one game-thread task
  - acceptance = the exact supplied executor is the observed active executor (IsRendering() never used)
  - REJECTED  -> immediate typed failure; no job identity exposed; no receipt; no retry
  - AMBIGUOUS -> fail closed; acceptance never claimed
  - ACCEPTED  -> unchanged response, job identity, polling and evidence semantics
  - a rejected submission's registry entry is removed (never left readable as "submitted")
  - no new transport operation, response field, status value, queue mutation or timeout change
```

Milestone: `MRQ submission outcome propagation — COMPLETE + LIVE-PROVEN`.

```text
preserved
  queue consumption unimplemented
  private queue migration unimplemented
  automatic retry prohibited
  exact job identity unchanged
  receipts only from fresh verified terminal evidence
```

Evidence: `tests/test_unreal_mrq_submission_outcome_real_integration.py` (2 passed in 22.80 s in ONE fresh UE
5.6.1 session, FOUR submission attempts: accepted while idle, rejected in 1.50 s while rendering, no receipt for
the rejection, multi-job and same-range attribution still exact), `tests/test_unreal_mrq_submission_outcome_contract.py`
(18 deterministic tests; 8 fail at the previous baseline), broad sweep 1216 passed / 7 skipped vs 1198 / 7, and
the engine log showing 3 executor starts for 4 attempts plus one "Render already in progress.". Details:
`docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md`, `docs/UNREAL_MRQ_SUBMISSION_ERROR_CLOSEOUT.md`.

Design-gate answers that framed it (`docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md`, verdict
`CLEAR WITH MINOR FINDINGS`):

```text
observable          only at the call site: GetActiveExecutor() == Executor immediately after the call, on the
                    game thread (public accessor on both the editor and the runtime subsystem). No callback
                    fires for a refusal; polling cannot see it (no liveness field; registry entries never pruned)
protocol change     NONE needed: success=false + error already exist on the wire and already raise
                    UnrealAdapterError -> structured UnrealPlanExecutionError (no job id, no polling, no receipt)
contract            REJECTED = submit fails hard; ACCEPTED-NOT-COMPLETE = success + job id + poll;
                    AMBIGUOUS = fail closed; LOST RESPONSE = typed transport error, no retry
engine window       the PIE executor sets bIsRendering only in OnPIEStartupFinished, so between acceptance and
                    that point IsRendering() is FALSE and a concurrent submission is ACCEPTED, overwriting
                    ActiveExecutor (no identity check in the subsystem) -> acceptance must be proven by
                    identity, never inferred from IsRendering(); exclusivity is best-effort engine behaviour
crash window        fail-closed (registry + queue are process-lifetime/transient; receipts need verified
                    terminal evidence; a retry mints a new GUID) — orphaned PNGs are not evidence
future executors    the refusal and the identity signal live in the subsystem contract, so an identity-anchored
                    design survives a future executor; an IsRendering()-timing-anchored design would not
candidates          A accept (with F); C accept; B partial (cannot see a refusal); D rejected as the mechanism;
                    E rejected as the contract
forbidden           no timeout inflation, no synthetic success, no automatic retry, no queue mutation, no new
                    transport operation, no new job-identity source, no new status value, no receipt change
```

### Queue isolation — ANSWERED (read-only design review, nothing authorized)

`docs/UNREAL_MRQ_QUEUE_ISOLATION_DESIGN_REVIEW.md` — **verdict CLEAR WITH MINOR FINDINGS**. Summary:

```text
correctness   none remaining (identity-bound slices make the queue layout irrelevant to evidence integrity)
availability  pass-scoped failure coupling: a queue-mate's fatal error fails OUR job's pass and is reported as
              our failure; a valid render can be lost with a misleading message
efficiency    measured amplification 2.5x-2.7x job-renders per accepted submission; orphan job re-rendered
visibility    the shared queue is the only operator-visible view of Atlas's renders
A  keep shared queue semantics        RECOMMENDED DEFAULT (permanent)
B  private queue (engine-proven)      DEFERRED, triggers T1-T4 + entry criteria recorded in the review
C  consume/delete Atlas-owned jobs    REJECTED (unsafe at every executor state; mutates operator-visible state)
D  hybrids                            only "A now, B later if a trigger fires"
trigger T1    retained queue depth >= 5, or per-submission re-render work exceeding the new job's own work
trigger T2    operator needs per-render isolation (cancellation / queue panel usability)
trigger T3    a queue-mate fatal error repeatedly fails healthy Atlas submissions
trigger T4    the queue-mate misdiagnosis appears in production reports as our render failing
```

Slice 3 queue consumption and the private-queue migration stay unimplemented and unauthorized; a new gate is
required before either changes.

### Pass-scoped executor failure attribution — ANSWERED (read-only design review, nothing authorized)

`docs/UNREAL_MRQ_PASS_FAILURE_ATTRIBUTION_DESIGN_REVIEW.md` — **verdict CLEAR WITH MINOR FINDINGS**. Summary:

```text
defect       OnExecutorFinished carries a PASS aggregate (!bAnyJobHadFatalError) and Atlas writes it into
             JOB-scoped fields (AtlasTransportServer.cpp:1480-1489), clobbering the healthy verdict our own job
             already recorded from its identity-guarded per-job payload (:1444-1449). The pass continues after a
             fatal job error, so both verdicts coexist in that entry.
effect       a healthy, evidence-complete render is denied its receipt at two layers (workflow checks `failed`
             before `finished`; the verifier rejects failed=True) and must be re-authorized and re-rendered.
class        availability + terminal-contract precision (fail-closed false negative; never a false accept)
fix scope    one existing callback: apply the pass verdict only when our entry has no job-scoped terminal verdict
             of its own. No new field/operation/authority, no queue interaction, no retry.
findings     F1 clobber; F2 no fixture pins the resulting state combination; F3 classification;
             F4 the failing mate's identity is not observable (two-way contract only); F5 fix scope;
             F7 ordering safety (our own failure always arrives through our own payload first)
F6 closed    on MEASURED grounds (B1 + B2); receipt impact UNPROVEN (§8.8-§8.10 of the review):
             both mechanisms produce a genuine engine-level fatal failure for the retained mate AND both abort
             the pass at that job - measured "starting job [2/...]" = 0 and "MoviePipelineLinearExecutorBase
             finished" = 0, with a later Atlas submission accepted but its own job never started (terminalised
             by the pass-level broadcast, no job-scoped verdict = the fail-closed fallback). So neither can
             reach the hypothesised healthy-job-then-pass-failure clobber, and no receipt was denied, corrupted
             or fabricated. The correction survives ONLY as a state-fidelity invariant (a job-scoped terminal
             verdict must not be overwritten by a weaker, later pass-scoped aggregate); no receipt-correctness
             claim is made.
F9 follow-up a FAILED job is unreadable through the authorised product path (`inspect_render_job` is mapped
             onto `verify_render_job_completion`, which raises "render job reports failed=True"); only the error
             text is visible to callers. Separate gate; not part of this slice.
next         a separate gate decides whether the small state-fidelity correction is worth implementing, with
             the receipt impact explicitly treated as UNPROVEN. Not started; nothing authorized.
```

The audit and candidate evaluation for that review are recorded in `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_DESIGN_REVIEW.md` (90 source anchors across the transport C++ and the UE 5.6.1 MovieRenderPipeline plugin, plus the measured failure evidence). Its recommended architecture is an identity guard in the existing `OnIndividualJobWorkFinished` lambda (the payload's job must equal the job this transport allocated) plus a PNG artifact-containment rule against the authorized output directory. The design gate returned `CLEAR WITH MINOR CONDITIONS`; Slice 1 and Slice 2 are now implemented and LIVE
CLEAR (see `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md`), and Slice 3 was deliberately not
implemented.

Measured risk driving the review: `SubmitRender` renders every job already present in the MRQ queue, and the per-job callback registered on the new executor writes every queue job's file paths into the newly submitted job's state. A second submission in one editor session therefore reports another job's artifacts (measured: 24 artifacts observed for an authorized 1–2 job whose own output directory was empty). That defect is **closed** by Slice 1 (artifact provenance) and Slice D (monitoring state): a non-empty queue is no longer an attribution risk, and the former procedural mitigation — one submission per fresh editor session — is no longer load-bearing for correctness. The Slice D live gate deliberately ran with a queue that already held two jobs and proved the property in that state.

Do not fold that issue into shot continuity: shot continuity is closed.

Other non-blocking observations:

- PNG completeness remains format-specific by design.
- Several sibling live tests retain the older concrete-`dict` evidence-reader assumption and were not changed when not directly exercised.
- `unreal_render_workflow._job_state` still duplicates render-job envelope resolution and should be considered for a later consolidation review.

## Workspace rules

Unreal development checkout:

```text
C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider
```

Never modify the Blender checkout:

```text
C:\Users\Gavin's PC\Desktop\Atlas
```

Never stage pre-existing Aider/session artifacts. Do not run workflow/action-runner tests unless explicitly authorized.

## Authoritative closeout documents

```text
docs/UNREAL_SHOT_CONTINUITY_RECONCILIATION.md
docs/UNREAL_SESSION_CLOSEOUT_2026-09-17.md
docs/UNREAL_SHOT_CONTINUITY_CLOSEOUT.md
docs/UNREAL_NEXT_ARCHITECTURE_REVIEW.md
docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_DESIGN_REVIEW.md (design: CLEAR WITH MINOR CONDITIONS)
docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md
docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_CLOSEOUT.md
docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md (design: CLEAR WITH MINOR FINDINGS)
docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md (design: CLEAR WITH MINOR FINDINGS)
docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md
docs/UNREAL_MRQ_SUBMISSION_ERROR_CLOSEOUT.md
docs/UNREAL_MRQ_QUEUE_ISOLATION_DESIGN_REVIEW.md (design: CLEAR WITH MINOR FINDINGS; published)
docs/UNREAL_MRQ_PASS_FAILURE_ATTRIBUTION_DESIGN_REVIEW.md (design: CLEAR WITH MINOR FINDINGS)
```

This file is the first-read continuation context for the next Unreal session.