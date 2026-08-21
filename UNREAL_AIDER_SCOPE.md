# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The real Unreal Engine 5.6 smoke test has **PASSED**:

`Atlas.UnrealAgent.OperationBoundary`

The disposable harness is a confirmed real-engine regression fixture. Development has now progressed to the production Unreal transport boundary and its response-read timeout hardening.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- The Unreal Agent reasons and plans; it does not authorize.
- Atlas authorization remains authoritative.
- The Unreal adapter executes authorized operations.
- Unreal provides independent execution evidence.
- Atlas verifies that evidence independently.
- The disposable Unreal harness is a regression fixture, not the production adapter.
- The Unreal adapter remains stateless.

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

## Existing Unreal work

The starting point includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, production adapter boundary, Named Pipe transport, and the disposable Unreal Engine 5.6 validation harness.

## Production transport milestone — August 21, 2026

The Python Named Pipe transport has been hardened against an indefinite response-read block without changing the wire protocol.

Current transport behavior:

- 5-second connection availability timeout;
- client pipe handle opened with `FILE_FLAG_OVERLAPPED`;
- request write performed through overlapped I/O with stable request-buffer lifetime;
- 1 MB allocated response buffer;
- Windows overlapped response I/O;
- 30-second `READ_TIMEOUT_MS` for pending response reads;
- explicit pywin32 result-code handling for `ERROR_IO_PENDING`;
- timeout cancellation before handle cleanup;
- existing `NamedPipeTransportError` propagation;
- existing JSON request/response framing preserved exactly.

Relevant commits:

- `127c99e` — initial overlapped response-read timeout implementation;
- `6c6be09` — corrected allocated-buffer handling;
- `2621610` — attempted to correct `ERROR_IO_PENDING` handling but used exception-based handling that does not match pywin32's `ReadFile` contract;
- `8ff3640` — corrected the pipe handle mode, request write path, and `ReadFile` result-code handling.

The transport contract and Unreal C++ server wire format remain unchanged.

## Confirmed implementation boundary

Python currently declares/plans multiple Unreal operations, including inspection, material, and verification operations. The current Unreal C++ transport server only implements the `inspect_target_actors` operation and rejects unsupported operation/capability/kind combinations.

Treat this as an intentional implementation boundary until the next production capability is explicitly designed end-to-end. Do not infer that every planner capability is already executable.

## Verified engine milestone

On August 17, 2026, the harness was compiled and run in Unreal Engine 5.6.1. `Atlas.UnrealAgent.OperationBoundary` initially exposed a harness defect: the temporary `AActor` had no registered transform root. The harness was corrected to create and register a `USceneComponent` root, rebuilt successfully, and the same automation test then passed.

The fix is commit `95966089ec3c9e3471ad72f9abf75b4c4195bf98` on `feat/unreal-engine-harness`.

## Git/workspace separation

The Unreal Aider workspace remains isolated from the Blender development workspace. Work on Unreal should occur from the dedicated `agent/unreal-aider-ready` checkout/branch. Do not point Aider at the Blender checkout.

## After the smoke test

The production phase is now:

1. validate the corrected transport at the real Windows/Unreal process boundary;
2. cover normal response completion, pending-read timeout, cancellation, and server disconnect;
3. preserve the disposable harness;
4. identify the smallest production capability actually supported by the current Unreal server;
5. connect actual Atlas authorization and independent evidence to that capability;
6. prove the first production Unreal capability end-to-end;
7. expand capabilities incrementally based on real requirements;
8. keep the smoke test as a regression gate throughout.

## Aider handoff

Before local implementation work:

- confirm the dedicated Unreal checkout state;
- use the intended Unreal development branch;
- keep Aider separate from the Atlas Python runtime where appropriate;
- never commit secrets;
- use `UNREAL_AGENT_HANDOFF_CURRENT.md` and this scope document as continuation context;
- use local edit/test/commit loops only when the relevant tests are authorized;
- keep GitHub Actions as the remote regression authority.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or CI gates.