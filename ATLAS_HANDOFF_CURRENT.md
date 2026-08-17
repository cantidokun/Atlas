# Atlas Current Development Handoff

**Updated:** August 17, 2026 14:41 UTC
**Current branch:** `main`
**Current HEAD:** `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` — `fix: align marker task tests with authorization and verification phases`
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

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; snapshots mutable supported arguments. It now also supports `create_empty_marker` with exact arguments `file_name`, `collection_name`, and `object_name`.
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

- `planning/marker_task.py` — task-specific marker target invariant and `create_empty_marker` action definition. This file deliberately contains task data/invariants only; it does not implement a second orchestration architecture.
- `tests/test_marker_conditional_task.py` — focused regression coverage for the second task.

The second task is **conditional creation of `Atlas_Marker` inside the `Atlas_Test` collection**, requiring the object to exist and be an `EMPTY`. Its action shape is intentionally different from goalpost movement: it has no `location` argument and performs object creation rather than transform mutation.

## 4. Current model/runtime setup

Live Qwen/Ollama/Blender runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Goalpost live tools currently exercised: `inspect_object_relationship`, `move_object`.
- The second-task live path still needs a dedicated harness/fixture integration before it can be considered live-proven.

## 5. Verified milestones and test history

Blender receipt milestones:

- `788d311` — add immutable Blender execution receipt
- `909b0c4` — expose receipt-bound Blender execution
- `09d1659` — receipt regression coverage and binding of the Blender execution receipt to request/result

Previously verified CI/live baseline:

- **Atlas Tests #385 — PASS** on Python 3.11 and 3.9.
- **Live Conditional Atlas Regression #142 — PASS**.
- Proven live behavior for goalposts:

```text
already-correct -> target satisfied -> zero writes -> fresh verification -> complete
incorrect -> target unsatisfied -> authorized writes -> fresh verification -> complete
```

### Latest second-task CI attempt

Commit `265045211ff111d3ae4fc0f2a5b8bef1e1a172a2` introduced the marker schema, marker task, and initial tests.

- **Atlas Tests #392 — FAILED** on both Python 3.11 and 3.9.
- Result: **377 passed, 3 failed**.
- Failure cause was entirely in the newly written test expectations, not a discovered regression in the generic orchestrator:
  - the test expected `COMPLETE` immediately after a satisfied conditional evaluation, but the architecture intentionally requires the `VERIFICATION` phase even when the write is skipped;
  - the test expected `ACTION` immediately after an unsatisfied evaluation, but the architecture intentionally requires `AUTHORIZATION` first;
  - the test attempted execution without issuing `ActionAuthorization`.
- The actual `ConditionalPlanningOrchestrator` behavior was confirmed from `planning/planning_orchestrator.py`: satisfied targets enter `VERIFICATION`; unsatisfied targets enter `AUTHORIZATION`; `execute_next_action()` rejects execution until exact action authorization exists.

The test contract was corrected in:

- `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` — `fix: align marker task tests with authorization and verification phases`

Current CI for that fix:

- **Atlas Tests #393 — QUEUED** on Python 3.11 and 3.9.
- **Live Conditional Atlas Regression #149 — QUEUED**.

Do not treat #392 as an implementation failure; it was a test-design mismatch with already-established Atlas state-machine semantics.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: the exact validated request and independently verified result are deterministically bound, so later mutation is detectable.

What is **not yet live-proven** is a broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary.

## 7. Current known issues / boundaries

- Goalpost execution remains the only materially different Blender task with a complete live proof.
- The marker task is implemented at the generic planning/task-definition layer but has not yet been live-proven.
- A dedicated deterministic marker `.blend` fixture and live Qwen/Blender marker harness still need to be built.
- Broader continuation/resume behavior needs a production-facing live proof.
- Full unattended autonomous local production operation has not been declared complete.
- Do not add goalpost-specific branches to generic planning layers.
- Do not bypass explicit authorization or the mandatory verification phase in second-task tests or live execution.

## 8. Exact next development stage

First, let **Atlas Tests #393** finish and inspect both Python versions. If green, build the deterministic marker fixtures and integrate the marker task into the live harness.

Required second-task path:

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

Required live cases:

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
3. inspect the actual logs before changing code if a test fails;
4. do not reinterpret a test-contract failure as a generic architecture failure without tracing the orchestrator state machine;
5. finish CI validation for commit `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac`;
6. build the deterministic marker `.blend` fixtures;
7. extend the live harness without contaminating generic planning layers;
8. run the live marker regression only after offline CI is green;
9. inspect live logs and verify both zero-write and authorized-write behavior;
10. update this handoff with the verified marker code milestone and live test result;
11. then proceed to the next materially different Blender production capability.

**Immediate continuation point:** validate commit `d7d6f3b4577ed2176c4d1c4b5a8a67828b91d0ac` with Atlas Tests #393, then complete the deterministic marker fixture/live-harness integration.
