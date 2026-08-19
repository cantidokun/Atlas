# Atlas Current Development Handoff

**Updated:** August 19, 2026 20:40 UTC  
**Branch:** `main`  
**Current HEAD:** `3d4c78f909bca3d08213d13e988feccd88d1a616` — `docs: define generic Atlas architecture contract`

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

## 2. Current development constraint

**Do not run, trigger, rerun, or approve any workflow/action-runner tests until the user explicitly authorizes them.** The local action runner cannot currently be set up.

Until authorization is given, development must remain isolated from the action runner and must not introduce changes whose validation depends on the runner. Prefer architecture, schemas, task contracts, deterministic utilities, receipt/verification logic, validation/error handling, documentation, and other offline-safe tooling. Treat all such newer work as **unverified** unless an already-completed test result explicitly covers it.

This constraint supersedes the normal next-step instruction to obtain fresh CI. The next resume point after the user authorizes workflow testing is to validate the accumulated offline-safe changes first.

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
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md` — explicit promotion/authority contract for production-task adapters

Conditional execution remains explicitly separated into evidence acquisition, target evaluation, skip/execute decision, authorization, deterministic execution, fresh verification, and fail-closed completion/blocking.

`VerificationPlan` is first-class: successful execution is never treated as proof of resulting state.

`AtlasTaskDefinition` contains task data only; orchestration logic must remain generic.

## 4. Blender files/tools

Core boundary:

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; includes `create_empty_marker`.
- `planning/blender_execution_boundary.py` — validated execution, `execute_verified()`, and receipt-bound single execution.
- `planning/blender_result_contract.py` — normalized immutable result contract.
- `planning/blender_verification.py` — requested-tool identity and successful-execution verification.
- `planning/blender_execution_receipt.py` — deterministic request/result receipt and mutation detection.
- `planning/verification_plan.py` — required/pending/complete/blocked verification state.
- `planning/task_definition.py` — `AtlasTaskDefinition` declarative task boundary.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task/harness files:

- `planning/marker_task.py`
- `planning/object_rotation_task.py`
- `tests/test_marker_conditional_task.py`
- `tests/test_task_definition.py`
- `tests/test_task_definition_immutability.py`
- `live_qwen_conditional_loop.py`
- `live_qwen_collection_task.py`
- `live_qwen_object_rotation.py`
- `scripts/provision_collection_task_fixtures.py`
- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`
- `collection_task_CORRECT.blend`
- `collection_task_INCORRECT.blend`
- `object_rotation_CORRECT.blend`
- `object_rotation_INCORRECT.blend`

Live Blender tools currently include `inspect_object_relationship`, `move_object`, `inspect_scene`, `create_collection`, `inspect_object_transform`, and `set_object_rotation`. Schema support also includes `create_empty_marker`.

## 5. Model/runtime

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Local GitHub Actions runner: `atlas-local` (currently unavailable for approved testing)
- Qwen structured planning uses `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, and `qwen_planning_runtime.py`.

## 6. Verified milestones

Blender receipt milestones:

- `788d311` — immutable execution receipt
- `909b0c4` — receipt-bound execution exposure
- `09d1659` — receipt regression/binding coverage

Goalpost baseline:

- **Atlas Tests #385 — PASS** on Python 3.11 and 3.9.
- **Live Conditional Atlas Regression #142 — PASS**.
- Proven: already-correct -> zero writes -> verification -> complete; incorrect -> authorized write -> verification -> complete.

Collection/marker development:

- Marker schema/task introduced by `265045211ff111d3ae4fc0f2a5b8bef1e1a172a2`.
- **Atlas Tests #392 — FAILED**, 377 passed / 3 failed on both Python versions; failures were test-contract mismatches.
- `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` corrected those contracts.
- **Atlas Tests #393 — PASS** and **#394 — PASS**.
- `dc22780dbf2cf501f7ae598f42718a57666c36e5` bound collection receipts to the exact single execution.
- **Atlas Tests #401 — PASS** on Python 3.11 and 3.9.

### Live Conditional Atlas Regression #155 — PASS

Run `32053379722` passed all four jobs:

- `live generic collection (incorrect)` — **PASS**
- `live generic collection (already-correct)` — **PASS**
- `live conditional (incorrect)` — **PASS**
- `live conditional (already-correct)` — **PASS**

The generic collection incorrect case proved:

```text
Qwen proposal -> authoritative evidence -> target false
-> authorization -> one create_collection execution
-> receipt bound to that execution -> fresh verification -> PASS
```

The already-correct path proved zero writes and successful verification.

### Object rotation

`d164ab34cfabe4e9ee16699148851184bb7fd924` added the receipt-bound object-rotation path. `planning/object_rotation_task.py` defines `Atlas_Rotation_Candidate` and required rotation `[0.0, 0.0, 90.0]`. `tools/blender_transform.py` validates finite 3-axis rotation input and performs authoritative transform inspection/mutation. `live_qwen_object_rotation.py` constrains Qwen to `inspect_object_transform` and `set_object_rotation`, requires exactly one evidence request and one action, authorizes the mutation, binds the single execution receipt, and performs fresh verification.

A fresh lookup for `d164ab34` returned **no workflow runs**, so object rotation is implemented but not CI/live-proven on that commit.

### Declarative task-definition layer

`planning/task_definition.py` adds `AtlasTaskDefinition` with:

- task name
- evidence requests
- action specifications
- target evaluator
- allowed action tools
- explicit write policy
- mandatory verification for write-capable tasks
- task snapshot metadata

`tests/test_task_definition.py` covers malformed structure, unauthorized tools, write-without-verification, and snapshot behavior.

`tests/test_task_definition_immutability.py` covers frozen top-level task identity and protection of task state from mutation through returned snapshots.

`docs/ATLAS_ARCHITECTURE_CONTRACT.md` now defines the generic task promotion contract, authority boundaries, zero-write rule, receipt rule, fail-closed rule, and current proof levels.

**Verification boundary:** `Atlas Tests #401` is the last completed offline baseline, and `Live Conditional Atlas Regression #155` is the last completed live baseline. The newer task-definition/architecture-contract/rotation work has not been validated by a fresh workflow run. No workflow tests are to be run until explicit user authorization.

