# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — actor-rotation tool-schema reconciliation
**Current focus:** Controlled actor transform expansion — rotation
**Current branch:** `feat/unreal-production-actor-write`
**Current state:** rotation planner/capability/transport implementation is present; focused executor coverage exposed one missing executor tool-schema registration, which has now been fixed.

## Immediate verification gate

The latest user test result was:

```text
3 passed

3 passed, 1 failed
```

The single failure was not a transport or Unreal failure. The executor rejected the new `set_actor_rotation` operation because `planning/unreal_tool_schema.py` had not yet registered that tool.

That boundary has now been repaired by adding the exact rotation schema:

```text
entity_ids
authorization_id
rotation:
  pitch
  yaw
  roll
```

Additional focused coverage was added for that tool-schema boundary.

### Next commands

```powershell
python -m pytest tests/test_unreal_actor_rotation_tool_schema.py -q
python -m pytest tests/test_unreal_actor_rotation_execution.py -q
```

Once both pass, proceed to the actual live gate:

```powershell
python -m pytest tests/test_unreal_actor_rotation_real_integration.py -vv -s
```

No Unreal harness rebuild is required for the Python-only schema fix. The previously implemented C++ rotation transport remains the code that will be exercised by the live integration test.

## Actor rotation architecture

The deterministic planner API is:

```python
UnrealTaskPlanner.plan_actor_rotation_write(intent, rotation)
```

It produces:

```text
READ inspect_target_actors
WRITE set_actor_rotation
VERIFY verify_target_actor_mapping
```

The Python capability registry accepts either the established actor-location payload or the actor-rotation payload for `MODIFY_ACTOR`, with strict fail-closed shape and numeric validation.

The Unreal transport implements `set_actor_rotation` on the Unreal game thread and returns fresh actor observation. Semantic verification continues to use the existing read-only `inspect_target_actors` transport operation; the wire protocol is not replaced.

## Proven production boundaries

- first real Unreal actor mutation and restoration;
- multi-operation actor-location mutation with independent verification;
- partial-failure recovery with fresh reassessment and no automatic mutation retry;
- explicit plan-bound replacement authorization;
- deterministic compound plan composition;
- material-variant mutation and verification.

## Important fixture convention

The current real integration fixture uses:

```text
FIELD_SURFACE
```

If Unreal reports `Actor not found for entity_id: FIELD_SURFACE`, fix the fixture's Atlas mapping/tag rather than introducing new entity discovery.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not weaken fail-closed validation.
- Keep development isolated from the action/workflow runner.
- Do not run workflow/action-runner tests unless explicitly authorized by the user.

## Architectural invariant

```text
Atlas owns the Twin.
Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
Failures require fresh evidence and explicit recovery.
Replacement mutations require explicit plan-bound authorization.
The Unreal Agent must never become a second autonomous authority separate from Atlas.
```
