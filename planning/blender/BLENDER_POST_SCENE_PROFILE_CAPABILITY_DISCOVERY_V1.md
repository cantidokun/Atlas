# Blender Post-Scene/Profile Capability Discovery v1

**Status: DISCOVERY ONLY — NO IMPLEMENTATION AUTHORIZED**

- Base branch: `main`
- Exact base commit: `1e546727dc590dcfca1cda84eccc0be138f85442`
- Discovery head under review: `fa73570aacb568a73dfca5b18d733549a7ae7b7b` (prior revision)
- Scope: close the remaining Blender capability surface after PR #127 and determine whether another bounded milestone is justified.
- This document does not authorize a correction, schema, extraction, Temporal, Unreal, persistence, recovery, workflow, or action-runner change.

## 1. Current checkpoint and traceability

PR #127 is merged into `main` at merge commit `1e546727dc590dcfca1cda84eccc0be138f85442`.

The merged Scene/Profile Compliance Evidence Boundary v1 provides operator-gated read-only evidence for:

- OBJECT_COLLECTION_INVALID
- OBJECT_NAME_INVALID
- SCENE_UNIT_INVALID
- zero-scale OBJECT_TRANSFORM_INVALID
- dangling-parent OBJECT_HIERARCHY_INVALID
- MESH_SCALE_OUT_OF_RANGE boundary/negative evidence
- missing-role readiness state
- OBJECT_BOUNDS_OVERLAP boundary evidence
- exact/ULP envelope behavior
- no-save/no-mutation and exact engine/build identity evidence

The existing non-manifold evidence boundary is merged in PR #124 at `6e400378e4175661877575d522033c0b29f3173c`. Earlier discovery material that proposed non-manifold as the next capability is historical and is not reused here.

Two governing discovery/design records remain on open branches rather than `main`:

- PR #125, discovery: cleared head `9e30e46d4244c6a9af38662681583c7168328ed7`.
- PR #126, design: head `b35acec7c962a6e9f7b875fed7e9874402c02694`.

Their established facts are restated below where needed so this closing discovery remains traceable even though those records are not ancestors of the current base.

## 2. Frozen authority boundaries

This discovery must not reopen or silently alter:

- `planning/blender/bpy_extraction.py`
- `planning/blender/extraction_payload.py`
- `planning/blender/scene_model.py`
- Temporal representation/schema semantics
- correction authorization semantics
- correction receipt schema
- persistence, rollback, or recovery
- workflow/action-runner authority
- Unreal integration

A concrete correctness defect may justify a separately named bounded defect gate, but that is outside this capability discovery.

## 3. Authoritative finding/correction inventory

The current correction mapping contains 18 finding codes. The inventory below is complete; OBJECT_HIERARCHY_INVALID is split into its two relevant semantic cases.

