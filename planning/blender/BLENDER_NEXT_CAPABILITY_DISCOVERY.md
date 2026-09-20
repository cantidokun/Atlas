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

## 5. Candidate discovery

### Candidate A — Read-Only Scene/Profile Compliance Evidence Boundary

This candidate is not a new correction. It is a real-Blender evidence boundary for the existing scene-health/profile semantics.

The current profile already defines:

- dimensional envelope: X [-50,50], Y [-40,40], Z [0,12] metres;
- accepted units;
- naming convention;
- allowed collections;
- required semantic roles;
- hierarchy depth;
- readiness-blocking finding set;
- envelope tolerance.

The scene-health kernel already evaluates:

- unit validity;
- origin/world-bounds validity;
- object naming;
- collection membership;
- transform validity;
- hierarchy validity;
- AABB overlap;
- mesh envelope compliance.

The kernel then derives a deterministic SceneReport and readiness state.

What is missing is a dedicated, adversarial real-Blender boundary proving that these existing profile semantics remain faithful when fed by actual Blender extraction.

Potential evidence matrix:

1. clean compliant scene;
2. one object outside envelope;
3. one disallowed collection;
4. invalid object naming;
5. invalid unit system;
6. invalid transform;
7. dangling parent;
8. hierarchy cycle where representable by Blender;
9. non-containment AABB overlap;
10. required-role omission;
11. boundary-tolerance case;
12. negative controls demonstrating that valid containment, boundary geometry, and compliant objects are not falsely reported.

The gate would use the existing extraction and kernel paths. It would not change them.

Potential value:

- closes the gap between deterministic scene-health semantics and real Blender representation;
- provides a more complete real-engine evidence layer for the digital-twin readiness gate;
- exercises world-space transform/envelope behavior at the actual Blender boundary;
- strengthens future asset-ingestion confidence without granting mutation authority.

Important limitation:

The existing operator-gated real-.blend validation already proves a clean, frozen asset path. Therefore this candidate must add meaningful negative/boundary evidence rather than simply duplicate the existing clean-asset gate.

Disposition:

**STRONG CANDIDATE FOR A DEDICATED READ-ONLY DESIGN GATE.**

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

The existing kernel computes world-space AABB overlap and deliberately excludes pure containment.

This is semantically useful and deterministic, but overlap is not inherently an error. There is no generic correction target: choosing which object moves would be scene-authoring policy.

A real-Blender read-only evidence gate could prove transform-aware overlap detection, but the current deterministic tests already exercise the central geometry semantics and the existing real asset gate intentionally uses disjoint probe bounds.

Disposition:

**POSSIBLE FUTURE EVIDENCE EXTENSION, BUT NOT AS STRONG AS CANDIDATE A.**

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

## 10. Promotion criteria

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

## 11. Discovery conclusion

At main @ 6e400378e4175661877575d522033c0b29f3173c:

**Candidate A — Read-Only Scene/Profile Compliance Evidence Boundary v1 — is the strongest next discovery candidate.**

It does not require inventing a correction policy, it builds on existing production semantics, and it addresses a real remaining evidence gap: systematic proof that the existing scene-health/profile/readiness path remains faithful at the real Blender boundary.

This document does **not** authorize implementation.

The next step is an independent architectural/red-team review of this discovery conclusion. If that review clears the candidate, a separate implementation design package should be written. If it does not, the candidate should be revised or rejected rather than forcing a Wave 16 implementation.
