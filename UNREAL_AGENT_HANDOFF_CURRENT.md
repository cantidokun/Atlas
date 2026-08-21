# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 21, 2026
**Current focus:** Production Unreal transport boundary and first production capability
**Current branch:** `agent/unreal-aider-ready`
**Base:** `main`

## Current position

The Unreal Agent planning/evidence architecture and the disposable Unreal Engine 5.6 validation harness are established. Development has now moved through the production Unreal transport boundary and its first transport robustness milestone.

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
Unreal transport
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
  - structured Unreal capabilities, operation kinds, intents, and proposals;
  - no direct execution authority.
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
- `planning/unreal_adapter_production.py`
  - stateless production adapter boundary;
  - authorization propagation;
  - enriched operation failure context.
- `planning/unreal_transport_contract.py`
  - request/response transport contract and correlation validation.
- `planning/unreal_transport_serialization.py`
  - strict JSON serialization/deserialization boundary.
- `planning/unreal_transport_named_pipe.py`
  - Windows named-pipe production transport;
  - 5-second connection timeout;
  - 30-second overlapped response-read timeout;
  - timeout cancellation and existing `NamedPipeTransportError` propagation.
- `planning/unreal_plan_executor.py`
  - Unreal-specific READ/WRITE/VERIFY dispatch;
  - independent evidence validation and ledger handling.

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

## Production transport milestone — August 21, 2026

The production Named Pipe transport has been audited and hardened against an indefinite response-read block.

Confirmed transport behavior:

- connection availability uses the existing 5-second `WaitNamedPipe` timeout;
- response reads use a 1 MB allocated buffer;
- response reads use Windows overlapped I/O;
- `READ_TIMEOUT_MS = 30000` is applied to pending response reads;
- `ERROR_IO_PENDING` is handled as the normal asynchronous-read path;
- timeout cancels the pending I/O before the transport closes its handles;
- non-pending Windows pipe errors continue through the existing `NamedPipeTransportError` boundary;
- the JSON Named Pipe wire protocol was not changed.

Relevant commits:

- `127c99e` introduced the initial overlapped response-read timeout implementation;
- `6c6be09` corrected buffer handling using an allocated 1 MB read buffer;
- `2621610` corrected `ERROR_IO_PENDING` exception handling.

These transport changes are intentionally isolated to the Python Named Pipe transport. The Unreal wire contract and `AtlasTransportServer.cpp` were not changed.

## Important production-boundary finding

The current Python planning/capability surface is broader than the currently implemented Unreal C++ transport server.

Python currently defines/plans operations including:

```text
inspect_target_actors
verify_target_actor_mapping
inspect_material_state
apply_material_variant
verify_material_variant
```

The current C++ transport implementation presently executes `inspect_target_actors` and rejects unsupported operation/capability/kind combinations. This is a confirmed implementation boundary, not a reason to weaken the Python contracts or invent entity discovery.

Therefore the next production capability must be selected deliberately and implemented end-to-end rather than assuming that every declared planner capability is already executable in Unreal.

## Disposable Unreal Engine 5.6 harness

Project:

`unreal/AtlasUnrealHarness/`

Target:

**Unreal Engine 5.6**

Automation test:

`Atlas.UnrealAgent.OperationBoundary`

The harness is Editor-only and disposable. It is not the production adapter.

The harness previously passed in Unreal Engine 5.6.1 after exposing and fixing the missing transform-root defect in the controlled temporary Actor. The exact assertion was preserved rather than weakened.

## Scope constraints

- Do not revisit AdapterExecutionBridge or Option B.
- Do not change the existing Named Pipe wire protocol.
- Do not introduce entity discovery or an Atlas-side entity cache.
- Do not add metrics unless a source audit establishes a concrete need.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Keep generic Atlas orchestration unchanged unless a shared-interface requirement is demonstrated.
- Do not weaken existing fail-closed validation.

## Action-runner constraint

Do not run workflow/action-runner tests unless explicitly authorized by the user. Local/offline development may continue when it is isolated from the runner and does not create system conflicts.

## Next development phase

1. complete the source-level audit of the production transport and its surrounding failure semantics;
2. validate the current transport implementation against the existing wire/response contract without changing that protocol;
3. identify the smallest end-to-end production capability supported by the existing Unreal server;
4. implement that capability only when its Atlas authorization → transport → Unreal execution → evidence → verification path is fully specified;
5. preserve the disposable Unreal harness as a regression fixture;
6. expand capabilities incrementally based on real production requirements.

The next implementation should not broaden the C++ operation surface merely because Python already declares future capabilities.

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
