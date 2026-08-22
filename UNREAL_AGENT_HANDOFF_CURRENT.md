# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026
**Current focus:** Live multi-operation failure/recovery boundary
**Current branch:** `feat/unreal-production-actor-write`
**Latest validated live gate:** compound actor-location sequence passed against the running Unreal Editor

## Current position

The Unreal Agent has crossed the first real Unreal production boundary and the first live multi-operation production boundary. The production adapter, Windows Named Pipe transport, actor-location write/verify path, read-only recovery reassessment, and the deterministic compound actor-location sequence have all been exercised against the running Unreal Editor.

Latest user-reported validation:

```text
python -m pytest tests/test_unreal_location_sequence.py -q
3 passed

python -m pytest tests/test_unreal_location_sequence_real_integration.py -vv -s
1 passed in 1.64s
```

The earlier full regression baseline remains green at:

```text
539 passed, 5 skipped
```

The two original live Unreal tests also pass:

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

## Multi-operation capability — LIVE PROVEN

`UnrealTaskPlanner.plan_actor_location_sequence(...)` produces a deterministic compound plan:

```text
READ
WRITE(location A)
VERIFY(location A)
WRITE(location B)
VERIFY(location B)
```

The live Unreal test `tests/test_unreal_location_sequence_real_integration.py` passed against the running Editor.

The live proof established that:

1. `FIELD_SURFACE` was inspected successfully;
2. the first location mutation executed;
3. the first mutation was independently verified;
4. the second location mutation executed;
5. the second mutation was independently verified;
6. the second verified state differed from the first;
7. the original actor location was restored in the test's cleanup path;
8. the executor preserved the declared operation/evidence order.

The unit regression `tests/test_unreal_location_sequence.py` also passed all 3 tests.

This is a meaningful milestone: Atlas is no longer proven only for a single isolated Unreal write. It now has a live proof of ordered multi-operation mutation with an independent proof boundary after each mutation.

## Recovery invariant

If any operation fails, execution stops at that operation. The executor preserves completed evidence and the exact operation boundary. Recovery may perform a fresh read-only reassessment, but it must never silently retry the mutation. Any replacement mutation requires explicit authorization.

The next work therefore focuses on the **live failure/recovery path for a partial multi-operation sequence**, not on another happy-path sequence test.

## Next major milestone — LIVE partial-failure recovery

The next milestone is to prove this sequence against the real Unreal Editor:

```text
READ
WRITE A
VERIFY A
WRITE B  ← failure boundary
HALT
↓
FRESH READ-ONLY REASSESSMENT
↓
CLASSIFY RESULT
↓
NO AUTOMATIC RETRY
```

The preferred implementation is to create a deterministic external failure condition at the second operation without changing the production wire protocol or weakening the executor. The test must establish that:

- the first mutation remains completed;
- the second operation is the exact failure boundary;
- no third mutation is sent;
- completed evidence and failed mutation intent remain available to recovery;
- fresh Unreal state is read after the failure;
- the reassessment decision does not authorize a mutation retry;
- the fixture is restored safely before the test exits.

A useful test should fail for a real transport/operation defect rather than converting the condition into a skip. Environmental unavailability may still be skipped only when the current integration conventions explicitly allow it.

## Important Unreal fixture convention

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

## What comes after the next gate

If the live partial-failure/recovery proof passes, the next production milestone is the explicit **replacement-plan authorization boundary**:

1. failed multi-operation sequence;
2. fresh reassessment;
3. explicit new mutation plan;
4. independent authorization of that replacement plan;
5. deterministic execution from the new plan;
6. final independent verification.

Only after that boundary is proven should the Unreal Agent move toward broader autonomous multi-operation task composition.

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
