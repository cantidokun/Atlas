# Blender Next Milestone — Read-Only Discovery / Design Gate

Status: DISCOVERY ONLY — no implementation authorized
Base: main @ 64c0ad0c3ef7f132d8285a921dc23502b6ecf1b0
Branch: design/blender-next-readonly-discovery

## 1. Purpose

This package inventories the current Blender correction surface after Wave 15 and Temporal Observation ↔ Correction Integration v3. It does not add a correction, change a finding classification, modify canonical extraction, modify Temporal semantics, or alter authorization.

The purpose is to determine whether a bounded next Blender capability is justified by an existing contract and real Blender representability.

## 2. Current bounded architecture

The current Blender stack is:

canonical extraction
→ deterministic scene health / findings
→ bounded correction proposal
→ authorization where required
→ canonical execution contract
→ real Blender adapter
→ postcondition verification + receipt
→ Temporal observation of resulting canonical state

Frozen boundaries remain:
- Blender Extraction Fidelity v1
- canonical scene model / extraction payload
- correction receipt schema
- correction authorization semantics
- Temporal schema and StateDelta semantics
- persistence / rollback / recovery authority
- workflow/action-runner authority

## 3. Existing correction surface

Already live-validated and merged:
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
- Wave 14 material-slot fidelity closure

No new correction family is pre-authorized.

## 4. Remaining finding surface

Current mapping classifies these as review/unsafe/out-of-scope rather than executable:

- MESH_INVALID_INDEX
- MESH_DUPLICATE_VERTEX (existing REPAIR_MERGE_VERTEX is deliberately not auto-proposed)
- MESH_NON_MANIFOLD_EDGE
- MESH_SCALE_OUT_OF_RANGE
- MESH_NORMAL_INCONSISTENT
- SCENE_ORIGIN_INVALID
- SCENE_BOUNDS_EMPTY
- OBJECT_HIERARCHY_INVALID review branch
- OBJECT_BOUNDS_OVERLAP
- OBJECT_COLLECTION_INVALID
- OBJECT_ID_DUPLICATE
- OBJECT_TRANSFORM_INVALID
- DIGITAL_TWIN_READINESS_FAILED

The classification itself is not to be changed by this discovery.

## 5. Candidate assessment

### Candidate A — MESH_NON_MANIFOLD_EDGE

Observed contract:
- canonical kernel reports only edge valence > 2;
- boundary edges are not treated as defects by the generic kernel;
- current mapping is REQUIRES_REVIEW;
- no executable correction is defined.

Why it is technically interesting:
- the finding is canonically represented;
- the condition is deterministic;
- the engine can represent the topology;
- the current Temporal/extraction stack can observe a resulting canonical state without schema expansion.

Why it is not yet a correction:
- there is no uniquely correct repair for arbitrary non-manifold topology;
- repair choices can delete, split, duplicate, or reinterpret geometry;
- a generic automatic repair would introduce policy authority not present today.

Discovery conclusion: suitable for a READ-ONLY LIVE EVIDENCE / DIAGNOSTIC boundary investigation, not for an automatic correction.

### Candidate B — MESH_NORMAL_INCONSISTENT

Not currently suitable for a correction boundary because canonical extraction intentionally does not provide Blender face-normal semantics as a frozen invariant. Adding a repair would risk reopening Extraction Fidelity v1.

Disposition: NO ACTION under current frozen contract.

### Candidate C — MESH_INVALID_INDEX

Canonical SceneModel construction rejects invalid face indices rather than representing them as a repairable canonical mesh state. A correction would therefore require a raw/invalid-input boundary outside the current canonical contract.

Disposition: NO ACTION under current frozen contract.

### Candidate D — SCENE_ORIGIN_INVALID / MESH_SCALE_OUT_OF_RANGE

Both are policy/profile-dependent. A correction requires an authoritative target frame or envelope policy and must not infer one from the finding alone.

Disposition: discovery only; no mutation proposal.

### Candidate E — OBJECT_BOUNDS_OVERLAP

Overlap is a spatial relationship, not an inherently erroneous state. Repair requires choosing which object moves and where. There is no unique correction encoded by the current contract.

Disposition: review-only; no correction.

### Candidate F — OBJECT_COLLECTION_INVALID

The current mapping explicitly refuses automatic restructuring because the intended allowed collection/path is ambiguous. A live evidence closure could be useful later, but no mutation is justified from the current finding alone.

Disposition: review-only.

### Candidate G — OBJECT_ID_DUPLICATE / OBJECT_TRANSFORM_INVALID

Both are explicitly UNSAFE_TO_AUTOMATE. A generic correction would create new identity or transform authority.

Disposition: no automatic correction.

## 6. Discovery recommendation

The next bounded Blender milestone should NOT be a generic "Wave 16 correction."

The technically justified candidate is:

**Read-Only Non-Manifold Evidence Boundary v1**

Scope:
- exercise the existing MESH_NON_MANIFOLD_EDGE finding against real Blender geometry;
- prove canonical extraction fidelity for the represented topology;
- prove the finding is deterministic at the real engine boundary;
- prove no correction is proposed or executed;
- prove Temporal observation can observe the unchanged canonical state if desired;
- document explicit non-claims about repairability.

This would be an evidence/discovery milestone, not a repair milestone.

## 7. Required design questions before implementation

A design package for the candidate must answer:

1. Can Blender 4.4.3 construct and preserve the exact non-manifold fixtures represented by the canonical model?
2. Does canonical extraction preserve the relevant vertices/faces and produce the expected finding without hidden Blender topology semantics?
3. Can the fixture distinguish valence >2 from ordinary boundary edges?
4. Does the live gate remain read-only and save-free?
5. Does the gate prove object/mesh target identity and source-report digest?
6. Can the same fixture be observed through the existing Temporal A/B machinery without adding schema?
7. What exact raw Blender observations are test-only evidence rather than canonical contract?
8. Which cases are explicitly refused as correction candidates?
9. What adversarial cases prevent a future implementation from treating a non-manifold finding as permission to mutate?
10. What would constitute sufficient evidence to either promote this to a future correction design or close it as review-only?

## 8. Mandatory non-claims

This discovery must not claim:
- that non-manifold geometry is always erroneous;
- that there is one correct repair;
- that a repair should delete, split, weld, duplicate, or move geometry;
- that raw Blender topology fields expand the canonical contract;
- that Temporal provides correction authority;
- that a live evidence gate authorizes mutation;
- that this milestone reopens Extraction Fidelity v1.

## 9. Promotion gate

No implementation begins until an independent architectural/red-team review is CLEAR or CLEAR WITH MINOR FINDINGS with no required changes.

Implementation, if later authorized, requires:
- deterministic fixture matrix;
- real Blender 4.4.3 representability proof;
- exact refusal matrix;
- persistence/no-save proof;
- frozen-boundary audit;
- exact-head CI;
- exact-head live Blender evidence;
- independent post-implementation red-team review.

## 10. Current conclusion

At this checkpoint, **MESH_NON_MANIFOLD_EDGE is the only remaining topology finding that appears suitable for a meaningful read-only live-boundary discovery without inventing a correction policy or reopening a frozen contract**.

This is a candidate for investigation, not an implementation authorization.
