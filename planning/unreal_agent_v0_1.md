# Unreal Agent v0.1 Milestone

## Goal

Establish a safe, engine-neutral Unreal Agent planning architecture that can translate Atlas-owned production intents into deterministic Unreal-domain operation proposals without executing or authorizing them.

## Complete in v0.1

- explicit Atlas entity targeting;
- declarative Unreal capability registry;
- capability-level operation permissions;
- deterministic task decomposition;
- inspect-before-write planning for production variants;
- explicit verification operations;
- fail-closed handling for missing targets and unsupported capabilities;
- separation from the generic Atlas authorization/execution/verification loop;
- no Unreal Engine API dependency in Atlas Core.

## Not included

- direct Unreal Engine control;
- remote process control;
- Blueprint compilation through a live editor;
- Niagara authoring against a live project;
- Sequencer mutation against a live project;
- rendering through Unreal;
- autonomous promotion of Unreal state into the canonical Digital Twin.

## v0.1 operation lifecycle

```text
Atlas production intent
        ↓
explicit Atlas entities
        ↓
Unreal task planner
        ↓
capability validation
        ↓
deterministic operation proposal
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

## Milestone exit criteria

The architecture is ready to move toward a live Unreal adapter when the repository can:

1. construct deterministic Unreal plans from explicit Atlas entities;
2. reject operations outside the declared capability registry;
3. guarantee that planning never executes a tool operation;
4. require verification after a production write;
5. keep canonical Twin state separate from production variants;
6. pass the full existing regression suite on the supported Python versions.

The next milestone after v0.1 is the **Unreal Adapter v0.1 contract implementation**, still engine-neutral at first. A real Unreal transport should only be introduced after that adapter contract is stable and the branch is reconciled with `main`.
