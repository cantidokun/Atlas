# Blender Next Milestone — Read-Only Discovery / Design Gate

Status: DISCOVERY ONLY — no implementation authorized
Base: main @ 64c0ad0c3ef7f132d8285a921dc23502b6ecf1b0
Branch: design/blender-next-readonly-discovery

## 1. Purpose

This package inventories the current Blender correction/finding surface after Wave 15 and Temporal Observation ↔ Correction Integration v3. It does not add a correction, change a finding classification, modify canonical extraction, modify Temporal semantics, or alter authorization.

The purpose is to determine whether a bounded next Blender capability is justified by an existing contract and real Blender representability.

The inventory explicitly includes the existing topology-intelligence analysis path and its live Blender gate so that this discovery does not create a parallel topology evidence surface without justification.

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

Read-only topology analysis is an adjacent analysis capability, not correction authority:
- planning/blender/topology_intelligence.py
- planning/blender/topology_serialization.py
- tests/test_live_blender_topology_intelligence_gate.py

The topology-intelligence module is analysis-only: no bpy, no mutation, no execution/authorization authority. Its live gate is currently manifold-only and has no CI workflow trigger. This discovery must reconcile with that existing capability rather than silently duplicate it.

## 3. Existing correction surface

The existing correction surface is composed of different families and is not an 11-wide executable correction set.

### Mesh executor types

These are the currently executable mesh correction types:
- REMOVE_DUPLICATE_FACE
- REMOVE_DEGENERATE_FACE
- REPAIR_FACE_WINDING
- REPAIR_MERGE_VERTEX

### Other live-validated correction/action families

These have their own bounded modules/action schemas and are not members of the mesh executor allowlist:
- REPAIR_PARENT_REFERENCE
- REMOVE_ISOLATED_VERTICES
- REMOVE_DUPLICATE_VERTICES
- NORMALIZE_UNIT_METADATA
- REPAIR_PARENT_CYCLE

### Object/action mapping families

These include:
- RENAME_OBJECT
- RESTRUCTURE_COLLECTION

RENAME_OBJECT is human-review-only and RESTRUCTURE_COLLECTION is review-only under the current mapping; neither is a generic executable fallback.

### Representation fidelity closure

- Wave 14 material-slot fidelity closure

No new correction family is pre-authorized by this discovery.

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
- the canonical kernel reports only edge valence > 2;
- boundary edges with valence 1 are not treated as this finding by the generic kernel;
- valence 2 is manifold;
- current mapping is REQUIRES_REVIEW;
- no executable correction is defined.

Why it is technically interesting:
- the finding is canonically represented;
- the condition is deterministic;
- Blender 4.4.3 can represent the relevant topology at the test boundary;
- the existing canonical extraction path preserves the authored vertices/faces needed to observe it.

Existing capability that must be reconciled:
- planning/blender/topology_intelligence.py already computes boundary/manifold/non-manifold edge counts, maximum edge valence, edge-valence histograms, and component breakdowns from the canonical mesh representation;
- planning/blender/topology_serialization.py serializes those topology metrics;
- tests/test_live_blender_topology_intelligence_gate.py already exercises the real Blender boundary, although its current fixture is intentionally manifold-only;
- the kernel finding and topology metric are currently separate and are not wired into a single report surface.

Therefore this milestone must extend/reconcile the existing topology live-gate capability rather than introduce a second unexplained topology harness. The key discovery question is whether the same real Blender fixture can establish coherence between the canonical finding and the existing canonical topology metric, while preserving the existing no-authority boundary.

Why it is not yet a correction:
- there is no uniquely correct repair for arbitrary non-manifold topology;
- repair choices can delete, split, duplicate, weld, or reinterpret geometry;
- a generic automatic repair would introduce policy authority not present today.

Discovery conclusion: suitable for a READ-ONLY LIVE EVIDENCE / DIAGNOSTIC boundary investigation, preferably as an extension of the existing topology-intelligence live gate, not as a parallel topology authority.

### Candidate B — MESH_NORMAL_INCONSISTENT

Not currently suitable for a correction boundary because canonical extraction intentionally does not provide Blender face-normal semantics as a frozen invariant. Adding a repair would risk reopening Extraction Fidelity v1.

Disposition: NO ACTION under current frozen contract.

### Candidate C — MESH_INVALID_INDEX

The canonical model does represent out-of-range and negative face indices as canonical state; the construction layer rejects type violations and repeated vertex indices, but does not reject every invalid value-range index. MESH_INVALID_INDEX is therefore a real canonical finding and is mapped to human review with no automatic proposal.

This does not make it a suitable next correction boundary. A safe repair would require defining what an invalid datum should become and would cross from detection into mutation policy. A future read-only discovery could separately investigate the raw-engine representability and boundary semantics of malformed indices, but that is not required for this milestone.

