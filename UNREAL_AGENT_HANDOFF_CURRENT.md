# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026
**Current focus:** Production Unreal execution boundary and multi-operation readiness
**Current branch:** `feat/unreal-production-actor-write`
**Current remote HEAD:** `a8608dd` or newer; always pull the current branch before continuing

## Current position

The Unreal Agent has progressed from the disposable Unreal Engine validation harness through the real Windows/Unreal transport boundary and the first live production execution/recovery proofs.

The current milestone is **real Unreal production-boundary validation passed** for the implemented actor-location capability and its recovery path. The next development phase is to generalize safe execution across realistic multi-operation production plans while preserving fail-closed behavior.

Atlas owns the canonical Digital Twin. Unreal is a production representation/execution tool around that canonical state, not the source of truth.

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

## Implemented Unreal-side architecture

- `planning/unreal_agent.py`
  - structured Unreal capabilities, operation kinds, intents, and proposals;
  - no direct execution authority.
- `planning/unreal_capability_registry.py`
  - capability permissions;
  - required evidence declarations;
  - exact operation argument validation.
- `planning/unreal_operation_contract.py`
  - strict AI-facing parsing;
  - exact top-level operation schema;
  - no fuzzy coercion.
- `planning/unreal_task_planner.py`
  - deterministic inspection flow;
  - production operation planning primitives.
- `planning/unreal_evidence_contract.py`
  - engine-neutral post-execution evidence shape;
  - operation/entity binding validation.
- `planning/unreal_adapter_production.py`
  - stateless production adapter boundary;
  - authorization propagation;
  - enriched operation failure context.
- `planning/unreal_transport_contract.py`
  - request/response transport contract and correlation validation.
- `planning/unreal_transport_serialization.py`
  - strict JSON serialization/deserialization boundary.
- `planning/unreal_transport_named_pipe.py`
  - Windows Named Pipe production transport;
  - bounded connection and response-read timeouts;
  - overlapped request/response I/O;
  - cancellation and cleanup on pending-read timeout;
  - typed transport failure translation.
- `planning/unreal_plan_executor.py`
  - Unreal-specific READ/WRITE/VERIFY dispatch;
  - independent evidence validation and ledger handling;
  - completed-target preservation across failures.
- `planning/unreal_recovery_policy.py`
  - fail-closed mutation/verification/observation failure classification.
- `planning/unreal_reassessment_decision.py`
  - fresh-state reassessment;
  - malformed evidence remains uncertain;
  - changed state never authorizes retry.
- `planning/unreal_reassessment_planner.py`
  - targeted read-only reassessment plans.
- `planning/unreal_recovery_orchestrator.py`
  - converts eligible failures into targeted reassessment plans without automatic mutation retry.
- `planning/unreal_recovery_coordinator.py`
  - coordinates post-failure fresh observation and reassessment decisions.

## Production evidence and recovery milestone — August 22, 2026

The following behavior is now covered by the Unreal regression suite:

- exact operation/entity binding in evidence;
- malformed fresh Unreal state remains `INSUFFICIENT_EVIDENCE` rather than being misclassified as a state change;
- changed fresh state never authorizes a retry;
- reassessment rejects wrong targets and halt assessments;
- mutation failure preserves requested targets without inventing completed evidence;
- post-write verification failure preserves completed write targets;
- observation/unknown failures halt fail closed;
- inconsistent completed targets are rejected;
- executor rejects unverified writes and incorrect verification targets;
- executor verifies actor location after writes;
- executor preserves mutation intent and boundary information on failure;
- recovery coordinator reassesses live state without retrying the mutation.

## Real Unreal production proof — PASSED

The local Windows/Unreal Editor boundary has now been exercised against the actual running Unreal process.

The proven real integration tests include:

```text
test_real_unreal_plan_executor_location_write_and_restore
    → PASS

test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
    → PASS
```

The combined live run passed both tests.

Earlier live transport/integration validation also passed the available real Unreal connection and sequential-request checks when the Editor transport was available.

The live proof establishes that Atlas can:

