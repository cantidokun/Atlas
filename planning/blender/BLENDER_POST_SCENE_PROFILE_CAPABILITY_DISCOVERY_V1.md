# Blender Post-Scene/Profile Capability Discovery v1

**Status: DISCOVERY ONLY — NO IMPLEMENTATION AUTHORIZED**

- Base branch: `main`
- Exact base commit: `1e546727dc590dcfca1cda84eccc0be138f85442`
- Trigger: PR #127 merged the Scene/Profile Compliance Evidence Boundary v1.
- Scope: inventory the remaining Blender capability surface and determine whether another bounded milestone is justified.
- This document does not authorize a correction, schema, extraction, Temporal, Unreal, persistence, recovery, workflow, or action-runner change.

## 1. Current checkpoint

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

The existing non-manifold evidence boundary is already merged in PR #124. The earlier discovery documents that proposed non-manifold as the next capability are therefore historical and must not be reused as the current roadmap.

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

A concrete correctness defect can justify a separate boundary-reopening design, but that is outside this discovery.

## 3. Remaining finding/correction surface

The current authoritative mapping in `planning/blender/correction_mapping.py` classifies the remaining findings as follows.

| Finding | Current classification | Current correction/proposal | Discovery disposition |
|---|---|---|---|
| MESH_INVALID_INDEX | REQUIRES_REVIEW | none | Investigate only whether a useful live evidence boundary exists without changing canonical representation |
| MESH_DUPLICATE_VERTEX | REQUIRES_REVIEW | REPAIR_MERGE_VERTEX | Already has a live correction boundary; no new family implied |
| MESH_NON_MANIFOLD_EDGE | REQUIRES_REVIEW | FLAG_NON_MANIFOLD_FOR_REVIEW | Already closed by PR #124; no repeat |
| MESH_SCALE_OUT_OF_RANGE | REQUIRES_REVIEW | FLAG_SCALE_FOR_REVIEW | Evidence boundary closed by PR #127 |
| MESH_NORMAL_INCONSISTENT | REQUIRES_REVIEW | REPAIR_NORMAL_CONSISTENCY | Likely blocked by frozen normal representation; investigate only |
| SCENE_ORIGIN_INVALID | REQUIRES_REVIEW | FLAG_ORIGIN_FOR_REVIEW | Already exercised by the Scene/Profile compliance scope or adjacent profile semantics; verify exact coverage before proposing anything |
| SCENE_BOUNDS_EMPTY | REQUIRES_REVIEW | none | Determine whether an evidence-only boundary adds information beyond existing readiness/scene-health state |
| OBJECT_HIERARCHY_INVALID (dangling) | REQUIRES_REVIEW | REPAIR_PARENT_REFERENCE | Evidence boundary closed for dangling-parent case; cycle remains unsafe |
| OBJECT_HIERARCHY_INVALID (cycle) | UNSAFE_TO_AUTOMATE | none | No correction implementation candidate without a separate safety contract |
| OBJECT_BOUNDS_OVERLAP | REQUIRES_REVIEW | FLAG_BOUNDS_OVERLAP_FOR_REVIEW | Evidence boundary closed by PR #127 |
| OBJECT_COLLECTION_INVALID | REQUIRES_REVIEW | RESTRUCTURE_COLLECTION | Evidence boundary closed by PR #127; correction remains ambiguous |
| OBJECT_ID_DUPLICATE | UNSAFE_TO_AUTOMATE | none | Investigate only if a deterministic, engine-representable identity defect can be evidenced without changing identity authority |
| OBJECT_TRANSFORM_INVALID | UNSAFE_TO_AUTOMATE | none | Zero-scale evidence is closed; no generic transform repair candidate |
| DIGITAL_TWIN_READINESS_FAILED | OUT_OF_SCOPE | none | Not a produced finding; readiness is represented by validation state/reason |

## 4. Candidate evaluation rules

A candidate may advance only if all of the following can be established without weakening a frozen boundary:

