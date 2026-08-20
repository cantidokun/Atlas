# Atlas Current Development Handoff

**Updated:** August 20, 2026 19:41 EDT  
**Branch:** `main`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## 1. Current operating constraint

Atlas remains actively developed, but **workflow/action-runner testing is explicitly paused until the user authorizes it**. Do not trigger, rerun, approve, or otherwise initiate GitHub Actions/self-hosted-runner tests while this constraint is in effect. The local Windows runner `atlas-local` is the intended live-test environment, but its availability does not constitute permission to use it.

Offline-safe development may continue when it is isolated from runner configuration and cannot create system conflicts. Suitable work includes contracts, schemas, receipt/verification logic, authorization/replan boundaries, deterministic utilities, static checks, diagnostics, fixture tooling, and documentation.

## 2. Scope and authority model

This track is the **Blender Agent only**. Unreal Agent work is out of scope.

```text
Qwen / AI -> reason + propose
Python / Atlas -> validate -> authorize -> execute -> track -> verify -> recover
Blender -> production execution adapter
Atlas -> independent authoritative-state verification
```

Qwen is never execution authority. Blender execution success is never treated as proof of final state.

Photogrammetry is upstream: dedicated photogrammetry software creates the initial 3D reconstruction; Blender receives it for analysis, cleanup, correction, and preparation.

## 3. Generic architecture currently implemented

Core primitives and boundaries include:

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
- `AtlasTaskDefinition` — declarative task data boundary
- `planning/task_runtime.py` — runtime enforcement of task write/verification policy
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md` — promotion and authority contract

The intended closed loop is:

```text
Qwen proposal
 -> validated task/evidence/action structure
 -> authoritative Blender evidence
 -> target-state evaluation
 -> conditional decision
 -> authorization
 -> deterministic execution
 -> fresh independent verification
 -> immutable receipt
 -> completion / conservative recovery
```

`AtlasTaskDefinition` contains task-specific data only. Orchestration and execution-policy enforcement remain generic runtime concerns.

## 4. Concrete Blender/task files and tools

Execution/verification boundary:

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; includes `create_empty_marker`.
- `planning/blender_execution_boundary.py` — validated execution, `execute_verified()`, and receipt-bound single execution.
- `planning/blender_result_contract.py` — normalized immutable result contract.
- `planning/blender_verification.py` — requested-tool identity and successful-execution verification.
- `planning/blender_execution_receipt.py` — deterministic request/result receipt and mutation detection.
- `planning/verification_plan.py` — required/pending/complete/blocked verification state.
- `planning/task_definition.py` — declarative `AtlasTaskDefinition`.
- `planning/task_runtime.py` — runtime preparation/enforcement of task write and verification policy.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task/harness coverage includes conditional goalpost, collection creation/membership, parent relationships, object rotation, rename, delete, marker creation, verification-failure, continuation/resume, and deterministic fixture tooling.

## 5. Model/runtime setup

- Ollama API: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Intended local live-test runner: `atlas-local` on Windows
- Structured Qwen planning: `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, `qwen_planning_runtime.py`

Recent reliability work added bounded transient Ollama planning-timeout retry behavior within the existing planning budget and audit trail. Ollama is treated as dedicated Atlas infrastructure.

## 6. Tests and verification status

### Established historical baselines

- **Atlas Tests #401:** PASS on Python 3.9 and Python 3.11. This is a historical offline baseline and does not automatically validate later code changes.
- **Live Conditional Atlas Regression #155:** PASS across all four jobs:
  - live generic collection — incorrect: PASS
  - live generic collection — already-correct: PASS
  - live conditional — incorrect: PASS
  - live conditional — already-correct: PASS

Historical live proofs also cover materially different Blender behaviors including object rotation, object rename, object delete, collection creation/membership, parent relationships, goalpost correction, continuation/pause-resume, tampered continuation rejection, and adversarial verification failure -> `BLOCKED`.

### Newer work

The `AtlasTaskDefinition` / `planning/task_runtime.py` refinement and subsequent offline hardening are newer than the established #401 baseline. Do **not** claim a fresh green workflow result for these changes while runner testing is paused.

The last handoff noted an in-flight **Atlas Tests #629** run at setup/checkout stage. Its final result must be checked when workflow testing is explicitly resumed; do not infer success or failure from its existence.

## 7. Current architectural progress

Atlas has progressed beyond a single Blender-edit proof. The same control architecture has been demonstrated across materially different Blender operations:

- evidence acquisition and validation;
- conditional skip vs execute;
- mandatory authorization before writes;
- deterministic single execution;
- independent post-action verification;
- immutable receipt binding;
- fail-closed `BLOCKED` behavior;
- continuation identity/integrity checks;
- authorized vs unauthorized replanning.

The current focus is hardening and integration rather than inventing another bespoke orchestration path for each Blender operation.

## 8. Known issues / boundaries

- Fresh CI/workflow validation of the newest integrated code is unavailable by instruction until the user authorizes runner testing.
- `create_empty_marker` remains the clean next materially distinct live capability to prove once testing resumes.
- Newer task-runtime changes must not be represented as verified merely because older historical suites passed.
- Production-facing continuation/resume still needs broader proof across multiple materially different task types.
- Do not modify runner configuration merely to work around test availability.

## 9. Offline-safe development priorities while runner testing is paused

1. Deterministic task-contract validation.
2. Receipt immutability and mutation detection.
3. Malformed-result and wrong-tool rejection.
4. Authorization/replan boundary hardening.
5. Fail-closed recovery logic.
6. Static architecture checks that cannot start workflows.
7. Deterministic Blender fixture and diagnostic tooling.
8. Documentation synchronization.

Required regression cases to preserve include: already-satisfied -> zero writes; unsatisfied -> exact authorized action order; authorization mandatory before writes; successful write -> verification mandatory; failed verification -> `BLOCKED`; failed action -> recovery gate; mutated arguments/result -> receipt mismatch; malformed executor response -> rejected; wrong result tool -> rejected; invalid continuation identity -> rejected; authorized fresh-evidence replan -> accepted; unauthorized replan -> rejected; one receipt-bound execution cannot duplicate writes; write-capable task runtime requires post-action verification; task snapshots cannot mutate live task definitions.

## 10. Exact next steps when workflow testing is authorized again

1. Inspect the final result of the already-existing **Atlas Tests #629** run before starting any new run.
2. Inspect current `main` and the newest workflow state.
3. Obtain a fresh fully green baseline for the current integrated code.
4. Live-prove `create_empty_marker` through the generic task/runtime architecture.
5. Preserve explicit zero-write, single-write, authorization, verification-failure, receipt-integrity, and malformed-result regressions.
6. Expand production-facing continuation/resume across multiple materially different Blender task types.
7. Promote the resulting closed loop as the next major Blender milestone only when the evidence supports it.

## 11. Resume rule

**Do not resume workflow testing automatically.** The explicit user constraint is the controlling instruction. When the user authorizes testing, read this handoff first, inspect the existing #629 result, then continue from the current code state without repeating already-completed work.
