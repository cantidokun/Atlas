# Atlas Current Development Handoff

**Updated:** August 17, 2026 02:39 UTC
**Current branch:** `main`
**Current HEAD:** `4661dc4301a1902b40073d4d22b8175bfa0923fd`
**HEAD message:** `test: enforce autonomous runtime integrity boundary`

## 1. Project and architectural direction

Atlas is an AI-assisted sports virtual production and digital-twin platform. Blender is the first proven execution environment; Unreal Engine is a planned complementary production environment.

The intended production pipeline is:

`captured sports footage / real-world environment -> dedicated photogrammetry software -> initial 3D reconstruction -> Blender Agent -> analysis / cleanup / correction / optimization -> prepared digital twin -> Unreal Agent -> real-time production / VFX -> independent Atlas verification`

Photogrammetry is an upstream reconstruction capability. It is not a responsibility of the Blender Agent. The photogrammetry-to-Blender boundary is a future intake/output contract and is not yet implemented.

The control principle is:

`Qwen / AI -> reason and propose`

`Python / Atlas -> validate, authorize, execute, track state, verify, recover`

`Production tools -> execute`

`Independent verification -> confirm actual resulting state`

The orchestration layer must remain production-tool-agnostic. The goalpost task is a proof fixture, not the generic architecture.

## 2. Verified runtime

### Local runtime

- Python `3.9.6`
- Ollama `0.32.13`
- Model `qwen3:8b`
- Blender `4.4`
- Blender executable: `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`
- Ollama endpoint: `http://localhost:11434/api/chat`

### CI runtime

GitHub Actions regression matrix:

- Python `3.11`
- Python `3.9`

Latest CI run checked:

- Atlas Tests run `#266`
- HEAD `4661dc4301a1902b40073d4d22b8175bfa0923fd`
- Python 3.11: **201 passed**
- Python 3.9: **PASS**

The 3.11 job log explicitly reports `201 passed in 0.42s`.

A separate live workflow is currently present:

- `Live Conditional Atlas Regression`
- run `#86`
- HEAD `4661dc4301a1902b40073d4d22b8175bfa0923fd`
- status at this handoff update: **waiting**

That live workflow result is not yet a pass/fail and must not be treated as proven until it completes.

## 3. Core planning and execution architecture

### Existing controller layer

- `controller_state.py` — controller-owned BEFORE/TARGET/WRITE/AFTER/COMPLETE state and target calculations.
- `controller_runtime.py` — one mandatory controller action at a time; ordering is not delegated to Qwen.
- `controller_bridge.py` — bridges controller state and the existing agent.
- `controller_execution_adapter.py` — mirrors controller-owned results into normal tool history/evidence.
- `controller_integration.py` — integration boundary between agent and controller.
- `run_agent_with_controller.py` — live compatibility entrypoint.
- `controller_finalization.py` — deterministic final report generation from verified evidence.

### Generic planning primitives

- `action_plan.py`
  - `ActionSpec` represents one ordered action.
  - `ActionPlan` exposes the next action, records results, advances only after success, blocks on required failure, and snapshots state.

- `evidence_plan.py`
  - ordered evidence requests, completion, reuse, and blocking failures.

- `planning/target_state.py`
  - `StateInvariant` and `TargetStateEvaluator`.
  - explicit satisfied/failed invariants and snapshots.

- `planning/verification_plan.py`
  - generic post-action verification.
  - write success is never proof of final state.
  - fresh evidence must be evaluated against explicit postconditions.
  - failed verification fails closed.

- `planning/planning_orchestrator.py`
  - `PlanningOrchestrator` for generic evidence -> action flow.
  - `ConditionalPlanningOrchestrator` for evidence -> target evaluation -> conditional execution -> independent verification -> completion.
  - explicit phases include `EVIDENCE`, `TARGET_EVALUATION`, `AUTHORIZATION`, `ACTION`, `VERIFICATION`, `COMPLETE`, `BLOCKED`, and `RECOVERY_REPLAN`.
  - integrates deterministic futures, action authorization, recovery, and replanning.

### Authorization and tool-boundary controls

- `planning/action_authorization.py`
  - immutable `ActionAuthorization` receipt.
  - binds the exact authorized action list to a digest and authorization ID.

- `planning/replan_authorization.py`
  - immutable `ReplanAuthorization` receipt.
  - binds fresh evidence and the exact replacement action list by digest.

- `task_plan_authorization.py`
  - explicit authorization boundary for model-proposed plans and write tools.

- `planning/tool_schema.py`
  - strict schemas for admitted tools including `inspect_scene`, `inspect_object_relationship`, `move_object`, and `create_collection`.
  - rejects unknown and missing arguments and validates types/finite 3D locations.

- `qwen/structured_plan.py`
  - shared Ollama JSON-schema constraint for task-plan proposals.
  - requires exactly the `evidence` and `actions` arrays and exact item shape.

- `qwen_planning_runtime.py`
  - parses and validates Qwen structured plans.

### Deterministic future and recovery architecture