1. inspect the real `FIELD_SURFACE` entity;
2. execute the authorized actor-location write through the production adapter and Named Pipe transport;
3. verify the resulting Unreal state independently;
4. restore the actor state;
5. encounter a recovery scenario and reassess fresh live Unreal state;
6. refuse to silently retry the mutation during reassessment.

This is the first meaningful real-process production-boundary proof. It is not yet proof of broad arbitrary production-task execution.

## Transport boundary — PASSED

The production Windows Named Pipe transport has been hardened and its important failure boundaries are regression-tested.

Confirmed behavior:

- connection availability has a bounded timeout;
- the client pipe handle is opened for overlapped I/O;
- request writes use overlapped I/O while preserving request bytes/framing;
- response reads use an allocated bounded buffer;
- pending response reads have a bounded timeout;
- timeout cancellation occurs before handle cleanup;
- pywin32 `ReadFile` result codes are handled explicitly, including `ERROR_IO_PENDING`;
- server disconnects remain distinguishable transport failures;
- the existing JSON Named Pipe wire protocol was not changed.

The focused transport boundary tests pass, and the full Python regression suite is green at the latest reported run:

```text
530 passed, 5 skipped
```

The remaining five tests were subsequently exercised by the user and reported as passing. The targeted real Unreal tests also passed after the transport boundary was cleared.

## Current production capability boundary

The current C++ Unreal transport server implements the actor inspection/location path required by the first production proof. Python still declares/plans additional future operations, including material inspection/variants and verification operations.

Do **not** infer that every planner capability is executable in Unreal merely because Python declares it.

The next production capability must be selected deliberately and implemented end-to-end:

```text
Atlas authorization
→ transport request
→ Unreal execution
→ independent evidence
→ Atlas verification
```

## Disposable Unreal Engine 5.6 harness

Project:

`unreal/AtlasUnrealHarness/`

Target:

**Unreal Engine 5.6**

Automation test:

`Atlas.UnrealAgent.OperationBoundary`

The harness is Editor-only and disposable. It remains a regression fixture and is not the production adapter.

The harness has passed in Unreal Engine 5.6.1 after a temporary-Actor transform-root defect was corrected without weakening the assertion.

## Important Unreal fixture convention

The current real integration fixture uses Atlas entity ID/tag:

```text
FIELD_SURFACE
```

The Unreal Actor must expose the Atlas entity mapping expected by the transport implementation. If the real integration reports `Actor not found for entity_id: FIELD_SURFACE`, first verify that the Actor has the exact `FIELD_SURFACE` mapping/tag required by the current harness/server contract before changing Python code.

Do not introduce an alternative entity-discovery mechanism merely to make the fixture pass.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Do not change the existing Named Pipe wire protocol.
- Do not introduce entity discovery or an Atlas-side entity cache.
- Do not add metrics unless a source audit establishes a concrete need.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Keep generic Atlas orchestration unchanged unless a shared-interface requirement is demonstrated.
- Do not weaken existing fail-closed validation.
- Do not run workflow/action-runner tests unless the user explicitly authorizes them.

## Next major milestone

The next milestone is **multi-operation production execution with failure containment**.

Develop the smallest reusable path that can execute a realistic ordered Unreal plan and prove:

1. inspection/evidence occurs before mutation;
2. authorization covers the exact ordered operations;
3. operation results are recorded per operation;
4. successful operations advance the execution cursor;
5. a later failure prevents subsequent unauthorized/unsafe operations;
6. completed write targets are preserved accurately;
7. recovery performs fresh read-only reassessment;
8. reassessment never silently retries the previous mutation;
9. a replacement plan requires explicit authorization;
10. final completion requires independent verification.

Keep this development isolated from the action/workflow runner.

## Next Unreal-dependent gate

Once the Python-side multi-operation boundary is implemented and fully regression-tested, the next required external gate will be a real Unreal Editor run exercising the expanded operation sequence. Stop at that point and provide the user with the exact command/test required.

Do not manufacture additional Unreal-specific complexity before that gate is reached.

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