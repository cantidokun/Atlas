# Atlas Current Development Handoff

> **Authoritative current-state reconciliation — September 20, 2026.**
>
> This document is the authoritative current development handoff. Older dated handoffs remain archival and must be reconciled against current main before use.

## Current position

### Blender track — CLOSED for the current declared contract

Main now includes the final Blender discovery/closure records:
- PR #125 — next-capability discovery — merged;
- PR #126 — scene/profile compliance design — merged;
- PR #128 — post-scene-profile capability discovery — merged;
- PR #129 — hierarchy-cycle determinism defect — merged.

Current main after this cleanup:
- `e4ac4c11e562cee687b33c62a308813b1b309d08`

Independent audit status:
- Blender Extraction Fidelity v1: **CLEAR / frozen**.
- Scene health / analysis: **complete**.
- Correction planning, authorization, execution bridge, postcondition verification, receipts: **complete for the declared contract**.
- Temporal Observation + State Delta v1 and Temporal ↔ Blender correction integration v3: **merged/live-gated**.
- Wave 14 representation fidelity: **closed**.
- Wave 15 correction/live-gate closure: **closed**.
- Non-manifold evidence boundary and scene/profile compliance evidence: **closed**.
- Hierarchy-cycle determinism defect: **fixed, independently re-gated, and merged in PR #129**.
- No immediate new Blender correction family is justified by the current contract/discovery evidence.

Do not reopen Blender implementation merely to create another wave. Remaining Blender work is documentation/process hygiene or separately approved contract work.

## Blender architectural boundary

The established authority chain remains:

```
canonical extraction
    ↓
scene health / deterministic analysis
    ↓
bounded correction proposal
    ↓
authorization
    ↓
canonical execution contract
    ↓
real Blender boundary adapter
    ↓
postcondition verification + receipt
    ↓
temporal observation of resulting canonical state
```

Frozen boundaries remain frozen unless a concrete, independently evidenced defect requires reopening them.

## Next engineering track — Unreal

The next engineering focus is the **separately maintained Unreal track**, including the existing Unreal-Aider work, while preserving the repository/architecture separation used during development.

This is **not** a request to mix Blender and Unreal implementation indiscriminately.

The first Unreal gate is **read-only reconciliation**, not implementation:

1. inventory the open Unreal PR/branch stack and dependency relationships;
2. identify what is already represented on current main versus stranded on long-lived branches;
3. establish one known candidate Unreal head for live validation;
4. verify deterministic evidence on that exact tree;
5. only then proceed to explicitly authorized UE 5.6 M7 live scenarios.

Known open Unreal stack requiring reconciliation includes PRs #103, #41, #58, #50, #42, #40, and #47. These PRs do not all share the same base and must not be blanket-merged.

### M7 live scenario posture

Per the current Unreal contract/checklist, live cross-process recovery is not production-capable until the relevant UE 5.6 scenarios are actually exercised and independently reviewed.

Current scenario readiness from the latest independent audit:
- S1 normal render — ready for live;
- S5 render finishes while Atlas is down — ready for live;
- S6 orphaned artifacts — ready for live;
- S7 missing artifact after terminal claim — ready for live;
- S2 Unreal restart — blocked/not yet live-proven;
- S4 both restart — blocked/not yet live-proven;
- S8 duplicate execution identity — blocked/not yet live-proven;
- S3 Atlas restart — not yet proven.

No live scenario should be credited without exact-tree evidence.

## Validation discipline

Use the following sequence for Unreal:

    reconciliation
        ↓
    deterministic validation
        ↓
    known exact head
        ↓
    explicit operator authorization
        ↓
    UE 5.6 live M7 scenarios
        ↓
    independent red-team review
        ↓
    production-capability claim only if the evidence supports it

Deterministic tests do not substitute for live engine evidence.

## Other tracks

- M11 remains frozen.
- M12.1–M12.4 are complete; M12.5 remains deferred.
- M13.8/token optimization remains paused.
- Digital Twin/controller/autonomy areas require separate assessment where not already covered by the current contract.

## Authority invariants

Models and agent wrappers propose/reason. Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender and Unreal are controlled execution environments. Independent verification establishes what actually happened.
