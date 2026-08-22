# Atlas Current Development Handoff

**Updated:** August 22, 2026 — 19:39 EDT  
**Current repository HEAD:** `7f35673d6881729b4a55265e6e6fe073a0b45b99` (`docs: refresh canonical Atlas handoff at 16:43 EDT`)  
**Latest implementation commit:** `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` (`Test named-pipe failure propagation through adapter`)  
**Previous handoff commit:** `7f35673d6881729b4a55265e6e6fe073a0b45b99` (`docs: refresh canonical Atlas handoff at 16:43 EDT`)  
**Latest recorded development test milestone:** **694 passed** (conversation/runtime report); this is not fresh GitHub Actions verification.  
**Previously recorded verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green.  
**Purpose:** canonical resume point for the next Atlas development session.

## Current state

Atlas remains actively under development. **Workflow/action-runner testing is paused by explicit user instruction and must not be triggered, rerun, or approved until the user explicitly authorizes it.** Offline-safe development may continue.

No newer implementation commit has been identified after `6e0c2c1e894615b47934cb17b7d7e66712e75f3c`; subsequent commits are handoff/documentation refreshes. Do not treat the 687-pass CI baseline as validation for code added after that baseline, and do not treat the 694-pass development report as GitHub Actions verification without an actual authorized runner result.

## Architecture

```text
Qwen / AI
  ↓ reason + propose
structured task reasoning
  ↓
Task Intent
  ↓
capability + argument validation
  ↓
ActionPlan
  ↓
explicit authorization
  ↓
controlled execution boundary / adapter
  ↓
immutable execution receipt
  ↓
independent fresh verification
  ↓
verified agent state / evidence
  ↓
replan if objective remains unsatisfied
```

Qwen is never execution authority. A production-tool response is never sufficient to establish final state. The established architecture includes evidence/action plans, target-state evaluation, verification plans, authorization and replan gates, deterministic futures, recovery, runtime integrity, audit trail, immutable receipts, task runtime policy, declarative task definitions, controlled adapters, and transport failure boundaries. The generic contract is `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

### Declarative runtime

- `planning/task_definition.py` — `AtlasTaskDefinition`; validates task identity, evidence/actions, tool allowlists, write policy, verification policy, and metadata.
- `planning/task_runtime.py` — `build_orchestrator(task)`, `validate_task_runtime(task)`, `prepare_task_runtime(task)`; validates before evidence or writes and bridges into `ConditionalPlanningOrchestrator`.

### Replanning

Replanning consumes verified production observations. It either stops on verified satisfaction or emits a new task intent through the normal planning/authorization path. An authorized plan is never silently mutated.

### Qwen contract

Structured Qwen output is constrained before executable intent formation. Current recorded coverage rejects malformed confidence, empty objective/observation/action/evidence fields, non-object action arguments, and unknown Blender tools. The latest recorded correction aligns the Qwen reasoning test with the canonical Blender rotation schema using `rotation_degrees` and required file/object fields.

## Model/runtime

- Reasoning model: **Qwen `qwen3:8b` via Ollama**
- Blender target: **Blender 4.4.3**
- Local Atlas runtime: **`atlas-local`**
- Qwen remains planner/reasoner only; it cannot become an arbitrary Python execution channel through a production adapter.

Photogrammetry remains upstream of Blender: dedicated photogrammetry software creates the initial reconstruction; Blender performs analysis, cleanup, correction, optimization, and preparation. Atlas remains focused on soccer/sports digital-twin production workflows.

## Tests and verification status

### Latest recorded development milestone

**694 passed** remains the newest test outcome available from the active Atlas development conversation. It is a development-session result, not fresh GitHub Actions verification.

### Latest verified CI baseline

**687 passed**, green on **Python 3.9 and 3.11**. Any code after that baseline requires fresh CI validation once workflow testing is authorized.

### Blender subprocess hardening

Commit `832ae2568df1197e96bfdb363f70c456bba44a2c` adds `tests/test_blender_process.py`, covering:

- non-zero Blender process exit rejection;
- invalid JSON between `ATLAS_START` / `ATLAS_END` rejection;
- JSON-array rejection when an object is required;
- valid structured JSON acceptance.

**Status:** no fresh result claimed. The test imports `tools.blender_process.run_checked_blender`; the prior repository inspection did not surface a tracked `tools/blender_process.py`. Reconcile that implementation/import surface before promoting the test.

### Unreal transport boundary hardening

Commit `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` adds `tests/test_unreal_transport_failure_boundary.py`, covering timeout/disconnect wrapping at `UnrealAdapterError`, original-cause preservation, propagation to `UnrealPlanExecutionError`, and preservation of operation index/name, entity IDs, and transport error context.

**Status:** no fresh result claimed. This is post-687 regression coverage and remains unverified until an authorized test/CI result is recorded.

## Current development gate

### Stage 10 — Blender Adapter / Real Execution Bridge

**PRIMARY GATE**

The target is the controlled adapter that maps an already-authorized Atlas action into a real Blender execution request and maps structured Blender response/evidence back into Atlas. Required properties:

- capability restrictions remain enforced;
- exact validated arguments are preserved;
- adapter cannot expand authorization scope;
- execution is deterministic and observable;
- process/transport failures surface as failures, not success payloads;
- structured responses are normalized and validated;
- verification remains independent;
- malformed/ambiguous responses fail closed;
- evidence returns to agent state/replanning;
- Qwen cannot use the adapter as arbitrary Python execution.

Do not add a parallel execution architecture; reuse the existing planning, authorization, receipt, verification, and state machinery.

The Unreal regression is complementary production-boundary hardening and does not complete the Blender gate.

## Concrete files/tools

Blender/planning/runtime:

- `planning/task_definition.py`
- `planning/task_runtime.py`
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `tools/blender.py`
- `tools/blender_transform.py`
- `tests/test_blender_process.py`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `ATLAS_HANDOFF_CURRENT.md`

Established flow: `BlenderTaskIntent` → `ActionPlan` → `ConditionalPlanningOrchestrator` → authorization/replan gates → execution receipt → independent verification → Qwen structured reasoning.

Unreal boundary:

- `planning/unreal_adapter_production.py`
- `planning/unreal_agent.py`
- `planning/unreal_plan_executor.py`
- `planning/unreal_task_planner.py`
- `planning/unreal_transport_contract.py`
- `planning/unreal_transport_named_pipe.py`
- `tests/test_unreal_transport_failure_boundary.py`

The Unreal test `FailingTransport` is local test infrastructure, not live Unreal proof.

## Offline-safe work while runner testing is paused

- Reconcile/implement the missing `tools.blender_process.run_checked_blender` import surface.
- Harden deterministic request/result normalization.
- Strengthen authorization boundaries, immutable receipts, evidence binding, and malformed/ambiguous response handling.
- Harden Unreal named-pipe/adapter failure normalization and recovery boundaries.
- Validate runtime policy, continuation/recovery identity, and static architecture invariants.
- Add focused unit tests that do not invoke workflow/action-runner infrastructure.
- Improve diagnostics and documentation.

Do not weaken authorization/verification or introduce a parallel execution path merely to avoid the runner.

## Blender integration gate

Do not connect to the real Blender environment merely because the architecture looks close. Once workflow testing is authorized, first establish focused adapter tests and a fresh green CI result, then prove one controlled live operation:

```text
controlled Blender scene
  ↓
