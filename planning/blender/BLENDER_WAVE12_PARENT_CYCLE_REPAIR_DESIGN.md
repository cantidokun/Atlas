# Atlas Blender Wave 12 — `REPAIR_PARENT_CYCLE` Design Gate

**Status:** DESIGN / NOT IMPLEMENTED  
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
- alter transforms independently of the parent field;
- repair dangling references (Wave 4 remains responsible for that case);
- mutate collections, names, geometry, units, or mesh topology;
- delete objects;
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

- the target object does not exist;
- the target has no parent;
- the expected parent does not exactly match the fresh target parent;
- the expected parent is absent from the fresh object identity set (that is Wave 4's dangling-reference case, not Wave 12);
- the fresh authoritative graph no longer contains the target's parent-cycle relationship;
- multiple candidate targets exist and no explicit target is supplied;
- the target is not actually a member of the fresh cycle being corrected;
- any unexpected plan parameter is present.

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

## 5. Authorization binding

Authorization remains exact and separate from planning.

The authorization artifact binds:

- correction type `REPAIR_PARENT_CYCLE`;
- correction id;
- plan id;
- source report digest;
- exact `target_object_id`;
- exact `expected_parent_id`.

No free-form hierarchy fields are accepted in the authorization artifact.

The executor independently recomputes the fresh source digest before mutation. A stale plan, target substitution, parent substitution, or changed cycle fails closed.

## 6. Mutation boundary

Exactly one canonical mutator operation is permitted:

```text
object_id=<target_object_id>,
expected_parent_id=<expected_parent_id>,
new_parent_object_id=None
```

The executor performs no cascade and no retry.

## 7. Postconditions

After mutation, the executor re-extracts authoritative state and verifies:

- target `parent_object_id == None`;
- every target field other than `parent_object_id` is unchanged;
- every non-target object is exactly unchanged;
- object identity set and object count are unchanged;
- geometry, transforms, names, collections, units, and mesh metadata are unchanged;
- the corrected cycle is absent;
- no new hierarchy cycle has been introduced elsewhere;
- the source digest relationship and authorization binding remain satisfied.

The correction is intentionally local: one parent edge, one selected object.

## 8. Live Blender boundary

Blender's live object model naturally supports parent relationships and cycle-prevention behavior. The live gate must therefore prove the actual detach primitive and the non-mutation invariants using a disposable in-memory scene.

The live gate must not open or save a `.blend`, must not modify frozen assets, and must not rely on an impossible dangling-reference state. It should construct a small parent cycle only to the extent Blender's actual API permits; where Blender prevents creation of an illegal cycle, the gate must instead prove the bounded detach primitive and preserve the canonical malformed-graph test as the authority for the cycle semantics.

No live workflow or action-runner execution is part of Wave 12.

## 9. Validation gate

Before merge:

- deterministic cycle-detection reference-model tests;
- self-cycle, two-node cycle, and multi-node cycle cases;
- ambiguous-target and stale-source fail-closed cases;
- target-substitution and expected-parent substitution rejection;
- exact authorization and closed-parameter tests;
- proof that one detached edge cannot silently repair or alter another cycle;
- full Wave 1–Wave 12 regression with workflow/action-runner tests excluded;
- live Blender boundary gate on the user's Blender 4.4.3 host;
- supported-Python final-head CI;
- independent red-team review focused on graph-topology broadening, hidden re-parenting, stale authorization, and accidental multi-edge mutation.

A cycle repair that changes more than the explicitly selected parent edge blocks merge.

## 10. C++ seam

The semantic contract is language-neutral: cycle detection operates on immutable object identifiers and parent identifiers, and correction mutates exactly one canonical parent-reference field. A future C++ implementation must reproduce the same cycle detection, plan binding, and postcondition semantics without Blender-specific types.
