# Atlas Current Development Handoff

**Updated:** August 18, 2026 17:40 UTC  
**Current branch:** `main`  
**Current HEAD:** `d164ab34cfabe4e9ee16699148851184bb7fd924` — `fix: bind rotation execution to single orchestrated write`  
**Latest completed live regression:** `Live Conditional Atlas Regression #155` — all four jobs passed.

## 1. Scope and authority model

This track is **Blender Agent only**. Unreal Agent work is out of scope here.

Atlas authority model:

```text
Qwen / AI -> reason and propose
Python / Atlas -> validate -> authorize -> execute -> track -> verify -> recover
Blender -> execute production operations
Atlas -> independently verify resulting state
```

Qwen is never the execution authority. Blender is an execution adapter, not Atlas's canonical source of truth.

Photogrammetry is upstream: dedicated photogrammetry software produces the initial reconstruction; Blender receives it for analysis, cleanup, correction, and preparation.

## 2. Current generic architecture

Core planning/execution primitives present:

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
- runtime context fingerprinting and integrity checks
- audit trail
- immutable Blender execution receipts

Conditional execution explicitly separates evidence acquisition, target-state evaluation, skip/execute decision, explicit authorization, deterministic action execution, fresh post-action verification, and fail-closed completion/blocking.

`VerificationPlan` is first-class. A successful write is not verification; fresh authoritative evidence must be evaluated against the explicit postcondition.

## 3. Blender-specific files and tools

Core Blender boundary:

- `planning/blender_tool_schema.py` — validates supported tools, required arguments, types, and 3D coordinates; supports `create_empty_marker` with `file_name`, `collection_name`, `object_name`.
- `planning/blender_execution_boundary.py` — validates calls before Blender execution; provides `execute_verified()` and receipt-bound execution. Receipt-bound execution captures the verified result from the same single executor call.
- `planning/blender_result_contract.py` — immutable `BlenderExecutionResult` and normalized result contract.
- `planning/blender_verification.py` — validates requested-tool identity and successful execution; fails closed on mismatches/failure.
- `planning/blender_execution_receipt.py` — deterministically binds validated tool + arguments + verified result and detects mutation.
- `planning/verification_plan.py` — generic post-action verification state with `required`, `pending`, `complete`, `blocked`, `verify()`, and `snapshot()`.
- `tools/blender.py` — scene inspection, relationship inspection, soccer-component inspection, collection creation, marker creation, and goalpost movement.
- `tools/blender_transform.py` — object transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

Task definitions / harnesses:

