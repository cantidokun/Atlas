# Atlas Blender — Next Capability Discovery

Status: DISCOVERY ONLY — no implementation authorized
Base: main @ 6e400378e4175661877575d522033c0b29f3173c
Branch: design/blender-next-capability-discovery

## 1. Purpose

This document is the post-PR-124 discovery pass for the next bounded Blender capability.

It is an inventory and decision record only. It does not authorize a correction, reopen the canonical extraction contract, alter Temporal semantics, change correction mapping, add a workflow, or change execution authority.

The discovery asks:

> After Read-Only Non-Manifold Evidence Boundary v1, what remaining capability has enough canonical representation, deterministic semantics, real Blender representability, independent testability, and safety evidence to justify a dedicated design gate?

The answer must be evidence-based. "Wave 16" is intentionally not assigned until a separate design package is independently cleared.

## 2. Authoritative baseline

Current main includes PR #124:

- merge commit: 6e400378e4175661877575d522033c0b29f3173c
- Read-Only Non-Manifold Evidence Boundary v1 is merged.
- Blender 4.4.3 live evidence for the non-manifold boundary is closed.
- No implementation-authorized new correction family exists.

The Blender architecture remains:

canonical extraction
→ deterministic scene health / findings
→ bounded correction proposal
→ authorization
→ canonical execution contract
→ real Blender adapter
→ postcondition verification / receipt
→ Temporal observation

Frozen boundaries remain:

- planning/blender/bpy_extraction.py
- planning/blender/extraction_payload.py
- planning/blender/scene_model.py
- Temporal representation and StateDelta semantics
- correction authorization semantics
- correction receipt schema
- persistence / rollback / recovery
- workflow / action-runner authority
- Unreal integration

## 3. Current finding inventory

The current FindingCode vocabulary contains:

### Mesh

- MESH_INVALID_INDEX
- MESH_DUPLICATE_VERTEX
- MESH_DUPLICATE_FACE
- MESH_DEGENERATE_FACE
- MESH_NON_MANIFOLD_EDGE
- MESH_WINDING_INCONSISTENT
- MESH_NORMAL_INCONSISTENT
- MESH_SCALE_OUT_OF_RANGE

### Scene

- SCENE_UNIT_INVALID
- SCENE_ORIGIN_INVALID
- SCENE_BOUNDS_EMPTY

### Object / organization

- OBJECT_ID_DUPLICATE
- OBJECT_NAME_INVALID
- OBJECT_HIERARCHY_INVALID
- OBJECT_BOUNDS_OVERLAP
- OBJECT_TRANSFORM_INVALID
- OBJECT_COLLECTION_INVALID

### Derived readiness

- DIGITAL_TWIN_READINESS_FAILED

The mapping remains closed and explicit. Existing executable correction families are already bounded; review-only and unsafe findings do not acquire mutation authority merely because they are observable.

## 4. Capability closure audit

### 4.1 Topology intelligence

Status: CLOSED for the currently justified read-only boundary.

Wave 5 topology intelligence already provides:

- edge counts;
- boundary/manifold/non-manifold counts;
- maximum edge valence;
- edge-valence histogram;
- face cardinality;
- connected components;
- isolated vertices;
- deterministic serialization.

PR #124 added the missing real-Blender evidence boundary for MESH_NON_MANIFOLD_EDGE and reconciled it with the existing topology metrics.

Conclusion:

- no second topology authority should be created;
- no automatic non-manifold repair should be proposed;
- topology does not currently justify another correction wave.

### 4.2 Canonical extraction fidelity

Status: FROZEN.

The producer deliberately omits:

- normals;
- UVs;
- local-frame data.

Material-slot representation was separately closed by Wave 14 within the existing extraction contract.

Conclusion:

A normal/UV correction or a richer normal/UV live boundary would require a separate representation-fidelity design. It must not be smuggled into an ordinary correction wave.

### 4.3 Existing bounded corrections