1. **Concrete value** — it exposes information materially useful to Atlas beyond existing evidence.
2. **Real Blender representability** — the intended defect can be constructed and observed in Blender 4.4.3, not merely fabricated in Python.
3. **Canonical compatibility** — evidence can be expressed using the current canonical model, or the need for representation change is explicitly identified as a separate design problem.
4. **Independent truth source** — the live gate can compare engine-derived evidence against an independent fixture truth or deterministic invariant.
5. **No mutation required** — discovery candidates should default to read-only evidence unless a later design proves a bounded correction is justified.
6. **Deterministic refusal** — malformed, ambiguous, unsupported, or unsafe cases have explicit refusal behavior.
7. **No authority expansion** — the candidate does not create planning, authorization, persistence, retry, rollback, scheduling, or workflow authority.
8. **Non-duplication** — the capability is not already closed by PR #124 or PR #127.
9. **Evidence identity** — engine version/build, repository head, payload/report identity, and artifact integrity are captured where applicable.
10. **Independent red-teamability** — the candidate can be reviewed against an exact immutable design head before implementation.

## 5. Candidate-specific discovery questions

### A. MESH_INVALID_INDEX

Determine the exact split between:

- live-representable negative/out-of-range indices;
- repeated vertex indices or otherwise parser-refused topology;
- malformed/non-integer/non-finite data that Blender itself cannot preserve.

The key question is whether a real Blender evidence gate can add meaningful coverage without changing the frozen extraction/parser contract.

**Do not authorize repair.** An evidence-only candidate is the maximum scope unless a separate contract is approved.

### B. MESH_NORMAL_INCONSISTENT

The current correction mapping references normal consistency, while the frozen extraction contract intentionally omits unsupported normal semantics.

Determine whether there is any non-invasive evidence boundary that is both meaningful and compatible with the frozen canonical representation.

If proving the capability requires introducing canonical normal semantics, this candidate is a **contract-reopen candidate**, not a next Blender milestone.

### C. OBJECT_ID_DUPLICATE

Determine how canonical object identity is constructed and whether Blender can produce a genuinely ambiguous identity condition under the current producer semantics.

Do not invent duplicate IDs by mutating evidence after extraction. If the condition cannot occur under the current identity authority, record it as non-live-representable rather than manufacturing a test.

### D. SCENE_BOUNDS_EMPTY

Determine whether an empty scene/empty geometry condition produces a useful independently verifiable evidence boundary that is not already adequately represented by scene readiness and existing extraction semantics.

If there is no additional operational value, classify as no-action/no-extension.

### E. OBJECT_HIERARCHY_INVALID cycle

Keep the current safety classification. Blender's live construction constraints must be checked, but the discovery must not force a cycle fixture or invent repair semantics merely to obtain a test case.

### F. Existing review-only findings already covered

For OBJECT_COLLECTION_INVALID, MESH_SCALE_OUT_OF_RANGE, OBJECT_BOUNDS_OVERLAP, zero-scale OBJECT_TRANSFORM_INVALID, and dangling-parent hierarchy, verify the merged PR #127 evidence is sufficient and do not propose duplicate gates.

## 6. Required discovery evidence

Before recommending any implementation design, the discovery package must contain:

- current main SHA and exact source inventory;
- complete finding-to-correction classification;
- existing deterministic test coverage;
- existing live-gate coverage and exact PR/commit references;
- canonical representation constraints;
- Blender 4.4.3 representability findings;
- candidate value/duplication analysis;
- adversarial/refusal matrix;
- no-save/no-mutation implications;
- authority/frozen-boundary audit;
- explicit non-claims;
- a final disposition for every remaining candidate.

A live probe may be added only if it is itself bounded as discovery evidence and does not become an implementation by implication.

## 7. Promotion gate

This discovery is **not implementation authorization**.

Promotion requires:

1. independent architectural/red-team review of this exact discovery head;
2. a CLEAR verdict;
3. if a candidate survives, a separate implementation design PR;
4. independent review of that design;
5. only then may implementation begin.

If every candidate is closed, duplicated, unsafe, or contract-blocked, the correct outcome is **NO IMMEDIATE BLENDER EXTENSION**. That is a valid discovery result.

## 8. Non-claims

This document does not claim:

- that any remaining finding should be corrected automatically;
- that any remaining finding is live-representable;
- that Blender extraction should be expanded;
- that normal/UV semantics should be added;
- that another correction wave is required;
- that a Wave 16 implementation is authorized;
- that Blender work must continue if the discovery closes the remaining useful surface.

## 9. Expected next decision

The next decision is deliberately binary at the capability level:

**A. A bounded, non-duplicative Blender capability survives discovery** → produce a separate design package.

**B. No bounded capability survives without reopening a frozen contract or adding unsafe authority** → close the Blender extension track at this checkpoint and move the engineering focus to the next Atlas layer.

No implementation should be started between this discovery and that decision.
