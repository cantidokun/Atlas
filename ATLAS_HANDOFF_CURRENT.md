# Atlas Current Development Handoff

**Updated:** August 17, 2026 19:42 UTC  
**Current branch:** `main`  
**Current HEAD:** `dc22780dbf2cf501f7ae598f42718a57666c36e5` — `fix: bind collection receipt to single execution`  
**Last fully live-verified Blender implementation milestone:** `09d165944b32dd5ee03100cff10a0d4b33481df3` — receipt binding. The newer collection/conditional work is offline-verified but its live regression is still queued.

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

Core planning/execution primitives currently present:

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

The conditional execution architecture explicitly separates:

1. evidence acquisition;
2. target-state evaluation;
3. conditional skip vs execute decision;
4. explicit authorization;
5. deterministic action execution;
6. fresh post-action verification;
7. fail-closed completion/blocking.

`VerificationPlan` is a first-class generic primitive. A successful write is not verification; fresh authoritative evidence must be evaluated against the explicit postcondition.

## 3. Blender-specific files and tools

Core Blender boundary:

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; snapshots mutable supported arguments. Supports `create_empty_marker` with exact arguments `file_name`, `collection_name`, and `object_name`.
- `planning/blender_execution_boundary.py` — validates calls before Blender execution; provides `execute_verified()` and receipt-bound execution. The receipt-bound path captures the normalized verified result from the same single executor call.
- `planning/blender_result_contract.py` — immutable `BlenderExecutionResult`; validates tool, boolean success, execution state, and details.
- `planning/blender_verification.py` — independently validates requested-tool identity and successful execution; fails closed on mismatches/failure.
- `planning/blender_execution_receipt.py` — deterministically binds validated tool + arguments + verified result; detects later mutation.
- `planning/verification_plan.py` — generic post-action verification state; exposes `required`, `pending`, `complete`, `blocked`, `verify()`, and `snapshot()`.
- `tools/blender.py` — Blender adapter containing scene inspection, relationship inspection, soccer-component candidate inspection, collection creation, marker creation, and goalpost movement.
- `tools/__init__.py` — tool registry including `create_empty_marker` and `move_object`.

Existing live goalpost harness:

- `live_qwen_conditional_loop.py`
- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`

Second-task/collection work:

- `planning/marker_task.py` — task-specific marker target invariant and `create_empty_marker` action definition. It deliberately contains task data/invariants only; it does not implement a second orchestration architecture.
- `tests/test_marker_conditional_task.py` — focused regression coverage for the second task.
- Live workflow jobs currently include `live generic collection (incorrect)`, `live generic collection (already-correct)`, `live conditional (incorrect)`, and `live conditional (already-correct)`.

The second task is **conditional creation of `Atlas_Marker` inside the `Atlas_Test` collection**, requiring the object to exist and be an `EMPTY`. Its action shape is intentionally different from goalpost movement: it has no `location` argument and performs object creation rather than transform mutation.

## 4. Current model/runtime setup

Live Qwen/Ollama/Blender runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Goalpost live tools currently exercised: `inspect_object_relationship`, `move_object`.
- Marker/collection live workflow integration has been added to the regression workflow, but it is not yet a fully live-proven production capability.

## 5. Verified milestones and test history

Blender receipt milestones:

- `788d311` — add immutable Blender execution receipt
- `909b0c4` — expose receipt-bound Blender execution
- `09d1659` — receipt regression coverage and binding of the Blender execution receipt to request/result

Goalpost live baseline:

- **Atlas Tests #385 — PASS** on Python 3.11 and 3.9.
- **Live Conditional Atlas Regression #142 — PASS**.
- Proven live behavior:

```text
already-correct -> target satisfied -> zero writes -> fresh verification -> complete
incorrect -> target unsatisfied -> authorized writes -> fresh verification -> complete
```

### Marker/collection development

Commit `265045211ff111d3ae4fc0f2a5b8bef1e1a172a2` introduced the marker schema, marker task, and initial tests.

- **Atlas Tests #392 — FAILED** on both Python 3.11 and 3.9: **377 passed, 3 failed**.
- The failures were test-design mismatches, not a generic orchestrator regression. The tests incorrectly assumed immediate `COMPLETE` after a satisfied evaluation, immediate `ACTION` after an unsatisfied evaluation, and execution without `ActionAuthorization`.
- The established state machine requires satisfied targets to enter `VERIFICATION`, unsatisfied targets to enter `AUTHORIZATION`, and writes to require exact action authorization.

The tests were corrected in:

- `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` — `fix: align marker task tests with authorization and verification phases`

That correction was validated:

- **Atlas Tests #393 — PASS**.
- **Atlas Tests #394 — PASS** on the subsequent documentation state.

Receipt execution was then tightened in:

- `dc22780dbf2cf501f7ae598f42718a57666c36e5` — `fix: bind collection receipt to single execution`

The change ensures the receipt is bound to the exact single executor result rather than creating a second execution path while validating the receipt.

Validation for that commit:

- **Atlas Tests #401 — PASS** on Python 3.11.
- **Atlas Tests #401 — PASS** on Python 3.9.

### Current live regression

- **Live Conditional Atlas Regression #155 — QUEUED** as of the latest check at 19:42 UTC.
- Run: `32053379722`.
- All four jobs are still waiting for the self-hosted/local runner:
  - `live generic collection (incorrect)`
  - `live generic collection (already-correct)`
  - `live conditional (incorrect)`
  - `live conditional (already-correct)`
- None of these jobs has executed yet, so **do not claim a new live collection/marker proof**.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: the exact validated request and independently verified result are deterministically bound, so later mutation is detectable.

What is **not yet live-proven** is a broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary.

## 7. Current known issues / boundaries

- Goalpost execution remains the only materially different Blender task with a complete live proof.
- The marker/collection architecture is offline/CI-proven but has not yet received a completed live proof.
- The live workflow has been extended for collection/conditional cases, but the self-hosted local runner is currently the gating point for **#155**.
- A successful executor response still cannot be treated as authoritative state; independent fresh scene evidence is mandatory.
- Broader continuation/resume behavior needs a production-facing live proof.
- Full unattended autonomous local production operation has not been declared complete.
- Do not add goalpost-specific branches to generic planning layers.
- Do not bypass explicit authorization or the mandatory verification phase.

## 8. Exact next development stage

1. Let **Live Conditional Atlas Regression #155** execute when the self-hosted runner becomes available.
2. Inspect all four live job logs/results rather than inferring success from queue completion.
3. If a live case fails, diagnose the actual runner/Blender/Qwen behavior and implement the smallest architecture-consistent fix; then rerun the affected regression.
4. If all four cases pass, record the first completed live proof for the second task.
5. Confirm the three important semantics explicitly:
   - already-correct -> zero writes;
   - incorrect -> explicit authorization -> exactly one creation/write -> fresh verification;
   - executor reports success but authoritative post-state is wrong -> verification fails -> `BLOCKED`.
6. Only after that live proof is green, select the next materially different Blender production capability.
7. Preserve the generic architecture and avoid task-specific branches in `PlanningOrchestrator`, `ConditionalPlanningOrchestrator`, authorization, deterministic future, or verification primitives.

Required second-task path:

```text
structured Qwen proposal
 -> exact Blender tool/argument validation
 -> authoritative scene evidence
 -> target-state evaluation
 -> conditional skip/create decision
 -> explicit ActionAuthorization
 -> deterministic future
 -> create_empty_marker / collection execution
 -> structured result
 -> fresh independent verification
 -> Blender execution receipt
 -> completion or BLOCKED
```

## 9. Required regression coverage to preserve

Continue proving:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
- authorization is mandatory before writes;
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

1. read this handoff;
2. inspect current `main` and the latest GitHub Actions state;
3. inspect actual logs before changing code if a test fails;
4. use **Atlas Tests #401 PASS / Python 3.9 + 3.11** as the current offline baseline;
5. resolve and inspect **Live Conditional Atlas Regression #155**;
6. do not mark the second task live-proven until its jobs actually execute and pass;
7. update this handoff with the actual live result;
8. then proceed to the next materially different Blender production capability.

**Immediate continuation point:** the receipt single-execution fix is green offline in CI; the remaining gating item is live regression **#155**, currently queued for the self-hosted runner.
