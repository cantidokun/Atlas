# Atlas Current Development Handoff

**Updated:** August 17, 2026 21:10 UTC  
**Current branch:** `main`  
**Current HEAD before this handoff update:** `f329df10444d4602fcb69faf6db9593c6d5bcace` — `docs: update Atlas handoff after receipt fix`  
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
- `tools/__init__.py` — tool registry including `create_empty_marker`, `create_collection`, and `move_object`.

Task definitions / live harnesses:

- `planning/marker_task.py` — task-specific marker target invariant and `create_empty_marker` action definition. It deliberately contains task data/invariants only; it does not implement a second orchestration architecture.
- `tests/test_marker_conditional_task.py` — focused regression coverage for the marker task.
- `live_qwen_conditional_loop.py` — live conditional goalpost harness.
- `live_qwen_collection_task.py` — live generic collection task harness.
- `scripts/provision_collection_task_fixtures.py` — deterministic collection fixture provisioning.
- `goalpost_test_CONDITIONAL_CORRECT.blend`
- `goalpost_test_CONDITIONAL_INCORRECT.blend`
- `collection_task_CORRECT.blend`
- `collection_task_INCORRECT.blend`

The collection task is **conditional creation of the `Atlas_Test` collection**. Its action is `create_collection` with `file_name` and `collection_name`. This is materially different from goalpost transform mutation and is now live-proven through the generic collection harness.

The marker task (`Atlas_Marker` `EMPTY` inside `Atlas_Test`) remains a separate task definition and is currently offline/CI-proven; it is not the task that was exercised by live regression #155.

## 4. Current model/runtime setup

Live Qwen/Ollama/Blender runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender version observed on the local runner: **4.4.3**
- Local GitHub Actions runner: `atlas-local`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Goalpost live tools exercised: `inspect_object_relationship`, `move_object`.
- Collection live tool exercised: `inspect_scene`, `create_collection`.

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

### Marker / collection development

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

### Live Conditional Atlas Regression #155 — PASS

Run `32053379722` completed successfully on the local self-hosted runner `atlas-local`.

All four jobs passed:

- `live generic collection (incorrect)` — **PASS**
- `live generic collection (already-correct)` — **PASS**
- `live conditional (incorrect)` — **PASS**
- `live conditional (already-correct)` — **PASS**

The two collection jobs are the important new live proof for the second materially different Blender capability.

The incorrect collection case log explicitly showed:

```text
Qwen proposal accepted
-> authoritative evidence
-> target_satisfied: false
-> failed invariant: target_collection_exists
-> authorization: authorized, action_count: 1
-> execution: create_collection, success
-> receipt bound to that execution
-> fresh verification: Atlas_Test present
-> PASS
```

The already-correct conditional goalpost case explicitly showed:

```text
target_satisfied: true
-> writes_skipped: true
-> WRITE EXECUTION SKIPPED
-> verification success
-> PASS
```

Therefore the latest live result proves that the generic collection path can perform a real Blender creation operation through Qwen proposal, Atlas evidence/evaluation, explicit authorization, single execution, receipt binding, and independent verification.

**Important boundary:** #155's `live conditional` jobs are still the goalpost conditional harness. They do not prove that `create_collection` has been integrated into the generic conditional goalpost-style harness. The second-task live proof is specifically the **generic collection** pair within the same regression run.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: the exact validated request and independently verified result are deterministically bound, so later mutation is detectable.

What is **not yet live-proven** is a broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary.

## 7. Current known issues / boundaries

- Goalpost execution and generic collection creation are now live-proven as materially different Blender capabilities.
- The marker task (`planning/marker_task.py`, `create_empty_marker`) is offline/CI-proven but not yet live-proven.
- The generic collection live proof is currently a focused task harness; it does not by itself prove arbitrary task generation or arbitrary Blender production planning.
- A successful executor response still cannot be treated as authoritative state; independent fresh scene evidence is mandatory.
- Broader continuation/resume behavior needs a production-facing live proof.
- Full unattended autonomous local production operation has not been declared complete.
- Do not add goalpost- or collection-specific branches to generic planning layers.
- Do not bypass explicit authorization or the mandatory verification phase.

## 8. Exact next development stage

1. Preserve the new live collection proof as a regression baseline.
2. Add the **failed-postcondition live case** for the collection task: make the executor report success while authoritative scene evidence remains incorrect, and require `VerificationPlan` to transition to `BLOCKED`.
3. Add a live **zero-write collection case** whose target is already satisfied and whose audit trail proves no creation call occurred.
4. If those focused live cases are green, promote the collection task's reusable evidence/action/verification wiring without adding task-specific branches to generic planners.
5. Then live-prove `create_empty_marker` as the next distinct creation task using `planning/marker_task.py` and `create_empty_marker`.
6. After the second creation capability is proven, build a broader production-facing continuation/resume scenario using the existing runtime fingerprint, deterministic future, recovery gate, and receipt integrity primitives.
7. Only after those live proofs are green, select the next materially different Blender production capability.

Required second-task path now proven for the collection success case:

```text
structured Qwen proposal
 -> exact Blender tool/argument validation
 -> authoritative scene evidence
 -> target-state evaluation
 -> conditional execute decision
 -> explicit ActionAuthorization
 -> deterministic future
 -> create_collection execution
 -> structured result
 -> fresh independent verification
 -> Blender execution receipt
 -> completion
```

The next required failure path is:

```text
structured proposal
 -> authoritative evidence
 -> target unsatisfied
 -> authorization
 -> executor reports success
 -> authoritative post-state still wrong
 -> VerificationPlan = BLOCKED
 -> no false completion
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
3. use **Atlas Tests #401 PASS / Python 3.9 + 3.11** as the current offline baseline;
4. use **Live Conditional Atlas Regression #155 PASS** as the current live collection/goalpost baseline;
5. inspect actual logs before changing code if a new live or offline test fails;
6. implement and live-test the collection **false-success / failed-verification -> BLOCKED** case;
7. implement and live-test the collection **already-correct -> zero-write** case;
8. then live-prove `create_empty_marker`;
9. update this handoff with actual results before moving to the next capability;
10. do not declare broader autonomous production operation complete until continuation/resume has a real live proof.

**Immediate continuation point:** the second materially different Blender capability, generic collection creation, is now live-proven for its normal incorrect-state creation path and its already-correct baseline. The next engineering proof is to demonstrate that the same path fails closed when the executor claims success but authoritative post-state verification fails, followed by live proof of `create_empty_marker`.
