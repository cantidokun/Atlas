# Atlas Current Development Handoff

**Updated:** August 23, 2026 — current development session  
**Current repository HEAD:** `23661b5309c6d650538c5a7926ade1df5be48fe1` (`Correct Blender timeout failure-boundary coverage`)  
**Previous implementation commit:** `158fe3bdd82f99f6759a4a3756d693335682e52d` (`Add fail-closed Blender subprocess boundary`)  
**Latest prior implementation:** `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` (`Test named-pipe failure propagation through adapter`)  
**Latest recorded development test milestone before this session:** **694 passed**; this is a development-session result, not fresh CI verification.  
**Previously verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green.  
**Purpose:** canonical resume point for the next Atlas development session.

## Current state

Atlas remains actively under development. The user has now explicitly authorized workflow/action-runner testing again and has confirmed the local action runner is running. Future workflow validation may therefore proceed when needed. Do not retroactively claim any new CI result until an actual runner/workflow result is observed.

This session made the first coherent implementation increment against the Stage 10 Blender subprocess boundary:

1. Added `tools/blender_process.py` with a fail-closed `run_checked_blender(...)` subprocess boundary.
2. Expanded `tests/test_blender_process.py` to cover non-zero exits, invalid JSON, non-object JSON, missing end markers, subprocess timeouts, and valid structured results.
3. Corrected the timeout test to exercise `subprocess.TimeoutExpired` and require Atlas to normalize it to `RuntimeError`.

No fresh CI/test result has been observed yet for these new commits. The 687-pass CI baseline therefore remains the last verified CI result, and the 694-pass development result remains historical session evidence only.

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

### Historical verified baselines

- **687 passed**, Python 3.9 and 3.11 green — last verified CI baseline.
- **694 passed** — latest recorded development-session milestone before this implementation session; not fresh GitHub Actions verification.

### Blender subprocess boundary — current implementation

Commit `158fe3bdd82f99f6759a4a3756d693335682e52d` adds `tools/blender_process.py` with:

- deterministic Blender subprocess invocation;
- non-zero exit rejection;
- stderr/stdout diagnostic preservation on process failure;
- timeout normalization;
- start/end marker extraction;
- empty-payload rejection;
- JSON decoding with fail-closed errors;
- JSON-object-only result enforcement;
- `OSError` startup failure normalization.

Commit `23661b5309c6d650538c5a7926ade1df5be48fe1` expands `tests/test_blender_process.py` with focused coverage for:

- non-zero process exit;
- invalid JSON;
- JSON arrays rejected when an object is required;
- missing end marker;
- `subprocess.TimeoutExpired` normalized to `RuntimeError`;
- valid structured JSON object acceptance.

**Status:** implementation and tests are committed, but no fresh workflow/CI result has yet been observed. This is the immediate validation target now that the action runner is available.

### Unreal transport boundary hardening

Commit `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` adds `tests/test_unreal_transport_failure_boundary.py`, covering timeout/disconnect wrapping at `UnrealAdapterError`, original-cause preservation, propagation to `UnrealPlanExecutionError`, and preservation of operation index/name, entity IDs, and transport error context.

**Status:** no fresh result claimed for this post-687 coverage.

## Current development gate

### Stage 10 — Blender Adapter / Real Execution Bridge

**PRIMARY GATE — NOW IN ACTIVE IMPLEMENTATION/VALIDATION**

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
- Qwen cannot use the adapter as arbitrary Python.

The new `tools/blender_process.py` is the low-level process boundary for this gate. It does not replace `planning/blender_execution_boundary.py`; higher-level authorization, normalization, verification, and receipt binding remain above it.

Do not add a parallel execution architecture. Reuse the existing planning, authorization, receipt, verification, and state machinery.

The Unreal regression is complementary production-boundary hardening and does not complete the Blender gate.

## OpenHands transition

`docs/OPENHANDS_TRANSITION_GUIDE.md` remains the planned transition guide for moving from the ChatGPT/GitHub/local-machine workflow toward an OpenHands-assisted local development workflow.

Important transition rules:

- Keep **Atlas-Unreal-Aider** and the **Blender Agent** as separate repositories.
- Planned workspace: `C:\Atlas-Development\` with independent repositories.
- Historical Atlas-Unreal-Aider checkout: `C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider`; verify the actual path before transition.
- Start OpenHands in a disposable workspace before connecting the production Atlas checkout.
- First Atlas access should be read-only; verify branch and working-tree state before edits.
- Use progressive access: source access → build/test access → Unreal access → broader production execution.
- Preserve repository boundaries, C++ interoperability, language-neutral contracts, authorization/runtime boundaries, test integrity, issue-driven development, incremental changes, and human control of high-impact operations.
- The transition guide is planning/documentation only; it is not evidence that OpenHands, WSL, Docker, or broader production access has been installed, tested, or authorized.

## Concrete files/tools

Blender/planning/runtime:

- `planning/task_definition.py`
- `planning/task_runtime.py`
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_result_contract.py`
- `planning/blender_verification.py`
- `tools/blender.py`
- `tools/blender_transform.py`
- `tools/blender_process.py` **(new current implementation)**
- `tests/test_blender_process.py` **(expanded current regression suite)**
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `docs/OPENHANDS_TRANSITION_GUIDE.md`
- `ATLAS_HANDOFF_CURRENT.md`

Established flow: `BlenderTaskIntent` → `ActionPlan` → `ConditionalPlanningOrchestrator` → authorization/replan gates → `BlenderExecutionBoundary` → low-level Blender process boundary → normalized result → independent verification → immutable receipt → agent state/replanning.

Unreal boundary:

- `planning/unreal_adapter_production.py`
- `planning/unreal_agent.py`
- `planning/unreal_plan_executor.py`
- `planning/unreal_task_planner.py`
- `planning/unreal_transport_contract.py`
- `planning/unreal_transport_named_pipe.py`
- `tests/test_unreal_transport_failure_boundary.py`

The Unreal test `FailingTransport` is local test infrastructure, not live Unreal proof.

## Current active work

1. Validate the new Blender subprocess boundary and its focused regression suite through the now-running action runner.
2. If failures occur, fix the smallest boundary defect and rerun the focused gate.
3. Integrate `tools/blender_process.run_checked_blender` beneath the existing controlled Blender adapter without moving authorization into the subprocess layer.
4. Add adapter-level tests proving validated arguments are preserved and process failures cannot become successful execution receipts.
5. Establish a fresh green regression baseline after the integration.
6. Only then prepare the first controlled live Blender operation with independent verification.
7. Expand from the first live operation into rotation/marker and closed-loop autonomous Blender behavior only after their specific proof gates pass.
8. Keep Unreal live transport proof as a separate gate.
9. Continue OpenHands transition work only in bounded, reversible steps.

## Regression requirements

Preserve/extend coverage for zero-write already-satisfied tasks; exact authorized ordering; mandatory post-write verification; verification failure → `BLOCKED`; action failure → recovery gate; receipt mismatches; malformed/wrong executor results; continuation identity; authorized/unauthorized replanning; malformed Qwen reasoning; unknown Blender tools; adapter authorization bypass; validated-argument preservation; executor-result normalization; subprocess non-zero exits; timeout; startup failure; missing markers; malformed/non-object JSON; Blender fail-closed behavior; Unreal timeout/disconnect → adapter failure; and Unreal transport failure retaining executor operation context.

## Do not regress

- Never give Qwen direct production-tool execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan during replanning.
- Never declare completion from a write/transport response alone.
- Never make goalpost-specific behavior the generic architecture.
- Never treat 687 passed as validation of newer code.
- Never treat 694 passed as fresh GitHub Actions verification without an actual runner result.
- Never connect live Blender until adapter-focused tests and the authorized regression gate are green.
- Never mark `tools/blender_process.py` complete as a production integration merely because its isolated tests pass; adapter integration and independent verification are still required.
- Never mark `tests/test_unreal_transport_failure_boundary.py` verified until its focused result is recorded.
- Never treat the OpenHands transition guide as evidence that OpenHands or production access is already installed, tested, or authorized.
