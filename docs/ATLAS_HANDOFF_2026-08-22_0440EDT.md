# Atlas Development Handoff — August 22, 2026 04:40 EDT

## Current state

Atlas remains actively under development. Workflow/action-runner testing is authorized as part of normal development and does not require separate per-run user authorization.

Current `main` HEAD: `e0546f1d07a1555cd5b0eaa0cf577ed52673ecb6` (`docs: refresh current Atlas handoff with latest adapter-boundary regression state`).

Latest implementation commit: `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` (`Test named-pipe failure propagation through adapter`).

Latest recorded development-session test milestone: **694 passed**. This is not a current GitHub Actions result.

## Architecture

```text
Qwen / AI
  ↓ structured reasoning
Task Intent
  ↓ capability + argument validation
ActionPlan
  ↓ explicit authorization
controlled production adapter
  ↓ immutable execution receipt
independent fresh verification
  ↓ verified agent state / evidence
replan if objective remains unsatisfied
```

Qwen is a planner/reasoner, never execution authority. Production-tool success responses do not establish final state; independent verification does.

The generic architecture contract is `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

Core established layers include action/evidence plans, target-state evaluation, verification plans, authorization and replan gates, deterministic futures/recovery, runtime integrity, audit trail, immutable execution receipts, declarative task definitions, task runtime policy, controlled production adapters, and transport failure boundaries.

Photogrammetry remains upstream of Blender: dedicated photogrammetry software produces the initial reconstruction, then Blender performs analysis, cleanup, correction, optimization, and preparation. Atlas remains focused on soccer/sports digital-twin production workflows.

## Declarative/runtime files

- `planning/task_definition.py` — `AtlasTaskDefinition`; validates task identity, evidence/actions, tool allowlists, authorization, write policy, and verification policy.
- `planning/task_runtime.py` — `build_orchestrator(task)`, `validate_task_runtime(task)`, `prepare_task_runtime(task)`; bridges declarative tasks to `ConditionalPlanningOrchestrator` without creating a second architecture.
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `tools/blender.py`
- `tools/blender_transform.py`

The established Blender path is Qwen structured reasoning → `BlenderTaskIntent` → validation → `ActionPlan` → authorization → controlled execution → immutable receipt → independent verification → replanning.

## Model/runtime

- Reasoning model: **Qwen `qwen3:8b` via Ollama**.
- Blender target runtime: **Blender 4.4.3**.
- Local Atlas runtime name used in the development context: **`atlas-local`**.

Qwen cannot use the production adapter as an arbitrary Python execution channel.

## Latest implementation/test additions

### Blender subprocess verification hardening

Commit `832ae2568df1197e96bfdb363f70c456bba44a2c` added `tests/test_blender_process.py` covering `run_checked_blender` behavior for non-zero Blender process exit, invalid JSON between markers, JSON arrays where an object is required, and valid structured JSON objects.

**Result:** no fresh test result is claimed in this historical handoff. The test imports `tools.blender_process.run_checked_blender`; the prior repository inspection did not surface a tracked `tools/blender_process.py`. Reconcile the implementation/import surface before promoting this historical test.

### Unreal transport failure boundary

Commit `6e0c2c1e894615b47934cb17b7d7e66712e75f3c` added `tests/test_unreal_transport_failure_boundary.py` covering propagation of `NamedPipeTransportTimeoutError` and `NamedPipeTransportDisconnectedError` through the Unreal adapter and planner/transport components.

**Result:** no fresh test result is claimed in this historical handoff.

## Current development gate

### Stage 10 — Blender Adapter / Real Execution Bridge

This remains the primary gate.

The adapter must map an already-authorized Atlas action into a controlled Blender execution request and map the structured Blender response/evidence back into Atlas without expanding authorization scope.

Required properties:

- exact validated arguments preserved;
- capability restrictions enforced;
- authorization cannot be bypassed or expanded;
- deterministic, observable execution;
- process/transport failures become failures, not successful payloads;
- structured responses normalized and validated;
- malformed/ambiguous responses fail closed;
- immutable receipt/evidence binding retained;
- independent verification retained;
- evidence can feed agent state/replanning;
- no arbitrary Python execution channel through the adapter.

Do not introduce a parallel bespoke execution architecture.

The Unreal transport regression is a complementary production-boundary hardening track and does not complete the Blender gate.

## Next work

1. Reconcile `tests/test_blender_process.py` with the actual implementation/import surface.
2. Implement or correct the controlled Blender subprocess helper if genuinely missing.
3. Harden deterministic request/result normalization and malformed-response handling.
4. Continue authorization-boundary, immutable-receipt, evidence-binding, runtime-policy, continuation/recovery, and static architecture/invariant hardening.
5. Continue Unreal named-pipe/adapter failure normalization without treating it as live Unreal proof.
6. Run the appropriate focused and workflow/action-runner validation for meaningful implementation increments.
7. Keep documentation and diagnostics synchronized with implementation state.

## Resume sequence

1. Read this handoff and inspect current `main`.
2. Identify all commits after the historical 687-pass verified CI baseline.
3. Reconcile and focused-test `tests/test_blender_process.py` / `tools.blender_process`.
4. Inspect and focused-test `tests/test_unreal_transport_failure_boundary.py`.
5. Obtain and inspect a fresh GitHub Actions result for the current code.
6. Reconfirm the 694-pass development milestone against the current checkout before promotion.
7. Implement the smallest coherent Blender adapter increment and add focused tests.
8. Run the applicable regression gate and fix failures.
9. Only after adapter tests and regression gates are green, prepare the first controlled live Blender proof.
10. Prove one authorized Blender operation with independent verification.
11. Expand toward rotation/marker and then closed-loop autonomous Blender behavior only after their specific proof gates pass.
12. Treat Unreal live transport proof as a separate gate.

## Regression requirements

Preserve coverage for zero-write satisfied tasks, exact authorized ordering, mandatory post-write verification, `BLOCKED` on verification failure, recovery gates, receipt mismatches, malformed/wrong executor results, continuation identity, authorized versus unauthorized replans, malformed Qwen reasoning, unknown Blender tools, adapter authorization bypass attempts, subprocess non-zero exits, malformed JSON, non-object payloads, malformed/ambiguous Blender responses, Unreal timeout/disconnect failure propagation, and retention of Unreal operation context.

## Do not regress

- Do not give Qwen direct production-tool authority.
- Do not automatically retry failed writes.
- Do not silently mutate authorized plans during replanning.
- Do not declare completion from write/transport success alone.
- Do not represent historical test results as proof for newer code.
- Do not connect live Blender before its adapter and regression gates are green.
- Do not mark historical tests complete without their actual focused result.
