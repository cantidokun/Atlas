# Atlas Blender Wave 12 — `REPAIR_PARENT_CYCLE` Design Gate

**Status:** IMPLEMENTATION / VALIDATION IN PROGRESS  
**Branch:** `feat/blender-wave12-reference-integrity`  
**Baseline:** Wave 11 merged to `main` at `fda85a994ec0669d8ee9d1ff1ab6d52e9bfec0d3`

## 1. Objective

Wave 12 extends the already-established hierarchy correction boundary from dangling parent references to one additional malformed-reference class: a parent cycle.

Wave 4 already provides a bounded correction for a child whose `parent_object_id` points to an absent object. It explicitly does not repair cycles, choose a new parent, or normalize hierarchy. The current canonical health kernel reports both unknown-parent and cycle conditions through `OBJECT_HIERARCHY_INVALID`. Wave 12 isolates the cycle case as a separate, explicitly targeted, review-gated correction rather than broadening Wave 4 implicitly.

This remains a narrow canonical correction capability. It does not add workflow, persistence, recovery, receipt, or action-runner authority.

## 2. Exact semantic boundary

Wave 12 adds exactly one correction type:

`REPAIR_PARENT_CYCLE`

The correction removes one selected parent edge by setting the selected object's `parent_object_id` to `None`.

It does **not**:

- choose a new parent;
- re-parent any other object;
- reorder hierarchy;
- normalize depth;
- repair dangling references (Wave 4 remains responsible for that case);
- mutate collections, names, geometry, units, or mesh topology;
- delete objects;
- independently alter the object's canonical local transform fields;
- persist or save Blender state;
- add retry, rollback, recovery, receipt, workflow, or action-runner authority.

## 3. Closed plan parameters

A dedicated planner/executor uses an exact closed parameter set:

```json
{
  "target_object_id": "<cycle member to detach>",
  "expected_parent_id": "<target's current parent>"
}
```

No caller-supplied cycle membership list is authoritative. The planner derives the cycle from authoritative scene input and emits one explicitly selected target. The caller must not be able to assert that an arbitrary edge belongs to a cycle.

A plan is rejected when:

- the target object does not exist exactly once;
- the target has no parent;
- the expected parent does not exactly match the fresh target parent;
- the expected parent is absent from the fresh object identity set (that is Wave 4's dangling-reference case, not Wave 12);
- the fresh authoritative graph no longer contains the target's parent-cycle relationship;
- the target is not actually a member of the fresh cycle being corrected;
- any unexpected plan parameter is present.

Malformed scene containers, object identifiers, and parent identifiers are also rejected with declared `ParentCycleError` failure codes rather than leaking unexpected exceptions from the public planner boundary.

An explicit target is required for a correction. The planner does not silently choose among multiple cycle members.

## 4. Cycle semantics

The authoritative parent graph is defined by `ObjectModel.object_id -> parent_object_id`.

A cycle exists when following parent references from a node eventually reaches a previously visited node. A self-parenting object is a one-node cycle.

For a valid Wave 12 plan:

1. the target is a member of exactly one concrete detected cycle;
2. `expected_parent_id` is the exact parent edge being removed;
3. no other cycle member is changed;
4. no new parent is inferred;
5. after the mutation the authoritative graph is acyclic with respect to the corrected cycle edge;
6. unrelated hierarchy state is byte-for-byte/canonical-value equivalent.

The executor must fail closed if the fresh graph contains a different cycle topology than the plan was derived from.

## 5. Authorization and digest binding

Authorization remains exact and separate from planning.

The authorization artifact binds:

- correction type `REPAIR_PARENT_CYCLE`;
- correction id;
- plan id;
- source report digest;
- exact `target_object_id`;
- exact `expected_parent_id`.

No free-form hierarchy fields are accepted in the authorization artifact.

Before mutation the executor independently computes the canonical Wave-12 scene digest from the extracted authoritative scene and requires both:

`extractor_report_digest == computed_scene_digest == plan.source_report_digest`

The canonical digest is exposed as the public `scene_report_digest(scene_model)` function in `planning/blender/parent_cycle.py`; `_scene_digest()` remains its implementation helper. For Mapping-shaped scene inputs the digest payload is the canonical deep-copied scene mapping. For object-model scene inputs the payload is explicitly composed from scene identity/state, ordered object fields, and mesh fields used by the Wave-12 boundary. An adapter returning `(scene_model, report_digest)` must therefore use this exact function/contract for the report digest it supplies to the executor.

The executor independently recomputes the output digest after mutation and requires the extractor-reported output digest to equal it. A stale plan, target substitution, parent substitution, changed scene, or forged digest fails closed before mutation.

## 6. Mutation boundary and trusted adapter qualification

Exactly one canonical mutator operation is permitted:

```text
object_id=<target_object_id>,
expected_parent_id=<expected_parent_id>,
new_parent_object_id=None
```

The executor performs no cascade and no retry or rollback authority. The canonical executor preserves the target's local transform fields exactly; it does not invent a world-space pose for a malformed cyclic graph.

The executor's own code performs only this single externally-reaching mutator call. Because rollback is deliberately outside the Wave-12 authority boundary, an injected/trusted adapter mutator that violates the one-edge contract cannot be undone by the executor; the fresh post-mutation extraction and invariant checks detect the violation and return a non-success outcome. A consumer must therefore treat any `POSTCONDITION_FAILED` outcome as a potentially partially mutated adapter state, never as proof that the scene remained unchanged.

The Blender live boundary separately proves that the underlying detach primitive preserves world pose on an acyclic disposable parent relationship. Any Blender-specific parent-inverse adjustment needed to preserve world pose is part of that boundary implementation, not a second semantic parent mutation.

## 7. Postconditions

After canonical mutation, the executor re-extracts authoritative state and verifies:

- target `parent_object_id == None`;
- target local `location`, `rotation`, and `scale` are exactly unchanged;
- every non-target object is exactly unchanged;
- object identity set and object count are unchanged;
- geometry, names, collections, units, and mesh metadata are unchanged;
- the corrected cycle is absent;
- no new hierarchy cycle has been introduced elsewhere;
- the source digest relationship and authorization binding remain satisfied.

A canonical world-space equality claim is intentionally **not** made for the malformed pre-state, because the existing world-pose engine correctly cannot resolve a cyclic parent chain.

## 8. Live Blender boundary

Blender's live object model naturally supports parent relationships and cycle-prevention behavior. The live gate proves the actual detach primitive, world-pose preservation on a valid acyclic parent relationship, and the non-mutation invariants using a disposable in-memory scene.

The live gate must not open or save a `.blend`, must not modify frozen assets, and must not rely on an impossible dangling-reference or cyclic `bpy` state. Where Blender prevents creation of an illegal cycle, the canonical malformed-graph tests remain authoritative for cycle detection and repair semantics; the live gate proves only the real Blender detach primitive and its preservation behavior.

No live workflow or action-runner execution is part of Wave 12.

## 9. Validation gate

Implementation currently includes the bounded canonical planner/executor, deterministic cycle tests, malformed-input boundary tests, the public digest contract, and the disposable Blender boundary probe/gate. Merge remains blocked until:

- deterministic self-cycle, two-node, and multi-node cycle cases pass;
- duplicate object-id and ambiguous-target fail-closed cases pass;
- malformed scene/container/id inputs fail with declared outcomes;
- stale-source, target-substitution, and expected-parent substitution rejection pass;
- exact authorization and closed-parameter tests pass;
- hostile Mapping plan/authorization inputs fail closed;
- one-edge-only and non-target preservation tests pass without aliasing false positives;
- canonical local-transform preservation is verified;
- live Blender proof of world-pose preservation passes on the user's Blender 4.4.3 host;
- full Wave 1–Wave 12 regression passes with workflow/action-runner tests excluded;
- supported-Python final-head CI is green;
- independent red-team review is clear.

A cycle repair that changes more than the explicitly selected parent edge, changes canonical local transform state, or causes world-pose drift in the live detach primitive blocks merge. A `POSTCONDITION_FAILED` result after an adapter-side mutation is not interpreted as an automatic rollback guarantee.

## 10. C++ seam

The semantic contract is language-neutral: cycle detection operates on immutable object identifiers and parent identifiers, and correction mutates exactly one canonical parent-reference field while preserving the selected object's canonical local transform. A future C++ implementation must reproduce the same cycle detection, plan binding, digest contract, and postcondition semantics without Blender-specific types.
