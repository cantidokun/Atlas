# Atlas Current Development Handoff

**Updated:** August 21, 2026 — automation handoff refresh (10:41 EDT)  
**Current repository HEAD before this handoff commit:** `a2f1ddd86e45c007ad5b5aeb2b4d4b4f9957c6f4` (`docs: refresh Atlas handoff with current repository state`)  
**Latest development test milestone:** **694 passed** (current conversation/runtime report); the 694 result is not represented as a fresh GitHub Actions verification in this handoff.  
**Previously recorded verified CI baseline:** 687 passed; Python 3.9 and 3.11 green.  
**Purpose:** canonical resume point for the next Atlas Blender-Agent development session.

## 1. Current operating state

Atlas remains actively under development. **Workflow/action-runner testing is currently paused by explicit user instruction and must not be triggered, rerun, or approved until the user explicitly authorizes it.** Offline-safe development may continue. Do not treat the previously verified 687-pass CI result as validation for code added after that baseline, and do not treat the current 694-pass development report as GitHub Actions verification unless a fresh runner result is explicitly recorded.

The current development loop is progressing offline-safe work while the local action runner is available only when explicitly authorized for testing. No workflow/action-runner test was triggered by this handoff update.

The repository `main` branch was at `a2f1ddd86e45c007ad5b5aeb2b4d4b4f9957c6f4` immediately before this documentation refresh. This handoff commit intentionally records the current development/test state without claiming a new workflow verification.

## 2. Scope

This track is **Blender Agent only**. Unreal Agent work is out of scope for this development thread.

Photogrammetry remains upstream: dedicated photogrammetry software creates the initial 3D reconstruction; Blender receives it for analysis, cleanup, correction, optimization, and preparation.

Atlas remains focused on soccer/sports digital-twin production workflows.

## 3. Architecture currently established

```text
Qwen / AI
  ↓ reason + propose
structured Blender reasoning
  ↓
BlenderTaskIntent
  ↓
capability + argument validation
  ↓
ActionPlan
  ↓
explicit authorization
  ↓
controlled execution boundary
  ↓
immutable execution receipt
  ↓
independent fresh verification
  ↓
verified agent state / evidence
  ↓
replan if objective remains unsatisfied
```

Qwen is never execution authority. A successful production-tool response is never sufficient to establish final state.

Core generic primitives include action/evidence plans, target-state evaluation, verification plans, action authorization, replan authorization, deterministic futures, future execution/recovery, runtime integrity, audit trail, immutable Blender execution receipts, task runtime policy, and declarative task definitions.

The generic architecture contract is documented in `docs/ATLAS_ARCHITECTURE_CONTRACT.md`.

## 4. Current declarative task/runtime layer

### `planning/task_definition.py`

`AtlasTaskDefinition` is the task-specific declarative boundary. It carries evidence requests, action specifications, target-state evaluation, allowed action tools, write policy, verification policy, and task metadata. Construction rejects empty task identity, missing evidence/actions, missing tool allowlists, unauthorized action tools, and write-capable tasks that disable post-action verification.

### `planning/task_runtime.py`

Provides the generic bridge from a task definition to `ConditionalPlanningOrchestrator`:

- `build_orchestrator(task)`
- `validate_task_runtime(task)`
- `prepare_task_runtime(task)`

Validation occurs before evidence or writes, and task-specific data does not create a second orchestration architecture.

### Architecture contract

`docs/ATLAS_ARCHITECTURE_CONTRACT.md` formalizes Qwen/Atlas/Blender authority, evidence-before-write, authorization, immutable receipts, fresh verification, zero-write behavior, fail-closed behavior, and promotion criteria.

## 5. Agent state + evidence-driven replanning

Replanning consumes a **verified** Blender observation and either:

- stops when the objective is verified satisfied; or
- produces a new `BlenderTaskIntent` for the normal planning/authorization path.

An existing authorized plan is never silently mutated by the replanner.

## 6. Qwen → Atlas reasoning contract

Structured Qwen output is constrained before it can become an executable intent. Current coverage rejects malformed confidence, empty objective/observation/action/evidence fields, non-object action arguments, and unknown Blender tools at the capability-planning boundary.

The latest correction aligned the Qwen reasoning test with the canonical Blender rotation schema using `rotation_degrees` and the required file/object fields.

## 7. Model/runtime setup

The current handoff baseline uses **Qwen `qwen3:8b` through Ollama** as the local reasoning model, with Atlas enforcing the planning, authorization, execution, receipt, verification, and replanning boundaries around it. The Blender target runtime baseline is **Blender 4.4.3**. The local Atlas runtime is referred to as **`atlas-local`** in the established development context.

Qwen remains a planner/reasoner, not an execution authority; it cannot turn the Blender adapter into an arbitrary Python execution channel.

