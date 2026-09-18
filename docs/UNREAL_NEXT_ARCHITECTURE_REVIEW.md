# Unreal Agent — Fresh Architecture Review After Composite Closeout

**Date:** September 17, 2026  
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`

## CURRENT STATE (September 17, 2026 — later the same session)

The review below selected shot-level production continuity as the next surface. That gate is now **closed**: designed, implemented, LIVE CLEAR against real UE 5.6.1, and PUBLISHED on the shared branch as `d582af3`.

The next architectural review was **MRQ queue hygiene / artifact attribution** — how a submission's artifacts are attributed when the MRQ queue retains prior jobs. That surface's Slice 1 (engine-side provenance guard in the existing per-job callback) and Slice 2 (PNG artifact containment against the authorized output directory) are now **MRQ artifact attribution — COMPLETE + LIVE-PROVEN** (job identity guard live-proven in a multi-submission single-editor session; foreign callback artifacts discarded; PNG artifacts contained within the authorized output directory; exact frame-set verification still active; Slice 3 queue consumption separate and unimplemented). See `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md`.

The NEXT gate was a **design review, not an implementation** — and it has now been performed AND acted on:
`docs/UNREAL_MRQ_QUEUE_LIFECYCLE_DESIGN_REVIEW.md` (**verdict: CLEAR WITH MINOR FINDINGS**; read-only, no code,
no tests, no live run). Its conclusion: after Slice 1 + Slice 2, queue accumulation is **not** a provenance or
evidence-correctness risk — it is an efficiency cost, a monitoring-state fidelity gap (`OnIndividualJobStarted`),
a fail-closed availability coupling (a queue job's fatal error reaches our executor-level callback) and a
silent-drop hazard (a submission made while another render is in progress is refused by the subsystem's
`ensure`, and the transport cannot see that).

Its recommended slice was implemented under its own gate and is now proven:

```text
D  identity-guard OnIndividualJobStarted      DONE - COMPLETE + LIVE-PROVEN (monitoring state is job-scoped)
A  retain current shared MRQ queue semantics  accepted as the default (unchanged)
C  Atlas-owned private MRQ queue instance     engine-proven (Quick Render does exactly this) - deferred,
                                              entry criteria recorded in the review; needs its own design gate
B  consume/delete only Atlas-owned jobs       rejected for now (does not establish provenance, mutates
                                              engine-owned queue state, executor index-invariant risk)
```

What remains from that review is the silent-drop hazard above (finding F2), carried forward — see the next
surface at the end of this document. It was deliberately not fixed with the Slice D work.

That carried surface has since been through its own **read-only design gate**
(`docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md`, **CLEAR WITH MINOR FINDINGS**) and then through an
authorized **implementation slice**: **MRQ submission outcome propagation — COMPLETE + LIVE-PROVEN**
(`docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md`). A refused submission is now an immediate typed failure
instead of a 300 s poll timeout; acceptance is proven by the observed identity of the supplied executor, read in
the same game-thread task as the submission call. See the CLOSED SURFACE section below. **The next surface is
now a different question — see NEXT SURFACE at the end of this document.**

The design review for that surface is drafted at `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_DESIGN_REVIEW.md` (audit of the MRQ job lifecycle, `SubmitRender` identity creation, queue state, callback/event ownership, `InspectRenderJob` construction, job-ID binding, artifact collection, receipt/evidence relations, continuity interaction, and recovery; candidates A–D evaluated; recommended architecture = engine-side provenance guard in the existing per-job callback plus PNG artifact containment against the authorized output directory). Its status is `CLEAR WITH MINOR CONDITIONS` (the operator relayed the independent gate result); Slice 1 and Slice 2 from it were implemented, live-proven and published at `8ecf7db`. Every frozen constraint in this document (no new transport primitive, no second authorization authority, no model-derived authority, no entity discovery/cache, fresh verification, exact render-job identity, fail-closed recovery, no distributed-render architecture) continues to apply to that review.

## Review conclusion

The completed composite actor-production boundary should remain frozen. The next development surface should not be another convenience wrapper around primitive actor operations.

The next architectural question is **production continuity across already-proven domains**: can one already-authorized production intent bind scene state, sequencer state, render configuration, render submission, render-job identity, and the final evidence/receipt chain without introducing a monolithic orchestration layer?

The proposed boundary is a narrow **shot-level production continuity gate**.

## Why this is the next surface

Atlas already has independently proven primitives and semantic verification for:

```text
actor transforms / material / Niagara
Blueprint state
sequencer playback range
render state
render job identity
render receipt/result continuity
controller trust binding
```

The remaining architectural risk is therefore less about adding another primitive and more about **continuity between authorized values across those existing primitives**.

The deferred render-job review already identified continuity risks around:

```text
sequence_asset_path
render frame/range/frame-count semantics
output_directory
output_format
artifact completeness
```

These are cross-operation consistency concerns. They should be addressed only where an authorized plan already contains the relevant values; Atlas must not infer them from returned engine state.

## Proposed contract boundary

A future shot-level production gate should conceptually preserve this path:

```text
already-authorized intent
        ↓
