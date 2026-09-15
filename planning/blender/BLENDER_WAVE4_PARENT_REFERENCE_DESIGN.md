# Atlas Blender — Wave 4 `REPAIR_PARENT_REFERENCE` Design

## Scope
Wave 4 adds one bounded correction: detach an object whose recorded `parent_object_id` is a dangling identifier absent from the authoritative fresh scene. The operation is human-authorized and review-gated. It does not repair cycles, choose a new parent, normalize hierarchy, or independently edit transforms.

## Canonical boundary
The canonical planner/executor is responsible for the malformed-reference case. The Blender live gate is intentionally boundary-faithful: Blender's live API does not normally permit a dangling `Object.parent` identifier to persist, so the live gate proves the actual detach primitive and its preservation semantics without fabricating an impossible `bpy` state.

## Detection and planning
The existing hierarchy validator remains authoritative. Automatic `plan_scene_report` behavior remains unchanged because `OBJECT_HIERARCHY_INVALID -> REPAIR_PARENT_REFERENCE` is not auto-proposed. A dedicated planner may emit exactly one review-required proposal for one resolved target. Multiple dangling targets without an explicit target are refused.

Closed parameters:

```json
{
  "expected_parent_id": "<missing object id>",
  "detach_to": null
}
```

The planner derives the proposal from fresh report provenance and authoritative scene input; callers do not provide a parent-existence assertion.

## Authorization
The authorization artifact binds the exact correction type, correction id, plan id, and source report digest. The executor verifies the artifact before mutation and accepts no parent-specific free-form fields.

## Executor preconditions
The executor re-extracts the authoritative pre-state and enforces:

- exactly one executable parent-reference correction with a resolvable target;
- fresh target parent equals the authorized `expected_parent_id`;
- authorized expected parent identifier is absent from the fresh object identity set;
- authorization and closed parameters remain exact;
- fresh report digest equals the plan's source report digest.

No predicate is satisfied from a caller assertion or stale scene object.

## Mutation boundary
Exactly one injected mutator call is permitted:

`object_id=<target>, expected_parent_id=<missing id>, new_parent_object_id=None`

The executor has no retry, cascade, persistence, rollback, recovery, save, or authorization authority.

## Postconditions
The executor re-extracts the authoritative post-state and enforces:

- target parent is `None`;
- every target field other than `parent_object_id` is exactly unchanged;
- object identity set and count are unchanged;
- every unrelated `ObjectModel` is exactly unchanged;
- the formerly missing parent identifier remains absent.

## Live Blender proof
`tests/parent_reference_live_script.py` and `tests/test_live_blender_parent_reference_gate.py` validate the Blender-side primitive with a disposable in-memory scene. The proof checks parent detachment, world-transform preservation, local non-parent state, identity/count invariants, parent datablock retention, and no file open/save.

## Closure gate
Wave 4 is **not closed** by the presence of these files. Promotion requires:

1. deterministic planner/executor suite passing;
2. live Blender 4.4.3 gate passing on the user's host;
3. independent red-team review of the complete implementation;
4. no regression in Waves 1–3.

Until those gates clear, this remains an implementation candidate.
