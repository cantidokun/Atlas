# Atlas Unreal Agent Architecture

## Purpose

The Unreal Agent is a production-tool agent operating on an Atlas-owned Digital Twin.
Unreal is not the source of truth for the Twin. The agent translates authorized Atlas
intent into Unreal operations and returns authoritative Unreal evidence to Atlas.

## Boundary

```text
Atlas canonical Digital Twin
        |
        | current revision + representation
        v
Unreal Adapter / Agent Boundary
        |
        +-- inspect
        +-- validate action
        +-- execute one authorized action
        +-- synchronize evidence
        |
        v
Unreal Engine
        |
        v
Atlas evidence / verification
```

The existing Atlas action-plan and authorization system remains above this boundary.
The Unreal Agent must never issue its own authorization, invent canonical state, or
promote Unreal state into the canonical Twin.

## Agent responsibilities

The Unreal Agent may:

- interpret Atlas-authorized production tasks;
- inspect Unreal representations and return authoritative evidence;
- map Atlas entity IDs to Unreal Actors/assets/components;
- propose structured Unreal actions for Atlas validation/authorization;
- execute one action only after Atlas authorization;
- report action results and evidence identifiers;
- synchronize Unreal state back into Atlas evidence;
- create or modify production variants and shot state without silently modifying
  canonical Twin state.

The Unreal Agent does not own:

- canonical Digital Twin identity;
- canonical revisions;
- authorization policy;
- final verification;
- recovery authority;
- the definition of what a real-world entity means.

## Capability domains

The initial Unreal capability taxonomy should remain small and composable:

1. World inspection
2. Entity/Actor inspection
3. Asset inspection
4. Actor creation and modification
5. Material inspection and controlled assignment
6. Niagara/VFX inspection and controlled modification
7. Blueprint inspection and controlled modification
8. Sequencer/shot inspection and controlled modification
9. Render/test execution

Capabilities should be added only when a demonstrated production task requires them.
Each capability must expose structured arguments and independently verifiable results.

## Entity mapping

Atlas entity identity is authoritative. Unreal Actor names are implementation details.
The adapter should maintain an explicit mapping:

```text
Atlas Entity ID -> Unreal Actor/Asset representation
```

A mapping must not be inferred solely from mutable display names when a stable Atlas
mapping can be maintained. Missing or ambiguous mappings fail closed and require
fresh evidence or explicit recovery.

## State separation

Unreal must distinguish:

- canonical Twin revision;
- Unreal representation of that revision;
- production variant;
- shot-specific state;
- temporary runtime/render state.

A cinematic operation such as a liquid-field transformation should normally create
or modify a production variant/shot state, not overwrite canonical field appearance.

## Execution contract

Every write follows:

```text
Qwen/agent proposal
    -> Atlas schema validation
    -> Atlas target-state evaluation
    -> Atlas authorization
    -> Unreal adapter executes ONE authorized action
    -> Unreal evidence
    -> independent Atlas verification
    -> canonical revision update only when explicitly authorized
```

A successful Unreal API call is not proof of final production state.

## Verification examples

A task such as "make the field behave like liquid" should not verify only that a
Niagara system was created. Verification can require a target-state bundle such as:

- required field entity is mapped;
- production variant exists;
- material state is assigned to the intended surface;
- Niagara system is attached to the intended entity/region;
- required parameters are within target ranges;
- Sequencer contains the required transition when the task is shot-specific;
- no unrelated canonical Twin state changed.

## Failure and recovery

Unreal action failure or ambiguous evidence must enter the existing Atlas recovery
boundary. Automatic retry is prohibited. Recovery requires fresh authoritative
evidence and a new authorized plan where a replacement action is appropriate.

## Blender relationship

Blender and Unreal implement the same engine-neutral adapter contract, but they do
not need identical capability sets. Blender is the primary reconstruction cleanup
and correction environment; Unreal is the primary real-time production environment.
Both consume Atlas-owned state and return evidence through the same control boundary.

## Implementation rule

Do not add a hard dependency on the Unreal Engine SDK to the Atlas core. Unreal-specific
transport, process control, Editor scripting, Python API, Remote Control, or future
integration mechanisms belong behind the Unreal adapter boundary.
