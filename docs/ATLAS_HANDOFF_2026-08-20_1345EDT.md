# Atlas Development Handoff — August 20, 2026

**Status:** Active development; workflow/action-runner testing paused by explicit user instruction.
**Branch:** `main`
**Current documented code baseline:** `934a615f3a1be5a22b75c3251ad005df7f7f79a2` — `fix: retry transient Ollama planning timeout in collection task`
**Canonical handoff reviewed:** `ATLAS_HANDOFF_CURRENT.md` (`635affff4b4af866fec8e3b51661ca0fd5be7c28`)

## 1. Scope and architecture

Atlas is an AI-assisted sports virtual-production and digital-twin platform. The current proven execution environment is Blender; photogrammetry is upstream and supplies the initial 3D reconstruction for Blender to analyze, clean, correct, and prepare.

Current Blender Agent authority model:

```text
Qwen / AI
  reason + propose
       ↓
Python / Atlas
  validate → authorize → execute → track → verify → recover
       ↓
Blender
  production execution adapter
       ↓
Atlas authoritative verification
```

Qwen is never the execution authority. Successful executor output is never accepted as proof of resulting Blender state.

## 2. Generic control architecture

Implemented primitives include:

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
- runtime-context fingerprinting/integrity checks
- audit trail
- immutable Blender execution receipts
- `AtlasTaskDefinition`
- `planning/task_runtime.py`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`

The intended generic loop is:

```text
Qwen proposal
 → validated task/evidence/action structure
 → authoritative Blender evidence
 → target-state evaluation
 → conditional decision
 → authorization
 → deterministic future
 → Blender execution
 → fresh independent verification
 → immutable receipt
 → completion / conservative recovery
```

`AtlasTaskDefinition` is declarative task data. Runtime policy is enforced separately by `prepare_task_runtime()` and the generic execution path.

## 3. Concrete Blender files/tools

Core boundaries:

- `planning/blender_tool_schema.py` — supported-tool schema and argument validation, including `create_empty_marker`.
- `planning/blender_execution_boundary.py` — validated execution and receipt-bound single execution via `execute_verified()`.
- `planning/blender_result_contract.py` — normalized immutable result contract.
- `planning/blender_verification.py` — requested-tool identity and execution-result verification.
- `planning/blender_execution_receipt.py` — deterministic request/result receipt and mutation detection.
- `planning/verification_plan.py` — required/pending/complete/blocked verification state.
- `planning/task_definition.py` — declarative `AtlasTaskDefinition`.
- `planning/task_runtime.py` — runtime write/verification-policy enforcement.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task/harness coverage includes collection creation, collection membership, parent relationships, object rotation, rename, delete, marker creation, conditional goalpost correction, continuation/resume, verification-failure, and adversarial verification paths.

Qwen planning components include `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, and `qwen_planning_runtime.py`.

## 4. Model/runtime setup

- Ollama endpoint: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Intended live-test runner: local Windows GitHub Actions runner `atlas-local`
- Ollama is treated as dedicated Atlas infrastructure.
- Recent collection planning hardening added bounded transient Ollama timeout retry within the existing planning budget and audit logging.

## 5. Tests and established results

Historical verified baselines that remain valid for the code they exercised:

- **Atlas Tests #401:** PASS on Python 3.9 and 3.11.
- **Live Conditional Atlas Regression #155:** PASS on all four jobs:
  - live generic collection — incorrect: PASS
  - live generic collection — already-correct: PASS
  - live conditional — incorrect: PASS
  - live conditional — already-correct: PASS

Broader historical live proofs also cover object rotation, rename, delete, continuation/pause-resume, tampered continuation rejection, collection membership, parent relationships, goalpost correction, and adversarial verification failure → `BLOCKED`.

A later development workflow was recorded as **Atlas Tests #629** and was at setup/checkout when last documented. Its final result must not be assumed. No new workflow run has been initiated during the current testing pause.

The latest task-runtime correction intentionally moved write-policy enforcement from task construction to runtime preparation; any historical test expecting construction-time rejection must be interpreted accordingly.

## 6. Current development constraint

**Do not run, trigger, rerun, approve, or otherwise initiate workflow/action-runner tests until the user explicitly authorizes them.**

The user cannot currently set up the action runner. Development may continue only where it is isolated from runner configuration and does not create system conflicts.

Safe work while the runner is unavailable includes:

1. deterministic task-contract validation;
2. receipt immutability and mutation detection;
3. malformed-result rejection;
4. authorization/replan boundary hardening;
5. fail-closed recovery logic;
6. static architecture checks;
7. deterministic fixture/diagnostic tooling;
8. documentation synchronization.

Do not modify runner configuration merely to work around test availability.

## 7. Current known issues / unverified boundaries

- Current newer task-runtime work requires a fresh workflow result before it can be called a new green baseline.
- `create_empty_marker` remains the clean next materially distinct capability to live-prove through the generic task/runtime architecture.
- Historical live proofs do not automatically validate newer untested code.
- Production-facing continuation/resume still needs broader proof across multiple materially different Blender task types.
- The action runner is currently unavailable for user-approved validation, so new workflow-dependent claims must remain explicitly unverified.

## 8. Exact next steps when testing is authorized again

1. Inspect the final result of the already-existing **Atlas Tests #629** run before initiating anything else.
2. Inspect current `main` and reconcile the code baseline with the latest documented handoff.
3. Obtain a fresh fully green baseline for the current integrated code if required.
4. Live-prove `create_empty_marker` through the generic task/runtime architecture.
5. Preserve regressions for zero-write already-satisfied tasks, exact authorized action order, mandatory authorization, mandatory fresh verification, verification failure → `BLOCKED`, failed-action recovery, receipt mismatch, malformed executor output, wrong-tool output, continuation identity, authorized replan, unauthorized replan, duplicate-write prevention, and task-definition snapshot immutability.
6. Expand production-facing continuation/resume across multiple materially different Blender task types.
7. Promote the resulting loop as the next major Blender milestone only after fresh evidence supports it.

## 9. Immediate resume point

Until the user explicitly authorizes workflow testing, continue only with isolated offline-safe development and documentation. Do not start another workflow run, do not alter the action runner, and do not treat the existing runner limitation as permission to bypass the testing boundary.
