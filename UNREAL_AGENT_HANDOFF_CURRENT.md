# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 17, 2026
**Current focus:** Unreal Agent and its supporting architecture only
**Current branch:** `feat/unreal-engine-harness`
**Base:** `main`
**Current work:** PR #10 — `feat: first Unreal Engine validation harness`

## Current position

The Unreal Agent architecture is now at the **first real-Unreal validation gate**. PR #10 remains Draft and must not be merged until the Unreal Editor automation test passes.

Atlas owns the canonical Digital Twin. Unreal is a production representation/execution tool around that canonical state, not the source of truth.

## Architecture

```text
Atlas production intent
        ↓
Unreal Agent
        ↓
Capability registry
        ↓
Strict operation contract / schema validation
        ↓
Atlas authorization
        ↓
Unreal adapter
        ↓
Unreal Engine
        ↓
Independent Unreal evidence
        ↓
Atlas verification
```

The Unreal Agent proposes/decomposes operations. It does not authorize or directly execute them.

## Implemented Unreal-side architecture

- `planning/unreal_agent.py`
  - `UnrealCapability`
  - `UnrealOperationKind`
  - `UnrealOperation`
  - `UnrealTaskIntent`
  - `UnrealAgent`
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
  - material-variant planning flow.
- engine-neutral Unreal adapter v0.1 boundary/design.

## PR #10 — disposable Unreal Engine harness

Branch:

`feat/unreal-engine-harness`

Project:

`unreal/AtlasUnrealHarness/`

Target:

**Unreal Engine 5.6**

Automation test:

`Atlas.UnrealAgent.OperationBoundary`

The harness is Editor-only and disposable. It is not the production adapter.

## Current smoke-test contract

The C++ harness now mirrors the strict structure of the Atlas-side operation contract for the limited smoke-test capability.

A valid operation requires exactly these top-level keys:

```text
capability
kind
name
arguments
entity_ids
```

For the current smoke-test `modify_actor/write` operation, `arguments` must contain exactly:

```text
entity_ids
```

The harness now fails closed on:

- unsupported operation kinds;
- unknown top-level keys;
- unknown argument keys;
- invalid/missing entity arrays;
- non-string or empty entity IDs;
- mismatched `arguments.entity_ids` and top-level `entity_ids`.

It then creates a temporary Unreal Actor, attaches:

`atlas_entity:FIELD_SURFACE`

and verifies the controlled smoke-test write reaches:

`X=100, Y=200, Z=300`

The Actor is destroyed at the end of the test.

## Important scope clarification

The current Actor write is a **controlled engine smoke-test write**. It does not yet prove that a real Atlas authorization receipt crosses a production transport into Unreal.

That is intentionally the next architecture after this gate.

## Exact resume action

Do not merge PR #10.

On the development PC:

```powershell
cd <ATLAS_REPO>
git fetch origin
git checkout feat/unreal-engine-harness
git pull
cd .\unreal\AtlasUnrealHarness
Start-Process ".\AtlasUnrealHarness.uproject"
```

Open in Unreal Engine 5.6, then run:

```text
Atlas.UnrealAgent.OperationBoundary
```

No manual Actor/Blueprint/Niagara/material/level setup is required.

If it fails, preserve the test and diagnose the actual Unreal-side failure. Do not weaken or bypass the assertion.

If it passes, record the result and proceed to production Unreal adapter transport design. Keep the harness as a disposable regression fixture.

## Command-line alternative

```powershell
& "<UE_INSTALL>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "<ATLAS_REPO>\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" `
  -unattended -nop4 -nosplash -nullrhi -NoSound `
  -ExecCmds="Automation RunTests Atlas.UnrealAgent.OperationBoundary; Quit"
```

Use the locally installed Unreal executable path; never hard-code a machine-specific installation path.

## Milestone status

**Unreal Engine Boundary Smoke Test — READY FOR HUMAN ENGINE TEST / NOT YET PASSED.**

The Python-side operation contracts have already been tested through Atlas CI. The Unreal C++ harness has now been tightened to match the same fail-closed schema expectations more closely.

The milestone is not complete until the actual Unreal Editor test passes.

## After the smoke test

If the test passes:

1. record the real-engine result;
2. preserve the disposable harness;
3. design production Unreal transport;
4. connect actual Atlas authorization and evidence;
5. prove the first production Unreal capability;
6. expand capabilities incrementally.

If the test fails:

1. capture the actual Unreal error;
2. diagnose the engine-side issue;
3. fix the harness/contract;
4. rerun the same test;
5. do not advance the milestone until it passes.

## Architectural invariant

```text
Atlas owns the Twin.
Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
```

The Unreal Agent must never become a second autonomous authority separate from Atlas.
