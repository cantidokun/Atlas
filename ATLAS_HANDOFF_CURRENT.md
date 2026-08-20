# Atlas Current Development Handoff

**Updated:** August 20, 2026 00:01 EDT  
**Branch:** `main`  
**Current verified HEAD:** `934a615f3a1be5a22b75c3251ad005df7f7f79a2` — `fix: retry transient Ollama planning timeout in collection task`

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

## 2. Current runtime/test posture

Workflow and action-runner testing is now explicitly **authorized by the user** and has resumed.

The local GitHub Actions runner `atlas-local` is operational and is used for Windows/Blender live regressions. Ollama is treated as **dedicated Atlas infrastructure** for this development track; no workflow-level compensation for unrelated Qwen workloads is required.

The GitHub-hosted offline CI workflow remains separate from the local Blender live workflows.

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

`AtlasTaskDefinition` contains task data only; orchestration logic remains generic.

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

Task/harness files include the conditional, collection, membership, parent, rotation, rename, delete, marker, verification-failure, and continuation live paths and their deterministic fixture tooling.

## 5. Model/runtime

- Ollama: `http://localhost:11434/api/chat`
- Model: `qwen3:8b`
- Blender: **4.4.3**
- Local GitHub Actions runner: `atlas-local` — operational
- Qwen structured planning uses `qwen/structured_plan.py`, `TASK_PLAN_JSON_SCHEMA`, and `qwen_planning_runtime.py`.

## 6. Verified milestones

### Offline CI

- **Atlas Tests #536 — PASS** after fixing two newer regressions.
- The stale object-rotation regression import was corrected in `tests/test_live_qwen_object_rotation.py`.
- `AtlasTaskDefinition.snapshot()` was hardened with deep copies for nested action/evidence arguments and metadata in `dd28f55`.

### Live Blender regressions

The following live capabilities have now passed using the local Windows runner and dedicated Ollama:

- **Object rotation — PASS**
  - already-correct path passes with no write
  - incorrect path passes with authorized `set_object_rotation`, receipt binding, and fresh verification
- **Object rename — PASS**
- **Object delete — PASS**
- **Blender continuation — PASS**
  - already-correct
  - incorrect
  - tampered-context rejection
- **Conditional goalpost — PASS**
  - already-correct
  - incorrect
- **Collection membership — PASS**
  - already-correct
  - incorrect
- **Parent relationship — PASS**
  - already-correct
  - incorrect
- **Adversarial verification — PASS**
  - executor claims success while fresh authoritative state disagrees -> `BLOCKED`
- **Generic collection — PASS**
  - already-correct
  - incorrect

### Runtime observation / hardening

The first rotation and rename live failures, and the initial generic-collection failure, were caused by Ollama structured-planning read timeouts while multiple Atlas Qwen-backed workflows were active against the same local Ollama service. After Ollama was dedicated to Atlas and workflows were rerun individually, rotation and rename passed.

The generic collection harness was additionally hardened in `934a615` to retry transient Ollama planning timeouts within the existing three-attempt planning budget and record timeout events in the audit trail. The subsequent full Live Conditional Atlas Regression passed.

Ollama is now treated as dedicated Atlas infrastructure; workflow orchestration does not need to account for unrelated projects using it.

## 7. Runtime integrity / continuation

Atlas has runtime identity checks binding continuation to stable instructions, authorized plan identity, and authoritative persisted-state identity. Invalid continuation fails closed. Blender receipts bind the exact validated request to the verified result from one execution and detect later mutation.

The live continuation regression has now proven pause/resume behavior and tampered-context rejection for the tested parent-relationship task.

## 8. Current known boundaries

- `create_empty_marker` remains the next materially distinct Blender capability to live-prove if required by the promotion sequence.
- Broader production-facing autonomous continuation across multiple materially different capabilities is not yet declared complete.
- Generic live proofs establish the architecture for the tested capabilities; they do not prove arbitrary Blender production planning.
- Executor success is never authoritative state; fresh verification remains mandatory.
- Do not add task-specific branches to generic planners or bypass authorization/verification.

## 9. Immediate next steps

1. Preserve the fresh passing regression baseline and keep current verified behavior stable.
2. Live-prove `create_empty_marker` with `planning/marker_task.py` and its deterministic fixture/harness.
3. Add or retain explicit audit assertions for zero-write already-correct paths and single-write incorrect paths.
4. Use the existing runtime fingerprinting, deterministic future, recovery gate, and receipt integrity primitives to expand production-facing continuation/resume across multiple materially different task capabilities.
5. After that broader continuation proof, select the next materially different Blender production capability.

## 10. Required regression coverage

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

## 11. Resume instructions

Read this file first. Current workflow testing is authorized. Treat **Atlas Tests #536 PASS** as the fresh offline baseline and the live regression results above as the current live proof boundary.

The immediate next capability is `create_empty_marker`, followed by a broader production-facing continuation/resume proof using the already-implemented runtime integrity primitives.
