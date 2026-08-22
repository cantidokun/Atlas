# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The real Unreal Engine 5.6 smoke test has **PASSED**:

`Atlas.UnrealAgent.OperationBoundary`

The disposable harness remains a confirmed real-engine regression fixture. Development has now progressed beyond the engine smoke test into the real production transport, actor write/restore, and recovery-coordination boundary.

## Current milestone — August 22, 2026

The first real production Unreal execution path has been proven against the running Unreal Editor.

Passed live integration coverage includes:

- production plan executor actor-location write and restore;
- recovery coordinator reassessment of live Unreal state without retrying the mutation.

The Python regression suite is also green at the latest reported full run, and the focused Windows Named Pipe timeout/failure boundaries have passed.

This establishes the first real process-boundary proof but does **not** establish broad arbitrary Unreal production-task execution.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- The Unreal Agent reasons and plans; it does not authorize.
- Atlas authorization remains authoritative.
- The Unreal adapter executes authorized operations.
- Unreal provides independent execution evidence.
- Atlas verifies that evidence independently.
- The disposable Unreal harness is a regression fixture, not the production adapter.
- The Unreal adapter remains stateless.
- Mutation failures and uncertain state require fresh authoritative evidence before recovery.
- Automatic mutation retry is prohibited.

## Aider operating rules

1. Preserve existing Unreal contracts and fail-closed behavior.
2. Do not weaken, remove, bypass, or rewrite tests merely to make them pass.
3. Do not modify Blender-specific implementation or tests unless a shared-interface change is demonstrably required and explicitly reviewed.
4. Preserve the disposable Unreal harness and keep `Atlas.UnrealAgent.OperationBoundary` passing after relevant changes.
5. Prefer small, deterministic changes with regression coverage.
6. Keep Unreal-specific code and tests clearly scoped.
7. Treat `UNREAL_AGENT_HANDOFF_CURRENT.md` as the authoritative continuation context.
8. For complex changes, audit before editing and verify affected tests before committing when test execution is authorized.
9. Do not introduce a second authorization authority inside Unreal.
10. Do not revisit AdapterExecutionBridge or Option B.
11. Do not change the existing Named Pipe wire protocol.
12. Do not introduce entity discovery or an Atlas-side entity cache.
13. Do not add metrics unless a source audit establishes a concrete need.
14. Do not run workflow/action-runner tests unless the user explicitly authorizes them.
15. Continue isolated source-level development when it cannot create system conflicts.
16. Stop at the next genuine Unreal-dependent gate rather than inventing additional engine-specific complexity prematurely.

## Existing Unreal work

The current architecture includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, production adapter boundary, Windows Named Pipe transport, plan executor, recovery policy, reassessment decision/planner, recovery orchestrator/coordinator, and the disposable Unreal Engine 5.6 validation harness.

## Production transport milestone — PASSED

The Python Named Pipe transport has been hardened against indefinite response-read blocking without changing the wire protocol.

Current transport behavior:

- bounded connection availability timeout;
- client pipe handle opened with `FILE_FLAG_OVERLAPPED`;
- request write performed through overlapped I/O with stable request-buffer lifetime;
- bounded allocated response buffer;
- Windows overlapped response I/O;
- bounded `READ_TIMEOUT_MS` for pending response reads;
- explicit pywin32 result-code handling for `ERROR_IO_PENDING`;
- timeout cancellation before handle cleanup;
- server disconnect classification;
- existing `NamedPipeTransportError` propagation;
- existing JSON request/response framing preserved exactly.

The focused timeout/cancellation/disconnect regression coverage has passed.

## First real production capability — PASSED

The first real production Unreal path uses the `FIELD_SURFACE` entity mapping and proves:

```text
Atlas operation
    ↓
production adapter
    ↓
Windows Named Pipe
    ↓
real Unreal Editor
    ↓
Actor state mutation
    ↓
independent readback/evidence
    ↓
verification
```

The real plan-executor write/restore test passed.

The real recovery-coordinator test also passed and demonstrated that fresh live reassessment does not silently retry the failed mutation.

## Confirmed implementation boundary

Python currently declares/plans multiple Unreal operations, including inspection, material, and verification operations. The current Unreal C++ transport server has a narrower executable surface.

Treat unsupported operations as an explicit implementation boundary. Do not infer that a declared Python capability is already executable in Unreal.

The next production capability must be selected and implemented end-to-end rather than broadening the server spec speculatively.

## Verified engine milestone

The disposable Unreal Engine 5.6.1 harness compiled and passed `Atlas.UnrealAgent.OperationBoundary` after exposing and fixing the missing transform-root defect in the controlled temporary Actor. The assertion was preserved rather than weakened.

## Unreal fixture convention

The current real integration uses the exact Atlas entity mapping/tag:

```text
FIELD_SURFACE
```

If a live integration reports `Actor not found for entity_id: FIELD_SURFACE`, verify the Unreal Actor's exact Atlas mapping/tag first. Do not add entity discovery or change the Python entity contract to compensate for a fixture configuration error.

## Git/workspace separation

The Unreal Aider workspace remains isolated from the Blender development workspace. Work on Unreal should occur from the dedicated Unreal development checkout/branch. Do not point Aider at the Blender checkout.

## Next development phase

The next implementation milestone is **multi-operation production execution with failure containment**.

Develop and regression-test the smallest reusable path that proves:

1. read/evidence operations precede mutation;
2. authorization binds the exact ordered operations;
3. each operation produces correctly bound evidence;
4. successful operations advance deterministically;
5. a later failure prevents unsafe continuation;
6. completed targets are preserved accurately;
7. recovery performs fresh read-only reassessment;
8. reassessment never silently retries the previous mutation;
9. replacement execution requires explicit authorization;
10. completion requires independent verification.

Only after this Python-side boundary is green should the next expanded multi-operation scenario be run against the real Unreal Editor.

## Aider handoff

Before local implementation work:

- confirm the dedicated Unreal checkout state;
- use the intended Unreal development branch;
- keep Aider separate from the Atlas Python runtime where appropriate;
- never commit secrets;
- use `UNREAL_AGENT_HANDOFF_CURRENT.md` and this scope document as continuation context;
- use local edit/test/commit loops only when the relevant tests are authorized;
- keep GitHub Actions as the remote regression authority;
- do not run the action/workflow runner unless the user explicitly authorizes it.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or regression gates.