The following correction/action families are already live-validated:

- REMOVE_DUPLICATE_FACE
- REMOVE_DEGENERATE_FACE
- REPAIR_FACE_WINDING
- REPAIR_MERGE_VERTEX
- REPAIR_PARENT_REFERENCE
- REMOVE_ISOLATED_VERTICES
- REMOVE_DUPLICATE_VERTICES
- NORMALIZE_UNIT_METADATA
- RENAME_OBJECT
- RESTRUCTURE_COLLECTION
- REPAIR_PARENT_CYCLE

These should not be duplicated under a new generic executor or generalized into an open-ended correction system.

### 4.4 Review / unsafe findings

The following remain intentionally non-automated:

- MESH_INVALID_INDEX
- MESH_DUPLICATE_VERTEX automatic dispatch
- MESH_NON_MANIFOLD_EDGE
- MESH_SCALE_OUT_OF_RANGE
- MESH_NORMAL_INCONSISTENT
- SCENE_ORIGIN_INVALID
- SCENE_BOUNDS_EMPTY
- OBJECT_BOUNDS_OVERLAP
- OBJECT_COLLECTION_INVALID automatic dispatch
- OBJECT_ID_DUPLICATE
- OBJECT_TRANSFORM_INVALID
- OBJECT_HIERARCHY_INVALID unsafe cycle branch
- DIGITAL_TWIN_READINESS_FAILED

No finding in this group has a uniquely justified generic correction based on the current contract.


## 4.5 Finding-code producer / representability classification

The discovery must distinguish a canonical finding predicate from a state that Blender 4.4.3 can actually produce at the live boundary. The following table is the authoritative classification for this discovery pass. “Live” means the production Blender extraction path can produce the canonical state without relying on direct mutation of the canonical model. “Canonical-only” means deterministic tests can construct the state, but the Blender boundary does not currently provide a faithful producer. “Unproduced” means the vocabulary exists but no current producer emits it.

