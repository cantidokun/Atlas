# Atlas Current Development Handoff

**Updated:** August 17, 2026 05:45 UTC
**Current branch:** `main`
**Current HEAD:** `3419c36536e0ffc82ba180504313d18b0d5d64ce` — `docs: refresh current Atlas handoff`
**Current verified Blender code milestone:** `09d165944b32dd5ee03100cff10a0d4b33481df3` — `test: bind Blender execution receipts to request and result`

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
- action authorization
- replan authorization
- deterministic future generation/execution
- recovery/replan gates
- runtime context fingerprinting and integrity checks
- audit trail

The conditional execution architecture explicitly separates:

1. evidence acquisition;
2. target-state evaluation;
3. conditional skip vs execute decision;
4. explicit authorization;
5. deterministic action execution;
6. fresh post-action verification;
7. fail-closed completion/blocking.

## 3. Blender-specific files and tools

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; snapshots mutable supported arguments.
- `planning/blender_execution_boundary.py` — validates calls before Blender execution; preserves raw `execute()`; provides `execute_verified()` and receipt-bound execution; rejects malformed responses.
- `planning/blender_result_contract.py` — immutable `BlenderExecutionResult`; validates tool, boolean success, execution state, and details.
- `planning/blender_verification.py` — independently validates requested-tool identity and successful execution; fails closed on mismatches/failure.
- `planning/blender_execution_receipt.py` — deterministically binds validated tool + arguments + verified result; detects later mutation.
- `execute_with_receipt()` — validation -> Blender execution -> result normalization -> independent verification -> immutable receipt.
- `live_qwen_conditional_loop.py` — live Qwen/Ollama/Blender conditional harness.
- `goalpost_test_CONDITIONAL_CORRECT.blend` — deterministic already-correct fixture.
- `goalpost_test_CONDITIONAL_INCORRECT.blend` — deterministic incorrect fixture.

Live harness runtime:

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Qwen output is constrained by `qwen/structured_plan.py` / `TASK_PLAN_JSON_SCHEMA` and parsed by `qwen_planning_runtime.py`.
- Current live tools: `inspect_object_relationship`, `move_object`.

## 4. Verified milestones

Recent Blender code milestones:

- `788d311` — add immutable Blender execution receipt
- `909b0c4` — expose receipt-bound Blender execution
- `09d1659` — receipt regression coverage and binding of the Blender execution receipt to request/result

The latest `main` HEAD is documentation-only, so `09d1659` remains the verified Blender implementation milestone.

## 5. Test status

### Offline / CI

- **Atlas Tests #384 — PASS**
- Python **3.11 — PASS**
- Python **3.9 — PASS**
- Run commit: `3419c36536e0ffc82ba180504313d18b0d5d64ce`

Previous green baseline: Atlas Tests #383 also passed on both Python versions.

### Live Blender regression

- **Live Conditional Atlas Regression #142 — PASS**
- Tested Blender code milestone: `09d165944b32dd5ee03100cff10a0d4b33481df3`
- Required `local-testing` environment approval was completed.

Proven live behavior:

```text
already-correct -> target satisfied -> zero writes -> fresh verification -> complete
incorrect -> target unsatisfied -> authorized writes -> fresh verification -> complete
```

The incorrect fixture is deterministic and does not inherit an accidental correct base state.

## 6. Runtime integrity / continuation

Atlas has a runtime identity boundary binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Continuation must fail closed when authoritative state, authorized future, or stable execution context changes.

The Blender receipt layer adds another integrity boundary: the exact validated request and independently verified result are deterministically bound, so later mutation is detectable.

What is **not yet live-proven** is a broader production-facing continuation/resume scenario using these integrity primitives across a real autonomous task boundary.

## 7. Current known issues / boundaries

- Live production breadth is still concentrated on the goalpost task.
- A second materially different Blender production task has not yet been live-proven.
- Broader continuation/resume behavior needs a production-facing live proof.
- Full unattended autonomous local production operation has not been declared complete.
- Do not contaminate generic planning layers with goalpost-specific branches.

## 8. Exact next development stage

Build and live-prove a **second materially different Blender production task** using the existing generic architecture.

Required path:

```text
structured Qwen proposal
 -> exact Blender tool/argument validation
 -> authoritative Blender evidence
 -> explicit target-state evaluation
 -> conditional decision
 -> explicit authorization
 -> deterministic future
 -> Blender execution
 -> structured result
 -> independent verification
 -> execution receipt
 -> completion
```

The second task must exercise different object relationships and a different action shape. Reuse the generic planning/verification/receipt layers rather than adding task-specific orchestration logic.

## 9. Required regression coverage for the next stage

Continue proving:

- already-satisfied state -> zero writes;
- unsatisfied state -> exact authorized action order;
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
2. inspect current `main` and latest GitHub Actions state;
3. do not rely on older conversational commit numbers if repository state differs;
4. implement the smallest coherent second-task increment;
5. add focused offline tests;
6. wait for CI;
7. inspect actual logs before changing code if anything fails;
8. run the live regression once the implementation is stable;
9. update this handoff with the new verified code milestone and live result;
10. continue to the next coherent Blender stage without waiting for a separate "keep going" instruction unless user input is genuinely required.

**Immediate continuation point:** expand the verified Blender Agent from the goalpost proof into a second generic live production task using the existing validation -> authorization -> deterministic future -> execution -> verification -> receipt architecture.