| Finding | Current classification | Current correction/proposal | Current disposition |
|---|---|---|---|
| MESH_INVALID_INDEX | REQUIRES_REVIEW | none | Live-representable for negative/out-of-range authored indices; no correction target; no immediate extension |
| MESH_DUPLICATE_FACE | DETERMINISTIC | REMOVE_DUPLICATE_FACE; auto-propose true | Already closed by live correction gate; no new family |
| MESH_DEGENERATE_FACE | DETERMINISTIC | REMOVE_DEGENERATE_FACE; auto-propose true | Already closed by live correction gate; no new family |
| MESH_DUPLICATE_VERTEX | REQUIRES_REVIEW | REPAIR_MERGE_VERTEX; auto-propose false | Correction live-validated; no new family |
| MESH_WINDING_INCONSISTENT | HEURISTIC | REPAIR_FACE_WINDING; auto-propose true | Already closed by W2 live gate; no new family |
| MESH_NON_MANIFOLD_EDGE | REQUIRES_REVIEW | FLAG_NON_MANIFOLD_FOR_REVIEW | Closed by PR #124; no repeat |
| MESH_SCALE_OUT_OF_RANGE | REQUIRES_REVIEW | FLAG_SCALE_FOR_REVIEW | Evidence closed by PR #127; no repeat |
| MESH_NORMAL_INCONSISTENT | REQUIRES_REVIEW | REPAIR_NORMAL_CONSISTENCY; auto-propose false | Contract-blocked by frozen producer representation |
| SCENE_UNIT_INVALID | HEURISTIC | NORMALIZE_UNIT_METADATA; auto-propose true | Evidence closed by #127; correction live-validated by Wave 8; no new family |
| SCENE_ORIGIN_INVALID | REQUIRES_REVIEW | FLAG_ORIGIN_FOR_REVIEW | Not live-representable from frozen producer; not a capability candidate |
| SCENE_BOUNDS_EMPTY | REQUIRES_REVIEW | none | Unproduced vocabulary; no independent evidence boundary to add |
| OBJECT_NAME_INVALID | HEURISTIC | RENAME_OBJECT; auto-propose true | Evidence closed by #127; correction live-validated by Wave 9; no new family |
| OBJECT_HIERARCHY_INVALID (dangling) | REQUIRES_REVIEW | REPAIR_PARENT_REFERENCE | Evidence closed by #127; correction already bounded |
| OBJECT_HIERARCHY_INVALID (cycle) | UNSAFE_TO_AUTOMATE | none | Not live-representable; separate determinism defect routing required |
| OBJECT_BOUNDS_OVERLAP | REQUIRES_REVIEW | FLAG_BOUNDS_OVERLAP_FOR_REVIEW | Evidence closed by #127; no repeat |
| OBJECT_COLLECTION_INVALID | REQUIRES_REVIEW | RESTRUCTURE_COLLECTION; auto-propose false | Evidence closed by #127; correction remains ambiguous; no new family |
| OBJECT_ID_DUPLICATE | UNSAFE_TO_AUTOMATE | none | Not live-representable under current Blender identity authority |
| OBJECT_TRANSFORM_INVALID | UNSAFE_TO_AUTOMATE | none | Zero-scale evidence closed by #127; no generic repair candidate |
| DIGITAL_TWIN_READINESS_FAILED | source-row ambiguity | none | Not a produced finding; readiness is validation state/reason |

Note: `DIGITAL_TWIN_READINESS_FAILED` is grouped as OUT_OF_SCOPE by the correction-mapping module docstring, while its actual mapping row carries `REQUIRES_REVIEW`, no correction type, and auto-propose false. This pre-existing source ambiguity is recorded rather than silently normalized.

## 4. Existing deterministic and live-gate coverage

The following existing correction/evidence families are already closed and must not be rediscovered as new capability:

- `MESH_DUPLICATE_FACE` — `tests/test_live_blender_w1_w1b_face_removal_gate.py`
- `MESH_DEGENERATE_FACE` — `tests/test_live_blender_w1_w1b_face_removal_gate.py`
- `MESH_WINDING_INCONSISTENT` — W2 live gate
- `MESH_DUPLICATE_VERTEX` — Wave 7 / merge-vertex live validation
- `MESH_NON_MANIFOLD_EDGE` — PR #124 live evidence boundary
- `SCENE_UNIT_INVALID` — Wave 8 correction gate and PR #127 evidence
- `OBJECT_NAME_INVALID` — Wave 9 correction gate and PR #127 evidence
- zero-scale `OBJECT_TRANSFORM_INVALID` — PR #127 evidence
- dangling-parent `OBJECT_HIERARCHY_INVALID` — PR #127 evidence
- `MESH_SCALE_OUT_OF_RANGE` — PR #127 evidence
- `OBJECT_BOUNDS_OVERLAP` — PR #127 evidence
- `OBJECT_COLLECTION_INVALID` — PR #127 evidence

PR #127's merged live gate covers A01-A17 with exact finding-code/readiness assertions, measured payloads, effective profile identity, canonical input/report digests, raw-state no-mutation checks, and exact Blender 4.4.3 build identity.

## 5. Canonical representation constraints