inspect
  ↓
one authorized operation
  ↓
structured result
  ↓
independent verification
```

Only then expand toward autonomous multi-step Blender work.

## Regression requirements

Preserve/extend coverage for zero-write already-satisfied tasks; exact authorized ordering; mandatory post-write verification; verification failure → `BLOCKED`; action failure → recovery gate; receipt mismatches; malformed/wrong executor results; continuation identity; authorized/unauthorized replanning; malformed Qwen reasoning; unknown Blender tools; adapter authorization bypass; validated-argument preservation; executor-result normalization; subprocess non-zero exits; malformed/non-object JSON; Blender fail-closed behavior; Unreal timeout/disconnect → adapter failure; and Unreal transport failure retaining executor operation context.

## Exact next steps when runner testing is authorized

1. Read this handoff and inspect current `main`/HEAD against the 687-pass baseline.
2. Reconcile `tests/test_blender_process.py` with the actual `tools.blender_process` implementation/import surface.
3. Inspect `tests/test_unreal_transport_failure_boundary.py` against the current Unreal transport/adapter implementation.
4. Run focused offline-safe tests where allowed without workflow/live infrastructure.
5. Inspect fresh GitHub Actions only after explicit workflow-test authorization.
6. Reconfirm the 694-pass development milestone against the current checkout before promotion.
7. Implement the smallest coherent Blender adapter increment and add focused tests.
8. Run the authorized regression gate and fix failures.
9. After adapter tests are green, prepare the first controlled live Blender connection.
10. Prove one live Blender operation with independent verification.
11. Expand toward rotation/marker and closed-loop autonomous Blender behavior only after their specific proof gates pass.
12. Treat Unreal live transport/connection proof as a separate gate; the named-pipe tests are regression coverage, not live proof.

## Do not regress

- Never give Qwen direct production-tool execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan during replanning.
- Never declare completion from a write/transport response alone.
- Never make goalpost-specific behavior the generic architecture.
- Never trigger workflow/action-runner tests during the current pause.
- Never represent 687 passed as validation of newer code.
- Never represent 694 passed as fresh GitHub Actions verification without an actual authorized runner result.
- Never connect live Blender until adapter-focused tests and authorized regression gates are green.
- Never mark `tests/test_blender_process.py` complete until its `tools.blender_process` dependency is confirmed and a result is recorded.
- Never mark `tests/test_unreal_transport_failure_boundary.py` verified until its focused result is recorded.
