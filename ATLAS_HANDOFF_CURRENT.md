# Atlas Current Development Handoff

**Updated:** August 23, 2026 — active runner development session
**Current repository HEAD before this handoff commit:** `4260cd33856c5a58b32e8a72a3624e1394137747`
**Latest write-capability implementation:** `f9312ceca1ec0f59d0f4b8a7d38ba0832075e290` (`planning/blender_tool_requests.py`)
**Latest write-capability focused tests:** `f4c7aee1c9f814012c1d119b60ba7a3fcbafc6c2` and `4260cd33856c5a58b32e8a72a3624e1394137747`
**Latest process-executor adapter:** `e9dca99382515db0ddafcbe7ff8cdd4d1f6ba755`
**Latest reported runner result:** **141 passed — PASS**
**Previous reported runner result:** **Test 313 — PASS**
**Historical development milestone:** **694 passed** (development-session result)
**Verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green

## Current state

The user has explicitly re-authorized workflow/action-runner testing and confirmed the local action runner is running. Atlas development is proceeding through the Stage 10 Blender Adapter / Real Execution Bridge gate.

The first capability seam has now been extended from a read-only `inspect_scene` request to the first controlled write capability: `move_object`. The request-builder registry contains only `inspect_scene` and `move_object`. `move_object` receives schema-validated `file_name`, `object_name`, and finite three-coordinate `location` arguments, emits a fixed write-result envelope, and saves the already-open Blender file using Blender's resolved `bpy.data.filepath`.

The new focused tests cover argument preservation, malformed-location rejection before transport, successful receipt binding, and the critical failure case where an object-not-found result is refused by independent verification. These new commits were made after the reported 141-pass result and therefore are not yet claimed as covered by that result.

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
  -> registered request builder
       -> inspect_scene (read)
       -> move_object (controlled write)
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

This is the capability-specific request-builder layer.

`build_inspect_scene_request(...)` creates a deterministic structured read request.

`build_move_object_request(...)` is the first controlled write request. It preserves the validated object name and coordinate vector, sets the object location, saves through `bpy.data.filepath`, and emits `{ok, state, details}` inside fixed `ATLAS_WRITE_START` / `ATLAS_WRITE_END` markers.

`BLENDER_PROCESS_REQUEST_BUILDERS` currently registers **only `inspect_scene` and `move_object`**. No arbitrary tool names are executable through this process path.

### `planning/blender_execution_boundary.py`

Remains the authoritative higher-level boundary. It validates tool arguments before execution, injects the executor, normalizes results, independently verifies them, and can bind immutable receipts.

The boundary—not the process builder—continues to own the authorization/execution separation and verification gate.

## Tests and verification status

### Reported results

- **141 passed — PASS**: latest user-reported focused runner result before the first controlled write-capability increment.
- **Test 313 — PASS**: previous reported runner result.
- **694 passed**: historical development-session milestone, not fresh CI verification.
- **687 passed**: last verified Python 3.9/3.11 CI baseline.

The `move_object` capability and its new focused tests were committed **after** the 141-pass report, so they are not yet claimed as covered by that result.

### New focused coverage

`tests/test_blender_tool_requests.py` verifies deterministic read-request construction and capability registration.

`tests/test_blender_execution_boundary_process.py` verifies a validated `inspect_scene` call can cross the execution boundary into the process executor and that unregistered capabilities cannot execute through it.

`tests/test_blender_tool_requests_write.py` verifies:

- `move_object` preserves the validated file/object/location arguments;
- the write request uses the expected write markers;
- tool mismatches are rejected;
- malformed coordinate vectors are rejected;
- only the intended read + write capabilities are registered.

`tests/test_blender_write_execution_gate.py` verifies:

- validated `move_object` reaches the transport with the exact expected arguments;
- successful execution can bind an immutable receipt;
- an `ok: false` object-not-found response cannot become verified success;
- malformed coordinates are rejected before the transport is called.

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
- Qwen cannot use the adapter as arbitrary Python execution;
- writes are limited to explicitly registered capabilities;
- a failed write cannot be promoted to verified success.

## Exact next steps

1. Run the new `move_object` focused tests through the active action runner.
2. Fix any failures without moving authorization or verification into the process layer.
3. Establish a fresh green focused regression baseline covering `tools/blender_process.py`, `planning/blender_process_executor.py`, the request builders, and the execution boundary.
4. Only after that gate is green, perform the **first controlled live `move_object` operation** against a deterministic Blender fixture.
5. Independently inspect the resulting object transform and require the verification layer to establish final state.
6. Bind the verified result to an immutable receipt and prove that a mismatched authoritative state becomes `BLOCKED`, not success.
7. Expand `set_object_rotation` and `create_empty_marker` through the same request-builder architecture.
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
- `tests/test_blender_tool_requests_write.py`
- `tests/test_blender_execution_boundary_process.py`
- `tests/test_blender_write_execution_gate.py`
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
- Never expand the request-builder registry beyond explicitly justified capabilities.
- Never mark the Unreal transport test verified without a recorded result.