- `planning/future_generator.py`
  - `DeterministicFutureGenerator` derives the only legal future implied by an already-authorized action list and resolved target state.
  - no model reasoning and no tool execution occur here.
  - target satisfied -> `SKIP_WRITES` -> `VERIFICATION` -> `COMPLETE`.
  - target unsatisfied -> ordered authorized actions -> `VERIFICATION` -> `COMPLETE`.

- `planning/future_execution.py`
  - `FutureExecutionController` owns the execution cursor.
  - prevents skipping, reordering, or inventing steps.
  - computes a plan digest and detects future mutation.
  - supports validated resume from a serialized snapshot.
  - only successful actions advance the cursor.
  - verification must be positive before completion can be finalized.

- `planning/future_recovery.py`
  - `FutureRecoveryGate` classifies deterministic-future failures.
  - no automatic retry.
  - action failure -> fresh authoritative evidence first.
  - verification failure -> fresh evidence and a new authorized plan.
  - terminal/ambiguous failure -> abort/fail closed.

### Runtime identity / continuation integrity

- `planning/runtime_context.py`
  - separates cacheable/stable instructions from authoritative dynamic state.
  - stable instructions receive a deterministic SHA-256 fingerprint.
  - live observation, plan digest, current step, and runtime state remain dynamic.

- `planning/model_request.py`
  - assembles model requests while preserving the stable/dynamic boundary.

- `planning/runtime_integrity.py`
  - `RuntimeIntegrity` binds continuation to three identities:
    1. stable instruction fingerprint
    2. authorized plan digest
    3. authoritative persisted-state digest
  - `require_continuation_integrity()` fails closed if any identity changes.
  - missing authoritative digests cannot be authorized.

The latest HEAD specifically adds regression coverage for this runtime integrity boundary.

### Audit/runtime bridge

- `audit_trail.py` — records proposal, evidence, authorization, execution, and verification order.
- `live_qwen_planning_loop.py` — live Qwen -> Python structured planning bridge.
- `live_qwen_conditional_loop.py` — live conditional Blender harness using the generic orchestrator and generic `VerificationPlan`.

## 4. Live conditional Blender proof

The live conditional harness is `live_qwen_conditional_loop.py`.

Runtime/model:

- Ollama: `http://localhost:11434/api/chat`
- model: `qwen3:8b`
- response constrained with `TASK_PLAN_JSON_SCHEMA`
- maximum plan attempts: `3`

Allowed tools in the harness:

- `inspect_object_relationship`
- `move_object`

Fixtures:

- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`

Target state:

- `Goal_Left_post = [0.0, 5.233, 0.0]`
- `Goal_Right_Post = [0.0, -5.233, 0.0]`
- midpoint `[0.0, 0.0, 0.0]`
- distance `10.466`
- symmetric about origin

The incorrect fixture was made deterministic so it cannot accidentally inherit an already-correct base state.

Historical live proof after those fixes:

- Run `#29` — `already-correct`: **PASS**
- Run `#30` — `incorrect`: **PASS**

Those tests proved:

1. already-correct -> target state satisfied -> writes skipped;
2. incorrect -> target state unsatisfied -> authorized writes execute -> final state independently verified.

The live harness has since been upgraded so the final inspection is passed through the generic `VerificationPlan` rather than a goalpost-specific final-verification shortcut.

## 5. Generic verification proof

`tests/test_verification_plan.py` currently covers:

- successful action enters `VERIFICATION` rather than `COMPLETE`;
- successful write does not count as verification;
- failed post-action verification blocks the orchestrator;
- already-correct state skips writes but still requires fresh verification before completion;
- standalone verification failure fails closed.

A previous test initially expected verification failure to raise immediately. That expectation was corrected to match the intended state-machine contract: verification returns an unsatisfied result and the orchestrator becomes `BLOCKED`.

The generic verification architecture is now integrated into `live_qwen_conditional_loop.py`.

## 6. Tool/schema validation proof

`planning/tool_schema.py` and `tests/test_tool_schema.py` cover:

- generic `create_collection` arguments;
- `move_object` with arbitrary object names, proving the schema is not goalpost-specific;
- rejection of unknown arguments;
- rejection of missing arguments.

This boundary exists because earlier live experimentation exposed malformed Qwen tool-argument structures reaching the executor boundary. The architectural response was to make tool argument validation explicit before execution.

## 7. Runtime context and integrity proof

Current tests include:

- `tests/test_runtime_context.py`
- `tests/test_runtime_context_fingerprint.py`
- `tests/test_model_request.py`
- `tests/test_runtime_integrity.py`

`tests/test_runtime_integrity.py` verifies:

- matching stable context + plan digest + state digest permits continuation;
- changed stable instructions fail closed;
- changed plan digest fails closed;
- changed persisted-state digest fails closed;
- missing authoritative digests cannot be authorized.

The latest HEAD commit is:

`4661dc4301a1902b40073d4d22b8175bfa0923fd`

`test: enforce autonomous runtime integrity boundary`