| FindingCode | Current producer / predicate | Blender 4.4.3 representability | Existing live evidence | Candidate-A treatment |
|---|---|---|---|---|
| MESH_INVALID_INDEX | `planning/blender/mesh_health.py::_collect_coordinate_validity` and `_collect_polygon_index_validity` | Canonical-only for malformed face indices; Blender mesh construction rejects/normalizes malformed references before extraction | Deterministic only | Out of scope |
| MESH_DUPLICATE_VERTEX | `mesh_health.py::_collect_duplicate_vertices` | Live-representable | PR #124 topology gate exercises topology boundary; correction family separately live-validated | Out of scope |
| MESH_DUPLICATE_FACE | `mesh_health.py::_collect_duplicate_faces` | Live-representable | Correction/live family coverage exists | Out of scope |
| MESH_DEGENERATE_FACE | `mesh_health.py::_collect_degenerate_faces` | Live-representable | Correction/live family coverage exists | Out of scope |
| MESH_NON_MANIFOLD_EDGE | `mesh_health.py::_collect_non_manifold_edges` | Live-representable | PR #124 closed | Closed |
| MESH_WINDING_INCONSISTENT | `mesh_health.py::_collect_winding_consistency` | Live-representable | Correction/live family coverage exists | Out of scope |
| MESH_NORMAL_INCONSISTENT | `mesh_health.py::_collect_normal_consistency` | Canonical-only for the frozen Blender v1 extraction path because normals are omitted | Deterministic canonical tests only | Out of scope / representation boundary |
| MESH_SCALE_OUT_OF_RANGE | `mesh_health.py::check_mesh_in_envelope`; per-world-vertex envelope predicate with profile tolerance | Live-representable | Existing real asset proves positive path; no adversarial negative boundary yet | **NEW** negative/boundary evidence |
| SCENE_UNIT_INVALID | `scene_health.py::_collect_unit_validity` | Live-representable, subject to Blender unit-token mapping | Existing live probes create invalid-unit state but do not assert this production finding | **NEW/PARTIAL** |
| SCENE_ORIGIN_INVALID | `scene_health.py::_collect_origin_validity` | Non-finite world-bounds branch is not a normal live Blender producer; treat as canonical-only for this gate | Deterministic only | Out of scope |
| SCENE_BOUNDS_EMPTY | No current producer in the scene-health kernel | **Unproduced** | None | Remove from matrix; track as vocabulary/contract gap |
| OBJECT_ID_DUPLICATE | `scene_health.py::_collect_duplicate_object_ids` | Not faithfully live-producible through Blender object names because Blender enforces unique names (e.g. duplicate “pitch” becomes “pitch.001”) | Deterministic only | Out of scope |
| OBJECT_NAME_INVALID | `scene_health.py::_collect_object_name` | Live-representable | Existing live probe can create invalid name but did not assert kernel finding | **NEW/PARTIAL** |
| OBJECT_HIERARCHY_INVALID | `scene_health.py::_collect_hierarchy_validity` | Dangling parent is live-representable; a persistent Blender parent cycle is not representable through the normal RNA path because Blender clears/normalizes the attempted assignment | Existing live probe for hierarchy states; kernel finding assertion is missing | **NEW** dangling-parent only |
| OBJECT_BOUNDS_OVERLAP | `scene_health.py::_collect_bounds_overlap` using world-space AABBs | Live-representable, but semantics are deliberately conservative | Deterministic geometry tests; clean real asset intentionally uses disjoint probes | **NEW/PARTIAL** only for live overlap/contact boundary evidence |
| OBJECT_TRANSFORM_INVALID | `scene_health.py::_collect_transform_validity` | Zero-scale branch is live-representable. Non-finite location/scale is not a reliable Blender live fixture: NaN is rejected and infinity may be clamped/normalized at the RNA boundary | Deterministic non-finite/zero-scale tests; existing live transform probes are valid-state evidence | **NEW** zero-scale only |
| OBJECT_COLLECTION_INVALID | `scene_health.py::_collect_object_collection` | Live-representable | Existing live probe creates disallowed collection but does not assert kernel finding | **NEW/PARTIAL** |
| DIGITAL_TWIN_READINESS_FAILED | `planning/blender/digital_twin_readiness.py::evaluate_readiness` derives state/reason from findings/profile | Live-representable as a derived state when a live finding/readiness condition is produced | Existing real asset proves positive readiness; negative readiness cases are not systematically asserted | **NEW** missing-required-role/readiness reason |

## 5. Candidate discovery

### Candidate A — Read-Only Scene/Profile Compliance Evidence Boundary

This candidate survives the independent review, but the scope is narrower than the original discovery draft. The implementation target is **finding-side evidence for live-representable profile/scene predicates**, not a generic replay of the existing clean real-asset gate.

The genuinely new evidence targets are:

- `OBJECT_COLLECTION_INVALID` from a real extracted Blender object;
- `OBJECT_NAME_INVALID` from a real extracted Blender object;
- `SCENE_UNIT_INVALID` from the real Blender unit mapping;
- zero-scale `OBJECT_TRANSFORM_INVALID`;
- dangling-parent `OBJECT_HIERARCHY_INVALID`;
- negative `MESH_SCALE_OUT_OF_RANGE` envelope evidence;
- `DIGITAL_TWIN_READINESS_FAILED` for a missing required role, including the readiness reason;
- envelope tolerance acceptance/rejection at the exact inclusive boundary;
- non-containment AABB overlap plus explicit contact/coincidence/containment controls.

The following are **not** new value and must not be presented as such:

- clean positive extraction;
- ordinary world-space transform fidelity;
- no-save proof;
- digest reproducibility;
- valid role presence;
- valid naming/collection/unit examples.

Those are already covered by the existing real-.blend gate and other live/deterministic coverage. The new gate must add negative or boundary evidence and assert the production kernel's actual FindingCodes/ValidationState.

