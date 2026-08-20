# Atlas Current Development Handoff

**Updated:** August 20, 2026 02:56 EDT  
**Branch:** `main` baseline; documentation update prepared on `docs-roadmap-handoff-2026-08-20`  
**Current repository HEAD before this documentation update:** `635affff4b4af866fec8e3b51661ca0fd5be7c28`  
**Latest code change on `main`:** `554c6dff7fc73f066737e76ab91784bb81da5055` — `test: defer write verification assertion to task runtime`

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

## 2. Current runtime/test posture

Workflow and action-runner testing is **currently authorized** by the user and has been actively used during this development pass. The local Windows GitHub Actions runner `atlas-local` is the intended live-test environment.

Ollama is treated as **dedicated Atlas infrastructure** for this development track. Do not compensate for or architect around unrelated Qwen workloads.

Do not represent a newer change as verified merely because a workflow was triggered. Use the actual local or live result as the authority for validation status.

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
- `planning/task_runtime.py` — runtime enforcement boundary for execution policy
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
- `planning/task_runtime.py` — prepares/validates a task for execution and enforces write-verification policy at the runtime boundary.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task/harness files include the conditional, collection, membership, parent, rotation, rename, delete, marker, verification-failure, and continuation live paths and their deterministic fixture tooling.

## 5. Model/runtime

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Local GitHub Actions runner: `atlas-local` — intended live-test environment
- Qwen structured planning uses `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, and `qwen_planning_runtime.py`.

## 6. Verified milestones and recent progress

### Multi-capability live Blender control

The original conditional goalpost proof is no longer the only live proof. The same generic control architecture has previously passed live regressions for:

- **Object rotation** — already-correct and incorrect paths, including authorized write and fresh verification.
- **Object rename** — incorrect path successfully planned/executed/verified.
- **Object delete** — incorrect path successfully planned/executed/verified.
- **Collection membership** — already-correct and incorrect paths.
- **Parent relationship** — already-correct and incorrect paths.
- **Generic collection** — already-correct and incorrect paths.
- **Blender continuation** — correct, incorrect, and tampered-context rejection.
- **Conditional goalpost** — already-correct and incorrect paths.
- **Adversarial verification** — executor claims success while authoritative Blender state disagrees -> `BLOCKED`.

This is the key Stage 9 advancement: Atlas is now demonstrating reuse of the same validation → evidence → target evaluation → authorization → deterministic future → execution → verification architecture across materially different Blender operations.

### Runtime/session integrity

Runtime continuation is bound to stable instructions, authorized future/plan identity, and authoritative persisted-state identity. Resume fails closed when required identity or checkpoint state is missing or tampered.

Recent regression work expanded session lifecycle, replay, and close-state coverage. This moves the controller toward a production-facing lifecycle rather than treating continuation as a standalone helper.

### Task-definition/runtime boundary

The recent task-runtime hardening established an important architectural separation:

- `AtlasTaskDefinition` describes the task.
- `prepare_task_runtime()` enforces execution-time policy.
- A write-capable task can therefore be constructed as declarative data even when its verification policy is malformed, but the runtime refuses to prepare it for execution without required post-action verification.

The associated regression was moved from task construction to runtime preparation in commits `353740a` and `554c6d`.

### Snapshot immutability

`AtlasTaskDefinition.snapshot()` has deep-copy protection for nested mutable metadata, action arguments, and evidence arguments. Mutating a returned snapshot cannot mutate the live task definition.

### Ollama reliability observation

Earlier live rotation/rename/collection failures exposed transient structured-planning read timeouts against local Ollama. Ollama is now treated as dedicated Atlas infrastructure, so no workload-sharing compensation is required. The generic collection planning path also received bounded retry handling for transient planning-service timeouts without allowing failed writes to auto-retry.

## 7. Current test state

The latest reported full local pytest gate immediately before the runtime-boundary test correction was:

```text
444 passed, 1 failed, 1 warning
```

The failure was:

```text
test_write_task_requires_verification
Failed: DID NOT RAISE ValueError
```

The underlying implementation had intentionally moved the policy check out of `AtlasTaskDefinition.__post_init__` so it could be enforced at runtime. Commit `353740a` made that implementation change, and commit `554c6d` corrected the regression test to assert that `prepare_task_runtime(task)` rejects the malformed write task.

**Fresh full green validation after `554c6d` has not yet been recorded in this handoff.** Do not call the newer task-runtime changes fully tested until that gate passes.

Previously verified live regression results remain valid historical baselines for the capabilities listed above, but they do not automatically validate newer untested code.

## 8. Current roadmap position

### Stages 1–8

The following are complete for their currently defined scope:

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

Stage 9 has progressed from “prove a second task” to “prove a reusable multi-capability control layer.” The architecture is now live-proven across rotation, rename, delete, collection, membership, parent, continuation, adversarial verification, and conditional goalpost behavior.

The remaining work is primarily integration/hardening rather than inventing a separate architecture per tool:

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

The next materially distinct live capability remains `create_empty_marker`, followed by broader production-facing continuation/resume proof using multiple task types.

## 9. What is still between us and the major Blender milestone

The major near-term milestone is the **first robust, production-facing autonomous Blender closed loop**, where the system can take a real task, plan it with Qwen, obtain authoritative evidence, decide whether work is necessary, execute only authorized actions, independently verify the resulting Blender state, produce an execution receipt, and safely continue or recover.

Most of the control machinery required for that loop now exists and has been exercised live. The remaining gap is proving the complete task/runtime integration on the newer architecture and expanding continuation/resume beyond the current regression fixtures.

This is why Atlas is now in Stage 9 rather than still in the foundational planning stages.

## 10. Required regression coverage

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
- write-verification policy enforced at task-runtime preparation
- session close/replay state cannot silently reopen or corrupt an authorized future

## 11. Next development sequence

1. Finish the current task-runtime/test hardening and obtain a fresh fully green local gate.
2. Preserve the existing live regression baseline.
3. Live-prove `create_empty_marker` using the generic task/runtime boundary.
4. Expand production-facing continuation/resume across multiple materially different Blender task types.
5. Demonstrate a coherent autonomous closed loop that is not dependent on the goalpost fixture.
6. Only then promote the next major production capability and begin the path toward broader digital-twin production workflows.

## 12. Resume instructions

Read this file first, then `README.md`. Inspect the current `main` HEAD and latest workflow state before changing code.

Ollama is dedicated to Atlas; do not design around unrelated workloads.

Do not add task-specific branches to generic planners or bypass authorization, evidence, verification, receipt, or recovery boundaries.

Do not claim a newer change is live-verified without an actual successful run against that change.

**Immediate resume point:** close the remaining task-runtime validation loop, then continue Stage 9 toward the first robust production-facing autonomous Blender closed loop.
