# Blender Development README

> **Current authoritative checkpoint — September 20, 2026.**
>
> Blender Extraction Fidelity v1, correction closure, Temporal integration, evidence boundaries, and the final Blender discovery/determinism gates are closed on current main. The Blender track is now a maintained/frozen execution capability rather than the next active engineering milestone.

## Architectural position

Atlas's Blender track is now organized into four bounded layers:

1. **Canonical extraction** — Blender Extraction Fidelity v1. The producer is frozen unless a
   concrete defect is discovered.
2. **Scene health / analysis** — deterministic findings, topology intelligence, and readiness
   evaluation.
3. **Bounded correction** — planner, authorization, executor, receipts, and narrowly scoped
   Blender boundary adapters.
4. **Temporal observation** — Temporal Observation + State Delta v1 consumes canonical world
   state; it does not repair or redefine that state.

The authority boundary remains unchanged:

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

Canonical executors remain engine-neutral. Blender-facing mutation is performed only through the
narrow injected/live adapter seam and never gains persistence, recovery, workflow, or action-runner
authority.

## Completed authoritative milestones

### Blender Extraction Fidelity v1 — FROZEN / MERGED

The read-only producer contract is complete and independently reviewed.

Frozen scope includes deterministic object membership and visibility, transforms including
quaternion-mode handling, mesh vertices/faces, material-slot names, explicit omission semantics for
unsupported normals/UV/local-frame data, deterministic payload evidence, and the established digest
boundary.

The producer remains frozen unless a concrete correctness defect requires reopening it.

### Temporal Observation + State Delta v1 — IMPLEMENTED / MERGED

Design revision 9 was cleared for implementation and the core implementation merged in PR #109:

- merge commit: 7c63c3190c4adacfddb8d8b6a35721234876669b;
- real Blender temporal L-1–L-5 evidence passed;
- the temporal layer remains engine-neutral and downstream of canonical world state;
- Event Abstraction, event recognition, streaming/storage, retention, and runtime authority remain
  outside this milestone.

Do not use the old pre-revision-9 Temporal hold text in archival handoffs as the current status.

## Blender correction closure

| Wave | Capability | Current status |
|---|---|---|
| W1 | REMOVE_DUPLICATE_FACE | Live-validated and merged in Wave 15 |
| W1b | REMOVE_DEGENERATE_FACE | Live-validated and merged in Wave 15 |
| W2 | REPAIR_FACE_WINDING | Live-validated and merged in Wave 15 |
| W3 / W13 | REPAIR_MERGE_VERTEX | Live-validated and merged; Wave 13 middle-table planner closure included |
| W4 | REPAIR_PARENT_REFERENCE | Live-validated and merged |
| W5 | Topology intelligence | Analysis/read-only boundary live-validated and merged |
| W6 | REMOVE_ISOLATED_VERTICES | Live-validated and merged |
| W7 | REMOVE_DUPLICATE_VERTICES | Live-validated and merged |
| W8 | NORMALIZE_UNIT_METADATA | Live-validated and merged |
| W9 | RENAME_OBJECT | Live-validated and merged |
| W10 | RESTRUCTURE_COLLECTION | Live-validated and merged |
| W11 | Empty-mesh canonical contract | Live-validated and merged |
| W12 | REPAIR_PARENT_CYCLE | Live-validated and merged |
| W14 | Correction-boundary material-slot fidelity | Live-validated, independently red-teamed, and merged |

Wave 14 is now the normative representation-fidelity reference for geometry-rebuilding Blender
corrections. Same-datablock table rebuilding is the reference pattern; raw Blender slot evidence is
used only at the boundary for information the frozen canonical model cannot express. The wave did
not expand the extraction contract or correction authority.

## Wave 14 — representation fidelity

Wave 14 closed the demonstrated material-slot evidence gap.

Key decisions:

- canonical MQ-5 material comparison is retained and is now exercised non-vacuously;
- material-bearing real-Blender fixtures prove slot preservation rather than comparing () == ();
- unassigned and OBJECT-linked slots are treated as raw-Blender-boundary evidence because the frozen
  producer omits the material key for those states;
- Pattern B (clear_geometry + from_pydata + update) is the normative reference primitive;
- the historical Pattern A datablock-replacement primitive is superseded as the reference pattern
  and retained only as a deliberately lossy RED diagnostic;
- datablock identity is not a canonical Atlas invariant;
- normals, UVs, local-frame data, polygon material_index, material node metadata, and material
  datablock identity remain outside the contract.

Wave 14 merged as PR #111 in merge commit 0d6cf88b2b7d0a72501bd20e5b42aa091be890bf.

## Current validation posture

The established development pattern remains:

    bounded design
        ↓
    implementation
        ↓
    deterministic validation
        ↓
    adversarial validation
        ↓
    live Blender boundary validation
        ↓
    focused regression + CI
        ↓
    independent red-team review
        ↓
    merge

Live Blender evidence is operator-gated and must not be described as CI evidence unless a workflow
actually executes it.

Workflow/action-runner tests remain excluded unless explicitly authorized.

## What is NOT the next correction wave

There is currently no evidence-based justification to invent a new correction family for:

- normals or UVs;
- invalid indices;
- non-manifold topology;
- bounds overlap;
- invalid transforms;
- duplicate object identifiers;
- scene-origin review cases;
- other findings already classified as review-only or unsafe.

Those cases either require additional representation semantics, human review, or a separate safety
contract. They should not be forced into an implementation wave merely to keep the wave number
moving.

## Current Blender status — CLOSED

The current declared Blender capability track is closed.

Final closure records merged into main:
- PR #125 — next-capability discovery;
- PR #126 — scene/profile compliance evidence design;
- PR #128 — post-scene-profile capability discovery;
- PR #129 — hierarchy-cycle determinism defect.

The discovery record concluded **no immediate Blender extension is justified**. The remaining finding surface is review-only, unsafe, contract-blocked, or not representable under the frozen canonical producer. The hierarchy-cycle issue was handled separately as a concrete determinism defect and is now closed.

There is therefore no implementation-authorized Wave 16 at this checkpoint.

### Next engineering focus

The next active engineering track is the separately maintained Unreal work, including the Unreal-Aider development surface. Do not mix Unreal implementation into Blender correction/extraction contracts.

The Blender track should now be treated as a stable execution/observation capability. Future Blender changes require a concrete defect or a separately approved contract/design gate.

## Repository-state hygiene

Historical dated handoffs may contain superseded status. Reconcile them against current main before using them as operational instructions.

## Frozen boundaries

Unless a separately approved design gate exists, do not reopen:

- planning/blender/bpy_extraction.py;
- planning/blender/extraction_payload.py;
- planning/blender/scene_model.py;
- Temporal representation or schema semantics;
- correction authorization semantics;
- correction receipt schema;
- persistence / rollback / recovery;
- workflow / action-runner authority;
- Unreal integration.

A concrete correctness defect may reopen a frozen boundary, but that requires its own evidence and
must not be smuggled into an unrelated correction wave.
