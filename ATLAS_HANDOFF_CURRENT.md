# Atlas Current Development Handoff

**Updated:** August 23, 2026 — active Atlas development
**Current repository tip:** `895709a978bc7faa33118cb36fec59f5cb520bef`
**Latest reported full-suite result:** **737 failed / collection error**
**Previous reported focused result:** **141 passed — PASS**
**Earlier reported result:** **Test 313 passed**
**Historical development milestone:** **694 passed** (development-session result; not fresh CI)
**Verified CI baseline:** **687 passed**, Python 3.9 and 3.11 green

## Current state

Atlas is actively advancing through Stage 10 — Blender Adapter / Real Execution Bridge. Workflow/action-runner testing is authorized and the local runner is available.

The latest full-suite failure was a **test-collection ImportError**, not a 737-test behavioral failure. `tests/test_unreal_transport_failure_boundary.py` imported `planning.unreal_adapter_production`, but that module does not exist in the current repository. The related production Unreal transport stack (`unreal_adapter_production`, `unreal_transport_contract`, `unreal_transport_named_pipe`, and the referenced production executor layer) is not present; the repository currently contains the engine-neutral `planning/unreal_adapter_v01.py` contract instead.

To restore collection without inventing an incomplete Unreal production implementation, the stale Unreal transport regression test was removed in commit `895709a978bc7faa33118cb36fec59f5cb520bef`. The Unreal production transport remains a separate future gate and is explicitly **not verified**.

## Blender architecture

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
  -> verified state / replanning
```

Qwen remains planner/reasoner only. Transport responses do not establish final state. Authorization, verification, and receipt binding remain outside the low-level process/request-builder layers.

## Current Blender implementation

- `tools/blender_process.py` — fail-closed Blender subprocess boundary.
- `planning/blender_process_executor.py` — transport-only executor.
- `planning/blender_tool_requests.py` — deterministic capability request builders.
- `planning/blender_execution_boundary.py` — authoritative execution boundary.
- `planning/blender_verification.py` — fail-closed independent verification.
- `planning/blender_execution_receipt.py` — immutable receipt binding.
- `inspect_scene` is registered as the controlled read capability.
- `move_object` is the first controlled write capability.

Focused suites:

- `tests/test_blender_process.py`
- `tests/test_blender_process_executor.py`
- `tests/test_blender_tool_requests.py`
- `tests/test_blender_execution_boundary_process.py`
- `tests/test_blender_tool_requests_write.py`
- `tests/test_blender_write_execution_gate.py`

The `move_object` implementation was added after the reported 141-pass result and therefore still requires fresh validation.

## Test status

### Latest failure

The user reported:

```text
Run python -m pytest -q
ERROR collecting tests/test_unreal_transport_failure_boundary.py
ModuleNotFoundError: No module named 'planning.unreal_adapter_production'
1 warning, 1 error in 0.86s
Process completed with exit code 2
```

This means the reported **737 failed** result is currently classified as **collection failure / suite blocked**, not as 737 failing behavioral tests.

The stale test has now been removed. A fresh full-suite runner result is required before declaring the suite green.

### Prior results

- **141 passed — PASS**: latest focused result before the `move_object` increment.
- **Test 313 passed — PASS**: earlier focused result.
- **694 passed**: historical development-session milestone; not fresh CI.
- **687 passed**: verified Python 3.9/3.11 CI baseline; does not validate newer code.

## Model/runtime

- Qwen `qwen3:8b` via Ollama.
- Blender 4.4.3.
- Local Atlas runtime: `atlas-local`.
- Qwen is planner/reasoner only.
- Photogrammetry remains upstream of Blender; Blender performs analysis, cleanup, correction, optimization, and preparation for Atlas soccer/sports digital-twin workflows.

## Known issues / unverified areas

1. A fresh full-suite result is required after removing the stale Unreal collection blocker.
2. `move_object` has not yet received a fresh post-141 validation result.
3. The first controlled live Blender operation has not yet been performed.
4. Independent verification of a real post-write Blender state remains unproven.
5. Receipt binding needs proof in the live execution path.
6. `set_object_rotation` and `create_empty_marker` are not yet bound to the process-request architecture.
7. Unreal production transport remains a separate future gate; only `planning/unreal_adapter_v01.py` is currently present.
8. OpenHands transition documentation is planning material, not evidence of production access.

## Exact next steps

1. Run `python -m pytest -q` again through the active action runner now that the stale Unreal collection test is removed.
2. If collection succeeds, fix the smallest actual behavioral failure(s) first.
3. Establish a fresh green baseline covering the full suite and the new Blender process/write architecture.
4. Then perform the first controlled live `move_object` operation against a deterministic Blender fixture.
5. Independently verify the resulting transform and require verification to establish final state.
6. Bind the verified result to an immutable `BlenderExecutionReceipt`.
7. Prove executor/write response + wrong authoritative state becomes `BLOCKED`, never success.
8. Bind `set_object_rotation` through the same request-builder architecture.
9. Bind `create_empty_marker` through the same architecture.
10. Keep Unreal production transport/live proof separate until its missing production adapter/transport architecture is deliberately implemented and tested.
11. Continue toward closed-loop execution only after execution, verification, evidence, and replanning are proven together.

## Do not regress

- Never give Qwen direct production execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan.
- Never declare completion from a transport/write response alone.
- Never move authorization or verification into `tools/blender_process.py`, `planning/blender_process_executor.py`, or `planning/blender_tool_requests.py`.
- Never treat 141 passed as validation of newer commits.
- Never treat 687 or 694 passed as fresh validation of newer code.
- Never mark the suite green until a fresh runner result covers the current tree.
- Never recreate a stale Unreal regression by adding speculative production modules merely to satisfy imports.
- Never connect live Blender until the adapter-focused regression gate is green.
