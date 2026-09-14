# Atlas Blender — Wave 4 REPAIR_PARENT_REFERENCE Design

## 1. Scope
Wave 4 adds one bounded correction only: detach an object whose recorded `parent_object_id` is a dangling identifier that is absent from the authoritative fresh scene. The operation is human-authorized and review-gated. It does not repair cycles, choose a new parent, normalize hierarchy, or edit transforms independently.

## 2. Why this operation is bounded
A dangling parent reference has an identity-level defect: the target object names a parent object that does not exist. The correction changes exactly one canonical field: `target.parent_object_id` from the evidence-bound missing identifier to `None`. Cycles are excluded because the referenced parent exists in the authoritative object identity set.

## 3. Detection and planning
The existing hierarchy validator remains authoritative. Automatic `plan_scene_report` behavior remains unchanged because `OBJECT_HIERARCHY_INVALID -> REPAIR_PARENT_REFERENCE` is `auto_propose=False`. A dedicated `plan_parent_reference_correction(...)` path may emit exactly one review-required proposal for one resolved target. When more than one dangling-parent target exists and no explicit target is supplied, planning refuses with `MULTIPLE_DANGLING_TARGETS`.

The proposal parameter schema is closed:

```json
{
  "expected_parent_id": "<missing object id>",
  "detach_to": null
}
```

The planner derives the proposal only from fresh report provenance plus the authoritative scene input. The caller does not provide a parent-existence assertion.

## 4. Authorization
The existing authorization artifact contract is extended with the exact correction type `REPAIR_PARENT_REFERENCE`. The artifact binds to the exact correction id, plan id, and source report digest. The executor constructs `ParentPresentedWork` from the exact plan and verifies the artifact before contacting the engine. No parent-specific free-form artifact fields are accepted.

## 5. Executor preconditions
The executor re-derives all operation predicates from a fresh authoritative extraction before mutation:

- PP-1: exactly one executable parent-reference correction exists and its target resolves.
- PP-2: the fresh target `parent_object_id` equals the authorized `expected_parent_id`.
- PP-3: the authorized expected parent identifier is absent from the fresh object identity set.
- PP-4: the correction remains human-authorized and its closed parameters are exact.

No precondition is satisfied from a caller assertion, receipt field, or stale scene object.

## 6. Mutation boundary
Exactly one injected mutator call is permitted:

`object_id=<target>, expected_parent_id=<missing id>, new_parent_object_id=None`

The executor has no retry, cascade, persistence, rollback, recovery, save, or authorization authority. The default mutator is unavailable and fails closed outside an injected adapter/test mutator.

## 7. Postconditions
The executor re-extracts the authoritative post-state and enforces:

- PQ-1: target parent is `None`.
- PQ-2: every target field other than `parent_object_id` is exactly unchanged. This intentionally refuses hidden transform, visibility, collection, naming, mesh, or geometry changes.
- PQ-3: object identity set and count are unchanged.
- PQ-4: every unrelated `ObjectModel` is exactly unchanged.
- PQ-5: the formerly missing parent identifier remains absent.

World-space semantic preservation beyond the canonical `ObjectModel` is not claimed because the current canonical contract does not model Blender `matrix_parent_inverse` as a separate field. A real adapter must therefore satisfy the canonical postcondition or the operation fails closed after mutation.

## 8. Audit receipt
The Wave 4 receipt records source and output report digests, authorization verification, exact target and expected parent, pre/post parent state, object-set/count invariants, target non-parent preservation, unrelated-object preservation, and explicit `persisted=False` / `rollback_performed=False` non-claims.

## 9. Test requirements
The deterministic test matrix covers: positive planning; cycle refusal; multi-target refusal; authorization binding; cross-plan rejection; successful single mutation; missing/wrong authorization; wrong expected parent; wrong target; unexpected parameter; non-None detach target; postcondition corruption; and proof that unrelated objects and target non-parent fields remain unchanged.

## 10. Live Blender status
Live Blender validation is intentionally not included in Wave 4 implementation. No Blender process, real `.blend` asset, workflow, or frozen asset is modified by this implementation pass. A future live gate must use a disposable fixture, verify no save, and independently verify the canonical postconditions.

## 11. Status
Implementation draft completed in the supplied development workspace. Formal promotion/closure remains blocked until an independent red-team gate reviews the implementation and its deterministic evidence.
