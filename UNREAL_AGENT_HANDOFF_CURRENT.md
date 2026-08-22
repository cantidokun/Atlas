# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — actor-rotation capability development
**Current focus:** Controlled actor transform expansion — rotation
**Current branch:** `feat/unreal-production-actor-write`
**Latest validated live gates:** recovery-to-explicit-authorized replacement, compound plan execution, and material-variant execution passed against the running Unreal Editor.

## Current position

The Unreal Agent has crossed the first real Unreal production boundary, multi-operation mutation, partial-failure/recovery, explicit replacement authorization, deterministic compound-plan composition, and material-variant mutation/verification.

The next capability is actor rotation. It extends the existing `MODIFY_ACTOR` capability rather than introducing a parallel execution architecture.

## Actor rotation — IMPLEMENTED, LIVE GATE NEXT

The new deterministic planner API is:

```python
UnrealTaskPlanner.plan_actor_rotation_write(intent, rotation)
```

It produces:

```text
READ inspect_target_actors
WRITE set_actor_rotation
VERIFY verify_target_actor_mapping
```

The write payload is exactly:

```text
entity_ids
rotation:
  pitch
  yaw
  roll
```

The capability registry now accepts either the established actor-location payload or the new actor-rotation payload for `MODIFY_ACTOR` writes, with strict numeric validation and fail-closed key sets.

The production Unreal transport now supports:

```text
set_actor_rotation
```

The mutation runs on Unreal's game thread, changes the actor's `FRotator`, and returns fresh actor observation. Semantic verification continues to use the existing read-only `inspect_target_actors` transport operation, preserving independent verification without changing the wire protocol.

Focused coverage added:

```text
tests/test_unreal_actor_rotation_schema.py
tests/test_unreal_actor_rotation_execution.py
tests/test_unreal_actor_rotation_real_integration.py
```

### Required live gate

After pulling the branch and rebuilding the Unreal harness:

```powershell
python -m pytest tests/test_unreal_actor_rotation_execution.py -q
python -m pytest tests/test_unreal_actor_rotation_real_integration.py -vv -s
```

The live gate must prove:

- original rotation is read from real Unreal;
- exact rotation write reaches the real Editor;
- the returned write evidence contains the requested rotation;
- the independent VERIFY evidence contains the requested rotation;
- the original rotation is restored even when the test exits through an assertion/failure path;
- the existing `FIELD_SURFACE` mapping is reused;
- no new entity-discovery mechanism is introduced.

## Proven production architecture

- `planning/unreal_task_planner.py`
  - deterministic inspection;
  - actor-location write and multi-location sequences;
  - actor-rotation write;
  - material-variant write/verify;
  - deterministic composition of already validated sub-plans.
- `planning/unreal_capability_registry.py`
  - fail-closed operation schemas;
  - strict actor location/rotation payload validation;
  - explicit material-variant schemas.
- `planning/unreal_plan_executor.py`
  - strict ordered READ/WRITE/VERIFY dispatch;
  - evidence ledger;
  - immediate failure boundary;
  - exact-plan authorized execution.
- `planning/unreal_plan_authorization.py`
  - immutable SHA-256 receipt binding an exact `UnrealTaskPlan` to an authorization ID;
  - changed plans rejected before transport.
- `planning/unreal_recovery_policy.py`
  - fail-closed mutation/verification/observation failure classification.
- `planning/unreal_reassessment_planner.py`
  - targeted read-only reassessment plans.
- `planning/unreal_recovery_orchestrator.py`
  - converts eligible failures into targeted reassessment without automatic mutation retry.
- `planning/unreal_recovery_coordinator.py`
  - executes fresh read-only reassessment and returns the resulting decision.
- `planning/unreal_adapter_production.py`
  - stateless production adapter;
  - authorization propagation;
  - transport/evidence correlation;
  - semantic VERIFY mapping to fresh read-only observations.
- `planning/unreal_transport_named_pipe.py`
  - bounded Windows Named Pipe transport;
  - typed timeout/disconnect translation;
  - pending-read cancellation and cleanup.
- `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`
  - real Unreal game-thread execution for actor location, actor rotation, and material variant operations.

## Live-proven boundaries

### Multi-operation actor mutation

The live location-sequence proof establishes:

```text
READ
WRITE(location A)
VERIFY(location A)
WRITE(location B)
VERIFY(location B)
```

with ordered mutation, independent verification, changed state between writes, and fixture restoration.

### Partial-failure recovery

The live failure proof establishes:

```text
READ
WRITE A
VERIFY A
WRITE B ← response-loss boundary
HALT
↓
FRESH READ-ONLY REASSESSMENT
↓
CLASSIFY
↓
NO AUTOMATIC RETRY
```

### Explicit replacement authorization

Recovery informs a replacement but does not authorize it. The replacement plan is independently authorized, plan-bound, and rejected before transport if modified.

### Compound plan composition

`UnrealTaskPlanner.compose_plans(...)` concatenates already validated plans for one intent without inventing operations, reordering them, or granting authority. The real compound-plan integration gate passed.

### Material variant

Material variant planning and transport are now live-proven. The current harness represents the semantic material variant as explicit actor state/tag data, avoiding asset discovery or an Atlas-side cache.

## Important fixture convention

The current real integration fixture uses:

```text
FIELD_SURFACE
```

If Unreal reports `Actor not found for entity_id: FIELD_SURFACE`, fix the Unreal fixture's Atlas mapping/tag rather than changing Atlas entity discovery.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Do not introduce entity discovery or an Atlas-side entity cache.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not weaken fail-closed validation.
- Keep development isolated from the action/workflow runner.
- Do not run workflow/action-runner tests unless explicitly authorized by the user.
- Preserve the existing Named Pipe protocol; new operations may extend its existing operation-name surface without replacing the protocol.

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

## End-of-session resume point

The implementation is now at the **LIVE ACTOR ROTATION** gate. Pull `feat/unreal-production-actor-write`, run the focused rotation unit/schema coverage, rebuild the Unreal harness, then run the real rotation integration test with the Editor open and `FIELD_SURFACE` present. Do not run action/workflow-runner tests without explicit authorization.
