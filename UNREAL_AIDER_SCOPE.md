# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The immediate milestone is the real Unreal Engine 5.6 smoke test:

`Atlas.UnrealAgent.OperationBoundary`

Do **not** advance into production Unreal transport or broader capability implementation until this real-engine smoke test passes.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- The Unreal Agent reasons and plans; it does not authorize.
- Atlas authorization remains authoritative.
- The Unreal adapter executes authorized operations.
- Unreal provides independent execution evidence.
- Atlas verifies that evidence independently.
- The disposable Unreal harness is a regression fixture, not the production adapter.

## Aider operating rules

1. Preserve existing Unreal contracts and fail-closed behavior.
2. Do not weaken, remove, bypass, or rewrite tests merely to make them pass.
3. Do not modify Blender-specific implementation or tests unless a shared-interface change is demonstrably required and explicitly reviewed.
4. Do not introduce production Unreal transport before the smoke-test gate passes.
5. Prefer small, deterministic changes with regression coverage.
6. Keep Unreal-specific code and tests clearly scoped.
7. Treat `UNREAL_AGENT_HANDOFF_CURRENT.md` as the authoritative continuation context.

## Existing Unreal work

The starting point already includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, adapter v0.1 boundary, and the disposable Unreal Engine 5.6 validation harness.

## After the smoke test

If the smoke test passes, the next development phase is:

1. preserve the disposable harness;
2. design production Unreal transport;
3. connect actual Atlas authorization and evidence to that adapter;
4. prove the first production Unreal capability;
5. expand capabilities incrementally based on real requirements.

If the smoke test fails, diagnose and fix the actual engine-side problem and rerun the same gate. Do not advance the milestone while it is failing.
