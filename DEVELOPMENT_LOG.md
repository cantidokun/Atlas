# Atlas Development Log

## August 16, 2026 — Live Controller Passed / General Planning Integration

### Live controller result

The real local end-to-end controller test passed.

The controller:

1. started from measured BEFORE evidence
2. calculated the target state
3. executed both required `move_object` writes
4. performed an independent `inspect_object_relationship` verification
5. confirmed the required final state
6. built the final report in Python
7. exited without another Qwen reasoning cycle

Final verified state:

```text
Goal_Left_post  = [0.0, 5.233, 0.0]
Goal_Right_Post = [0.0, -5.233, 0.0]
Midpoint        = [0.0, 0.0, 0.0]
Distance        = 10.466 units
Symmetric       = true
```

### General Action Planning V1

Added:

`action_plan.py`

It contains:

- `ActionSpec` — one ordered authorized action
- `ActionPlan` — deterministic state for an ordered action sequence

The plan exposes the next action, records results, advances only after success, blocks after a required failure, reports completion, and provides a serializable state snapshot.

### General Evidence Planning V1

Added:

`evidence_plan.py`

It tracks ordered evidence requests, completion, reuse, and blocking failures.

### Planning Orchestrator V1

Added:

`planning_orchestrator.py`

It connects evidence and action plans. Action execution remains blocked until required evidence is complete.

### Controlled failure / recovery

The live recovery harness passed.

A failed write is detected as recoverable, fresh evidence is required, and automatic retry is refused. A new validated and explicitly authorized plan is required before retrying.

### Audit trail

The live action workflow records the lifecycle in order:

```text
Qwen proposal
 ↓
Evidence
 ↓
Authorization
 ↓
Execution 1
 ↓
Execution 2
 ↓
Verification
```

The final live test completed with an audit trail and independent verification.

### Qwen Structured Planning Bridge — PASS

Added:

`live_qwen_planning_loop.py`

The live planning bridge now proves:

```text
Qwen structured plan
 ↓
Python plan validation
 ↓
Read-only Blender evidence
 ↓
Planning orchestrator
 ↓
Structured action plan
 ↓
No write execution
```

The successful run produced:

- 1 structured evidence request
- 2 structured actions
- validated plan
- authoritative read-only evidence
- completed evidence plan
- structured action plan with the next action exposed
- zero write execution

Result:

```text
QWEN PLAN ACCEPTED
EVIDENCE VERIFIED READ-ONLY
ACTION PLAN STRUCTURED
WRITE EXECUTION NOT PERFORMED
ATLAS QWEN PLANNING BRIDGE TEST: PASS
```

This is the first live boundary between Qwen task planning and the generic Python planning primitives.

### Regression status

Latest local regression result at this early checkpoint:

```text
98 passed
```

## August 17, 2026 — Runtime Continuation Integrity Milestone

The runtime-integrity boundary was promoted from an isolated regression primitive into the actual autonomous continuation/resume path.

Implemented and merged in PR #9:

- `RuntimeIntegrity` receipts are serializable and persisted with future runtime checkpoints.
- `AutonomousFutureRuntime` binds continuation to stable instruction fingerprint, authorized future/plan digest, and exact persisted checkpoint-state digest.
- validated resume fails closed when the receipt is missing, tampered, the stable instructions change, or the authorized future changes.
- `resume_from_store()` makes the validated resume boundary explicit.
- regression coverage was added for matching, changed-context, tampered-receipt, missing-receipt, and exact-checkpoint continuation.
- an existing Unreal planner regression was corrected so empty target sets fail closed rather than producing an executable plan.

Validation:

```text
Atlas Tests PR run #348
Python 3.9: PASS
Python 3.11: PASS
```

The next major development target became the broader live autonomous-task proof: use a second non-goalpost production task to demonstrate that the same generic conditional planning, authorization, deterministic future, verification, recovery, and continuation-integrity machinery works outside the original goalpost fixture.

## August 21, 2026 — Unreal Architecture Decision Finalized

### Comprehensive Unreal Integration Audit Completed

A complete source-level audit of the Unreal integration architecture was conducted across the Unreal-specific planning, capability, adapter, executor, evidence, schema, and transport layers.

### Final Architectural Decision: Option B Investigation CLOSED

**Decision:** `UnrealPlanExecutor` remains the Unreal-specific execution boundary. `AdapterExecutionBridge` integration is NOT pursued.

