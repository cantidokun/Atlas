# Atlas Current Development Handoff

**Updated:** August 20, 2026 03:39 EDT  
**Branch:** `main`  
**Documentation HEAD:** `635affff4b4af866fec8e3b51661ca0fd5be7c28` — `docs: restore current runner pause in handoff`  
**Code baseline:** `934a615f3a1be5a22b75c3251ad005df7f7f79a2` — `fix: retry transient Ollama planning timeout in collection task`

## 1. Scope and authority

This track is the **Blender Agent only**. Unreal Agent work is out of scope.

Atlas authority model:

```text
Qwen / AI -> reason + propose
Python / Atlas -> validate -> authorize -> execute -> track -> verify -> recover
Blender -> production execution adapter
Atlas -> independent authoritative-state verification
```

Qwen is never the execution authority. Blender is not the canonical source of truth for whether an Atlas task succeeded.

Photogrammetry is upstream: dedicated photogrammetry software creates the initial reconstruction; Blender receives it for analysis, cleanup, correction, and preparation.

## 2. Current runtime/test posture — PAUSED

**The user has now explicitly paused further development/testing for the night. Do not initiate new development work, workflow runs, action-runner jobs, approvals, or test runs until the user explicitly resumes work.**

The local Windows GitHub Actions runner `atlas-local` remains the intended live-test environment, but its operational state does not authorize new activity during this pause.

A workflow was already in progress when the pause was issued: **Atlas Tests #629**. It was at the setup/checkout stage when last inspected. Do not start another run or approve any new environment request while paused. Treat that run as an existing in-flight operation, not as permission to continue development.

Ollama is dedicated Atlas infrastructure and should be treated as available for Atlas when work resumes.

## 3. Generic architecture

Implemented generic primitives include:

- `ActionPlan`
- `EvidencePlan`
- `TargetStateEvaluator`
- `VerificationPlan`
- `PlanningOrchestrator`
- `ConditionalPlanningOrchestrator`
- `ActionAuthorization`
- `ReplanAuthorization`
- `DeterministicFutureGenerator`
- `FutureExecutionController`
- `FutureRecoveryGate`
- runtime-context fingerprinting / integrity checks
- audit trail
- immutable Blender execution receipts
- `AtlasTaskDefinition` — declarative task boundary for evidence, actions, target evaluation, allowed tools, write policy, and verification policy
- `planning/task_runtime.py` — runtime enforcement boundary for task execution policy
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md` — explicit promotion/authority contract for production-task adapters

Conditional execution remains explicitly separated into evidence acquisition, target evaluation, skip/execute decision, authorization, deterministic execution, fresh verification, and fail-closed completion/blocking.

`VerificationPlan` is first-class: successful execution is never treated as proof of resulting state.

`AtlasTaskDefinition` contains task data only; orchestration and execution-policy enforcement remain generic runtime concerns.

## 4. Blender files/tools

Core boundary:

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; includes `create_empty_marker`.
- `planning/blender_execution_boundary.py` — validated execution, `execute_verified()`, and receipt-bound single execution.
- `planning/blender_result_contract.py` — normalized immutable result contract.
- `planning/blender_verification.py` — requested-tool identity and successful-execution verification.
- `planning/blender_execution_receipt.py` — deterministic request/result receipt and mutation detection.
- `planning/verification_plan.py` — required/pending/complete/blocked verification state.
- `planning/task_definition.py` — `AtlasTaskDefinition` declarative task boundary.
- `planning/task_runtime.py` — runtime preparation and enforcement of task write/verification policy.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task/harness files include the conditional, collection, membership, parent, rotation, rename, delete, marker, verification-failure, and continuation live paths and their deterministic fixture tooling.

## 5. Model/runtime

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Local GitHub Actions runner: `atlas-local` — intended live-test environment; no new runs while paused
- Qwen structured planning uses `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, and `qwen_planning_runtime.py`.

## 6. Recent development progress

### Task-definition/runtime boundary

A significant architectural refinement was completed immediately before the current pause:

- `AtlasTaskDefinition` remains a declarative task description.
- Runtime policy is enforced by `prepare_task_runtime()` rather than by making task construction itself the execution-policy boundary.
- Write-capable tasks must require post-action verification before runtime preparation can authorize execution.
- Snapshot immutability protects nested metadata, action arguments, and evidence arguments from mutation through returned snapshots.

This preserves the separation between **describing a task** and **preparing a task for execution**.

### Broader Blender capability coverage

The generic control architecture has already been live-proven across materially different Blender behaviors, including:

- object rotation;
- object rename;
- object delete;
- collection creation;
- collection membership;
- parent relationships;
- conditional goalpost correction;
- continuation/pause-resume;
- tampered continuation rejection;
- adversarial verification failure -> `BLOCKED`.

The important milestone is no longer proving that Atlas can perform one Blender edit. It is demonstrating that the same validation → evidence → target evaluation → authorization → deterministic execution → independent verification → receipt architecture can govern many different Blender operations.

