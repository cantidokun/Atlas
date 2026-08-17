# Atlas Unreal Engine Validation

This directory contains the first disposable Unreal Engine harness for Atlas.

## Purpose

The harness proves the smallest real-engine loop before we add a production Unreal integration:

1. receive a structured Atlas Unreal operation;
2. validate the operation at the Unreal boundary;
3. reject an unsupported operation kind;
4. map an Atlas entity ID to an Unreal Actor;
5. perform an authorized Actor write;
6. verify the resulting Unreal state.

This is intentionally **not** the production Unreal adapter. It is a disposable integration test that establishes that the engine-side boundary works in a real Unreal Editor process.

## Project

`AtlasUnrealHarness/AtlasUnrealHarness.uproject` is an Editor-only Unreal project with a single module. The project does not require any Atlas runtime service or network connection.

## First engine test

Build the project with the Unreal Editor version installed on the development machine, then run the automation test:

```text
Atlas.UnrealAgent.OperationBoundary
```

For a command-line editor run on Windows, the equivalent shape is:

```powershell
& "<UE_INSTALL>\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" \
  "<ATLAS_REPO>\unreal\AtlasUnrealHarness\AtlasUnrealHarness.uproject" \
  -unattended -nop4 -nosplash -nullrhi -NoSound \
  -ExecCmds="Automation RunTests Atlas.UnrealAgent.OperationBoundary; Quit"
```

The exact Unreal executable path depends on the local installation and should not be hard-coded into Atlas.

## Expected assertions

The test must establish all of the following:

- a canonical structured operation is accepted;
- an unsupported operation kind is rejected fail-closed;
- the Atlas entity ID is preserved;
- an Unreal editor world is available;
- an Unreal Actor can be created;
- the Actor can carry the Atlas entity mapping;
- the authorized write reaches Unreal Actor state;
- the resulting state is directly observable by the test.

## Milestone boundary

This harness is the first point at which Atlas's Unreal architecture is tested against the **actual Unreal Engine**, rather than only through Python-side contracts.

A passing run is therefore the exit criterion for the next milestone: **Unreal Engine Boundary Smoke Test — PASS**.

Only after that milestone should we connect the harness to a real Unreal adapter transport and begin production-domain capabilities such as Materials, Niagara, Blueprint, Sequencer, and rendering.
