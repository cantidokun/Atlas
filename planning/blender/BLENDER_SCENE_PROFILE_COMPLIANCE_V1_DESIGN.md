# Atlas — Read-Only Scene/Profile Compliance Evidence Boundary v1 — Implementation Design

**Status:** DESIGN ONLY — IMPLEMENTATION NOT AUTHORIZED

**Base:** `6e400378e4175661877575d522033c0b29f3173c`

**Discovery gate:** PR #125, final CLEAR at `9e30e46d4244c6a9af38662681583c7168328ed7`

**Target capability:** Read-Only Scene/Profile Compliance Evidence Boundary v1

## 1. Purpose

This design turns the cleared Candidate A discovery into a bounded, read-only live evidence gate.

The gate will exercise the existing production path:

`Blender scene -> bpy_extraction.extract_scene -> payload_to_scene_model -> run_scene_health(scene, profile) -> readiness/report evidence`

It will not add a correction family, authorization, persistence, retry/rollback, Temporal coupling, Unreal coupling, or extraction semantics.

The purpose is specifically to close the remaining real-Blender evidence gap for live-representable scene/profile predicates that already exist in the deterministic kernel.

## 2. Exact scope

### NEW live evidence

1. `OBJECT_COLLECTION_INVALID`
2. `OBJECT_NAME_INVALID`
3. `SCENE_UNIT_INVALID`
4. zero-scale `OBJECT_TRANSFORM_INVALID`
5. dangling-parent `OBJECT_HIERARCHY_INVALID`
6. `MESH_SCALE_OUT_OF_RANGE` negative and exact-tolerance boundary behavior
7. missing-required-role readiness state
8. non-containment `OBJECT_BOUNDS_OVERLAP`
9. x-flush contact false-negative control
10. y/z-flush contact reported control
11. pure containment negative control
12. coincident AABB negative control
13. rotated-AABB inflation limitation

### Explicitly excluded

- `DIGITAL_TWIN_READINESS_FAILED` as a FindingCode — unproduced vocabulary; readiness is represented by `validation_state` and `scene_metrics["readiness_reason"]`.
- hierarchy-cycle live evidence — Blender 4.4.3 does not preserve the intended persistent cycle through normal RNA parenting.
- hierarchy-cycle determinism repair — separate defect; no production change in this milestone.
- `OBJECT_ID_DUPLICATE` live evidence — Blender object names are unique at the live boundary.
- non-finite transform live fixtures — NaN is rejected by the frozen extraction contract; ±Infinity is clamped by Blender RNA and can surface as envelope evidence.
- `MESH_INVALID_INDEX` — live-representable, but outside this scene/profile evidence milestone because it is mesh-topology scope and has no justified correction policy.
- normals/UVs/local-frame representation changes.
- any new correction or executor authority.

## 3. Frozen production path

Every live case must use the existing production functions. The test must not reimplement their predicates as a second authority.

Required path:

1. Create or load a disposable Blender scene in memory.
2. Establish the intended fixture state.
3. Call `planning.blender.bpy_extraction.extract_scene(bpy)`.
4. Convert with `planning.blender.extraction_payload.payload_to_scene_model`.
5. Run `planning.blender.kernel.run_scene_health(scene, effective_profile, include_envelope=True)`.
6. Capture the actual report/findings/readiness fields.
7. Dispose the Blender process without saving.

The gate must fail if extraction refuses the fixture rather than manufacturing a canonical state after extraction.

## 4. Effective profile identity

The gate must record the complete effective profile policy because the report currently identifies only profile name/version while the profile factory permits overrides.

The evidence record must include:

- profile name;
- envelope min/max;
- allowed units;
- naming pattern;
- allowed collections;
- required roles;
- ready-blocking codes;
- envelope tolerance;
- all other consumed policy fields;
- Blender `version_string`;
- Blender `version`;
- Blender `build_hash`;
- Blender build date/commit identity when available;
- canonical payload `schema_version`;
- validator/report format version.

For the default soccer profile, the evidence must pin:

- envelope X: [-50, 50] m
- envelope Y: [-40, 40] m
- envelope Z: [0, 12] m
- tolerance: 0.05 m
- allowed unit: METERS
- allowed collections: Field, Sidelines, Goals, Players, Structure
- required roles: pitch, goal_left, goal_right

Declared-but-inert fields `permitted_hierarchy_depth`, `expected_up_axis`, and `expected_ground_level` must not be represented as enforced evidence.

## 5. Fixture matrix