- `planning/marker_task.py` — `Atlas_Marker` / `EMPTY` target and `create_empty_marker` action definition.
- `planning/object_rotation_task.py` — `Atlas_Rotation_Candidate` target and required rotation `[0.0, 0.0, 90.0]`.
- `tests/test_marker_conditional_task.py` — marker conditional regression coverage.
- `live_qwen_conditional_loop.py` — live conditional goalpost harness.
- `live_qwen_collection_task.py` — live generic collection task harness.
- `live_qwen_object_rotation.py` — live Qwen object-rotation harness.
- `scripts/provision_collection_task_fixtures.py` — deterministic collection fixture provisioning.
- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`
- `collection_task_CORRECT.blend`
- `collection_task_INCORRECT.blend`
- `object_rotation_CORRECT.blend`
- `object_rotation_INCORRECT.blend`

The collection task is conditional creation of `Atlas_Test` using `inspect_scene` + `create_collection`. It is materially different from goalpost transform mutation and is live-proven.

The marker task is a separate creation task and is offline/CI-proven but not yet live-proven.

The object-rotation task is the current next materially different transform capability. Its harness constrains Qwen to `inspect_object_transform` and `set_object_rotation`, uses `ConditionalPlanningOrchestrator`, `VerificationPlan`, `ActionAuthorization`, and `BlenderExecutionBoundary.execute_with_receipt()`, and requires exactly one evidence request and one action.

## 4. Current model/runtime setup

Live Qwen/Ollama/Blender runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender on the local runner: **4.4.3**
- Local GitHub Actions runner: `atlas-local`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Goalpost live tools: `inspect_object_relationship`, `move_object`.
- Collection live tools: `inspect_scene`, `create_collection`.
- Rotation live tools: `inspect_object_transform`, `set_object_rotation`.

## 5. Verified milestones and test history

Blender receipt milestones:

- `788d311` — add immutable Blender execution receipt
- `909b0c4` — expose receipt-bound Blender execution
- `09d1659` — receipt regression coverage and binding of receipt to request/result

Goalpost baseline:

- **Atlas Tests #385 — PASS** on Python 3.11 and 3.9.
- **Live Conditional Atlas Regression #142 — PASS**.
- Proven: already-correct -> zero writes -> verification -> complete; incorrect -> authorized write -> verification -> complete.

Marker / collection development:

- `265045211ff111d3ae4fc0f2a5b8bef1e1a172a2` introduced marker schema/task/tests.
- **Atlas Tests #392 — FAILED**, 377 passed / 3 failed on both Python versions. Failures were test-contract mismatches, not generic architecture regressions.
- `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` aligned marker tests with the authorization and verification phases.
- **Atlas Tests #393 — PASS** and **#394 — PASS**.
- `dc22780dbf2cf501f7ae598f42718a57666c36e5` bound collection receipt handling to the exact single execution.
- **Atlas Tests #401 — PASS** on Python 3.11 and 3.9.

### Live Conditional Atlas Regression #155 — PASS

Run `32053379722` completed successfully on `atlas-local`.

All four jobs passed:

- `live generic collection (incorrect)` — **PASS**
- `live generic collection (already-correct)` — **PASS**
- `live conditional (incorrect)` — **PASS**
- `live conditional (already-correct)` — **PASS**

The collection incorrect case demonstrated:

```text
Qwen proposal
-> authoritative evidence
-> target_satisfied: false
-> authorization: action_count 1
-> create_collection success
-> receipt bound to that execution
-> fresh verification: Atlas_Test present
-> PASS
```

The already-correct path demonstrated zero writes and successful verification.

Important boundary: the two `live conditional` jobs in #155 are the goalpost conditional harness. The second-task live proof is specifically the `live generic collection` pair.

### Current rotation stage

`d164ab34cfabe4e9ee16699148851184bb7fd924` changed `live_qwen_object_rotation.py` so the rotation action is executed exactly once through `BlenderExecutionBoundary`, with the receipt captured from that same execution and matched against the authorized action/result. It also validates the plan shape as exactly one evidence request and one action.

`planning/object_rotation_task.py` defines `Atlas_Rotation_Candidate` with required rotation `[0.0, 0.0, 90.0]`. `tools/blender_transform.py` validates finite three-axis rotation input, inspects authoritative transform state, and mutates/saves the Blender file only when the target rotation is not already present.

`live_qwen_object_rotation.py` constrains Qwen through `TASK_PLAN_JSON_SCHEMA`, allows only `inspect_object_transform` and `set_object_rotation`, requires exactly one evidence request and one action, authorizes the mutation explicitly, binds the single execution receipt, and performs fresh independent verification.

A fresh GitHub workflow lookup for `d164ab34cfabe4e9ee16699148851184bb7fd924` was performed on August 18, 2026 and returns **no workflow runs**. Therefore no newer CI/live result is being claimed for that HEAD. The last completed offline baseline remains **Atlas Tests #401 — PASS**; #401 predates the rotation commit.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: exact validated request + independently verified result are deterministically bound, so later mutation is detectable.

A broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary is still not live-proven.

## 7. Current known issues / boundaries

- Goalpost and generic collection creation are live-proven.
- Marker creation (`planning/marker_task.py`, `create_empty_marker`) is offline/CI-proven but not live-proven.
- Object rotation is implemented with receipt-bound single execution but is not yet live-proven on the current HEAD.
- Current HEAD `d164ab34` has no fresh workflow-run result in the available GitHub status surface as of August 18, 2026.
- Generic collection proof is a focused harness; it does not prove arbitrary task generation or arbitrary Blender production planning.
- Executor success is never authoritative state; fresh scene evidence remains mandatory.
- Broader continuation/resume needs a production-facing live proof.
- Full unattended autonomous local production operation is not declared complete.
- Do not add goalpost/collection/rotation-specific branches to generic planners.
- Do not bypass explicit authorization or mandatory verification.

## 8. Exact next development stage

1. Obtain fresh CI validation for current HEAD `d164ab34`; if the normal workflow is not automatically triggered, trigger it through the repository's established workflow path rather than assuming the old #401 result covers this commit.
2. Live-test `live_qwen_object_rotation.py` on `object_rotation_CORRECT.blend` and `object_rotation_INCORRECT.blend`.
3. Require both rotation cases to prove zero-write behavior, explicit authorization for mutation, exactly one `set_object_rotation` call, receipt binding, and fresh independent verification.
4. Add the collection false-success live case: executor reports success while authoritative post-state remains wrong; require `VerificationPlan` -> `BLOCKED`.
5. Add the collection already-correct live case with an explicit audit assertion that no creation call occurred if that assertion is not already captured by the harness.
6. Then live-prove `create_empty_marker` using `planning/marker_task.py` and `create_empty_marker`.
7. After multiple distinct mutation/creation capabilities are live-proven, build a broader production-facing continuation/resume scenario using runtime fingerprinting, deterministic future, recovery gate, and receipt integrity.
8. Only then select the next materially different Blender production capability.

Required current rotation path:

```text
structured Qwen proposal
 -> exact tool/argument validation
 -> authoritative transform evidence
 -> target-state evaluation
 -> conditional execute decision
 -> explicit ActionAuthorization
 -> deterministic execution
 -> one set_object_rotation call
 -> receipt bound to that result
 -> fresh transform verification
 -> completion