existing actor/composite operations
        ↓
existing sequencer operation
        ↓
existing render configuration operation
        ↓
existing render submission
        ↓
existing render-job identity verification
        ↓
fresh final evidence + matching receipt
```

The design should prefer composing the existing operations over inventing a new low-level Unreal capability.

## Frozen constraints

Any implementation gate must preserve:

1. **No new transport primitive.** Continue using the existing Named Pipe contract.
2. **No second authorization authority.** Authorization remains upstream of execution.
3. **No model-derived authority.** Model payloads may propose but never authorize.
4. **No entity discovery/cache.** Entity identity remains explicit and authorization-bound.
5. **Fresh verification.** VERIFY operations consume fresh Unreal evidence rather than echoed write arguments.
6. **Immediate write verification.** Every mutating operation retains the established WRITE → VERIFY shape.
7. **Render-job identity remains exact.** The already-proven job-ID binding cannot be weakened.
8. **Recovery remains fail-closed.** Uncertain mutation/verification never triggers automatic mutation retry.
9. **No premature distributed-rendering architecture.** Multi-job/distributed execution remains deferred.
10. **Language-agnostic boundary.** The Python planning contract must remain replaceable by C++ implementations later without changing the semantic contract.

## Candidate implementation seam

The existing planner already exposes plan composition and the existing executor already enforces operation sequencing. Before adding a new abstraction, audit whether the current plan composition plus existing semantic verifiers can express the continuity invariants directly.

The preferred design order is:

```text
existing operation contracts
        ↓
plan-level consistency checks only where required
        ↓
existing executor
        ↓
existing adapter / transport
        ↓
existing Unreal evidence
```

A new orchestration object should be introduced only if an actual contract gap is demonstrated by the audit and cannot be expressed with the existing task-plan structure without weakening authorization or verification.

## Questions to answer before implementation

### Sequence continuity

Can the authorized `sequence_asset_path` be proven to remain the same value from render submission through the final render-job evidence without a cross-plan lookup or inferred state?

### Frame/range continuity

Can the authorized sequencer range and authorized render range be shown to be consistent before submission, and can the final job evidence prove the submitted range without relying only on artifact existence?

### Output continuity

Can the authorized output directory and output format be bound to the submitted render and final artifact evidence without introducing a second artifact-identity authority?

### Artifact completeness

Can Atlas distinguish “render job completed” from “all authorized expected artifacts exist and cover the authorized frame/range” using fresh engine/filesystem evidence at the correct trust boundary?

### Cross-domain failure behavior

When a later operation fails after earlier writes have completed, can recovery stop safely, reassess from fresh evidence, and require a new exact authorization without implicitly replaying the earlier mutations?

## What should not happen next

Do not expand the composite abstraction with sequencer/render operations simply to make it look more complete.

Do not introduce a generic workflow engine inside Unreal.

Do not introduce entity discovery or an Atlas-side cache.

Do not merge Blender and Unreal execution paths.

Do not change the Named Pipe wire protocol.

Do not start distributed render orchestration as part of this gate.

## Entry criteria for the next implementation gate

Implementation should begin only after a focused design review produces:

```text
CLEAR
```

or

```text
CLEAR WITH MINOR FINDINGS
```

with explicit evidence for the affected existing contracts and a frozen list of invariants.

The first deterministic matrix should cover the continuity failure modes before any new live Unreal test is authorized.

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
NEXT: none scheduled. Standing decision: shared queue semantics stay the default;
      isolation only against triggers T1-T4; queue consumption stays unimplemented
      (a new gate is required before either changes)
```

