# Unreal Agent — Fresh Architecture Review After Composite Closeout

**Date:** September 17, 2026  
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`

## CURRENT STATE (September 17, 2026 — later the same session)

The review below selected shot-level production continuity as the next surface. That gate is now **closed**: designed, implemented, LIVE CLEAR against real UE 5.6.1, and PUBLISHED on the shared branch as `d582af3`.

The next architectural review is therefore **MRQ queue hygiene / artifact attribution** — how a submission's artifacts are attributed when the MRQ queue retains prior jobs. It is **NOT yet implemented**: no queue-clearing, no attribution change, and no transport or protocol change has been made, and it must not start without its own design gate. Every frozen constraint in this document (no new transport primitive, no second authorization authority, no model-derived authority, no entity discovery/cache, fresh verification, exact render-job identity, fail-closed recovery, no distributed-render architecture) continues to apply to that review.

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
        ↓
NEXT: MRQ queue hygiene / artifact attribution architecture review (NOT implemented)
```