#### 5.1 Existing-live evidence inventory

| Existing evidence | What it already proves | Candidate-A relation |
|---|---|---|
| `tests/test_live_blender_real_asset_gate.py` | Real frozen .blend → production extraction → SceneModel → `run_scene_health`; exact object set, units, topology, world-space transforms, hierarchy chain, empty findings, `production_ready`, digest reproducibility, host-side no-save hash and state digest | **PARTIAL/DUPLICATE** for clean positive path; do not duplicate |
| Existing operator-gated live scene-health probes | Real Blender can create invalid name, disallowed collection, invalid unit, dangling-parent/cycle attempts and other fixture states | **PARTIAL**: fixture truth exists, but production FindingCode/report assertions are missing |
| Deterministic scene-health tests | Naming, duplicate IDs, units, collections, zero-scale, hierarchy, overlap/containment predicates | **PARTIAL**: canonical semantics exist; live representation is the missing boundary |
| PR #124 topology gate | Real Blender non-manifold production finding and topology coherence | **DUPLICATE** for topology; excluded |
| Temporal and correction live workflows | Their own bounded live contracts | **DUPLICATE / out of scope** |

Matrix items shall be explicitly tagged **NEW**, **PARTIAL**, or **DUPLICATE** in the implementation design.

#### 5.2 Exact profile and policy identity

The evidence run shall record the complete profile policy, not merely `profile.name`. The current report identity binds `profile_name` and the validator/report version, while the profile factory permits overrides. Therefore the gate must freeze and record:

- profile name;
- exact envelope min/max;
- allowed units;
- naming pattern;
- allowed collections;
- required roles;
- ready-blocking codes;
- envelope tolerance;
- any other profile fields consumed by the selected predicates.

The declared `permitted_hierarchy_depth`, `expected_up_axis`, and `expected_ground_level` are currently inert in the evaluated production path and are **not** evidence claims for this gate. Their declared presence must not be confused with enforcement.

#### 5.3 Exact transform and envelope predicates