**Rationale:**
- Option B would require breaking API changes to `UnrealPlanExecutor` constructor
- Generic `AdapterExecutionBridge` does not support Unreal-specific READ/WRITE/VERIFY dispatch
- `TwinRepresentation` dependencies are not available in the Unreal context
- authorization propagation is incompatible with the generic adapter contract

### Confirmed Unreal Execution Architecture

```text
UnrealTaskPlanner
→ UnrealTaskPlan
→ UnrealPlanExecutor
→ UnrealAdapterProduction
→ UnrealTransport
→ Unreal Process
→ UnrealEvidence
→ UnrealPlanExecutor validation/ledger
```

Key confirmations:

- READ/WRITE/VERIFY dispatch remains Unreal-specific;
- `authorization_id` propagates through the complete execution path;
- authorization validation remains delegated to the Unreal process;
- generic Atlas infrastructure remains unchanged;
- the Unreal integration preserves the intended separation from generic orchestration.

### Production Named Pipe hardening

The Windows Named Pipe transport was hardened against indefinite response-read blocking while preserving the existing JSON wire protocol.

The corrected transport uses a genuinely overlapped pipe handle, bounded pending response reads, explicit pywin32 result-code handling, cancellation on timeout, and safe cleanup.

Focused regression coverage was added for connection timeout, pending-read timeout, cancellation, and server-disconnect behavior.

## August 22, 2026 — First Real Unreal Production Boundary Milestone

### Regression and boundary fixes

The Unreal production path went through several deliberately fail-closed fixes during live validation.

A malformed fresh Unreal state containing a non-numeric coordinate was initially classified incorrectly as `STATE_CHANGED`. The reassessment decision boundary was corrected so malformed fresh evidence remains `INSUFFICIENT_EVIDENCE` / uncertain rather than being treated as proof of a changed state.

An evidence/transport metadata consistency issue was also corrected so transport requests and the corresponding evidence ledger entries remain aligned through the executor pipeline.

The Named Pipe transport failure boundary was hardened further so:

- `WaitNamedPipe` timeout is translated before `CreateFile` is attempted;
- pending response-read timeouts cancel the pending operation and close handles safely;
- pywin32 `ReadFile` result codes are interpreted correctly rather than assuming asynchronous completion always raises an exception.

### Full regression status

The latest full local regression reported:

```text
530 passed, 5 skipped
```

The focused transport boundary tests then passed, and the user subsequently reported the remaining skipped coverage as passed as well.

The key focused Unreal recovery/executor suite reached:

```text
24 passed
```

and the recovery coordinator/executor integration suite reached:

```text
22 passed
```

### Real Unreal Editor proof — PASS

The first actual production-boundary tests were run against the running Unreal Editor.

Passed:

```text
test_real_unreal_plan_executor_location_write_and_restore

test_real_unreal_recovery_coordinator_reassesses_live_state_without_retrying_write
```

The combined live run passed both tests.

Earlier live Unreal transport/integration checks also passed when the Editor transport was available, including real connection, sequential requests, production actor write/restore, and recovery reassessment.

### What is now proven

Atlas has now demonstrated the following real process-boundary sequence:

```text
Atlas operation
    ↓
production Unreal adapter
    ↓
Windows Named Pipe transport
    ↓
real Unreal Editor
    ↓
actor state mutation
    ↓
independent state readback
    ↓
verification
    ↓
restore
```

And for recovery:

```text
mutation / verification uncertainty
    ↓
fresh live Unreal observation
    ↓
reassessment
    ↓
NO automatic mutation retry
```

This is a genuine external production-boundary milestone. It is not yet proof of arbitrary multi-operation Unreal production automation.

### Fixture lesson

The live integration initially failed because the expected Unreal entity mapping was absent:

```text
Actor not found for entity_id: FIELD_SURFACE
```

The correct resolution was to configure the Unreal fixture with the exact expected `FIELD_SURFACE` entity mapping/tag rather than changing Atlas entity discovery or weakening the Python contract.

This convention is now documented in the Unreal handoff and Unreal README.

### Current architectural boundary

Python currently declares/plans additional Unreal capabilities beyond the operation surface implemented by the current C++ transport server. The next capability must therefore be selected deliberately and implemented end-to-end.

Do not broaden the C++ operation surface merely because a future capability exists in Python planning code.

## August 22, 2026 — Next Milestone Definition

The next major development target is **multi-operation production execution with failure containment**.

The Python-side implementation should establish:

