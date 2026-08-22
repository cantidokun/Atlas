# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026
**Current focus:** Real Unreal multi-operation production gate
**Current branch:** `feat/unreal-production-actor-write`
**Latest branch development commits:** `20a4b265` and `372ad001`

## Current position

The Unreal Agent has crossed the first real Unreal production boundary. The production adapter, Windows Named Pipe transport, actor-location write/verify path, and read-only recovery reassessment have all been exercised against the running Unreal Editor.

The latest user-reported full regression is:

```text
539 passed, 5 skipped
```

The two existing live Unreal tests also pass:

```text
test_real_unreal_plan_executor_location_write_and_restore                         PASS
test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write PASS
```

Atlas remains the authority. Unreal is a production execution/evidence environment around the Atlas-owned canonical Digital Twin.

## Proven execution architecture

```text
Atlas production intent
        ↓
Unreal Agent / task planner
        ↓
Capability registry + strict operation contract
        ↓
Atlas authorization
        ↓
UnrealPlanExecutor
        ↓
UnrealAdapterProduction
        ↓
Windows Named Pipe transport
        ↓
Unreal Engine
        ↓
Independent Unreal evidence
        ↓
Atlas verification / recovery policy
```

The Unreal Agent proposes/decomposes operations. It does not authorize or directly execute them.

## Implemented production architecture

- `planning/unreal_task_planner.py`
  - deterministic inspection and actor-location planning;
  - compound actor-location sequence planning;
  - every mutation is immediately followed by verification.
- `planning/unreal_plan_executor.py`
  - strict ordered READ/WRITE/VERIFY dispatch;
  - evidence ledger;
  - immediate failure boundary;
  - preservation of completed evidence and exact mutation intent.
- `planning/unreal_recovery_policy.py`
  - fail-closed mutation/verification/observation failure classification.
- `planning/unreal_reassessment_planner.py`
  - targeted read-only reassessment plans.
- `planning/unreal_recovery_orchestrator.py`
  - converts eligible failures into targeted reassessment plans without automatic mutation retry.
- `planning/unreal_recovery_coordinator.py`
  - executes fresh read-only reassessment and returns the resulting decision.
- `planning/unreal_adapter_production.py`
  - stateless production adapter;
  - authorization propagation;
  - transport/evidence correlation.
- `planning/unreal_transport_named_pipe.py`
  - bounded Windows Named Pipe transport;
  - typed timeout/disconnect failure translation;
  - pending-read cancellation and cleanup.

## Multi-operation capability

`UnrealTaskPlanner.plan_actor_location_sequence(...)` now produces a deterministic compound plan:

```text
READ
WRITE(location A)
VERIFY(location A)
WRITE(location B)
VERIFY(location B)
...
```

The executor rejects any write that is not immediately followed by verification for the same targets.

Unit coverage now includes sequence execution/order and a failure-containment regression. The new failure test proves that when the second write fails:

- execution stops exactly at that operation;
- no later operation is sent;
- completed evidence is preserved;
- the failed write's exact location intent is preserved for recovery;
- the already-applied first mutation is not silently retried.

## Real Unreal proof already passed

The running Unreal Editor has already proven:

1. live actor inspection of `FIELD_SURFACE`;
2. authorized actor-location mutation through the production adapter;
3. independent post-write verification;
4. restoration to the original location;
5. read-only recovery reassessment after a simulated failure boundary;
6. no silent mutation retry during reassessment.

## Current external gate

A new live integration test has now been added:

```text
tests/test_unreal_location_sequence_real_integration.py
```

It is intentionally narrow. It must prove against the running Unreal Editor that:

1. `FIELD_SURFACE` can be inspected;
2. the first location write succeeds;
3. the first location is independently verified;
4. the second location write succeeds;
5. the second location is independently verified;
6. the second verified location differs from the first;
7. the fixture is restored to its original location;
8. the sequence produces exactly the declared READ/WRITE/VERIFY operation order.

**This is now the next Unreal-dependent gate.** Do not add more Unreal-specific architecture before this test passes unless the live result exposes a genuine implementation defect.

Suggested command after pulling the latest branch:

```powershell
python -m pytest tests/test_unreal_location_sequence_real_integration.py -vv -s
```

If the Editor transport or `FIELD_SURFACE` fixture is unavailable, the test may skip for those explicit environmental conditions. A real transport/operation failure must not be converted into a skip.

## Recovery invariant

If any operation fails, execution stops at that operation. The executor preserves completed evidence and the exact operation boundary. Recovery may perform a fresh read-only reassessment, but it must never silently retry the mutation. Any replacement mutation requires explicit authorization.

## Unreal fixture convention

The current real integration fixture uses the Atlas entity ID/tag:

```text
FIELD_SURFACE
```

If Unreal reports `Actor not found for entity_id: FIELD_SURFACE`, fix the Unreal fixture's Atlas mapping/tag rather than introducing another discovery mechanism.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Do not change the existing Named Pipe wire protocol.
- Do not introduce entity discovery or an Atlas-side entity cache.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not weaken fail-closed validation.
- Keep development isolated from the action/workflow runner.
- Do not run workflow/action-runner tests unless explicitly authorized by the user.

## What comes after the gate

If the live compound sequence passes, the next development milestone is broader multi-operation failure/recovery behavior against the real Editor. The likely progression is:

1. live sequence success proof;
2. live mid-sequence failure containment with preserved recovery context;
3. live read-only reassessment of that partial state;
4. explicit re-authorization boundary for any replacement mutation plan;
5. reusable multi-operation production task composition.

Do not skip directly to broad autonomous behavior. Each new production capability must preserve the same Atlas authority, explicit authorization, deterministic execution, independent verification, and fail-closed recovery model.

## Architectural invariant

```text
Atlas owns the Twin.
Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
Failures require fresh evidence and explicit recovery.
```

The Unreal Agent must never become a second autonomous authority separate from Atlas.