For `OBJECT_TRANSFORM_INVALID`, the live fixture is limited to the production predicate `abs(scale) < 1e-9) (zero scale). Non-finite transform cases remain canonical-only for this evidence boundary because Blender 4.4.3 does not reliably preserve the intended malformed state through RNA.

For `MESH_SCALE_OUT_OF_RANGE`, the live fixture must be defined in world space. The production predicate accepts each coordinate when:

`min - tolerance <= coordinate <= max + tolerance`

with the default tolerance of **0.05 m**, inclusive. The gate must test:

- a point exactly at the lower/upper tolerated boundary: accepted;
- a point just beyond the tolerated boundary: rejected;
- a clearly outside point: rejected.

The finding's measured payload is mesh/vertex-oriented: the current producer records `mesh_id` and vertex index/world coordinate rather than an `object_id`. The design must assert this exact identity convention.

#### 5.4 Exact AABB overlap semantics

The production overlap predicate is world-space AABB based. The implementation design must explicitly test and document:

- non-containment overlap: finding expected;
- pure containment: no finding;
- coincident/equal AABBs: no finding because mutual containment suppresses the signal;
- exact face/edge/point contact: the current sweep excludes exact min-x contact because the sweep condition is strict `min_x < max_x`; therefore a flush contact can be a deliberate false-negative class and must not be silently described as overlap evidence;
- rotated geometry: overlap is against the transformed world-space AABB, so AABB inflation relative to oriented geometry is expected and must be documented as a limitation, not treated as exact geometric intersection.

The gate must use independently known fixture geometry and must not reimplement the production overlap algorithm as a second authority.

#### 5.5 Hierarchy cycle removed from Candidate A

A persistent hierarchy cycle is **not** a live Candidate-A case. Blender 4.4.3's normal RNA parent assignment normalizes/clears the attempted cycle, so the intended canonical cycle never reaches the extraction boundary.

Separately, the canonical hierarchy-cycle evaluator currently iterates a set of object IDs. That makes cycle finding order/digest behavior sensitive to `PYTHONHASHSEED` for synthetic cyclic scenes. This is a **determinism defect to record and gate separately**, not a defect to repair inside the read-only evidence milestone.

Candidate A must not claim to validate hierarchy-cycle live behavior.

#### 5.6 Unproduced and declared-but-inert profile semantics

`SCENE_BOUNDS_EMPTY` currently has no producer in the planning code and therefore must be removed from the live evidence matrix and tracked as a vocabulary/contract gap.

Likewise, `permitted_hierarchy_depth`, `expected_up_axis`, and `expected_ground_level` are declared profile fields without a current consumer in the evaluated scene-health path. They are recorded as **declared but unenforced**, not tested as if they were active policy.

#### 5.7 Evidence mechanism and authorization

The live evidence gate is operator-authorized and is not assumed to run in ordinary deterministic CI. The implementation design must choose one explicit mechanism:

1. run the pinned SHA manually with the existing operator-gated harness and persist the complete evidence artifact; or
2. add an explicitly authorized workflow invocation, which is a separate workflow-authority change and therefore outside the read-only implementation unless separately approved.

No claim of exact-head live validation may be made merely because deterministic CI is green or because a live test exists but was skipped.

#### 5.8 Standard no-save / no-mutation proof

The gate shall adopt the existing standard rather than invent another:

- host-side SHA-256 of the frozen .blend before and after;
- raw Blender-state snapshot equality across the extraction/report operation;
- explicit absence of newly created `.blend` or `.blend1` artifacts in the authorized working location;
- subprocess failure on unexpected mutation rather than accommodation.

The PR #124 topology gate and `tests/test_live_blender_real_asset_gate.py` are precedents for this evidence pattern.

### Candidate B — MESH_NORMAL_INCONSISTENT / normal fidelity

The kernel can analyze normals when a canonical MeshModel contains per-face normals, but the frozen Blender producer intentionally does not emit normals in v1.

A real Blender normal probe therefore cannot honestly become a canonical normal-fidelity claim without reopening extraction semantics.

Disposition:

**BLOCKED BY REPRESENTATION CONTRACT.**

Any future work belongs in a dedicated representation-fidelity discovery, not a correction wave.

### Candidate C — MESH_INVALID_INDEX raw-engine investigation

The canonical model can carry range-invalid indices sufficiently for the kernel finding, while Blender's native mesh construction may reject or normalize some malformed states before extraction.

This makes raw-engine malformed-index evidence interesting, but it does not provide a correction policy. A correction would require deciding what an invalid reference should become.

Disposition:

**LOW-VALUE FOR THE NEXT MILESTONE; REVIEW-ONLY.**

A future investigation can be justified if malformed imported assets become an observed production problem.

### Candidate D — OBJECT_BOUNDS_OVERLAP evidence

This is not a separate next milestone. The independent review established that the useful uncovered portion of D is the live boundary/contact evidence, which is now folded into Candidate A.

The production semantics remain policy-dependent: overlap is not inherently an error, pure containment is suppressed, and no generic correction target exists.

Disposition:

**FOLDED INTO CANDIDATE A AS A NARROW LIVE-EVIDENCE CASE; NO SEPARATE CORRECTION DESIGN.**

### Candidate E — SCENE_ORIGIN_INVALID / MESH_SCALE_OUT_OF_RANGE correction

Both are policy/profile dependent.

The profile already supplies the envelope and expected frame information, but the finding itself does not authorize a target-frame or geometry remap.

Disposition:

**NO CORRECTION DESIGN JUSTIFIED.**

A read-only profile evidence gate can cover the scale/envelope aspect as part of Candidate A.

### Candidate F — OBJECT_COLLECTION_INVALID / OBJECT_NAME_INVALID extension

Collection and naming are already represented and correction families exist with explicit target semantics.

A new generic organization wave would duplicate closed capability.

Disposition:

**CLOSED / DO NOT DUPLICATE.**

### Candidate G — new topology correction

No unique safe correction exists for arbitrary non-manifold, boundary, n-gon, disconnected-component, or similar topology.

Disposition:

**REJECTED AS A DISCOVERY DIRECTION.**

## 6. Cross-cutting gap discovered

The strongest remaining gap is not another correction primitive.

It is the distance between:

- canonical deterministic scene-health semantics;
- real Blender extraction;
- profile-specific world-space validation;
- readiness evaluation.

Topology now has a dedicated real-engine evidence boundary. Correction families have dedicated live gates. Temporal has real Blender evidence.

Scene/profile health is comparatively less systematically exercised at the real Blender boundary, especially for intentional negative and boundary cases.

This makes a read-only Scene/Profile Compliance Evidence Boundary the most coherent next investigation.

## 7. Proposed discovery target

Provisional name:

**Read-Only Scene/Profile Compliance Evidence Boundary v1**

This is a discovery target only.

It should investigate whether one disposable Blender harness can exercise the existing production path:

Blender fixture
→ frozen extraction
→ canonical SceneModel
→ run_scene_health(profile)
→ SceneReport
→ readiness evaluation

while independently checking raw Blender observations.

The harness should not implement its own scene-health rules as an alternative authority. Independent evidence should be used only to establish fixture truth and selected engine-boundary facts.

## 8. Required questions for the next design gate

Before implementation authorization, the design must answer:

1. Which existing profile semantics are actually observable from Blender 4.4.3?
2. Which semantics are canonical versus derived versus raw-boundary-only?
3. How is each negative fixture independently known to be invalid?
4. How are envelope boundary/tolerance cases constructed exactly?
5. Can Blender represent the intended invalid-transform, invalid-unit, collection, naming, and hierarchy cases without silently normalizing them?
6. Which hierarchy-invalid states can Blender physically represent, and which must remain canonical-only tests?
7. How are world-space coordinates independently recomputed from raw Blender state?
8. How are overlap and containment independently distinguished?
9. How are required semantic roles tested without turning the harness into a second readiness implementation?
10. How is the existing real-.blend gate reconciled so the new gate adds evidence rather than duplicates it?
11. What exact no-save/no-mutation proof is required?
12. What exact profile/configuration is frozen for the evidence run?
13. What cases must explicitly remain out of scope?
14. Does this capability warrant promotion to a future correction design, or should it remain permanently read-only?

## 9. Non-claims

This discovery does not claim:

- that every scene-health finding is an error;
- that profile non-compliance implies a unique correction;
- that an envelope violation should be fixed by moving, scaling, or clipping geometry;
- that object overlap authorizes repositioning;
- that a naming or collection finding authorizes automatic organization;
- that Blender can represent every malformed canonical state;
- that raw Blender observations expand the canonical extraction contract;
- that readiness is correction authority;
- that a live evidence gate authorizes mutation;
- that Temporal should participate in this gate;
- that a new correction executor is required.


## 10. Separate determinism defect record

The discovery review identified a pre-existing canonical-only determinism defect in hierarchy-cycle handling:

- `planning/blender/scene_health.py::_collect_hierarchy_validity` iterates the object-ID set without a stable ordering before DFS;
- synthetic cyclic scenes can therefore produce different finding order/content and report digests under different `PYTHONHASHSEED` values;
- Blender cannot currently represent the intended persistent cycle at the live boundary, so Candidate A cannot use the live gate to conceal or repair this issue.

This defect is **not part of Candidate A implementation scope**. It must receive a separately named deterministic test/gate decision before any production fix is proposed. The evidence milestone must preserve the existing production code and report the defect rather than patching it opportunistically.

## 11. Exact implementation-gate evidence inventory

A future implementation design must provide, for every proposed fixture:

| Case | Predicate / production path | Expected code/state | Evidence status |
|---|---|---|---|
| Clean positive | frozen extraction + `run_scene_health` | no new findings / `production_ready` | DUPLICATE — already covered |
| Disallowed collection | `_collect_object_collection` | `OBJECT_COLLECTION_INVALID` | NEW/PARTIAL |
| Invalid name | `_collect_object_name` | `OBJECT_NAME_INVALID` | NEW/PARTIAL |
| Invalid unit | `_collect_unit_validity` | `SCENE_UNIT_INVALID` | NEW/PARTIAL |
| Zero scale | `_collect_transform_validity` | `OBJECT_TRANSFORM_INVALID` | NEW |
| Dangling parent | `_collect_hierarchy_validity` | `OBJECT_HIERARCHY_INVALID` | NEW |
| Envelope exact tolerated boundary | `check_mesh_in_envelope` | no `MESH_SCALE_OUT_OF_RANGE` | NEW |
| Envelope just outside tolerance | `check_mesh_in_envelope` | `MESH_SCALE_OUT_OF_RANGE` | NEW |
| Missing required role | readiness evaluator | `DIGITAL_TWIN_READINESS_FAILED` + reason | NEW |
| Non-containment overlap | `_collect_bounds_overlap` | `OBJECT_BOUNDS_OVERLAP` | NEW/PARTIAL |
| Pure containment | `_collect_bounds_overlap` | no overlap finding | NEW negative control |
| Coincident AABB | `_collect_bounds_overlap` | no overlap finding | NEW negative control |
| Exact contact | sweep + AABB predicate | no finding under current strict sweep | NEW boundary/false-negative control |
| Rotated AABB inflation | world-space transform → AABB | documented AABB result | NEW boundary limitation |
| Hierarchy cycle | canonical evaluator only | **NOT A LIVE CASE**; separate determinism defect | REMOVED |
| Duplicate object ID | canonical `_collect_duplicate_object_ids` | **NOT A LIVE CASE** | REMOVED |
| Non-finite transform | canonical `_collect_transform_validity` | **NOT A LIVE CASE** | REMOVED |
| Scene bounds empty | no current producer | **UNPRODUCED** | REMOVED / gap record |

## 12. Promotion criteria

A future implementation design is justified only if an independent review establishes:

- exact production-path reuse;
- no canonical extraction change;
- no correction mapping change;
- no authorization change;
- no Temporal coupling;
- no persistence/workflow authority;
- independent fixture truth;
- adversarial negative controls;
- exact world-space/profile-boundary evidence;
- deterministic report/input digest evidence;
- no-save/no-mutation evidence;
- frozen-boundary audit;
- exact-head CI/live validation plan.

If those conditions cannot be met without changing the frozen extraction or profile semantics, the candidate must be stopped and converted into a separate representation/contract investigation.

## 13. Discovery conclusion

At main @ 6e400378e4175661877575d522033c0b29f3173c:

**Candidate A — Read-Only Scene/Profile Compliance Evidence Boundary v1 — remains the strongest next discovery candidate, with the scope narrowed to genuinely new live finding/readiness evidence.**

The independent review does not justify another correction wave or a new authority. It justifies a bounded read-only evidence milestone covering live-representable scene/profile predicates while explicitly excluding canonical-only, unproduced, already-closed, and non-deterministic cases.

This document does **not** authorize implementation. The separate hierarchy-cycle determinism defect is recorded as an independent issue and must not be repaired opportunistically inside Candidate A.

The next step is a **second independent architectural/red-team review of this revised discovery document**. The review must verify R-1 through R-10 from the first review, especially the per-code representability table, existing-live inventory, exact AABB semantics, profile identity binding, no-save standard, and separation of the hierarchy-cycle determinism defect. If cleared, a separate implementation design package may be written. Until then, implementation remains unauthorized.