Disposition: NO ACTION under this discovery; correction policy remains explicitly undefined.

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
- extend/reconcile the existing topology-intelligence live-gate capability rather than create a parallel topology evidence authority;
- exercise the existing MESH_NON_MANIFOLD_EDGE finding against real Blender geometry;
- prove canonical extraction fidelity for the represented topology;
- prove the finding is deterministic at the real engine boundary;
- prove coherence between the kernel finding and the existing topology-intelligence metric for the same canonical fixture;
- prove no correction is proposed or executed;
- prove the live gate is read-only and save-free;
- document explicit non-claims about repairability.

Temporal Observation is explicitly OUT OF SCOPE for this first implementation. A mutation-free A/B transaction would require either invoking the correction transaction machinery or hand-driving Temporal session semantics, neither of which adds evidence about non-manifold topology. A future design may separately define what mutation-free temporal evidence means, but this milestone does not.

This would be an evidence/discovery milestone, not a repair milestone.

## 7. Required design questions before implementation

A design package for the candidate must answer:

1. Can Blender 4.4.3 construct and preserve the exact non-manifold fixtures represented by the canonical model?
2. Does canonical extraction preserve the relevant vertices/faces and produce the expected finding without hidden Blender topology semantics?
3. Can the fixture distinguish valence 1 from valence 2 and valence >2?
4. Does the live gate remain read-only and save-free?
5. What is the exact canonical finding identity convention (mesh_id/object scoping), and can the gate prove target isolation?
6. How does this gate extend/reuse planning/blender/topology_intelligence.py, planning/blender/topology_serialization.py, and the existing topology live gate rather than creating a parallel topology authority?
7. What exact raw Blender observations are test-only evidence rather than canonical contract?
8. Which cases are explicitly refused as correction candidates?
9. What adversarial cases prevent a future implementation from treating a non-manifold finding as permission to mutate?
10. What coherence assertions establish that the kernel finding and topology metric agree for the same canonical fixture?
11. What would constitute sufficient evidence to either promote this to a future correction design or close it as review-only?
12. Is any CI workflow trigger required? If so, it must be a separately reviewed infrastructure change and not be silently bundled into the implementation of this evidence gate.

## 8. Mandatory non-claims

This discovery must not claim:
- that non-manifold geometry is always erroneous;
- that there is one correct repair;
- that a repair should delete, split, weld, duplicate, or move geometry;
- that raw Blender topology fields expand the canonical contract;
- that the topology-intelligence metric is correction authority;
- that Temporal provides correction authority;
- that a live evidence gate authorizes mutation;
- that this milestone reopens Extraction Fidelity v1;
- that a mutation-free Temporal A/B transaction is required or demonstrated by this milestone.

## 9. Promotion gate

No implementation begins until an independent architectural/red-team review is CLEAR or CLEAR WITH MINOR FINDINGS with no required changes.

Implementation, if later authorized, requires:

### Offline deterministic evidence
- valence matrix covering 1/2/3/4;
- finding present iff incidence > 2;
- exact measured edge and face incidence;
- exact expected payload and severity;
- multi-edge ordering;
- boundary/manifold negative controls;
- duplicate-face and quad+triangle topology traps;
- planner no-authority assertion plus an independent positive planner control;
- unchanged correction mapping/executor/severity invariants;
- reproducible report digest and input digest;
- coherence between MESH_NON_MANIFOLD_EDGE findings and analyze_topology(mesh).non_manifold_edge_count;
- histogram evidence reflecting the >2 incidence rule.

### Real Blender evidence
- Blender 4.4.3 disposable process;
- factory-startup cleanup;
- compliant object names/collection;
- geometry inside the active profile envelope;
- authored fixture source as the independent expectation;
- raw Blender polygon equality with authored faces;
- independently recomputed raw incidence;
- canonical face equality with authored faces;
- exact valence-1/2/3/4 behavior;
- target isolation by canonical mesh_id;
- planner returns zero corrections for the clean fixture;
- no mutation;
- no save/persistence side effect;
- second extraction produces identical payload/report digest;
- evidence artifact proves the live test actually executed (N passed, not only skipped).

### Frozen-boundary audit
The implementation must not modify:
- planning/temporal/**
- correction executor/authorization/contract/mapping/codes
- scene_model.py
- extraction_payload.py
- bpy_extraction.py
- kernel.py
- mesh_health.py
- topology_intelligence.py
- topology_serialization.py
- the existing classification table

No new correction type, canonical field, edge table, or workflow trigger is part of this implementation.

An independently reviewed workflow change may be considered separately if CI coverage is required.

### Independent post-implementation review
- exact-head deterministic checks;
- exact-head real Blender evidence;
- independent post-implementation red-team review before merge.

## 10. Current conclusion

At this checkpoint, **MESH_NON_MANIFOLD_EDGE remains the only remaining topology finding currently justified for a focused read-only live-boundary discovery without inventing a correction policy or reopening a frozen contract.**

The existing topology-intelligence capability is part of that conclusion: the next milestone should reconcile and extend the existing analysis/live-gate path rather than create a parallel topology authority.

This is a candidate for investigation, not an implementation authorization.
