# Atlas Current Development Handoff

**Updated:** August 17, 2026 14:43 UTC
**Current branch:** `main`
**Current HEAD:** `0ae2ad371ce0e1f2a0ce601ddb97915f19b3a8d0` — `docs: refresh Atlas handoff for second Blender task`
**Last verified Blender implementation milestone:** `09d165944b32dd5ee03100cff10a0d4b33481df3` — receipt binding remains the last fully live-verified Blender implementation milestone.

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

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; snapshots mutable supported arguments. It now supports `create_empty_marker` with exact arguments `file_name`, `collection_name`, and `object_name`.
- `planning/blender_execution_boundary.py` — validates calls before Blender execution; provides `execute_verified()` and receipt-bound execution.
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

New second-task definition:

- `planning/marker_task.py` — task-specific marker target invariant and `create_empty_marker` action definition. It deliberately contains task data/invariants only; it does not implement a second orchestration architecture.
- `tests/test_marker_conditional_task.py` — focused regression coverage for the second task.

The second task is **conditional creation of `Atlas_Marker` inside the `Atlas_Test` collection**, requiring the object to exist and be an `EMPTY`. Its action shape is intentionally different from goalpost movement: it has no `location` argument and performs object creation rather than transform mutation.

## 4. Current model/runtime setup

Live Qwen/Ollama/Blender runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Goalpost live tools currently exercised: `inspect_object_relationship`, `move_object`.
- The marker task is not yet integrated into the live Qwen/Blender harness.

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

### Marker-task development

Commit `265045211ff111d3ae4fc0f2a5b8bef1e1a172a2` introduced the marker schema, marker task, and initial tests.

- **Atlas Tests #392 — FAILED** on both Python 3.11 and 3.9: **377 passed, 3 failed**.
- The failures were test-design mismatches, not a generic orchestrator regression. The tests incorrectly assumed immediate `COMPLETE` after a satisfied evaluation, immediate `ACTION` after an unsatisfied evaluation, and execution without `ActionAuthorization`.
- The established state machine requires satisfied targets to enter `VERIFICATION`, unsatisfied targets to enter `AUTHORIZATION`, and writes to require exact action authorization.

The tests were corrected in:

- `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` — `fix: align marker task tests with authorization and verification phases`

That correction is now validated:

- **Atlas Tests #393 — PASS**.
- The run completed successfully for the marker test correction. citehttps://github.com/cantidokun/Atlas/actions/runs/32039885675

The latest documentation commit then triggered:

- **Atlas Tests #394 — PASS** on the current documentation state. citehttps://github.com/cantidokun/Atlas/actions/runs/32039910015

### Live regression state

- **Live Conditional Atlas Regression #149 — WAITING** for self-hosted/local runner capacity. All four jobs are currently waiting; none has executed yet. The jobs are `live generic collection (incorrect)`, `live conditional (incorrect)`, `live generic collection (already-correct)`, and `live conditional (already-correct)`. citehttps://api.github.com/repos/cantidokun/Atlas/actions/runs/32039885682/jobs
- Therefore **do not claim a new live marker-task proof yet**.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: the exact validated request and independently verified result are deterministically bound, so later mutation is detectable.

What is **not yet live-proven** is a broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary.

## 7. Current known issues / boundaries

- Goalpost execution remains the only materially different Blender task with a complete live proof.
- The marker task is now offline/CI-proven but has not yet been live-proven.
- The existing live workflow still targets the established generic/goalpost conditional harness; a dedicated marker `.blend` fixture and marker-specific live Qwen/Blender harness integration are still required.
- The self-hosted local runner is currently the gating point for Live Conditional Atlas Regression #149.
- Broader continuation/resume behavior needs a production-facing live proof.
- Full unattended autonomous local production operation has not been declared complete.
- Do not add goalpost-specific branches to generic planning layers.
- Do not bypass explicit authorization or the mandatory verification phase.

## 8. Exact next development stage

1. Allow **Live Conditional Atlas Regression #149** to run when the self-hosted runner becomes available and inspect its actual logs/results.
2. In parallel, build deterministic marker `.blend` fixtures for:
   - marker already present and correct;
   - marker absent;
   - optional deliberate post-write verification-failure state.
3. Extend the live Qwen/Blender harness to support the marker task without changing generic orchestration semantics.
4. Add marker-specific live cases for zero-write, authorized creation, fresh verification, and fail-closed `BLOCKED` behavior.
5. Only after live marker proof is green, select the next materially different Blender production capability.

Required marker path:

```text
structured Qwen proposal
 -> exact Blender tool/argument validation
 -> authoritative scene evidence
 -> marker target-state evaluation
 -> conditional skip/create decision
 -> explicit ActionAuthorization
 -> deterministic future
 -> create_empty_marker execution
 -> structured result
 -> fresh independent verification
 -> Blender execution receipt
 -> completion
```

Required marker live cases:

1. marker already present and correct -> zero writes -> fresh verification -> complete;
2. marker absent -> explicit authorization -> create marker -> fresh verification -> complete;
3. marker creation reports success but marker is absent afterward -> verification fails -> `BLOCKED`.

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
- unauthorized replan -> rejected.

## 10. Resume instructions

On the next development session:

1. read this handoff;
2. inspect current `main` and the latest GitHub Actions state;
3. inspect actual logs before changing code if a test fails;
4. keep generic planning layers task-agnostic;
5. use the green **Atlas Tests #393/#394** baseline as the offline starting point;
6. resolve the self-hosted-runner gate for **Live Conditional Atlas Regression #149** before treating the current live workflow as a new proof;
7. build the deterministic marker fixtures;
8. extend the live harness for marker creation;
9. run and inspect the marker live cases;
10. update this handoff with the verified marker implementation milestone and live result;
11. then proceed to the next materially different Blender production capability.

**Immediate continuation point:** offline marker architecture is green; the remaining work is deterministic marker fixture + live harness integration, with Live Conditional Atlas Regression #149 currently waiting for the self-hosted runner.