1. ordered evidence before mutation;
2. exact authorization of the ordered operation set;
3. evidence bound to each exact operation/entity target;
4. deterministic execution cursor advancement;
5. safe stop when a later operation fails;
6. preservation of completed write targets;
7. fresh read-only reassessment after uncertain mutation/verification;
8. no automatic mutation retry;
9. explicit authorization for any replacement plan;
10. independent verification before completion.

Only after this boundary is green in offline regression should the expanded multi-operation scenario be exercised against the real Unreal Editor.

### Action-runner constraint

Do not run workflow/action-runner tests unless the user explicitly authorizes them. Continue isolated development that cannot create system conflicts while the external runner is unavailable or intentionally unused.

### Documentation checkpoint

The following current-state documents were updated after the real production-boundary milestone:

- `UNREAL_AGENT_HANDOFF_CURRENT.md`
- `UNREAL_AIDER_SCOPE.md`
- `unreal/README.md`

These documents now identify the first real production proof as passed and point to the multi-operation/failure-containment milestone as the next gate.

## September 15, 2026 — Controller Host Reconciliation + Live Controller-to-Production Gate

### Reconciliation of the local autonomy branch with origin

The local autonomy commit had diverged from `origin/integrate-origin-main-with-render-receipt` (ahead 1, behind 12). The divergence was analyzed before any write operation and reconciled in three controlled commits:

```text
09015d9  feat: integrate Unreal autonomy into controller runtime
   ↓
c0321bd  fix: compose agent controller boundary from AgentControllerHost
   ↓
bac08e8  Merge origin/integrate-origin-main-with-render-receipt
   ↓
fe2322f  test: align synthetic Unreal result fixtures with strict contract
```

- `c0321bd` committed the audited Host-seam change by itself: `agent.py` composes its controller boundary from `AgentControllerHost` (host-owned runtime and loop) instead of constructing `AtlasEntrypointRuntime` and `AgentControllerLoopAdapter` directly.
- `bac08e8` recorded exactly one merge conflict, `planning/unreal_production_workflow.py`, resolved to origin's strict exact-type `verified_render` implementation. A typed `UnrealProductionExecutionResult` is now required for production/render intent binding, and the duck-typed fallback that produced a self-comparison is gone. The merge preserved the local `normalize_unreal_production_event` failure semantics, the local recovery-action capability admission, and all 14 local-only implementation paths.
- `fe2322f` repaired two synthetic fixtures in `tests/test_agent_controller_host_unreal_synthetic_end_to_end.py` that had passed only because of the removed duck-typed fallback; they now build a real `UnrealProductionExecutionResult` whose plan intent matches the render intent.

Nine of the twelve origin commits were already content-identical in the local commit, two were net no-ops, and the real delta was the single `verified_render` guard.

### Deterministic validation on the reconciled branch

```text
focused controller/agent/host/result/evidence suite : 268 passed, 1 skipped, 1 deselected
broader deterministic Unreal/controller/agent/
  capability/evidence/receipt sweep                 : 742 passed, 5 skipped
Python 3.9 focused parity                           : 268 passed, 1 skipped, 1 deselected
four directly affected surfaces                     : 37 passed
```

> **CORRECTED 2026-09-15 (checkpoint continuation):** the focused figure above was not
> reproducible on fe2322f from any recorded selection. See the September 15, 2026
> checkpoint-continuation entry at the end of this log for the measured figures and the
> exact canonical focused-suite command.

### Live controller-to-production gate — PASSED

An already-authorized Unreal production operation was driven through the complete host-owned controller path against a real Unreal Engine 5.6.1 editor:

```text
model text → ATLAS_CONTROLLER_REQUEST → AgentControllerIntent → AgentTaskRequest
→ AgentControllerHost → AgentControllerLoopAdapter → AgentEntrypointRuntime
→ AgentProcessRuntime → capability admission → TrustedUnrealContext
→ Unreal production capability → Named Pipe → real Unreal → fresh evidence
→ render receipt → UnrealProductionResultContract
```

```text
test    : tests/test_agent_controller_host_production_real_integration.py
command : .venv/Scripts/python.exe -m pytest tests/test_agent_controller_host_production_real_integration.py -m integration -q -s
result  : 1 passed in 10.77s
```

The harness is a newly created, integration-marked, test-only live gate; no production or test source was modified by the gate.

### Live Unreal details

