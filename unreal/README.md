# Atlas Unreal Engine Validation

This directory contains the disposable Unreal Engine validation harness for Atlas and documents the transition into the production Unreal execution boundary.

## Current purpose

The harness is the **real-Unreal regression fixture** for the Unreal Agent architecture. It is intentionally disposable and is not the production Unreal adapter.

The current production work has progressed beyond the original engine smoke test: the real Windows/Unreal transport, first actor-location write/restore path, and recovery reassessment path have now been exercised successfully.

## Project

Open:

```text
unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject
```

The project is Editor-only and the harness does not replace the production transport implementation.

The current harness targets **Unreal Engine 5.6**.

## Proven engine smoke test

The Unreal Automation Test:

```text
Atlas.UnrealAgent.OperationBoundary
```

has passed in Unreal Engine 5.6.1.

It remains a regression fixture and should continue to pass after relevant Unreal-side changes.

## Real production proof

The first real production Unreal execution path has also passed from the Atlas Python test suite against the running Unreal Editor.

Passed integration tests:

```text
tests/test_unreal_plan_executor_real_integration.py::test_real_unreal_plan_executor_location_write_and_restore

tests/test_unreal_recovery_coordinator_real_integration.py::test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
```

These tests establish:

```text
Atlas operation
        ↓
production plan executor
        ↓
production Unreal adapter
        ↓
Windows Named Pipe transport
        ↓
real Unreal Editor
        ↓
Actor state
        ↓
independent evidence / verification
```

The recovery test additionally establishes that fresh live reassessment does **not** silently retry the previous mutation.

This is a first production-boundary proof, not a claim that all future Unreal capabilities are implemented.

## Current real fixture identity

The current real integration fixture uses the exact Atlas entity mapping/tag:

```text
FIELD_SURFACE
```

If a live test reports:

```text
Actor not found for entity_id: FIELD_SURFACE
```

verify that the intended Unreal Actor has the exact `FIELD_SURFACE` mapping/tag expected by the current transport/server implementation. Do not compensate by inventing entity discovery or changing the Atlas entity contract.

## Production transport boundary

The Windows Named Pipe transport now has bounded behavior for the important failure modes:

- bounded connection availability timeout;
- overlapped request writes;
- overlapped response reads;
- bounded pending-read timeout;
- cancellation of a timed-out pending read before cleanup;
- explicit handling of pywin32 `ERROR_IO_PENDING` results;
- server-disconnect error classification;
- unchanged JSON request/response framing.

Focused transport boundary tests and the full Python regression suite have passed in the current development cycle.

## Architecture

```text
Atlas intent
    ↓
Unreal Agent / planner
    ↓
strict operation contract
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
independent evidence
    ↓
Atlas verification / recovery
```

The Unreal Agent does not become an execution authority. Atlas authorization remains authoritative.

## Current capability boundary

The current C++ transport server has a narrower executable operation surface than the Python planner declares. The first production capability has been implemented and proven through the actor inspection/location path.

Do not assume that future material, lighting, Sequencer, camera, or other planned capabilities are already executable merely because their Python-side contracts exist.

The next capability must be selected deliberately and implemented end-to-end:

```text
Atlas authorization
→ transport
→ Unreal execution
→ evidence
→ independent verification
```

## Regression rules

- Do not weaken a failing test to make it pass.
- Preserve the disposable harness.
- Preserve fail-closed validation.
- Do not change the existing Named Pipe wire protocol.
- Do not add entity discovery as a workaround for fixture configuration.
- Keep the Unreal adapter stateless.
- Keep Atlas as the authorization and verification authority.
- Do not run workflow/action-runner tests unless explicitly authorized by the user.

## Next milestone

The next development target is **multi-operation production execution with failure containment**.

The Python-side implementation should first prove, with offline regression coverage:

1. ordered evidence before mutation;
2. exact authorization of the ordered operation set;
3. correctly bound evidence for every operation;
4. deterministic execution cursor advancement;
5. safe stop on a later operation failure;
6. preservation of completed write targets;
7. fresh read-only recovery reassessment;
8. no automatic mutation retry;
9. explicit authorization for any replacement plan;
10. independent verification before completion.

After that boundary is green, run the expanded multi-operation scenario against the real Unreal Editor.

## Detailed continuation state

See:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
UNREAL_AIDER_SCOPE.md
```

for the current production-boundary status, architectural constraints, and exact next gate.