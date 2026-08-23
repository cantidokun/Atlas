# Atlas Current Development Handoff

**Updated:** August 23, 2026 — active runner development session
**Current repository HEAD:** `1e6c073a6760a800036a07a1ec48487e29a3fc5b`
**Latest subprocess boundary:** `158fe3bdd82f99f6759a4a3756d693335682e52d`
**Latest subprocess test correction:** `23661b5309c6d650538c5a7926ade1df5be48fe1`
**Latest process-executor adapter:** `e9dca99382515db0ddafcbe7ff8cdd4d1f6ba755`
**Latest process-executor tests:** `1e6c073a6760a800036a07a1ec48487e29a3fc5b`
**Latest reported runner result:** **Test 313 — PASS**
**Historical development milestone:** **694 passed** (development-session result)
**Verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green

## Current state

The user has explicitly re-authorized workflow/action-runner testing and confirmed the local action runner is running. Atlas development is therefore proceeding through the Stage 10 Blender Adapter / Real Execution Bridge gate.

The latest work adds a transport-only `BlenderProcessExecutor` beneath the existing `BlenderExecutionBoundary`. It deliberately does not own authorization, capability validation, verification, or receipt creation.

## Architecture

```text
Qwen / AI
  -> structured task reasoning
  -> Task Intent
  -> capability + argument validation
  -> ActionPlan
  -> explicit authorization
  -> BlenderExecutionBoundary
  -> BlenderProcessExecutor
  -> fail-closed Blender subprocess
  -> normalized result
  -> independent verification
  -> immutable execution receipt
  -> verified agent state / replanning
```

Qwen is never execution authority. Production-tool responses are never sufficient to establish final state. Authorized plans are never silently mutated during replanning.

Generic contract: `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

### Declarative runtime

- `planning/task_definition.py` — `AtlasTaskDefinition`.
- `planning/task_runtime.py` — runtime validation/build/prepare bridge.
- `planning/blender_tool_schema.py` — Blender capability/argument validation.
- `planning/blender_execution_boundary.py` — validation, execution, normalization, verification, receipt binding.
- `planning/blender_execution_receipt.py` — immutable execution receipts.
- `planning/blender_result_contract.py` — structured result normalization.
- `planning/blender_verification.py` — independent verification.

### Model/runtime

- Qwen `qwen3:8b` via Ollama.
- Blender 4.4.3.
- Local Atlas runtime: `atlas-local`.
- Qwen remains planner/reasoner only.

Photogrammetry is upstream of Blender; Blender handles analysis, cleanup, correction, optimization, and preparation for Atlas soccer/sports digital-twin workflows.

## Current Blender transport implementation

### `tools/blender_process.py`

`run_checked_blender(...)` is a fail-closed process boundary. It provides:

- deterministic `--background` / `--python-expr` invocation;
- non-zero exit rejection;
- stderr/stdout diagnostic preservation;
- timeout normalization;
- startup `OSError` normalization;
- required start/end marker extraction;
- empty payload rejection;
- invalid JSON rejection;
- JSON-object-only result enforcement.

### `planning/blender_process_executor.py`

`BlenderProcessExecutor` is the new transport adapter. It maps an already-selected tool to a `BlenderProcessRequest`, then delegates exclusively to `run_checked_blender`. It copies the arguments before passing them to the request builder and rejects unknown tools or invalid builder results.

It does **not** authorize tools, broaden capability scope, perform verification, or create receipts.

### Tests

`tests/test_blender_process.py` covers non-zero exits, invalid JSON, JSON-array rejection, missing end markers, timeouts, and valid structured results.

`tests/test_blender_process_executor.py` covers:

- validated request propagation to the transport;
- unknown-tool rejection;
- invalid request-builder result rejection;
- argument-copy isolation.

**Test 313 — PASS** is the latest user-reported runner result. Do not infer that every subsequent commit is covered by Test 313; fresh results are required for the new process-executor commits.

## Existing production bridge

`planning/blender_execution_boundary.py` remains the authoritative higher-level boundary. It already validates the tool call, executes through an injected executor, normalizes the result, independently verifies it, and can bind an immutable receipt.

`planning/blender_autonomous_executor.py` adapts the verified boundary to the autonomous `ToolExecutor` API while retaining the last verified result and receipt.

The correct integration direction is therefore:

```text
validated/authorized Atlas action
  -> BlenderExecutionBoundary
  -> BlenderProcessExecutor
  -> run_checked_blender
```

Do not create a second authorization or verification path.

## Current development gate

### Stage 10 — Blender Adapter / Real Execution Bridge

**ACTIVE PRIMARY GATE**

Required properties:

- capability restrictions remain enforced;
- exact validated arguments are preserved;
- adapter cannot expand authorization scope;
- subprocess failures become failures, never success payloads;
- malformed/ambiguous responses fail closed;
- structured responses are normalized;
- independent verification remains outside the process transport;
- immutable receipts bind successful verified execution;
- Qwen cannot use the adapter as arbitrary Python execution.

## Current exact next steps

1. Validate `planning/blender_process_executor.py` and `tests/test_blender_process_executor.py` through the active runner.
2. Fix any focused failures without changing the authorization/verification architecture.
3. Wire one real validated Blender capability into `BlenderProcessExecutor` using a request builder that preserves the exact validated arguments.
4. Add adapter-level tests proving the argument contract, fail-closed process behavior, and receipt/verification boundary.
5. Run the authorized regression suite and establish a fresh green baseline.
6. Only after that, perform the first controlled live Blender operation with independent verification.
7. Expand to rotation and marker operations only after their individual proof gates pass.
8. Continue toward closed-loop autonomous Blender execution only after execution, verification, evidence, and replanning are proven together.
9. Keep Unreal transport/live proof as a separate production-boundary gate.
10. Continue OpenHands transition work only in bounded, reversible steps; `docs/OPENHANDS_TRANSITION_GUIDE.md` is planning documentation, not proof of installed/authorized production access.

## Unreal boundary

`planning/unreal_adapter_production.py`, `planning/unreal_agent.py`, `planning/unreal_plan_executor.py`, `planning/unreal_task_planner.py`, `planning/unreal_transport_contract.py`, and `planning/unreal_transport_named_pipe.py` remain separate from the Blender gate.

`tests/test_unreal_transport_failure_boundary.py` covers timeout/disconnect normalization, cause preservation, executor context, operation identity, and transport error context. No new result is claimed for that post-687 coverage unless explicitly reported.

## OpenHands transition

`docs/OPENHANDS_TRANSITION_GUIDE.md` remains the transition plan. Keep `Atlas-Unreal-Aider` and `Blender-Agent` as separate repositories; use disposable validation before production access; progress from source -> build/test -> Unreal -> broader production execution; preserve C++ interoperability through language-neutral contracts; and retain human approval for high-impact operations.

## Do not regress

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Never move authorization or verification into `tools/blender_process.py` or `planning/blender_process_executor.py`.
- Never treat Test 313 as validation of commits made after that test unless the runner actually reports them.
- Never treat 687 passed as validation of newer code.
- Never treat 694 passed as fresh CI verification.
- Never connect live Blender until the adapter-focused regression gate is green.
- Never mark the Unreal transport test verified without a recorded result.