```text
Unreal Engine 5.6.1 / UnrealEditor-Cmd.exe / unreal/AtlasUnrealHarness
transport     : \\.\pipe\AtlasUnrealTransport (AtlasTransportServer.cpp)
fixture map   : /Game/AtlasTest/Generated/AtlasRenderFixture (required)
```

Launching the editor without the fixture map can leave `GEngine->GetWorldContexts()[0]` pointing at a cleaned-up world, which makes the server-side entity lookup fail with `Actor not found for entity_id: FIELD_SURFACE`. This was diagnosed as a pre-existing harness/setup characteristic and was not fixed.

### Real production operation

The proven `FIELD_SURFACE` composite production was reused unchanged: location 10/20/30, rotation pitch 0 / yaw 15 / roll 0, scale 1.1, material variant `liquid_surface`, Niagara variant `goal_burst`, sequencer playback range 1–24, and a 1280x720 PNG Movie Render Queue render of 24 frames. The render completed successfully and the engine log confirms the pipeline finished the submitted job.

The fixture was restored afterwards and verified at location 0/0/0, identity rotation, scale 1/1/1.

### Trust boundary proof

The model output deliberately supplied forged authorization and context (`authorized_production: FORGED-BY-MODEL`, a forged intent string, and `/Game/Forged/ModelSequence`). The host-installed `TrustedUnrealContext` overrode all three: the admitted and executed request used the host-authorized production plan, the trusted intent, and the trusted sequence path. The model's declared intent survived only as diagnostic metadata.

**The agent controller host trust boundary has now been validated against real Unreal execution.**

### Evidence, receipt, and result contract

```text
evidence  : inspect_render_job / FIELD_SURFACE / unreal-editor-atlas-transport / verified True
digest    : 81bbf55a6c29b589d3dda5f57de8dcfdeb15203617811233712a0fa810e7d853
render job: B6F524E9-4527-4804-27A4-B7BD92A1CBB6
receipt   : matches final evidence True
digest    : aab94cdf375f00454290275e8e70493001e4d020861b8d0789787791c11240c7
```

The typed controller result reported `controller_executed = True`, capability `unreal_production`, operation `start`, snapshot state `complete`, `workflow_result.success = True`, `verified_render = True`, `failed = False`, `requires_recovery = False`, and `integration.complete = True`. The production instance was an exact `UnrealProductionExecutionResult` and the render intent, trusted intent, and production plan intent all matched. The result was grounded in an independent post-execution engine readback rather than trusting the controller request.

The persisted receipt artifact was preserved at `C:\Users\Gavin's PC\AppData\Local\Temp\atlas-live-gate-evidence\host-path-render-receipt.json`.

### Outstanding items

1. **Test-only compatibility issue.** `tests/test_agent_controller_production_real_integration.py` is currently RED under the hardened evidence contract: `UnrealEvidence.observed_state` is frozen into a `MappingProxyType` tree while its helper `_variant` requires `isinstance(value, dict)`. Smallest repair: use `collections.abc.Mapping` in the test helper. Not implemented on the night of
September 15; **APPLIED 2026-09-15 (checkpoint continuation)** in the working tree, with both live
controller production tests rerun green — see the continuation entry at the end of this log.
2. **Harness setup dependence.** The live harness requires launching with `/Game/AtlasTest/Generated/AtlasRenderFixture` because the server-side entity lookup uses `GEngine->GetWorldContexts()[0]` while fixture provisioning uses the editor world. A durable C++ active-editor-world fallback is a future harness improvement, separate from the controller milestone.

### Current state

```text
RECONCILED + DETERMINISTIC GREEN + LIVE CONTROLLER-TO-UNREAL PRODUCTION GREEN
```

The next genuine architectural/engine milestone remains the **live Blueprint production boundary** (narrow metadata mutation, compile, verify, and persisted metadata under `metadata` in post-mutation evidence). Blueprint production is not green and was not started.

Existing invariants are unchanged: Atlas is the canonical authority, models and providers reason and propose only, `AgentControllerHost` owns the trusted execution context, `TrustedUnrealContext` is host-installed, capability admission is fail-closed, Unreal supplies fresh evidence, render receipts must match verified evidence, recovery requires fresh evidence and replacement authorization, the Named Pipe transport is unchanged, and Blender/Qwen remain isolated from this milestone.

## September 15, 2026 — Checkpoint Continuation: Canonical Test Counts, Mapping Repair Applied, Blueprint Gate Preparation

### Canonical focused-suite correction

The previously recorded focused figure (`268 passed, 1 skipped, 1 deselected`) is not reproducible on
`fe2322f7e76caf3115e3e5be6dafce05d62251ca` from any recorded selection. Measured at this checkpoint:

```text
canonical focused suite (13 modules)     : 160 passed, 2 deselected   [Python 3.11.16]
Python 3.9.6 parity (same 13 modules)    : 160 passed, 2 deselected
broader deterministic sweep              : 742 passed, 5 skipped      (747 collected, exact match)
four directly affected contract surfaces : 37 passed
```

Exact focused command:

```text
.venv/Scripts/python.exe -m pytest tests/test_agent_controller_*.py tests/test_agent_entrypoint_*.py \
  tests/test_agent_execution_context.py tests/test_agent_trusted_context.py tests/test_agent_task_request.py \
  tests/test_agent_process_runtime.py tests/test_agent_process_runtime_identity.py \
  tests/test_capability_admission.py tests/test_capability_execution.py \
  tests/test_unreal_production_result_contract.py tests/test_unreal_evidence_contract.py \
  tests/test_unreal_render_receipt.py tests/test_unreal_render_receipt_store.py -m "not integration" -q
```

The broader deterministic sweep reproduces the documented `742 passed, 5 skipped` exactly, so that baseline
is preserved unchanged. No test behavior was altered to reach any figure.

### Test-only mapping repair applied (working tree, uncommitted)

`tests/test_agent_controller_production_real_integration.py`:

```python
from collections.abc import Mapping
...
if not isinstance(value, Mapping):      # was dict
```

The hardened evidence contract freezes `UnrealEvidence.observed_state` into a `MappingProxyType` tree, so
the helper's `isinstance(value, dict)` check rejected present, readable data. Test-only: no production,
transport, authorization, trusted-context, result-contract, C++, Blueprint, Blender or Qwen code touched.

Both live controller production tests were rerun against real Unreal Engine 5.6.1 (Named Pipe
`\\.\pipe\AtlasUnrealTransport`, fixture map `/Game/AtlasTest/Generated/AtlasRenderFixture`):

```text
tests/test_agent_controller_production_real_integration.py      : 1 passed in 9.53s
tests/test_agent_controller_host_production_real_integration.py : 1 passed in 6.10s
```

Host-path identities from the rerun:

```text
render job id      : 1F901C1E-4AA7-6477-D7FB-81B91ED0FD94
evidence           : inspect_render_job / FIELD_SURFACE / verified True
evidence digest    : 5481a35eb952e80179ba2d48e9e92d80b1657581bfcfad9482c3efc195e77c11
receipt digest     : e92769129aab7795126e66420ef4b48acff42e4813610e02166f794d4b3aec2e
contract           : success=True verified_render=True failed=False requires_recovery=False
live readback      : location 10/20/30 after execution
restore            : 0/0/0, identity rotation, 1/1/1 (verified by an independent read-only probe)
```

Engine-side corroboration: `LogMovieRenderPipeline` reports a 1-job render (`+00:00:02.326`) and a 2-job
render (`+00:00:02.845`) completing during the two runs, and the tracked harness assets under
`Content/AtlasTest/` are byte-identical (sha256) before and after.

### Residual mapping compatibility sites (known follow-up, not fixed)

```text
tests/test_unreal_composite_real_integration.py
tests/test_unreal_heterogeneous_recovery_real_integration.py
tests/test_unreal_production_workflow_real_integration.py
tests/test_unreal_material_variant_real_integration.py
```

Same defect class as the repaired helper: each requires `dict` where the frozen `observed_state` supplies a
`MappingProxyType`, so they fail the same way on a live run until the same one-line repair is authorized.
Not modified in this task.

### Working-tree state at this checkpoint

Seven tracked documentation files are modified (this handoff/status set) together with the applied two-line
test-only repair. Nothing is committed, nothing is staged, and HEAD remains
`fe2322f7e76caf3115e3e5be6dafce05d62251ca`. The live controller gate harness
(`tests/test_agent_controller_host_production_real_integration.py`) and the pre-existing Aider artifacts
remain untracked.

### Next gate

The live Blueprint production boundary remains **not green**: `inspect_blueprint_state` ->
`set_blueprint_metadata` -> `compile_blueprint` -> `verify_blueprint_state`, with the open acceptance
condition that persisted Blueprint metadata must appear under `metadata` in post-mutation evidence. The
boundary has not been re-gated live since the recorded `KeyError: 'metadata'` failure, so it must be
revalidated against the real editor before any Blueprint-complete claim.
