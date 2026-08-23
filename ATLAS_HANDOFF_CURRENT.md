# Atlas Current Development Handoff

**Updated:** August 23, 2026 — active runner development session
**Current repository HEAD:** `bb3818223db398895699a646fd2725cfed8a15f7`
**Latest capability binding:** `89ca4c7c979ffc0244fd61a026f36d66132c1d74` (`planning/blender_tool_requests.py`)
**Latest capability binding tests:** `fdd0abc9c171c3a7a52221d91e7bbae161a2e15c` and `bb3818223db398895699a646fd2725cfed8a15f7`
**Latest process-executor adapter:** `e9dca99382515db0ddafcbe7ff8cdd4d1f6ba755`
**Latest reported runner result:** **141 passed — PASS**
**Previous reported runner result:** **Test 313 — PASS**
**Historical development milestone:** **694 passed** (development-session result)
**Verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green

## Current state

The user has explicitly re-authorized workflow/action-runner testing and confirmed the local action runner is running. Atlas development is proceeding through the Stage 10 Blender Adapter / Real Execution Bridge gate.

The latest work makes the first real capability binding through the controlled process layer. `inspect_scene` is now represented by a deterministic request builder and registered as the only capability in the new process-request registry. This keeps the transport adapter narrow while proving the architecture can bind a real validated Blender capability without giving the process layer authorization authority.

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
  -> registered request builder (`inspect_scene`)
  -> fail-closed Blender subprocess
  -> normalized result
  -> independent verification
  -> immutable execution receipt
  -> verified agent state / replanning
```

Qwen is never execution authority. Production-tool responses are never sufficient to establish final state. Authorized plans are never silently mutated during replanning.

Generic contract: `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

## Current implementation

### `tools/blender_process.py`

`run_checked_blender(...)` is the fail-closed low-level process boundary. It rejects non-zero exits, startup failures, timeouts, missing markers, empty payloads, invalid JSON, and non-object JSON results while preserving useful diagnostics.

### `planning/blender_process_executor.py`

`BlenderProcessExecutor` is transport-only. It receives an already-selected tool and copied validated arguments, resolves a registered request builder, validates that the builder returns `BlenderProcessRequest`, and delegates to `run_checked_blender`.

It does not authorize tools, broaden capability scope, verify scene state, or create receipts.

### `planning/blender_tool_requests.py`

This is the first capability-specific request-builder layer. `build_inspect_scene_request(...)` converts the validated `inspect_scene` call into a deterministic `BlenderProcessRequest` with the exact file name and fixed result markers. `BLENDER_PROCESS_REQUEST_BUILDERS` currently registers **only `inspect_scene`**.

This intentionally establishes a one-capability integration seam before expanding to write operations or more complex tools.

### `planning/blender_execution_boundary.py`

Remains the authoritative higher-level boundary. It validates tool arguments before execution, injects the executor, normalizes results, independently verifies them, and can bind immutable receipts.

## Tests and verification status

### Reported results

- **141 passed — PASS**: latest user-reported focused runner result before this capability-binding increment.
- **Test 313 — PASS**: previous reported runner result.
- **694 passed**: historical development-session milestone, not fresh CI verification.
- **687 passed**: last verified Python 3.9/3.11 CI baseline.

The new capability-binding commits were made **after** the 141-pass report, so they are not yet claimed as covered by that result.

### New focused coverage

`tests/test_blender_tool_requests.py` verifies:

- deterministic request construction;
- tool/request-builder mismatch rejection;
- empty filename rejection;
- registry contains only the intended capability.

`tests/test_blender_execution_boundary_process.py` verifies:

- a validated `inspect_scene` call can flow through `BlenderExecutionBoundary` into `BlenderProcessExecutor`;
- the expected Blender command, file path, and result markers reach the transport layer;
- an unregistered capability cannot execute through this process adapter.

`tests/test_blender_process.py` and `tests/test_blender_process_executor.py` remain the lower-level regression suites.

## Model/runtime

- Qwen `qwen3:8b` via Ollama.
- Blender 4.4.3.
- Local Atlas runtime: `atlas-local`.
- Qwen remains planner/reasoner only.

Photogrammetry remains upstream of Blender; Blender performs analysis, cleanup, correction, optimization, and preparation for Atlas soccer/sports digital-twin workflows.

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

## Exact next steps

1. Run the focused capability-binding tests through the active action runner.
2. Fix any failures without moving authorization or verification into the process layer.
3. Extend the request-builder registry to **one controlled write capability**, preferably an existing validated operation with established schema/verification coverage.
4. Add tests proving the write request preserves the exact validated arguments and cannot be invoked through an unregistered tool name.
5. Integrate that capability through the existing receipt/verification machinery and establish a fresh green regression baseline.
6. Only after the adapter gate is green, perform the first controlled live Blender operation with independent verification.
7. Expand to rotation and marker operations through the same architecture, not parallel execution paths.
8. Continue toward closed-loop autonomous Blender execution only after execution, verification, evidence, and replanning are proven together.
9. Keep Unreal transport/live proof as a separate production-boundary gate.
10. Continue OpenHands transition work only in bounded, reversible steps; `docs/OPENHANDS_TRANSITION_GUIDE.md` is planning documentation, not proof of installed/authorized production access.

## Concrete files/tools

Blender/planning/runtime:

- `planning/task_definition.py`
- `planning/task_runtime.py`
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_result_contract.py`
- `planning/blender_verification.py`
- `planning/blender_process_executor.py`
- `planning/blender_tool_requests.py`
- `tools/blender.py`
- `tools/blender_transform.py`
- `tools/blender_process.py`
- `tests/test_blender_process.py`
- `tests/test_blender_process_executor.py`
- `tests/test_blender_tool_requests.py`
- `tests/test_blender_execution_boundary_process.py`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `docs/OPENHANDS_TRANSITION_GUIDE.md`
- `ATLAS_HANDOFF_CURRENT.md`

## Do not regress

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Never move authorization or verification into `tools/blender_process.py`, `planning/blender_process_executor.py`, or `planning/blender_tool_requests.py`.
- Never treat 141 passed as validation of commits made after that result unless a new runner result covers them.
- Never treat 687 passed as validation of newer code.
- Never treat 694 passed as fresh CI verification.
- Never connect live Blender until the adapter-focused regression gate is green.
- Never expand the request-builder registry broadly before the first capability seam is validated.
- Never mark the Unreal transport test verified without a recorded result.
