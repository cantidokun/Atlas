# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026
**Current focus:** Multi-operation production execution and failure containment
**Current branch:** `feat/unreal-production-actor-write`

## Current position

The Unreal Agent has crossed the first real Unreal production-process boundary. The actor-location write/verify path and read-only recovery reassessment have both been exercised against the running Unreal Editor. The Python regression suite and focused live Unreal tests are green at the latest user-reported runs.

Atlas owns the canonical Digital Twin. Unreal is a production representation/execution tool around that canonical state, not the source of truth.

## Proven execution architecture

```text
Atlas production intent
        ↓
Unreal Agent / task planner
        ↓
Capability registry + strict operation contract
        ↓
Atlas authorization
        ↓
UnrealPlanExecutor
        ↓
UnrealAdapterProduction
        ↓
Windows Named Pipe transport
        ↓
Unreal Engine
        ↓
Independent Unreal evidence
        ↓
Atlas verification / recovery policy
```

The Unreal Agent proposes/decomposes operations. It does not authorize or directly execute them.

## Implemented production architecture

- `planning/unreal_task_planner.py`
  - deterministic inspection and actor-location planning;
  - compound actor-location sequence planning;
  - every sequence mutation is immediately followed by verification.
- `planning/unreal_plan_executor.py`
  - strict ordered READ/WRITE/VERIFY dispatch;
  - evidence ledger;
  - immediate failure boundary;
  - preservation of completed evidence and mutation intent.
- `planning/unreal_recovery_policy.py`
  - fail-closed mutation/verification/observation failure classification.
- `planning/unreal_reassessment_planner.py`
  - targeted read-only reassessment plans.
- `planning/unreal_recovery_orchestrator.py`
  - converts eligible failures into targeted reassessment plans without automatic mutation retry.
- `planning/unreal_recovery_coordinator.py`
  - executes fresh read-only reassessment and returns the resulting decision.
- `planning/unreal_adapter_production.py`
  - stateless production adapter;
  - authorization propagation;
  - transport/evidence correlation.
- `planning/unreal_transport_named_pipe.py`
  - bounded Windows Named Pipe transport;
  - typed timeout/disconnect failure translation;
  - pending-read cancellation and cleanup.

## Real Unreal proof — PASSED

The local Windows/Unreal Editor boundary has been exercised against the actual running Unreal process.

Passed live tests include:

```text
test_real_unreal_plan_executor_location_write_and_restore
    → PASS

test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
    → PASS
```

The combined live run passed both tests.

The proof establishes that Atlas can inspect `FIELD_SURFACE`, perform an authorized actor-location write through the production adapter and Named Pipe transport, independently verify the resulting Unreal state, restore the state, and perform a recovery reassessment without silently retrying the mutation.

## Current development milestone

The next milestone is **multi-operation production execution with failure containment**.

The first reusable step toward that milestone is now implemented: `UnrealTaskPlanner.plan_actor_location_sequence(...)` creates a deterministic compound plan consisting of one initial inspection followed by repeated:

```text
WRITE → VERIFY
```

pairs.

For example, two requested locations produce:

```text
READ
WRITE(location A)
VERIFY(location A)
WRITE(location B)
VERIFY(location B)
```

This keeps every mutation behind an explicit proof boundary and gives the executor a precise operation cursor if a later operation fails.

New regression coverage was added in:

```text
tests/test_unreal_location_sequence.py
```

It proves the compound plan executes in order and preserves the immediate write/verify pairing.

## What remains before the next Unreal-dependent gate

The Python-side sequence capability still needs its full regression run on the user's checkout. After that, the next external gate should exercise the expanded multi-operation sequence against the real Unreal Editor.

The external test should prove at minimum:

1. the initial `FIELD_SURFACE` inspection succeeds;
2. the first authorized location write succeeds;
3. its verification succeeds;
4. the second location write succeeds;
5. its verification succeeds;
6. the final observed location is correct;
7. no operation outside the declared sequence is sent.

Do not broaden the Unreal server or introduce a new wire protocol for this gate.

## Recovery invariant

If any later operation fails, execution must stop at that operation. The executor must preserve the completed evidence and exact mutation intent at the boundary. Recovery may perform a fresh read-only reassessment, but it must never silently retry the mutation. Any replacement mutation plan requires explicit authorization.

## Important Unreal fixture convention

The current real integration fixture uses Atlas entity ID/tag:

```text
FIELD_SURFACE
```

If the real integration reports `Actor not found for entity_id: FIELD_SURFACE`, verify the Unreal Actor's Atlas mapping/tag before changing Python code. Do not introduce an alternative discovery mechanism merely to make the fixture pass.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Do not change the existing Named Pipe wire protocol.
- Do not introduce entity discovery or an Atlas-side entity cache.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not weaken fail-closed validation.
- Keep development isolated from the action/workflow runner.
- Do not run workflow/action-runner tests unless the user explicitly authorizes them.

## Next gate

After the Python regression suite passes with the new compound-sequence coverage, stop at the **real Unreal Editor multi-operation gate** and provide the exact test command. Do not add unnecessary Unreal-specific complexity before that proof.

## Architectural invariant

```text
Atlas owns the Twin.
Unreal Agent reasons/plans.
Atlas authorizes.
Unreal adapter executes.
Unreal provides evidence.
Atlas verifies.
Failures require fresh evidence and explicit recovery.
```

The Unreal Agent must never become a second autonomous authority separate from Atlas.