```

Required failure behavior remains:

```text
executor claims success
 -> authoritative post-state remains wrong
 -> VerificationPlan = BLOCKED
 -> no false completion
```

## 9. Required regression coverage to preserve

Continue proving:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
- authorization mandatory before writes;
- successful write -> verification remains mandatory;
- failed verification -> `BLOCKED`;
- failed action -> recovery gate;
- mutated arguments -> receipt mismatch;
- mutated result -> receipt mismatch;
- malformed executor response -> rejected;
- wrong result tool -> rejected;
- invalid resume/continuation identity -> rejected;
- authorized replan from fresh evidence -> accepted;
- unauthorized replan -> rejected;
- receipt is bound to one execution and cannot cause a duplicate write.

## 10. Resume instructions

On the next development session:

1. Read this handoff.
2. Inspect `main` and latest GitHub Actions state.
3. Use **Atlas Tests #401 PASS / Python 3.9 + 3.11** as the last completed offline baseline, but do not assume it validates `d164ab34`; obtain fresh CI first.
4. Use **Live Conditional Atlas Regression #155 PASS** as the current live collection/goalpost baseline.
5. Inspect actual logs before changing code if current rotation CI/live tests fail.
6. Prove object rotation live on both deterministic fixtures.
7. Then prove collection false-success -> `BLOCKED` and explicit zero-write behavior.
8. Then live-prove `create_empty_marker`.
9. Update this handoff with actual results before moving to another capability.
10. Do not declare broader autonomous production operation complete until continuation/resume has a real live proof.

**Immediate continuation point:** `d164ab34` has advanced Atlas to a third materially different task, object rotation, with receipt-bound single execution implemented but not yet live-proven. The August 18, 2026 repository check confirms no newer workflow run is attached to that commit. The next required action is to obtain fresh CI validation for the current HEAD and then run both deterministic rotation cases. The collection live proof from #155 remains the baseline, and marker/continuation proofs remain outstanding.