| ID | Fixture | Production path | Expected result | Classification |
|---|---|---|---|---|
| A01 | clean control | extraction + kernel | no new findings; production-ready | DUPLICATE/POSITIVE CONTROL |
| A02 | object in disallowed collection | `_collect_object_collection` | `OBJECT_COLLECTION_INVALID` | NEW |
| A03 | invalid object name | `_collect_object_name` | `OBJECT_NAME_INVALID` | NEW |
| A04 | invalid scene unit | `_collect_unit_validity` | `SCENE_UNIT_INVALID` | NEW |
| A05 | zero scale | `_collect_transform_validity` | `OBJECT_TRANSFORM_INVALID` with zero scale | NEW |
| A06 | dangling parent | `_collect_hierarchy_validity` | `OBJECT_HIERARCHY_INVALID` | NEW |
| A07 | exact upper X tolerance | `check_mesh_in_envelope` | no `MESH_SCALE_OUT_OF_RANGE` | NEW |
| A08 | one ULP+ beyond upper X tolerance | `check_mesh_in_envelope` | `MESH_SCALE_OUT_OF_RANGE` | NEW |
| A09 | exact lower X tolerance | `check_mesh_in_envelope` | no finding | NEW |
| A10 | one ULP beyond lower X tolerance | `check_mesh_in_envelope` | `MESH_SCALE_OUT_OF_RANGE` | NEW |
| A11 | missing required role | readiness composition | `validation_state="needs_review"`; readiness reason names missing role(s); no readiness FindingCode | NEW |
| A12 | non-containment overlap | `_collect_bounds_overlap` | `OBJECT_BOUNDS_OVERLAP` | NEW/PARTIAL |
| A13 | pure containment | `_collect_bounds_overlap` | no overlap finding | NEW negative control |
| A14 | coincident AABBs | `_collect_bounds_overlap` | no overlap finding | NEW negative control |
| A15 | exact x-flush contact | sweep + AABB predicate | no overlap finding | NEW boundary control |
| A16 | exact y/z-flush contact | sweep + AABB predicate | overlap finding when sweep-axis overlap remains | NEW boundary control |
| A17 | rotated AABB inflation | world transform -> AABB | overlap finding may occur despite disjoint oriented geometry | NEW limitation control |

## 6. Fixture construction requirements

### 6.1 Common fixture rules

Each case must begin from a disposable in-memory Blender scene. Fixtures must be authored independently of the expected result.

The test may use helper geometry, but expected FindingCodes must never be computed by duplicating the production predicate.

Each fixture must state:
- source Blender state;
- intended canonical state;
- expected report evidence;
- negative controls where applicable.

### 6.2 Collection

Place a mesh object in a collection outside the profile allowlist. The extracted object must retain that collection identity and the production kernel must emit `OBJECT_COLLECTION_INVALID`.

### 6.3 Name

Use an object name that violates the profile naming regex. Do not assert a name that Blender silently normalizes.

### 6.4 Unit

Use a unit configuration that maps through the existing unit mapper to a canonical value outside the allowed profile set. The gate must assert the canonical `SCENE_UNIT_INVALID` measured/expected fields, not raw Blender UI state alone.

A separate unit-token control must not assume `IMPERIAL -> INCHES` when a precise `length_unit` is present; precise `length_unit` takes precedence.

### 6.5 Zero scale

Set one object scale component to exactly 0.0. Assert `OBJECT_TRANSFORM_INVALID` and the canonical measured scale.

Do not use NaN or Infinity as Candidate-A fixtures.

### 6.6 Dangling parent

Construct an extracted object whose parent reference resolves to an unknown parent at the canonical boundary without relying on a persistent Blender cycle. If normal Blender RNA cannot produce the desired dangling state directly, the implementation design must use only an already-supported live fixture mechanism; it must not mutate the canonical SceneModel to synthesize the finding after extraction.

If no faithful live producer exists for a dangling parent, the case must be reported as blocked rather than converted into a synthetic canonical-only test.

### 6.7 Envelope boundaries

Use the default profile envelope and world-space vertices.

For upper X:
- tolerated boundary = 50.05 m;
- exact boundary must be accepted;
- rejected fixture must be at least one representable float32 step beyond the tolerated boundary;
- a practical margin around 1e-5 m is acceptable at this magnitude.

For lower X:
- tolerated boundary = -50.05 m;
- exact boundary must be accepted;
- one float32 step beyond the lower boundary must be rejected.

The fixture must be quantisation-aware. Blender stores mesh coordinates as float32 and extraction rounds canonical coordinates to six decimals.

Assertions must use the canonical FindingCode and authoritative report fields. The rounded four-decimal `measured.world` display field must not be used as the mathematical source of truth for a sub-centimetre boundary decision.

The production producer emits at most one finding per affected mesh. Expected finding cardinality is therefore by affected mesh, not offending vertex.

### 6.8 Readiness

Remove one required role from an otherwise compliant scene.

Assert:
- `validation_state == "needs_review"`;
- `scene_metrics["readiness_reason"]` identifies the missing required role;
- `DIGITAL_TWIN_READINESS_FAILED` is absent from FindingCodes.

Do not fabricate or synthesize a readiness FindingCode.

### 6.9 AABB overlap

Use independently authored cuboids.

Required controls:
- partial/non-containment overlap → finding;
- pure containment → no finding;
- equal/coincident AABBs → no finding;
- x-flush contact → no finding because the sweep excludes `min_x == max_x`;
- y-flush contact → finding if x remains overlapping;
- z-flush contact → finding if x/y remain overlapping.

For rotated geometry, use a known pair whose oriented geometry is disjoint but whose transformed world-space AABBs overlap. The result demonstrates the known AABB inflation limitation.

