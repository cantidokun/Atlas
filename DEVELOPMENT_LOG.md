# Atlas Development Log

## August 16, 2026 — Live Controller Passed / General Planning Integration

### Live controller result

The real local end-to-end controller test passed.

The controller:

1. started from measured BEFORE evidence
2. calculated the target state
3. executed both required `move_object` writes
4. performed an independent `inspect_object_relationship` verification
5. confirmed the required final state
6. built the final report in Python
7. exited without another Qwen reasoning cycle

Final verified state:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

### General Action Planning V1

Added:

`action_plan.py`

It contains:

- `ActionSpec` — one ordered authorized action
- `ActionPlan` — deterministic state for an ordered action sequence

The plan exposes the next action, records results, advances only after success, blocks after a required failure, reports completion, and provides a serializable state snapshot.

### General Evidence Planning V1

Added:

`evidence_plan.py`

It tracks ordered evidence requests, completion, reuse, and blocking failures.

### Planning Orchestrator V1

Added:

`planning_orchestrator.py`

It connects evidence and action plans. Action execution remains blocked until required evidence is complete.

### Controlled failure / recovery

The live recovery harness passed.

A failed write is detected as recoverable, fresh evidence is required, and automatic retry is refused. A new validated and explicitly authorized plan is required before retrying.

### Audit trail

The live action workflow records the lifecycle in order:

```text
Qwen proposal
 ↓
Evidence
 ↓
Authorization
 ↓
Execution 1
 ↓
Execution 2
 ↓
Verification
```

The final live test completed with an audit trail and independent verification.

### Qwen Structured Planning Bridge — PASS

Added:

`live_qwen_planning_loop.py`

The live planning bridge now proves:

```text
Qwen structured plan
 ↓
Python plan validation
 ↓
Read-only Blender evidence
 ↓
Planning orchestrator
 ↓
Structured action plan
 ↓
No write execution
```

The successful run produced:

- 1 structured evidence request
- 2 structured actions
- validated plan
- authoritative read-only evidence
- completed evidence plan
- structured action plan with the next action exposed
- zero write execution

Result:

```text
QWEN PLAN ACCEPTED
EVIDENCE VERIFIED READ-ONLY
ACTION PLAN STRUCTURED
WRITE EXECUTION NOT PERFORMED
ATLAS QWEN PLANNING BRIDGE TEST: PASS
```

This is the first live boundary between Qwen task planning and the generic Python planning primitives.

### Regression status

Latest local regression result at this early checkpoint:

```text
98 passed
```

## August 17, 2026 — Runtime Continuation Integrity Milestone

The runtime-integrity boundary was promoted from an isolated regression primitive into the actual autonomous continuation/resume path.

Implemented and merged in PR #9:

- `RuntimeIntegrity` receipts are serializable and persisted with future runtime checkpoints.
- `AutonomousFutureRuntime` binds continuation to stable instruction fingerprint, authorized future/plan digest, and exact persisted checkpoint-state digest.
- validated resume fails closed when the receipt is missing, tampered, the stable instructions change, or the authorized future changes.
- `resume_from_store()` makes the validated resume boundary explicit.
- regression coverage was added for matching, changed-context, tampered-receipt, missing-receipt, and exact-checkpoint continuation.
- an existing Unreal planner regression was corrected so empty target sets fail closed rather than producing an executable plan.

Validation:

```text
Atlas Tests PR run #348
Python 3.9: PASS
Python 3.11: PASS
```

The next major development target became the broader live autonomous-task proof: use a second non-goalpost production task to demonstrate that the same generic conditional planning, authorization, deterministic future, verification, recovery, and continuation-integrity machinery works outside the original goalpost fixture.

## August 21, 2026 — Unreal Architecture Decision Finalized

### Comprehensive Unreal Integration Audit Completed

A complete source-level audit of the Unreal integration architecture was conducted across the Unreal-specific planning, capability, adapter, executor, evidence, schema, and transport layers.

### Final Architectural Decision: Option B Investigation CLOSED

**Decision:** `UnrealPlanExecutor` remains the Unreal-specific execution boundary. `AdapterExecutionBridge` integration is NOT pursued.

**Rationale:**
- Option B would require breaking API changes to `UnrealPlanExecutor` constructor
- Generic `AdapterExecutionBridge` does not support Unreal-specific READ/WRITE/VERIFY dispatch
- `TwinRepresentation` dependencies are not available in the Unreal context
- authorization propagation is incompatible with the generic adapter contract

### Confirmed Unreal Execution Architecture

```text
UnrealTaskPlanner
→ UnrealTaskPlan
→ UnrealPlanExecutor
→ UnrealAdapterProduction
→ UnrealTransport
→ Unreal Process
→ UnrealEvidence
→ UnrealPlanExecutor validation/ledger
```