## 7. Runtime integrity / continuation

Atlas has runtime identity checks binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Invalid continuation must fail closed. Blender receipts additionally bind the exact validated request to the verified result from one execution and detect later mutation.

A broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary is still not live-proven.

## 8. Known issues / boundaries

- Goalpost and generic collection creation are live-proven.
- Marker creation (`planning/marker_task.py`, `create_empty_marker`) is offline/CI-proven but not live-proven.
- Object rotation is implemented but not live-proven.
- `AtlasTaskDefinition` and its immutability tests are newer than the last completed CI baseline.
- The architecture contract is documentation-only and is not a substitute for CI/live proof.
- Current newer code must receive fresh CI after workflow testing is authorized before it is treated as verified.
- Generic collection proof does not prove arbitrary task generation or arbitrary Blender production planning.
- Executor success is never authoritative state; fresh evidence remains mandatory.
- Broader continuation/resume remains unproven live.
- Full unattended autonomous local production operation is not declared complete.
- Do not add task-specific branches to generic planners or bypass authorization/verification.

## 9. Offline-safe development allowed while runner is unavailable

Continue work that does not require workflow execution, including:

- strengthen `AtlasTaskDefinition` and its validation/immutability contract
- improve Blender tool schemas and normalized result contracts
- harden receipt binding and mutation detection
- expand pure unit/regression coverage locally in ways that do not trigger workflow runs
- improve authorization/replan validation
- strengthen runtime-context fingerprinting and continuation guards
- improve deterministic future/recovery abstractions
- add static architecture checks preventing task-specific logic from leaking into generic planners
- improve audit/event structures and diagnostics
- maintain deterministic fixture generation without running the action runner
- update documentation and handoff material

Avoid changes to workflow definitions, runner orchestration, or live harness behavior unless there is a concrete architectural need; those changes should remain reviewable and explicitly unverified until workflow testing is authorized.

## 10. Exact next steps after workflow testing is authorized

1. Run fresh CI validation for the accumulated current `main` changes, including `planning/task_definition.py`, `tests/test_task_definition.py`, `tests/test_task_definition_immutability.py`, and any intervening offline-safe changes.
2. Fix any CI/import/contract issues before live work.
3. Integrate `AtlasTaskDefinition` into one existing adapter using the smallest safe candidate; keep orchestration generic.
4. Live-test `live_qwen_object_rotation.py` on `object_rotation_CORRECT.blend` and `object_rotation_INCORRECT.blend`.
5. Require both rotation cases to prove zero-write behavior, explicit authorization, exactly one `set_object_rotation`, receipt binding, and fresh independent verification.
6. Add collection false-success live proof: executor reports success while authoritative post-state is wrong -> `VerificationPlan` **BLOCKED**.
7. Add/retain an explicit audit assertion that already-correct collection performs zero creation calls.
8. Live-prove `create_empty_marker` with `planning/marker_task.py`.
9. After multiple distinct capabilities are live-proven, build a production-facing continuation/resume scenario using runtime fingerprinting, deterministic future, recovery gate, and receipt integrity.
10. Only then select the next materially different Blender production capability.

## 11. Required regression coverage

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

## 12. Resume instructions

Read this file first. Inspect `main` and current repository state. Use **Atlas Tests #401 PASS (Python 3.9 + 3.11)** only as the last completed offline baseline and **Live Conditional Atlas Regression #155 PASS** as the live collection/goalpost baseline. Do not treat either as validation of the newer task-definition/rotation/architecture-contract work.

**Do not run workflow/action-runner tests until the user explicitly authorizes them.** While that constraint remains active, continue only with isolated offline-safe development. Once authorized, the immediate continuation point is fresh CI validation of the accumulated changes, followed by the smallest safe task-definition integration and live object-rotation proof.
