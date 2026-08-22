# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — resumed session
**Current focus:** Live recovery-to-explicit-replacement authorization
**Current branch:** `feat/unreal-production-actor-write`
**Latest validated live gate:** partial multi-operation failure/recovery sequence passed against the running Unreal Editor

## Current position

The Unreal Agent has crossed the first real Unreal production boundary, the live multi-operation mutation boundary, and the live partial-failure/recovery boundary. The production adapter, Windows Named Pipe transport, actor-location write/verify path, read-only recovery reassessment, deterministic compound actor-location sequencing, and fail-closed partial recovery have all been exercised against the running Unreal Editor.

The next implementation is now prepared for the **LIVE AUTHORIZED REPLACEMENT** gate. A new real-integration test has been added at:

```text
tests/test_unreal_authorized_replacement_real_integration.py
```

That test intentionally exercises the complete boundary:

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

The test deliberately uses the same real `FIELD_SURFACE` Unreal fixture and real Named Pipe transport used by the preceding live gates. It also proves that the replacement authorization ID, rather than the failed or reassessment authorization ID, reaches Unreal for the replacement mutation.

## Latest validated baseline before the new gate

User-reported validation from the previous session:

```text
python -m pytest tests -q
539 passed, 5 skipped

python -m pytest tests/test_unreal_location_sequence_real_integration.py -vv -s
1 passed

python -m pytest tests/test_unreal_partial_sequence_recovery_real_integration.py -vv -s
1 passed

python -m pytest tests/test_unreal_plan_executor_real_integration.py::test_real_unreal_plan_executor_location_write_and_restore tests/test_unreal_recovery_coordinator_real_integration.py::test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write -vv -s
2 passed
```

The Named Pipe transport regression suite also passed, and the real Unreal transport/executor/recovery integration gates have been exercised successfully. The remaining skipped tests are environment-gated coverage and are not an action/workflow-runner blocker for the current milestone.

## Implemented production architecture

- `planning/unreal_task_planner.py`
  - deterministic inspection and actor-location planning;
  - compound actor-location sequence planning;
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
  - transport/evidence correlation.
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

Important invariant: the second write may have reached Unreal before its response was discarded, so the system treats the mutation state as uncertain rather than pretending the write definitely did or did not happen. Recovery reads fresh state and classifies it without replaying the write.

## Explicit replacement-plan authorization — IMPLEMENTED

`planning/unreal_plan_authorization.py` introduces the explicit authorization receipt required for a replacement mutation plan.

The receipt binds:

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

Unit coverage exists in `tests/test_unreal_plan_authorization.py` for exact-plan binding, changed-plan rejection, authorization propagation, wrong receipt type, and digest sensitivity to operation changes.

## Current gate — LIVE AUTHORIZED REPLACEMENT

Run this next against the running Unreal Editor:

```powershell
python -m pytest tests/test_unreal_authorized_replacement_real_integration.py -vv -s
```

The live proof must establish that:

- the replacement plan is distinct from the failed plan;
- reassessment confirms the live state without authorizing retry;
- a mismatched replacement plan is rejected before any transport call;
- the authorized replacement uses the new authorization ID;
- the replacement mutation is independently verified;
- the original Unreal fixture is restored safely.

If this gate passes, the next development step is to review the complete recovery-to-replacement boundary and then move toward broader autonomous multi-operation task composition without weakening Atlas authorization ownership.

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

The implementation is now waiting at the **LIVE AUTHORIZED REPLACEMENT** gate. Pull the branch and run the one integration test above with the Unreal Editor fixture available. Do not run action/workflow-runner tests without explicit authorization.
