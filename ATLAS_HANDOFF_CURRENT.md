# Atlas Current Development Handoff

**Updated:** August 23, 2026 — active Atlas development
**Latest reported runner result:** **141 passed — PASS**
**Previous reported runner result:** **Test 313 — PASS**
**Historical development milestone:** **694 passed** (development-session result; not fresh CI)
**Verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green

## Current state

Atlas is actively being advanced through the Stage 10 Blender Adapter / Real Execution Bridge gate. Workflow/action-runner testing is explicitly authorized again and the local action runner is available.

The Blender execution architecture has progressed from a fail-closed subprocess boundary to a transport adapter and then to explicit capability-specific request builders. Two capabilities are now registered:

- `inspect_scene` — controlled read capability
- `move_object` — first controlled write capability

The `move_object` implementation and its focused tests were added after the reported 141-pass result. They require a fresh runner result before being considered verified.

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

Qwen is planner/reasoner only and never production execution authority. Transport responses do not establish final state. Authorization and verification remain outside the low-level process layer. Authorized plans must not be silently mutated during replanning.

Generic contract: `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

## Files/tools added or changed

### `tools/blender_process.py`

`run_checked_blender(...)` is the fail-closed subprocess boundary. It rejects non-zero exits, startup failures, timeouts, missing result markers, empty payloads, invalid JSON, and non-object JSON results.

### `planning/blender_process_executor.py`

`BlenderProcessExecutor` is transport-only. It receives an already-selected tool and validated arguments, resolves a registered request builder, requires a `BlenderProcessRequest`, and delegates to `run_checked_blender`.

It does not authorize tools, broaden scope, verify scene state, or create receipts.

### `planning/blender_tool_requests.py`

Capability-specific request-builder layer.

`build_inspect_scene_request(...)` creates a deterministic read request and emits a structured scene inspection result.

`build_move_object_request(...)` creates the first controlled write request. It preserves the validated `file_name`, `object_name`, and finite three-coordinate `location`; sets the target object's location; saves through Blender's resolved `bpy.data.filepath`; and emits `{ok, state, details}` between `ATLAS_WRITE_START` / `ATLAS_WRITE_END` markers.

`BLENDER_PROCESS_REQUEST_BUILDERS` registers only `inspect_scene` and `move_object`.

### `planning/blender_execution_boundary.py`

Remains the authoritative higher-level boundary. It validates tool arguments before transport, normalizes results, performs independent verification, and supports immutable receipt binding.

### `planning/blender_verification.py`

`verify_blender_execution(...)` is fail-closed: the result must be a `BlenderExecutionResult`, belong to the expected tool, and report success. A failed write cannot become verified success.

### `planning/blender_execution_receipt.py`

`BlenderExecutionReceipt` immutably binds the tool, argument digest, and normalized-result digest.

## Tests and outcomes

### Explicitly reported by the user

- **Test 313 passed** — reported August 23, 2026.
- **141 passed** — reported August 23, 2026.

The 141-pass result predates the current `move_object` implementation, so it does not validate those newer commits.

### Historical / baseline

- **694 passed** — historical development-session milestone; not fresh CI.
- **687 passed** — verified CI baseline across Python 3.9 and 3.11; not validation of newer code.

### Focused coverage

`tests/test_blender_process.py` — subprocess failure, timeout/startup, marker/payload, and JSON/result validation.

`tests/test_blender_process_executor.py` — transport delegation, registered-builder enforcement, request-shape validation, and failure propagation.

`tests/test_blender_tool_requests.py` — deterministic `inspect_scene` request construction, mismatch/invalid-input rejection, and capability restrictions.

`tests/test_blender_execution_boundary_process.py` — validated `inspect_scene` crossing the execution boundary, exact command/path/marker propagation, and unregistered capability rejection.

`tests/test_blender_tool_requests_write.py` — exact `move_object` argument preservation, write markers, mismatch rejection, malformed coordinate rejection, and restricted registry.

`tests/test_blender_write_execution_gate.py` — validated `move_object` transport, receipt binding, failed-write verification rejection, and pre-transport argument rejection.

## Model/runtime setup

- Qwen: `qwen3:8b` via Ollama
- Blender: **4.4.3**
- Local Atlas runtime: `atlas-local`
- Qwen remains planner/reasoner only
- Photogrammetry is upstream of Blender; Blender handles analysis, cleanup, correction, optimization, and preparation for Atlas soccer/sports digital-twin workflows.

## Current known issues / unverified areas

1. `move_object` has not yet been covered by a fresh runner result.
2. The first controlled live Blender operation has not yet been performed.
3. Independent verification of a real post-write Blender state still needs to be demonstrated.
4. Receipt binding has focused test coverage but needs proof in the live execution path.
5. `set_object_rotation` and `create_empty_marker` are not yet bound to the process-request architecture.
6. Unreal transport/live proof remains a separate production-boundary gate.
7. OpenHands transition documentation exists, but is not evidence of installed/authorized production access.

## Exact next steps

1. Run the new focused `move_object` tests through the active action runner.
2. Fix failures without moving authorization or verification into `tools/blender_process.py`, `planning/blender_process_executor.py`, or `planning/blender_tool_requests.py`.
3. Establish a fresh green focused regression baseline covering the subprocess boundary, process executor, request builders, and execution boundary.
4. After that gate is green, perform the **first controlled live `move_object` operation** against a deterministic Blender fixture.
5. Independently inspect the resulting object transform and require the verification layer to establish final state.
6. Bind the verified result to an immutable `BlenderExecutionReceipt`.
7. Prove a mismatched authoritative state becomes `BLOCKED`, never success.
8. Add `set_object_rotation` through the same request-builder architecture.
9. Add `create_empty_marker` through the same architecture.
10. Continue toward closed-loop execution only after execution, verification, evidence, and replanning are proven together.
11. Keep Unreal transport/live proof separate from the Blender gate.
12. Continue OpenHands transition work only in bounded, reversible steps; do not treat planning documentation as proof of production access.

## Do not regress

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Never move authorization or verification into the low-level process/request-builder layers.
- Never treat 141 passed as validation of commits made after that result.
- Never treat 687 or 694 passed as fresh validation of newer code.
- Never connect live Blender until the adapter-focused regression gate is green.
- Never expand the capability registry without an explicit validated capability and focused tests.
- Never mark Unreal transport/live proof verified without a recorded result.
