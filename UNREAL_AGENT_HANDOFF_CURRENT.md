# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 17, 2026
**Current focus:** Unreal Agent and its supporting architecture only
**Current branch:** `feat/unreal-engine-harness`
**Aider workspace:** `agent/unreal-aider-ready`
**Base:** `main`
**Current work:** PR #10 — `feat: first Unreal Engine validation harness`

## Current position

The Unreal Agent has now passed its first real-Unreal validation gate. PR #10 remains Draft and unmerged; the disposable harness is preserved as a regression fixture while development moves to the production Unreal transport boundary.

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
- `planning/unreal_evidence_contract.py`
  - engine-neutral post-execution evidence shape;
  - operation/entity binding validation.
- engine-neutral Unreal adapter v0.1 boundary/design.

## Evidence boundary milestone

The engine-neutral evidence contract is defined and regression-tested.

`UnrealEvidence` requires:

```text
operation_name
entity_ids
observed_state
source
verified
```

Evidence is explicitly **not** an authorization receipt. Evidence cannot authorize itself. Atlas verification remains independent.

Evidence must identify the exact operation and exact Atlas entity targets that produced it.

This gives the production adapter a stable evidence target without coupling Atlas Core to Unreal APIs.

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

## Smoke-test result — PASSED

On August 17, 2026, the harness was compiled and executed in Unreal Engine 5.6.1.

The first execution correctly exposed a harness defect: the temporary `AActor` had no registered transform root, so the controlled transform write could not reach valid Actor state. The assertion was not weakened. The harness was fixed by creating and registering a `USceneComponent` root, then the project was rebuilt successfully.

The exact same automation test was rerun in the real Unreal Editor and **PASSED**.

Fix commit:

`95966089ec3c9e3471ad72f9abf75b4c4195bf98`

The fix is now on `feat/unreal-engine-harness` and is present in the dedicated `agent/unreal-aider-ready` workspace history.

## Current smoke-test contract

The C++ harness mirrors the strict structure of the Atlas-side operation contract for the limited smoke-test capability.

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

The harness fails closed on:

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

That is the next architecture.

## Git/workspace separation

The Unreal development workspace is isolated from the Blender development workspace. The dedicated local checkout is:

`C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider`

Its intended branch is:

`agent/unreal-aider-ready`

Do not point Aider at the Blender checkout.

The dedicated branch contains the passed Unreal harness plus the Unreal Aider scope/handoff documentation. The PR branch `feat/unreal-engine-harness` contains the same Unreal harness fix and remains Draft/unmerged.

## Next development phase

1. preserve the disposable harness as a regression gate;
2. design the production Unreal transport boundary;
3. connect actual Atlas authorization and evidence to that adapter;
4. prove the first production Unreal capability;
5. expand capabilities incrementally based on real requirements;
6. keep the smoke test passing throughout.

Do not treat the disposable harness as production transport.

## Aider handoff

Before the first Aider session:

- confirm the dedicated Unreal checkout is clean;
- fast-forward/pull it to the intended `agent/unreal-aider-ready` branch state;
- install Aider separately from the Atlas Python environment;
- configure the chosen LLM API key without committing secrets;
- start Aider from the Unreal workspace with `UNREAL_AIDER_SCOPE.md` available;
- use Aider for local edit/test/commit loops while GitHub Actions remains the remote regression authority.

Aider is an implementation tool, not a replacement for the Atlas architecture, Git history, or CI gates.

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
