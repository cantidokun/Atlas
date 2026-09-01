# Atlas Development Handoff — August 21, 2026 16:42 EDT

## Current state

Atlas remains actively under development. Workflow/action-runner testing is authorized as part of normal development and does not require separate per-run user authorization.

The current repository tip before this handoff refresh is `482250596a9d6f358f43ce1cb35d53cd650fee38` (`docs: refresh Atlas handoff with current repository state`). No newer implementation commit was identified in the current repository history; the commits since the implementation baseline are handoff/documentation commits.

## Architecture

Current authority flow:

`Qwen / AI → structured Blender reasoning → BlenderTaskIntent → capability/argument validation → ActionPlan → explicit authorization → controlled execution boundary → immutable execution receipt → independent fresh verification → verified agent state/evidence → replan if objective remains unsatisfied`

Qwen is a planner/reasoner, never execution authority. A successful Blender response does not establish final state; independent verification is mandatory.

The generic architecture contract is `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

The current declarative/runtime layer is:

- `planning/task_definition.py` — `AtlasTaskDefinition`; task-specific evidence, actions, target-state evaluation, tool allowlist, write policy, verification policy, and metadata.
- `planning/task_runtime.py` — `build_orchestrator(task)`, `validate_task_runtime(task)`, `prepare_task_runtime(task)`; bridges task definitions into `ConditionalPlanningOrchestrator` without creating a second orchestration architecture.
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `tools/blender.py`
- `tools/blender_transform.py`

Evidence-driven replanning consumes a verified Blender observation and either stops on verified satisfaction or produces a new `BlenderTaskIntent`. It does not silently mutate an existing authorized plan.

## Model/runtime

- Local reasoning model: **Qwen `qwen3:8b` via Ollama**.
- Blender target runtime: **Blender 4.4.3**.
- Established local runtime name: **`atlas-local`**.
- Qwen remains outside the execution-authority boundary and must not become an arbitrary Python execution channel.

Photogrammetry remains upstream of Blender: dedicated photogrammetry software produces the initial reconstruction; Blender performs analysis, cleanup, correction, optimization, and preparation. Atlas remains focused on soccer/sports digital-twin production workflows.

## Tests and verification status

**Latest development-session result:** **694 passed**.

**Latest explicitly recorded verified CI baseline:** **687 passed**, with Python **3.9** and **3.11** green. Code added after that baseline must receive fresh regression validation before being treated as verified.

Previously established live proof includes goalpost conditional execution and generic collection creation. Object rotation and marker creation remain subject to fresh live proof where applicable.

A prior Qwen reasoning correction aligned the rotation test with the canonical schema using `rotation_degrees` plus the required file/object fields.

## Current development stage

### Stage 10 — Blender Adapter / Real Execution Bridge

The next implementation target is the controlled adapter mapping an already-authorized Atlas action into a real Blender execution request and mapping the Blender response/evidence back into Atlas.

The adapter must:

- enforce existing capability restrictions;
- preserve exact validated arguments;
- prevent authorization scope expansion;
- be deterministic and observable;
- normalize results into the existing Blender result contract;
- retain independent verification;
- fail closed on malformed or ambiguous responses;
- return evidence suitable for agent state/replanning;
- never provide Qwen an arbitrary Python execution path.

Reuse the existing planning, authorization, receipt, verification, and state machinery. Do not introduce a parallel execution architecture.

## Required regression coverage

Preserve and extend coverage for:

- already-satisfied → zero writes;
- unsatisfied → exact authorized order;
- successful write → verification still mandatory;
- verification failure → `BLOCKED`;
- action failure → recovery gate;
- mutated arguments/result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized fresh-evidence replan → accepted;
- unauthorized replan → rejected;
- malformed Qwen reasoning → rejected;
- unknown/non-capability Blender tool → rejected;
- adapter cannot bypass authorization;
- adapter preserves validated arguments;
- adapter normalizes executor results;
- adapter fails closed on malformed/ambiguous responses.

## Exact next steps

1. Read this handoff and `ATLAS_HANDOFF_CURRENT.md`.
2. Inspect current `main`/HEAD and distinguish implementation commits from documentation commits since the 687-pass CI baseline.
3. Reconfirm the 694-pass development result against the current checkout before treating it as a promotion candidate.
4. Implement the smallest coherent Blender adapter increment.
5. Add focused tests for the adapter contract and failure modes.
6. Run the appropriate GitHub Actions/workflow and local regression validation for the current code.
7. Once the relevant regression gates are green, prepare one controlled live Blender operation.
8. Independently verify that live operation.
9. Expand toward rotation/marker and then closed-loop autonomous Blender behavior only after their specific proof gates pass.

## Do not regress

- Never give Qwen direct Blender execution authority.
- Never automatically retry failed writes.
- Never silently mutate an authorized plan during replanning.
- Never declare completion from a write response alone.
- Never turn goalpost-specific behavior into the generic architecture.
- Never represent historical regression results as proof for later code.
- Never connect live Blender before the adapter's focused tests and appropriate regression gates are green.