The current producer contract intentionally omits unsupported normal/UV/local-frame semantics. In particular, normals, UVs, and `local_frame_id` are not emitted by the frozen v1 producer.

Therefore:

- A capability requiring canonical normal semantics is a contract-reopen problem, not a Blender milestone.
- Identity cannot be fabricated by mutating extracted evidence: current object identity is derived from the Blender object name, and Blender enforces unique names by suffixing duplicates.
- Scene-origin validity depends on producer fields not emitted by the frozen extractor.
- Scene bounds-empty is not a produced canonical finding; readiness state/reason is the observable for geometry-free/readiness conditions.
- No candidate may introduce repair authority, scheduler/retry/recovery authority, persistence, or workflow authority.

## 6. Blender 4.4.3 representability findings

The following determinations are based on the merged production code at this base and Blender 4.4.3 behavior.

### MESH_INVALID_INDEX

Negative and out-of-range indices are live-representable: Blender `from_pydata` accepts authored faces such as `(0,1,9)` and `(-1,0,1)`; extraction preserves the authored face and the kernel can emit `MESH_INVALID_INDEX` alongside `MESH_DEGENERATE_FACE`.

Repeated indices are refused by the canonical parser as `SceneReportInputError`, and non-integer indices are rejected by Blender's mesh API. There is no correction policy. This is evidence-only at most, and the current evidence shows no operational need that justifies a new milestone.

**Disposition: NO IMMEDIATE EXTENSION JUSTIFIED.**

### MESH_NORMAL_INCONSISTENT

The producer omits normals by contract, and the correction mapping explicitly defers normal consistency because the kernel does not own per-face normal semantics.

**Disposition: CONTRACT-BLOCKED; no Blender capability milestone.**

### OBJECT_ID_DUPLICATE

Under current producer semantics, `object_id` is the source object name. Blender prevents two objects from retaining the same name in the same namespace by suffixing duplicates (for example, `.001`).

**Disposition: NOT LIVE-REPRESENTABLE; no action.**

### SCENE_BOUNDS_EMPTY

No producer in `planning/` emits this finding as an observed scene condition; it exists in the vocabulary/mapping but not as a producer-backed evidence path. Geometry-free scenes instead expose readiness/validation state and reason.

**Disposition: UNPRODUCED CONTRACT/INTERFACE GAP; no capability milestone.**

### OBJECT_HIERARCHY_INVALID (cycle)

Blender's live parent assignment does not form the requested parent cycle; the attempted cycle assignment reads back as no cycle in the tested 2- and 3-cycle cases. The condition is therefore not live-representable through normal Blender construction and remains unsafe to automate.

A separate determinism defect is recorded in §7.

**Disposition: UNSAFE + NOT LIVE-REPRESENTABLE; no correction capability.**

### OBJECT_TRANSFORM_INVALID beyond zero scale

NaN is retained by RNA but refused by the frozen extractor. Infinity is clamped by RNA to a finite envelope and surfaces as evidence rather than preserving the authored infinity. The mapping classifies this family as unsafe to automate.

**Disposition: NO GENERIC REPAIR CANDIDATE.**

### SCENE_ORIGIN_INVALID

The predicate requires scene fields such as coordinate frame/world bounds that the frozen producer does not emit. The merged #127 A01-A17 gate therefore does not exercise this finding.

**Disposition: NOT LIVE-REPRESENTABLE FROM THE FROZEN PRODUCER; no capability milestone.**

## 7. Separate named hierarchy-cycle determinism defect

The previous discovery work identified a correctness defect that must not be lost merely because it is not a capability.

`scene_health._collect_hierarchy_validity` iterates an unordered object-ID set before DFS. For synthetic cyclic inputs, this can make the resulting cycle findings and report digests depend on `PYTHONHASHSEED`.

This is a deterministic correctness defect in shipped code, not a new Blender capability and not a correction-authority request. It is outside this discovery's implementation scope.

**Required routing:** create a separately named bounded defect decision/gate that either:
1. applies an ordering fix and adds a `PYTHONHASHSEED` determinism test, with exact-head verification; or
2. records an explicit, reviewable deferral.

