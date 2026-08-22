# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — resumed development
**Current focus:** Deterministic compound task-plan composition
**Current branch:** `feat/unreal-production-actor-write`
**Latest validated live gate:** explicit recovery-to-authorized-replacement passed against the running Unreal Editor

## Current position

The Unreal Agent has crossed the first real Unreal production boundary, the live multi-operation mutation boundary, the live partial-failure/recovery boundary, and the live recovery-to-explicit-replacement authorization boundary.

The latest live authorized-replacement proof established:

```text
FAILED MULTI-OPERATION SEQUENCE
        ↓
FRESH READ-ONLY REASSESSMENT
        ↓
CONFIRMED STATE / NO RETRY AUTHORIZATION
        ↓
EXPLICIT NEW REPLACEMENT PLAN
        ↓
PLAN-BOUND ATLAS AUTHORIZATION RECEIPT
        ↓
MISMATCHED PLAN REJECTED BEFORE TRANSPORT
        ↓
execute_authorized(EXACT PLAN, RECEIPT)
        ↓
WRITE
VERIFY
        ↓
RESTORE ORIGINAL FIXTURE
```

The replacement mutation used its new authorization ID and the modified replacement plan was rejected before any transport request.

## New development completed after the live replacement gate

`UnrealTaskPlanner.compose_plans(...)` now provides a controlled composition boundary for broader autonomous multi-operation planning.

The composition API deliberately does **not** create new operations or grant authority. It accepts already validated `UnrealTaskPlan` instances and:

- requires one explicit `UnrealTaskIntent`;
- requires at least one sub-plan;
- requires every sub-plan to use the same `intent_id`;
- preserves the exact caller-supplied sub-plan order;
- returns a new immutable `UnrealTaskPlan` containing the concatenated operations;
- leaves authorization entirely outside planning.

New unit coverage:

```text
tests/test_unreal_plan_composition.py
```

The next live gate is:

```text
tests/test_unreal_compound_plan_real_integration.py
```

It composes an inspection plan and an actor-location mutation plan, executes the resulting five-operation plan against the real Unreal Editor, checks the ordered evidence and wire requests, and restores the original fixture.

## Implemented production architecture

- `planning/unreal_task_planner.py`
  - deterministic inspection and actor-location planning;
  - compound actor-location sequence planning;
  - deterministic composition of already validated sub-plans;
  - every mutation is immediately followed by verification.
- `planning/unreal_plan_executor.py`
  - strict ordered READ/WRITE/VERIFY dispatch;
  - evidence ledger;
  - immediate failure boundary;
  - preservation of completed evidence and exact mutation intent;
  - explicit `execute_authorized(...)` boundary for plan-bound mutation authorization.
- `planning/unreal_plan_authorization.py`
  - immutable SHA-256 receipt binding an exact `UnrealTaskPlan` to an authorization ID;
  - changed plans are rejected before transport;
  - receipt authorization ID is the only ID propagated through authorized execution.
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
  - transport/evidence correlation;
  - semantic VERIFY mapping to fresh read-only transport observation where the wire protocol has no distinct VERIFY command.
- `planning/unreal_transport_named_pipe.py`
  - bounded Windows Named Pipe transport;
  - typed timeout/disconnect failure translation;
  - pending-read cancellation and cleanup.

## Multi-operation capability — LIVE PROVEN

`UnrealTaskPlanner.plan_actor_location_sequence(...)` produces:

```text
READ
WRITE(location A)
VERIFY(location A)
WRITE(location B)
VERIFY(location B)
```

The live Unreal location-sequence test passed against the running Editor. The test proved ordered mutation, independent verification after every write, changed state between writes, and safe restoration of the original location.

## Partial-failure recovery — LIVE PROVEN

The live partial-sequence test proves:

```text
READ
WRITE A
VERIFY A
WRITE B  ← deliberate response-loss/failure boundary
HALT
↓
FRESH READ-ONLY REASSESSMENT
↓
CLASSIFY RESULT
↓
NO AUTOMATIC RETRY
```

The second write may have reached Unreal before its response was discarded, so Atlas treats the mutation state as uncertain rather than pretending the write definitely did or did not happen. Recovery reads fresh state and classifies it without replaying the write.

## Explicit replacement-plan authorization — LIVE PROVEN

`planning/unreal_plan_authorization.py` binds:

```text
exact UnrealTaskPlan
        ↓
SHA-256 plan digest
        ↓
Atlas authorization ID
```

`UnrealPlanExecutor.execute_authorized(...)` enforces:

1. the caller supplies an `UnrealPlanAuthorization` receipt;
2. the receipt matches the exact replacement plan;
3. a modified plan is rejected before any transport call;
4. the receipt's authorization ID is propagated to Unreal;
5. normal WRITE→VERIFY execution rules remain in force.

The real integration test `tests/test_unreal_authorized_replacement_real_integration.py` passed against the running Editor.

## Compound task-plan composition — IMPLEMENTED, LIVE GATE NEXT

The new composition boundary is intentionally conservative:

```text
Atlas intent
    ↓
validated sub-plan A
    +
validated sub-plan B
    +
...
    ↓
ordered UnrealTaskPlan
    ↓
Atlas authorization
    ↓
executor
```

Composition does not authorize, mutate, discover entities, or reorder operations.

Unit gate added:

```powershell
python -m pytest tests/test_unreal_plan_composition.py -q
```

Live gate to run next with the Unreal Editor fixture available:

```powershell
python -m pytest tests/test_unreal_compound_plan_real_integration.py -vv -s
```

The live gate must establish:

- sub-plan operations remain in exact order;
- the composed plan executes through the existing executor boundary;
- read-only semantic verification still maps correctly at the wire boundary;
- the single compound authorization ID reaches every transport request;
- the mutation is independently verified;
- the original `FIELD_SURFACE` fixture is restored.

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

The implementation is now at the **LIVE COMPOUND PLAN COMPOSITION** gate. Pull `feat/unreal-production-actor-write`, run the new unit test, then run the live integration gate with the Unreal Editor fixture available. Do not run action/workflow-runner tests without explicit authorization.
