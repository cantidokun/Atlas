# Atlas Unreal Engine Validation

This directory contains the first disposable Unreal Engine harness for Atlas.

## Current purpose

This is the **first real-Unreal validation point** for the Unreal Agent architecture. It is intentionally a disposable integration fixture, not the production Unreal adapter.

The current development focus is solely the Unreal Agent and its supporting architecture.

## Project

Open:

```text
unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject
```

The project is Editor-only and does not require an Atlas runtime service or network connection.

The current harness targets **Unreal Engine 5.6**.

## Exact next test

The current milestone is:

**Unreal Engine Boundary Smoke Test — PASS**

It is **not yet passed**. The Python-side Atlas contracts are already tested; the remaining gate is execution inside the real Unreal Editor.

### From the Atlas repository on Windows

```powershell
cd <ATLAS_REPO>
git fetch origin
git checkout feat/unreal-engine-harness
git pull
cd .\unreal\AtlasUnrealHarness
Start-Process ".\AtlasUnrealHarness.uproject"
```

Replace `<ATLAS_REPO>` with the local Atlas repository path.

Do not merge PR #10 before the Unreal test passes.

### In Unreal Editor

Open the **Automation Tests** window.

Find and run exactly:

```text
Atlas.UnrealAgent.OperationBoundary
```

No manual Actor, Blueprint, Niagara, material, or level setup is required. The test creates and destroys its own temporary Actor.

## What the test proves

The Automation Test performs this sequence:

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
temporary Actor created
        ↓
Atlas entity mapping attached to Actor
        ↓
authorized Actor write
        ↓
Actor state read back
        ↓
verification
        ↓
temporary Actor destroyed
```

The fixture uses Atlas entity ID:

```text
FIELD_SURFACE
```

and verifies the temporary Actor reaches:

```text
X = 100
Y = 200
Z = 300
```

## Command-line option

For a Windows command-line Editor run, use PowerShell backticks for line continuation:

```powershell
& "<UE_INSTALL>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "<ATLAS_REPO>\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" `
  -unattended -nop4 -nosplash -nullrhi -NoSound `
  -ExecCmds="Automation RunTests Atlas.UnrealAgent.OperationBoundary; Quit"
```

The exact Unreal executable path depends on the local installation. Do not hard-code a machine-specific path into Atlas.

## Expected result

A passing run must establish all of the following:

- canonical structured operation accepted;
- unsupported operation kind rejected fail-closed;
- Atlas entity ID preserved across the boundary;
- Unreal Editor world available;
- temporary Actor created;
- Atlas entity mapping present on the Actor;
- authorized write reaches Unreal Actor state;
- resulting state directly observable by the test;
- temporary Actor cleaned up.

If the test fails, **do not weaken the test or work around the failure**. Capture the Unreal Automation Test result/error and return it to Atlas development for diagnosis and correction.

## Architectural boundary

The harness is deliberately narrower than the production Unreal adapter:

```text
Atlas intent
    ↓
Unreal Agent
    ↓
strict operation contract
    ↓
Atlas authorization
    ↓
future production Unreal adapter
    ↓
Unreal Engine
    ↓
independent evidence
    ↓
Atlas verification
```

The harness proves only the engine-side boundary. It does not yet establish production transport, full Digital Twin synchronization, or production Materials/Niagara/Blueprint/Sequencer/rendering capabilities.

## After this test passes

Do not immediately turn the harness into the production adapter.

First:

1. record the real-Unreal result;
2. repair any harness limitations revealed by the test;
3. preserve the harness as a disposable regression fixture;
4. design the production Unreal adapter transport against the proven boundary;
5. connect Atlas authorization and evidence to that adapter;
6. begin the first production Unreal capability.

The current detailed continuation state is documented in:

```text
UNREAL_AGENT_HANDOFF_CURRENT.md
```