No repair semantics, authority expansion, or capability milestone is implied by this routing.

## 8. Candidate disposition / adversarial refusal matrix

| Candidate | Live truth | Canonical fit | Safety/authority | Terminal disposition |
|---|---|---|---|---|
| MESH_INVALID_INDEX | Yes, negative/out-of-range only | Existing representation | Read-only; no correction target | NO IMMEDIATE EXTENSION |
| MESH_NORMAL_INCONSISTENT | Not observable under frozen producer | Requires normal semantics | Contract reopen required | CONTRACT-BLOCKED |
| OBJECT_ID_DUPLICATE | No under Blender identity semantics | Existing identity authority prevents condition | Unsafe to manufacture | NOT LIVE-REPRESENTABLE |
| SCENE_BOUNDS_EMPTY | No producer-backed finding | Existing readiness state is the observable | No added operational value | UNPRODUCED / NO ACTION |
| hierarchy cycle | No live Blender construction path | Existing model can contain synthetic canonical data | Unsafe; no repair | NOT LIVE-REPRESENTABLE + separate defect gate |
| SCENE_ORIGIN_INVALID | No producer-backed predicate inputs | Frozen extractor omits required fields | Contract reopen would be required | NOT LIVE-REPRESENTABLE |
| already-closed #124/#127 findings | Yes | Already evidenced | Duplicate gate adds no authority/value | CLOSED / NO REPEAT |

Adversarial cases that must refuse rather than fabricate evidence include parser-refused repeated indices, non-integer indices, manufactured duplicate identities, forced hierarchy cycles, and unsupported normal semantics.

## 9. No-save / no-mutation implications

Discovery remains read-only. A valid future live probe may create disposable in-memory fixture state, observe it, and dispose without saving. It must not mutate persistent scene data, authorize correction, or imply a production mutation path.

No candidate in this discovery justifies reopening the correction executor or introducing a new correction family.

## 10. Authority and frozen-boundary audit

The change remains documentation-only. No production, test, workflow, Temporal, Unreal, authorization, receipt, persistence/recovery, or action-runner file is modified by this discovery.

The discovery proposes no:

- new correction family;
- automatic repair;
- planner/scheduler;
- retry or rollback;
- persistence/recovery authority;
- workflow/action-runner authority;
- Temporal schema or representation change;
- Unreal integration;
- extraction contract expansion.

Anything requiring new canonical representation semantics is explicitly routed as a contract-reopen question rather than smuggled into a capability milestone.

## 11. Final capability decision

The complete inventory and representability analysis leave no bounded, non-duplicative, live-representable Blender capability with demonstrated operational value that survives the frozen boundaries.

Therefore:

**OUTCOME B — NO IMMEDIATE BLENDER EXTENSION.**

This closes the Blender extension track at this checkpoint. It does **not** mean Blender support is abandoned; it means the current evidence does not justify another capability milestone without reopening a frozen contract or introducing unsafe/ambiguous authority.

The hierarchy-cycle determinism defect in §7 remains separately routed and must not be silently closed by this outcome.

## 12. Promotion gate and non-claims

This document is still **DISCOVERY ONLY — NO IMPLEMENTATION AUTHORIZED**.

Promotion of this discovery requires:

1. independent architectural/red-team review of the exact corrected discovery head;
2. a CLEAR verdict that the record is complete and traceable.

Because no candidate survives, a follow-on implementation design is **not** justified. A CLEAR result closes the capability discovery; it does not authorize implementation.

This document does not claim:

- that any remaining finding should be corrected automatically;
- that unsupported normal/UV semantics should be added;
- that another correction wave is required;
- that Wave 16 implementation is authorized;
- that the hierarchy-cycle determinism defect is resolved;
- that Blender development as a whole must stop.

**Expected next engineering decision:** route the hierarchy-cycle determinism defect separately, then move the primary engineering focus to the next Atlas layer unless a new, independently justified Blender requirement appears.