Do not reimplement `_aabbs_overlap` or the sweep in the test to derive expectations.

## 7. Evidence and assertions

Every case must capture:

- case identifier;
- Blender version/build;
- payload schema version;
- effective profile identity;
- input payload digest;
- report digest;
- exact FindingCode set;
- exact measured/expected fields for the targeted finding;
- validation state;
- readiness reason where applicable;
- object/mesh identity;
- raw-state snapshot before/after;
- host-side source artifact hash when a frozen asset is used;
- generated artifact list.

Assertions must be exact enough to distinguish:
- expected finding;
- missing finding;
- wrong finding;
- wrong identity;
- wrong measured/expected payload;
- wrong readiness state;
- mutation.

The gate must not use "any report passes" logic.

## 8. No-save / no-mutation contract

The implementation must adopt the established live-gate standard.

For any frozen source asset:
1. compute host-side SHA-256 before;
2. execute the read-only extraction/report path;
3. compute SHA-256 after;
4. require equality.

For every live process:
1. capture a raw Blender state snapshot before;
2. run extraction/report;
3. capture the same snapshot after;
4. require equality.

The authorized working directory must contain no newly created `.blend` or `.blend1` artifacts after the gate.

The gate must fail closed on unexpected mutation. It must never save, rewrite, repair, or accommodate the fixture.

## 9. Evidence mechanism

The gate is **operator-authorized**, not ordinary deterministic CI.

Required invocation pattern:

`ATLAS_RUN_LIVE_BLENDER=1 python -m pytest <new-live-gate> -s`

The test must:
- skip when authorization is absent;
- fail loudly when authorization is present but prerequisites are missing;
- capture Blender stderr/stdout;
- return non-zero on extraction/report failure;
- record the exact Git SHA being tested;
- record Blender build identity;
- persist the complete evidence artifact outside the repository unless a separately authorized artifact mechanism is established.

No claim of live validation may be inferred from a skipped CI job.

Adding a new GitHub workflow is outside this design's authority. If workflow integration is later desired, it requires a separate workflow-authority decision.

## 10. Deterministic companion tests

The live gate must be paired with offline tests for:
- expected FindingCode sets;
- measured/expected payload shape;
- readiness state/reason;
- envelope boundary predicate;
- one-finding-per-mesh cardinality;
- AABB containment/contact semantics;
- profile identity serialization;
- deterministic report/input digest.

The existing hierarchy-cycle `PYTHONHASHSEED` defect must receive a separate deterministic test/issue. It must not be modified as part of this implementation.

## 11. Exact-head validation gates

Before implementation can be considered complete:

1. deterministic Python 3.9 suite green;
2. deterministic Python 3.11 suite green;
3. hostile/clean environment import checks for the new live gate;
4. operator-authorized Blender 4.4.3 live gate at the exact implementation head;
5. all required assertions pass;
6. no-save/no-mutation evidence passes;
7. evidence artifact records exact commit and engine build;
8. independent post-implementation red-team review is run against the exact implementation head.

A live gate that was skipped does not satisfy item 4.

## 12. Failure and ambiguity policy

- Extraction failure: FAIL. Never fabricate a canonical state.
- Missing expected FindingCode: FAIL.
- Unexpected FindingCode: FAIL unless explicitly classified as an independent fixture interaction and asserted.
- Wrong measured/expected payload: FAIL.
- Wrong readiness state/reason: FAIL.
- Any mutation: FAIL.
- Missing artifact/hash evidence: FAIL.
- Blender process timeout after mutation could have begun: classify as ambiguous/fail-closed; do not infer a successful post-state.
- Unexpected Blender normalization: FAIL the fixture and classify representability; do not modify production semantics to accommodate it.
- Test harness disagreement with production output: production output remains authoritative; revise the fixture/test design rather than duplicating the predicate.

## 13. Frozen-boundary constraints

This implementation may add only test/harness/evidence assets required to exercise the existing production path.

It must not modify:
- canonical extraction contract;
- `SceneModel`;
- `mesh_health.py` production semantics;
- `scene_health.py` production semantics;
- correction mapping;
- correction executor;
- correction authorization;
- Temporal schemas/evaluator/receipts;
- Unreal extraction/transport;
- persistence/retry/rollback;
- production workflow authority.

No new FindingCode is introduced.

No correction is proposed or executed.

## 14. Deliverables

The implementation package should contain only the minimum required live-gate/test/evidence files.

Expected deliverables:
- one operator-gated live test;
- one Blender-side fixture/harness script if required;
- deterministic companion tests;
- documentation of invocation and evidence output;
- no production-code modification.

The exact filenames may be selected during implementation provided they preserve the above boundary.

## 15. Implementation authorization gate

This document itself is **not implementation authorization**.

Before any implementation begins:

1. independently review this exact design;
2. obtain a CLEAR verdict;
3. freeze the reviewed design head;
4. implement only the reviewed scope;
5. run exact-head deterministic and live gates;
6. obtain an independent post-implementation red-team review.

**Status:** IMPLEMENTATION DESIGN — REVIEW REQUIRED — IMPLEMENTATION NOT AUTHORIZED
