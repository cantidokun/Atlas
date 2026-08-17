# Atlas Unreal Agent — Current Handoff

**Date:** August 17, 2026
**Focus:** Unreal Agent and its supporting architecture only
**Current baseline:** `main`
**Current Unreal work:** PR #10 — `feat: first Unreal Engine validation harness`
**Unreal branch:** `feat/unreal-engine-harness`
**PR #10 status:** Draft — **do not merge yet**

## Current architectural position

Atlas owns the canonical Digital Twin. Unreal is a production representation/execution environment around that canonical state.

The Unreal control boundary is:

```text
Atlas intent
    ↓
Unreal Agent
    ↓
capability registry
    ↓
strict operation contract/schema
    ↓
Atlas authorization
    ↓
Unreal adapter
    ↓
Unreal Engine
    ↓
independent evidence
    ↓
Atlas verification
```

The Unreal Agent proposes and decomposes operations. It does not authorize or directly execute them. The existing Atlas authorization, deterministic execution, verification, recovery, and runtime-integrity architecture remains authoritative.

## Unreal architecture implemented today

The Unreal side now includes:

- `planning/unreal_agent.py`
- `planning/unreal_capability_registry.py`
- `planning/unreal_operation_contract.py`
- `planning/unreal_task_planner.py`
- Unreal adapter v0.1 boundary/design
- dedicated regression tests for Unreal capabilities, operation schemas, structured-operation parsing, and task planning

The capability model includes Actors, assets, materials, Niagara, Blueprint, Sequencer, rendering, and world inspection.

The AI-facing operation contract requires exactly:

```text
capability
kind
name
arguments
entity_ids
```

Malformed, ambiguous, unsupported, or mismatched payloads fail closed.

## Current real-Unreal milestone

PR #10 adds a disposable Editor-only Unreal project:

```text
unreal/AtlasUnrealHarness/
```

Target engine: **Unreal Engine 5.6**.

Automation test:

```text
Atlas.UnrealAgent.OperationBoundary
```

The test proves:

1. valid structured operation accepted;
2. unsupported operation kind rejected fail-closed;
3. Atlas entity ID preserved;
4. Unreal Editor world available;
5. temporary Actor created;
6. Atlas entity mapping attached to Actor;
7. authorized Actor write reaches Unreal state;
8. state read back and verified;
9. temporary Actor destroyed.

Fixture entity:

`FIELD_SURFACE`

Expected temporary Actor location:

`X=100, Y=200, Z=300`

## Exact point to resume

The next required action is the **first actual Unreal Engine test**. No further architecture should be piled onto PR #10 until this gate is resolved.

On the development PC:

```powershell
cd <ATLAS_REPO>
git fetch origin
git checkout feat/unreal-engine-harness
git pull
cd .\unreal\AtlasUnrealHarness
Start-Process ".\AtlasUnrealHarness.uproject"
```

Open the project in Unreal Engine 5.6.

In the Unreal Editor Automation Tests window, run:

```text
Atlas.UnrealAgent.OperationBoundary
```

No manual Actor/Blueprint/Niagara/material/level setup is required.

If the test fails, preserve the test and diagnose the actual Unreal-side failure. Do not weaken or bypass the assertion.

If it passes, record the result and proceed to production Unreal adapter transport design. Keep the harness as a disposable regression fixture.

## Command-line alternative

```powershell
& "<UE_INSTALL>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "<ATLAS_REPO>\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" `
  -unattended -nop4 -nosplash -nullrhi -NoSound `
  -ExecCmds="Automation RunTests Atlas.UnrealAgent.OperationBoundary; Quit"
```

Use the locally installed Unreal executable path; do not hard-code it into Atlas.

## Milestone status

**Unreal Engine Boundary Smoke Test — READY FOR HUMAN TEST / NOT YET PASSED.**

Python-side Unreal contracts have already been through the Atlas CI regression matrix. The remaining proof must occur inside the real Unreal Editor.

## After the smoke test

Do not turn the disposable harness directly into the production adapter. First prove the engine boundary, then:

1. preserve the harness as a regression fixture;
2. design production Unreal transport;
3. connect Atlas authorization/evidence to the adapter;
4. prove the first production Unreal capability;
5. expand into Materials, Niagara, Blueprint, Sequencer, rendering, and Digital Twin synchronization only as justified by real capability gaps.

## Architectural invariant

```text
Atlas owns the Twin.
Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
```

This handoff is the authoritative continuation point for the Unreal Agent work until superseded by a newer handoff.