### Ollama reliability

Earlier live failures exposed structured-planning read timeouts against the local Ollama endpoint. Ollama is now treated as **dedicated Atlas infrastructure**, so no architecture is being designed around unrelated Qwen workloads. The generic collection planning path also gained bounded transient-timeout retry behavior within its existing planning budget and records timeout events in the audit trail.

## 7. Current verification boundary

The newest task-runtime changes have been exercised through the development/test workflow, but **do not declare a new green baseline until the actual run for the current code state has completed successfully**.

The last established historical offline baseline before the latest task-runtime correction was:

```text
444 passed, 1 failed
```

The failure was the old test expecting construction-time rejection. The implementation intentionally moved that policy to runtime preparation, and the regression test was corrected accordingly.

An already-running workflow at pause time was **Atlas Tests #629**. Its final result should be checked first when work resumes, rather than assuming success or failure.

Historical live regressions remain valid as historical proofs for the capabilities listed above; they do not automatically validate newer untested code.

## 8. Current roadmap position

### Stages 1–8

Complete for their currently defined scope:

- Stage 1 — Basic Blender Agent
- Stage 2 — Reliable Evidence
- Stage 3 — Mandatory Evidence Acquisition
- Stage 4 — Evidence Validation and Recommendation Restraint
- Stage 5 — General Evidence Planner
- Stage 6 — Reliable Modification Control
- Stage 7 — General Action Planning
- Stage 8 — Conditional Action Planning for the live goalpost proof

### Stage 9 — Broader Autonomous Blender Task Control

**IN PROGRESS — SUBSTANTIALLY ADVANCED**

The architecture now has the major control primitives required for a production-facing autonomous Blender loop. The remaining work is integration/hardening and broader proof, not rebuilding the architecture.

The target loop is:

```text
Qwen proposal
 ↓
validated task/evidence/action structure
 ↓
authoritative Blender evidence
 ↓
target-state evaluation
 ↓
conditional decision
 ↓
authorization
 ↓
deterministic future
 ↓
Blender execution
 ↓
fresh independent verification
 ↓
immutable receipt
 ↓
completion / conservative recovery
```

### Next materially distinct capability

`create_empty_marker` remains the next clean capability to live-prove after testing is explicitly resumed. It is useful because it exercises the task/runtime boundary with a simple write whose resulting state can be independently inspected.

## 9. Remaining path to the major Blender milestone

The major near-term milestone is the **first robust production-facing autonomous Blender closed loop** in which Atlas can accept a real task, use Qwen for planning, obtain authoritative evidence, decide whether work is necessary, authorize only valid actions, execute through the Blender boundary, independently verify the resulting Blender state, create a receipt, and safely continue or recover.

Most of the control machinery required for this now exists. What remains is fresh validation of the current integrated runtime plus broader continuation/resume proof across multiple materially different task types.

## 10. Offline-safe priorities after the pause is lifted, if runner testing remains unavailable

If development resumes while workflow testing remains unavailable, safe work can focus on:

1. deterministic task-contract validation;
2. receipt immutability and mutation detection;
3. malformed-result rejection;
4. authorization/replan boundaries;
5. fail-closed recovery logic;
6. static architecture checks;
7. diagnostics and deterministic fixture tooling;
8. documentation synchronization.

Do not modify runner configuration merely to work around test availability.

## 11. Next steps when the user resumes

1. Check the final result of existing **Atlas Tests #629** before doing anything else.
2. Inspect current `main` and the newest workflow state.
3. Obtain a fresh fully green baseline for the current code if required.
4. Live-prove `create_empty_marker` through the generic task/runtime architecture.
5. Preserve explicit zero-write, single-write, verification-failure, receipt-integrity, and authorization regressions.
6. Expand production-facing continuation/resume across multiple materially different Blender task types.
7. Promote the resulting closed loop as the next major Blender milestone only after the evidence supports it.

## 12. Required regression coverage

Preserve proofs for:

- already-satisfied -> zero writes
- unsatisfied -> exact authorized action order
- authorization mandatory before writes
- successful write -> verification mandatory
- failed verification -> `BLOCKED`
- failed action -> recovery gate
- mutated arguments -> receipt mismatch
- mutated result -> receipt mismatch
- malformed executor response -> rejected
- wrong result tool -> rejected
- invalid continuation identity -> rejected
- authorized replan from fresh evidence -> accepted
- unauthorized replan -> rejected
- one receipt-bound execution cannot cause duplicate writes
- write-capable task runtime requires post-action verification
- task snapshots cannot mutate live task definitions

## 13. Resume instructions

**Do not resume automatically.** The user explicitly ended the development session for the night.

When the user returns and explicitly asks to continue, read this handoff first, inspect the final status of Atlas Tests #629, then resume from the current code state without repeating already-completed work.