It adds `tests/test_runtime_integrity.py`.

## 8. Resume / mutation integrity proof

`tests/test_future_execution_resume.py` covers:

- exact plan digest required for resume;
- changed action plan rejected;
- tampered history rejected;
- valid resume continues from the exact authorized checkpoint without reordering or reauthorizing the existing future.

This complements `FutureExecutionController`'s internal plan digest check.

## 9. Audit and recovery model

The intended execution lifecycle is:

`Qwen proposal -> schema validation -> authoritative evidence -> target-state evaluation -> authorization -> deterministic future -> execution -> independent verification -> completion`

Failure lifecycle:

`action/verification failure -> BLOCKED -> fresh authoritative evidence -> explicit recovery decision -> new plan -> independent re-authorization -> new deterministic future`

Automatic retry is prohibited. A failure cannot silently alter the existing authorized future.

## 10. Current regression status

Latest completed CI run inspected:

- workflow: `Atlas Tests`
- run `#266`
- commit: `4661dc4301a1902b40073d4d22b8175bfa0923fd`
- Python 3.11: **201 passed in 0.42s**
- Python 3.9: **PASS**

The latest live conditional regression workflow is separate:

- workflow: `Live Conditional Atlas Regression`
- run `#86`
- same HEAD commit
- status when this handoff was generated: **waiting**

Do not treat the waiting live workflow as a pass. Its completion must be checked before the current live-integrity milestone is declared fully green.

## 11. Current known issues / boundaries

1. Qwen is still a proposal source, never an execution authority.
2. The structured-plan schema validates plan shape and the tool schema validates tool arguments, but semantic correctness of a proposed task still depends on the target-state and authorization layers.
3. The goalpost task is the primary live end-to-end proof. The generic primitives are broader, but arbitrary production tasks have not yet been proven live.
4. Recovery/replanning primitives are implemented and regression-tested, but broad live end-to-end recovery across arbitrary Blender failures still needs dedicated integration coverage.
5. CI is offline Python regression testing. It does not replace the local Ollama + Qwen + Blender live environment.
6. Full unattended local autonomous operation is not yet the declared milestone. Human-triggered/local harness execution remains part of the current proof protocol.
7. Dedicated photogrammetry integration is not implemented. The intake/output contract and downstream Blender cleanup/optimization workflow still need design.
8. Unreal Engine execution is planned, not implemented.
9. The latest live regression run `#86` is waiting and therefore the newest runtime-integrity change still needs live confirmation.

## 12. Exact next steps to resume development

### Step 1 — finish the newest live integrity regression

Wait for `Live Conditional Atlas Regression #86` to complete against HEAD `4661dc4301a1902b40073d4d22b8175bfa0923fd`.

If it fails, diagnose and fix the runtime-integrity boundary before proceeding.

If it passes, record the live result as the next verified milestone.

### Step 2 — generalize beyond the goalpost

Build a second live Blender task with different invariants and a different action shape. Reuse the existing generic primitives rather than adding another goalpost-specific branch.

Required flow:

`structured proposal -> exact tool/argument validation -> authoritative evidence -> target evaluation -> conditional decision -> authorization -> deterministic future -> execution -> fresh verification -> completion`

### Step 3 — expand generic conditional regression coverage

Ensure regression coverage includes:

- already satisfied -> zero writes;
- unsatisfied -> all authorized actions in exact order;
- successful action -> verification still required;
- verification failure -> BLOCKED;
- action failure -> recovery gate;
- mutated future -> integrity failure;
- invalid resume snapshot -> rejected;
- unauthorized replan -> rejected;
- authorized replan matching fresh evidence -> accepted;
- stable-context/plan/state identity change -> continuation rejected.

### Step 4 — make the runtime integrity boundary part of actual continuation

The new `RuntimeContext` / `RuntimeIntegrity` primitives currently have direct regression coverage. The next architectural step is to ensure the same identity check is invoked at every real autonomous continuation/resume boundary, not merely tested as an isolated primitive.

### Step 5 — then begin broader autonomous task control

Once a second non-goalpost live task passes, the next milestone should be reusable autonomous task composition across production operations. Qwen should continue to decide and propose; Python should continue to own validation, authorization, deterministic continuation, execution, verification, and recovery.

## 13. Photogrammetry future boundary

Do not implement photogrammetry integration yet merely to reserve the architecture.

When production requirements are ready, define:

- photogrammetry output contract;
- file/scene interchange contract into Blender;
- reconstruction metadata and provenance;
- Blender intake evidence requirements;
- Blender cleanup/correction/optimization responsibilities;
- validation criteria for downstream readiness;
- handoff contract to the Unreal Agent.

Photogrammetry remains upstream of the Blender Agent.

## 14. Resume rule

When continuing Atlas development, start from the repository's current `main` HEAD rather than relying on an older conversational milestone. Treat `ATLAS_HANDOFF_CONTEXT.txt` as historical context and this file as the current concise handoff. Verify current GitHub Actions state before claiming a milestone is green.
