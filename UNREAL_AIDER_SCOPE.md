# Atlas Unreal Agent — Aider Scope

## Purpose

This workspace is for continued development of the Atlas Unreal Agent only. It starts from the existing Unreal validation work and must not replace or restructure the existing Atlas architecture.

## Current gate

The real Unreal Engine 5.6 smoke test has **PASSED**:

`Atlas.UnrealAgent.OperationBoundary`

The disposable harness is now a confirmed real-engine regression fixture. The next phase is production Unreal transport and the first production capability; the harness remains in place as a regression gate.

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
4. Preserve the disposable Unreal harness and keep `Atlas.UnrealAgent.OperationBoundary` passing after relevant changes.
5. Prefer small, deterministic changes with regression coverage.
6. Keep Unreal-specific code and tests clearly scoped.
7. Treat `UNREAL_AGENT_HANDOFF_CURRENT.md` as the authoritative continuation context.
8. For complex changes, plan before editing and verify the affected tests before committing.
9. Do not introduce a second authorization authority inside Unreal.

## Existing Unreal work

The starting point already includes the Unreal Agent planning boundary, capability registry, strict operation contract, deterministic task planning, engine-neutral evidence contract, adapter v0.1 boundary, and the disposable Unreal Engine 5.6 validation harness.

## Verified engine milestone

On August 17, 2026, the harness was compiled and run in Unreal Engine 5.6.1. `Atlas.UnrealAgent.OperationBoundary` initially exposed a harness defect: the temporary `AActor` had no registered transform root. The harness was corrected to create and register a `USceneComponent` root, rebuilt successfully, and the same automation test then passed.

The fix is commit `95966089ec3c9e3471ad72f9abf75b4c4195bf98` on `feat/unreal-engine-harness`.

## Git/workspace separation

The Unreal Aider workspace is intended to remain isolated from the Blender development workspace. Work on Unreal should occur from the dedicated `agent/unreal-aider-ready` checkout/branch. Do not point Aider at the Blender checkout.

## After the smoke test

The next development phase is:

1. preserve the disposable harness;
2. design the production Unreal transport boundary;
3. connect actual Atlas authorization and evidence to that adapter;
4. prove the first production Unreal capability;
5. expand capabilities incrementally based on real requirements;
6. keep the smoke test as a regression gate throughout.

## Aider handoff

Before the first Aider session:

- confirm the dedicated Unreal checkout is clean;
- fast-forward it to the intended Unreal development branch state;
- install Aider separately from the Atlas Python environment;
- configure the chosen LLM API key without committing secrets;
- start Aider from the Unreal workspace with the Unreal scope document available;
- use Aider for local edit/test/commit loops while GitHub Actions remains the remote regression authority.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or CI gates.