Key confirmations:

- READ/WRITE/VERIFY dispatch remains Unreal-specific;
- `authorization_id` propagates through the complete execution path;
- authorization validation remains delegated to the Unreal process;
- generic Atlas infrastructure remains unchanged;
- the Unreal integration preserves the intended separation from generic orchestration.

### Production Named Pipe hardening

The Windows Named Pipe transport was hardened against indefinite response-read blocking while preserving the existing JSON wire protocol.

The corrected transport uses a genuinely overlapped pipe handle, bounded pending response reads, explicit pywin32 result-code handling, cancellation on timeout, and safe cleanup.

Focused regression coverage was added for connection timeout, pending-read timeout, cancellation, and server-disconnect behavior.

## August 22, 2026 — First Real Unreal Production Boundary Milestone

### Regression and boundary fixes

The Unreal production path went through several deliberately fail-closed fixes during live validation.

A malformed fresh Unreal state containing a non-numeric coordinate was initially classified incorrectly as `STATE_CHANGED`. The reassessment decision boundary was corrected so malformed fresh evidence remains `INSUFFICIENT_EVIDENCE` / uncertain rather than being treated as proof of a changed state.

An evidence/transport metadata consistency issue was also corrected so transport requests and the corresponding evidence ledger entries remain aligned through the executor pipeline.

The Named Pipe transport failure boundary was hardened further so:

- `WaitNamedPipe` timeout is translated before `CreateFile` is attempted;
- pending response-read timeouts cancel the pending operation and close handles safely;
- pywin32 `ReadFile` result codes are interpreted correctly rather than assuming asynchronous completion always raises an exception.

### Full regression status

The latest full local regression reported:

```text
530 passed, 5 skipped
```

The focused transport boundary tests then passed, and the user subsequently reported the remaining skipped coverage as passed as well.

The key focused Unreal recovery/executor suite reached:

```text
24 passed
```

and the recovery coordinator/executor integration suite reached:

```text
22 passed
```

### Real Unreal Editor proof — PASS

The first actual production-boundary tests were run against the running Unreal Editor.

Passed:

```text
test_real_unreal_plan_executor_location_write_and_restore

test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
```

The combined live run passed both tests.

Earlier live Unreal transport/integration checks also passed when the Editor transport was available, including real connection, sequential requests, production actor write/restore, and recovery reassessment.

### What is now proven

Atlas has now demonstrated the following real process-boundary sequence:

```text
Atlas operation
    ↓
production Unreal adapter
    ↓
Windows Named Pipe transport
    ↓
real Unreal Editor
    ↓
actor state mutation
    ↓
independent state readback
    ↓
verification
    ↓
restore
```

And for recovery:

```text
mutation / verification uncertainty
    ↓
fresh live Unreal observation
    ↓
reassessment
    ↓
NO automatic mutation retry
```

This is a genuine external production-boundary milestone. It is not yet proof of arbitrary multi-operation Unreal production automation.

### Fixture lesson

The live integration initially failed because the expected Unreal entity mapping was absent:

```text
Actor not found for entity_id: FIELD_SURFACE
```

The correct resolution was to configure the Unreal fixture with the exact expected `FIELD_SURFACE` entity mapping/tag rather than changing Atlas entity discovery or weakening the Python contract.

This convention is now documented in the Unreal handoff and Unreal README.

### Current architectural boundary

Python currently declares/plans additional Unreal capabilities beyond the operation surface implemented by the current C++ transport server. The next capability must therefore be selected deliberately and implemented end-to-end.

Do not broaden the C++ operation surface merely because a future capability exists in Python planning code.

## August 22, 2026 — Next Milestone Definition

The next major development target is **multi-operation production execution with failure containment**.

The Python-side implementation should establish:

1. ordered evidence before mutation;
2. exact authorization of the ordered operation set;
3. evidence bound to each exact operation/entity target;
4. deterministic execution cursor advancement;
5. safe stop when a later operation fails;
6. preservation of completed write targets;
7. fresh read-only reassessment after uncertain mutation/verification;
8. no automatic mutation retry;
9. explicit authorization for any replacement plan;
10. independent verification before completion.

Only after this boundary is green in offline regression should the expanded multi-operation scenario be exercised against the real Unreal Editor.

### Action-runner constraint

Do not run workflow/action-runner tests unless the user explicitly authorizes them. Continue isolated development that cannot create system conflicts while the external runner is unavailable or intentionally unused.

### Documentation checkpoint

The following current-state documents were updated after the real production-boundary milestone:

- `UNREAL_AGENT_HANDOFF_CURRENT.md`
- `UNREAL_AIDER_SCOPE.md`
- `unreal/README.md`

These documents now identify the first real production proof as passed and point to the multi-operation/failure-containment milestone as the next gate.
