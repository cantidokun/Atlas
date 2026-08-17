# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 17, 2026
**Current focus:** Unreal Agent and its supporting architecture only
**Current branch:** `feat/unreal-engine-harness`
**Base:** `main`
**Current work:** PR #10 — `feat: first Unreal Engine validation harness`

## 1. Scope decision

For the current development phase, Atlas work is intentionally limited to the **Unreal Agent and its relative architecture**.

Do not broaden the active implementation into Blender-agent features, photogrammetry implementation, sports-analysis features, or production VFX modules unless a later Unreal milestone requires an explicit architectural boundary for them.

Atlas still owns the canonical Digital Twin. Unreal is a production tool/representation around that canonical model, not the source of truth.

## 2. Architecture established before Unreal Engine testing

The Unreal side has been designed around this control boundary:

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

The Unreal Agent proposes structured operations; it does not directly authorize or execute them.

The existing Atlas execution architecture remains authoritative for ordering, authorization, execution state, verification, recovery, and continuation integrity.

## 3. Unreal Agent primitives already implemented

### `planning/unreal_agent.py`

Defines the engine-neutral Unreal Agent boundary, including:

- `UnrealCapability`
- `UnrealOperationKind`
- `UnrealOperation`
- `UnrealTaskIntent`
- `UnrealAgent`

The Agent requires explicit Atlas entity targets and initially proposes inspection rather than silently inventing writes.

### `planning/unreal_capability_registry.py`

Defines the declarative Unreal capability taxonomy:

- world inspection
- Actor inspection/modification
- asset inspection/modification
- materials
- Niagara
- Blueprint
- Sequencer
- rendering

Each capability declares permitted operation kinds and required evidence. Capability validation is not authorization; Atlas authorization remains the authority.

The registry also validates operation argument schemas and requires the payload entity IDs to match the operation's explicit `entity_ids`.

### `planning/unreal_operation_contract.py`

This is the AI-facing structured-operation boundary.

`parse_unreal_operation()` accepts only the exact top-level operation schema:

```text
capability
kind
name
arguments
entity_ids
```

It rejects malformed, unknown, ambiguous, or unsupported values without fuzzy coercion.

### `planning/unreal_task_planner.py`

Provides deterministic Unreal-domain task decomposition. Current supported planning patterns include:

- inspection
- material-variant flow

The material-variant sequence is explicitly:

```text
inspect Actor
→ inspect material state
→ apply material variant
→ verify material variant
```

The planner proposes operations only. It does not execute them.

### Unreal adapter boundary

An engine-neutral Unreal adapter v0.1 boundary has already been designed so Unreal-specific APIs remain behind the adapter rather than leaking into Atlas Core.

The adapter is responsible for translating authorized Atlas operations into Unreal operations and returning authoritative tool evidence.

## 4. First real-Unreal milestone

PR #10 introduces a **disposable Unreal Engine validation harness**.

PR:

`#10 — feat: first Unreal Engine validation harness`

Branch:

`feat/unreal-engine-harness`

The PR is intentionally **Draft** and must **not be merged yet**.

Files are under:

```text
unreal/AtlasUnrealHarness/
```

The harness is an Editor-only Unreal project and is intentionally not a production Unreal adapter.

## 5. Current Unreal Engine smoke test

Automation test name:

```text
Atlas.UnrealAgent.OperationBoundary
```

The test is designed to prove the smallest real-engine loop:

```text
structured Atlas operation
        ↓
Unreal-side validation
        ↓
unsupported operation rejected fail-closed
        ↓
Atlas Entity ID preserved
        ↓
Unreal Editor world available
        ↓
test Actor created
        ↓
Actor mapped to Atlas entity
        ↓
authorized Actor write
        ↓
Unreal Actor state read back
        ↓
verification
```

The fixture uses the Atlas entity ID:

`FIELD_SURFACE`

and verifies an Actor location of:

`X=100, Y=200, Z=300`

The temporary Actor is destroyed at the end of the test.

## 6. What has NOT been proven yet

The following are intentionally still unproven:

- actual Unreal Editor compilation/execution on the user's machine;
- live Atlas → Unreal transport;
- production Unreal adapter implementation;
- Materials/Niagara/Blueprint/Sequencer/rendering against a real production project;
- canonical Digital Twin synchronization with a real Unreal project;
- Unreal-side independent evidence returned through the production adapter.

Do not claim the Unreal Engine Boundary Smoke Test is PASS until the actual Automation Test has passed in Unreal Engine.

## 7. Exact next action when resuming

Do **not** merge PR #10.

On the development PC:

```powershell
cd <ATLAS_REPO>
git fetch origin
git checkout feat/unreal-engine-harness
git pull
cd .\unreal\AtlasUnrealHarness
Start-Process ".\AtlasUnrealHarness.uproject"
```

Open the project in **Unreal Engine 5.6**.

In Unreal Editor, open the Automation Tests window and run:

```text
Atlas.UnrealAgent.OperationBoundary
```

The expected result is a fully passing test containing the assertions listed above.

If Unreal Engine is not installed at the required version, stop before changing the repository or installing dependencies and report the available Unreal version.

## 8. Command-line test shape

For a Windows command-line Editor run, the README contains this pattern:

```powershell
& "<UE_INSTALL>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "<ATLAS_REPO>\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" `
  -unattended -nop4 -nosplash -nullrhi -NoSound `
  -ExecCmds="Automation RunTests Atlas.UnrealAgent.OperationBoundary; Quit"
```

Use the locally installed Unreal executable path. Atlas must not hard-code a machine-specific Unreal installation path.

## 9. Current milestone boundary

### Milestone: Unreal Engine Boundary Smoke Test

**Status: READY FOR HUMAN ENGINE TEST — NOT YET PASSED**

The Python-side Unreal operation contracts have already passed the standard Atlas CI regression matrix on the current `main` before the harness branch was created.

The next milestone is complete only when the real Unreal Editor test passes.

## 10. What happens after the Unreal smoke test

If the smoke test passes:

1. record the real-engine result;
2. diagnose/repair any remaining harness limitations;
3. keep the harness as a disposable integration fixture;
4. design the real Unreal adapter transport against the proven boundary;
5. connect Atlas authorization/evidence to that adapter;
6. begin the first production Unreal capability;
7. continue incrementally through Materials, Niagara, Blueprint, Sequencer, rendering, and Digital Twin synchronization as justified by real capability gaps.

If the smoke test fails:

- do not work around the failure by weakening the test;
- diagnose the actual Unreal-side failure;
- fix the harness/contract;
- rerun the same test;
- do not advance the milestone until it passes.

## 11. Repository / Git rule for tomorrow

PR #10 is the current Unreal integration branch. Do not merge it merely because the Python CI is green. The first real Unreal Engine result is the gate.

After the Unreal boundary is proven, create the next controlled development stage from the resulting baseline rather than piling unrelated production functionality into the harness PR.

## 12. Architectural invariant to preserve

```text
Atlas owns the Twin.

Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
```

The Unreal Agent must never become a second autonomous authority separate from Atlas.