## CLOSED SURFACE — concurrent-submission rejection / error propagation (finding F2)

**Status: design-reviewed AND implemented.** Design gate
`docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md` (`CLEAR WITH MINOR FINDINGS`); implementation
`docs/UNREAL_MRQ_SUBMISSION_ERROR_IMPLEMENTATION.md` and
`docs/UNREAL_MRQ_SUBMISSION_ERROR_CLOSEOUT.md` — **MRQ submission outcome propagation — COMPLETE +
LIVE-PROVEN**.

```text
before   the start was deferred into an AsyncTask whose outcome was discarded; a refused submission returned
         success with a pollable job id, then polled "submitted" until the 300 s timeout
after    the submission call and the GetActiveExecutor() identity observation happen in one game-thread task;
         acceptance = the exact supplied executor is the observed active executor
         REJECTED  -> the operation fails immediately with a typed message; no job id, no receipt, no retry
         AMBIGUOUS -> fail closed, acceptance never claimed
         ACCEPTED  -> unchanged response, job identity, polling and evidence semantics
proof    18 deterministic tests (8 fail at the previous baseline) + one clean live UE 5.6.1 session:
         accepted while idle, rejected in 1.50 s while rendering, no receipt for the rejection, multi-job and
         same-range attribution still exact, four submission attempts against three executor starts
```

What did NOT change: the Named Pipe protocol, the response field set, job identity, receipt/evidence contracts,
queue semantics, timeouts, shot continuity and artifact attribution. Still unimplemented: Slice 3 queue
consumption and the private queue instance.

---

## ANSWERED SURFACE — is queue isolation / a private queue instance worth its lifecycle surface?

**Status: read-only design review performed — `docs/UNREAL_MRQ_QUEUE_ISOLATION_DESIGN_REVIEW.md`, verdict
`CLEAR WITH MINOR FINDINGS`. Recommendation: keep the shared queue semantics as the permanent default; defer
isolation against written triggers; reject consumption/deletion. Nothing is authorized.**

```text
correctness   none remaining. After Slice 1 + Slice D + the submission-outcome slice, no queue layout can
              produce a false receipt, a mis-attributed artifact, a false success or an untruthful outcome.
availability  pass-scoped failure coupling: a fatal error in ANY queue-mate (foreign job or the orphan left by a
              rejected submission) fails the whole pass and reports the ATLAS job as failed
              ("Render executor finished with failure"), even when Atlas's own job rendered fine. Fail-closed,
              but a valid render can be lost and the diagnosis names the wrong job.
efficiency    measured amplification: 2.5x-2.7x job-renders per accepted submission in 3-4 job sessions
              ("starting 1,2,3,4" = 10 renders for 4 submissions; "starting 1,3,4" = 8 for 3), growing with
              retained depth and frame counts; plus the orphan job's frames in every later pass.
visibility    the shared queue is the ONLY place an operator can see, inspect and clear Atlas's jobs (the MRQ
              queue panel, the queue editor and the active-render settings tab all read GetQueue()).
hygiene       unbounded in-memory accumulation across a long editor session.
```

```text
A  shared queue (current)         KEEP as the permanent default
B  private queue (engine-proven,  DEFER with entry criteria; adopt only if a trigger fires
   Quick Render precedent)        removes amplification, orphan re-render and the failure coupling, but adds an
                                  Atlas-owned UObject on a NON-UObject holder (root/release obligations), removes
                                  operator visibility and diverges the MRQ UI from the rendered queue
C  consume/delete Atlas jobs      REJECT: deletion is unsafe at every executor state (check() + live Num());
                                  consumption is honoured by the local executor (correcting the earlier
                                  queue-lifecycle review) but fires no callback when it skips, and it mutates
                                  operator-visible engine state without removing the foreign-job coupling
D  hybrids                         only "A now, B later if a trigger fires"; B+C is redundant (a per-submission
                                  private queue is bounded by construction); A+C is the worst trade
triggers T1..T4                   amplifier materiality (retained depth >= 5 or re-render work exceeding the new
                                  job's own work), operator need for per-render isolation, repeated queue-mate
                                  failures of healthy submissions, or the misdiagnosis appearing in reports
```

Anything that would answer this differently, or that wants to implement B or C, needs a new gate. The blocked
alternative is closed: this surface is answered, not open.