## 8. Latest test status

**Current development milestone: 694 passed.** This result is preserved from the active Atlas development session and is the newest test outcome available in the current conversation context. It should be treated as a development-session result, not as a newly verified GitHub Actions result, because workflow/action-runner testing remains paused.

**Previously verified CI milestone: 687 passed.** The corresponding GitHub Actions run was green on both:

- Python 3.9
- Python 3.11

The 687-pass result remains the latest explicitly recorded GitHub Actions baseline in the repository handoff history. Any code added after that baseline requires fresh CI validation once workflow testing is authorized.

Previously established live proof includes goalpost conditional execution and generic collection creation. Other capabilities, including object rotation and marker creation, remain subject to fresh live proof where applicable.

## 9. Current development stage

### Stage 10 — Blender Adapter / Real Execution Bridge

**CURRENT**

The next implementation target is the adapter that maps an already-authorized Atlas action into a controlled real Blender execution request and maps the resulting Blender response/evidence back into Atlas.

Required properties:

- capability restrictions remain enforced;
- exact validated arguments are preserved;
- authorization scope cannot expand at the adapter;
- execution is deterministic and observable;
- results are normalized into the existing Blender result contract;
- verification remains independent;
- malformed/ambiguous responses fail closed;
- evidence can be returned to agent state/replanning;
- Qwen cannot use the adapter as an arbitrary Python execution channel.

Do not add a second bespoke execution architecture. Reuse the existing planning, authorization, receipt, verification, and state machinery.

## 10. Concrete files/tools currently relevant

Core architecture and planning/runtime files currently documented as relevant include:

- `planning/task_definition.py`
- `planning/task_runtime.py`
- `planning/blender_tool_schema.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `tools/blender.py`
- `tools/blender_transform.py`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `ATLAS_HANDOFF_CURRENT.md`

The established flow uses `BlenderTaskIntent`, `ActionPlan`, `ConditionalPlanningOrchestrator`, authorization/replan gates, execution receipts, independent verification, and Qwen structured reasoning. The Blender adapter must integrate with those existing contracts rather than creating a parallel path.

## 11. Offline-safe work permitted during runner pause

Continue development that does not require the action runner or real Blender connection, including:

- adapter contracts and schemas;
- deterministic request/result normalization;
- authorization-boundary checks;
- immutable receipt and evidence-binding hardening;
- malformed/ambiguous response handling;
- runtime policy validation;
- continuation/recovery identity checks;
- static architecture/invariant checks;
- focused unit tests that do not invoke workflow/action-runner infrastructure;
- diagnostics and documentation.

Do not make changes that introduce a parallel execution path or weaken the existing authorization/verification boundary merely to avoid the runner.

## 12. Blender integration gate

Do **not** connect to the user's real Blender environment yet merely because the architecture looks close.

When workflow testing is eventually authorized, the adapter must first have focused tests and a fresh green CI result. Only then should the first live Blender proof be prepared:

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

Only after that should the loop be expanded toward autonomous multi-step Blender work.

## 13. Regression requirements

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

## 14. Exact resume procedure after runner authorization

1. Read this handoff first.
2. Inspect current `main`/HEAD and identify commits added since the 687-pass verified CI baseline.
3. Inspect fresh GitHub Actions status only after workflow testing is explicitly authorized.
4. Reconfirm the 694-pass development milestone against the current checkout before treating it as a promotion candidate.
5. Implement the smallest coherent Blender adapter increment.
6. Add focused tests before considering the increment complete.
7. Run the applicable regression gate once authorized and fix any failures.
8. Only after the adapter tests are green, prepare the first controlled live Blender connection.
9. Prove one small live operation with independent verification.
10. Expand toward rotation/marker and then closed-loop autonomous Blender behavior only after their specific proof gates pass.

## 15. Product architecture reminders

- Atlas is a soccer/sports digital-twin production platform, not a generic gym-digital-twin system.
- Photogrammetry is upstream of Blender.
- Blender receives the initial reconstruction and performs analysis, cleanup, correction, optimization, and preparation.
- Unreal is a later complementary production environment.
- Canonical Digital Twin identity/state must remain distinct from `.blend` representations and shot-specific variants.

## 16. Do not regress

- Do not give Qwen direct Blender execution authority.
- Do not allow automatic retry after failed writes.
- Do not silently mutate an authorized plan during replanning.
- Do not declare completion from a write response alone.
- Do not make goalpost-specific behavior the generic architecture.
- Do not trigger workflow/action-runner tests during the current pause.
- Do not represent 687 passed as validation of newer code.
- Do not represent 694 passed as fresh GitHub Actions verification without an actual authorized runner result.
- Do not connect live Blender until the adapter's focused tests and later authorized regression gates are green.
