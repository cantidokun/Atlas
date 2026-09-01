# Atlas Current Development Handoff

**Updated:** September 1, 2026 — active development.  
**Branch:** `feat/blender-coordinator-result-integrity-final`  
**PR:** #42 (`Harden Blender execution result integrity`)  
**Current head:** `8c4d32ee46c1768c05f4283876ae3c7d758e8676`  
**Purpose:** canonical resume point for the next Atlas development session.

## Current milestone

**AUTONOMOUS ADMISSION / RESTART-RECOVERY / GENERALIZED SEQUENCE / PRODUCTION-GOAL ORCHESTRATION / EVIDENCE-DRIVEN REPLANNING SEAM**

Atlas has moved from deterministic, authorization-bound Blender execution into a production-facing autonomous admission, sequencing, and goal-orchestration layer. The runtime has a defined startup safety boundary: persisted interrupted executions must be reconciled before autonomous execution can become READY.

The current composition is:

```text
AutonomousProductionGoal
 -> AutonomousProductionGoalPlanner
 -> BlenderTaskPlanner
 -> validated ActionPlan
 -> explicit ActionAuthorization
 -> AutonomousProductionGoalPreparation
 -> ActionPlanSequenceAdapter
 -> AutonomousTaskSequence
 -> autonomous admission
 -> ProductionOperationLifecycle
 -> authoritative completion
 -> AutonomousProductionGoalRun
 -> authoritative outcome evidence
 -> AutonomousProductionGoalFeedback
 -> replacement declarative goal proposal
 -> canonical planning + fresh authorization
```

The final feedback/replan step is planning-only. It creates a clean seam for a future agent to reason from verified evidence without reusing prior authorization or receiving direct execution authority.

## Safety and integrity invariants

- Qwen / upstream reasoning proposes; Atlas validates, authorizes, executes, verifies, tracks, and recovers.
- The goal layer is planning data only and cannot authorize or execute Blender work.
- `BlenderTaskPlanner` remains the canonical capability and argument-schema validation path.
- `ActionAuthorization` remains the exact write authorization boundary.
- `ActionPlanSequenceAdapter` accepts only authorized, pristine plans and does not authorize or execute.
- A partially executed or failed `ActionPlan` is rejected from fresh autonomous sequencing; established checkpoint/recovery must be used instead.
- Autonomous admission is checked before every sequence step.
- Autonomous sequence checkpoints bind sequence identity, ordered step names, operation identities, resume position, and a canonical SHA-256 digest.
- Checkpoint persistence precedes in-memory sequence advancement.
- `BlenderAutonomousAdmission` and `BlenderLiveWriteGate` must share the same durable execution journal instance.
- Saved authorization is never replayed; resumed/new writes require the normal authorization-bound path.
- `ProductionOperationLifecycle` remains authoritative for `COMPLETED` versus `BLOCKED` and requires authoritative verification plus a production completion receipt.
- `AutonomousProductionGoalRun` and `AutonomousProductionGoalFeedback` are audit/feedback context only and do not become a second execution or authorization system.
- Follow-up requests and feedback records contain no tool dispatch or executable authorization instructions.
- A replacement goal receives fresh authorization through `compile_goal`; prior authorization identity is explicitly rejected from reuse.

## Current orchestration boundaries

### Production goal
`planning/autonomous_production_goal.py`

Normalized production objective plus declarative proposed actions. No execution authority.

### Goal planning
`planning/autonomous_production_goal_planner.py`

Routes production goals into the existing `BlenderTaskPlanner` validation surface rather than introducing another validator.

### Canonical Blender planning
`planning/blender_task_planner.py`

Rejects unknown capabilities and invalid tool arguments; normalizes actions into `ActionPlan`.

### Authorization
`planning/action_authorization.py`

Creates immutable authorization receipts bound to the exact compiled action sequence by digest.

### Goal orchestration
`planning/autonomous_production_orchestrator.py`

Composes goal planning, explicit authorization, autonomous admission, sequence execution, and the planning-only replan bridge. It owns no separate execution, verification, journal, checkpoint, receipt, registry, or completion mechanism.

### Goal preparation / audit context
`planning/autonomous_production_goal_preparation.py`

Execution-free binding of goal identity to the normalized authorized plan and authorization digest.

`planning/autonomous_production_goal_run.py`

Audit-oriented outcome containing goal identity, authorization context, sequence state, progress, and structured non-executable follow-up information when needed.

### Evidence-driven feedback
`planning/autonomous_production_goal_feedback.py`

Binds a non-completed goal run to authoritative outcome evidence. `from_run()` refuses completed runs. The feedback record is immutable planning context and has no execution mechanism.

### Corrective replan seam
`AutonomousProductionOrchestrator.prepare_replan_from_run()`

Hands the feedback record to an injected proposal callback, accepts only a new `AutonomousProductionGoal`, then recompiles and freshly authorizes it through the canonical goal-planning path. Reuse of the prior authorization identity is rejected.

## CI / workflow position

GitHub Actions is the development gate with two complementary tiers:

```text
GitHub-hosted Ubuntu
    -> portable/offline Python regression suite

Self-hosted Windows runner
    -> Blender environment validation
    -> live Blender integration/regression evidence
```

Offline pytest does not constitute live Blender evidence. The self-hosted Windows/Blender workflow remains the authority for environment-dependent Blender behavior.

### Latest confirmed workflow

**Atlas Tests #1150 — ✅ PASSED** on `8c4d32ee46c1768c05f4283876ae3c7d758e8676`.

- `tests (3.12)` — passed.
- `blender-integration` — skipped because this run was PR-triggered; the workflow's Blender job is currently conditioned on `push` to a `feat/**` branch.
- Therefore #1150 is green portable CI only and provides **no new live Blender evidence**.

The self-hosted runner is available locally, but no live Blender result is claimed until the workflow executes the `push`-conditioned integration job and its result is inspected.

## Proven architecture / boundaries

```text
Qwen / AI agent proposal
 -> structured Blender reasoning
 -> AutonomousProductionGoal
 -> capability + argument validation
 -> ActionPlan
 -> exact authorization
 -> autonomous goal preparation
 -> autonomous sequence
 -> admission
 -> deterministic production operation lifecycle
 -> immutable execution receipt / completion receipt
 -> fresh authoritative verification
 -> durable journal / checkpoint / recovery
 -> VERIFIED / BLOCKED / COMPLETED
 -> authoritative evidence
 -> planning-only feedback
 -> new declarative goal
 -> canonical replan / fresh authorization
```

Previously proven live Blender capabilities include `set_object_rotation`, `move_object`, `delete_object`, `create_empty_marker`, and `move_object_to_collection`, with legitimate paths verified and adversarial paths blocked.

Previously proven live gates include durable checkpoint resume, stale-state zero-write behavior, registry-bound stale-revision blocking, registry snapshot rehydration/tamper rejection, durable production sequence interruption/resume, and rehydrated production completion/blocking.

## Key files advanced in this phase

- `planning/autonomous_task_sequence.py` — ordered autonomous production sequencing, admission checks, checkpoint integrity, and persistence-safe progression.
- `planning/action_plan_sequence_adapter.py` — authorized-pristine ActionPlan to autonomous sequence bridge.
- `planning/autonomous_production_goal.py` — planning-only production-goal boundary.
- `planning/autonomous_production_goal_planner.py` — production-goal compilation through canonical Blender planning validation.
- `planning/autonomous_production_orchestrator.py` — high-level goal/action-plan orchestration façade and evidence-driven replan seam.
- `planning/autonomous_production_goal_preparation.py` — execution-free prepared-goal record.
- `planning/autonomous_production_goal_run.py` — audit-oriented goal-run result and non-executable follow-up context.
- `planning/autonomous_production_goal_feedback.py` — immutable authoritative evidence feedback context for incomplete runs.
- `tests/test_autonomous_production_goal_feedback.py` — feedback creation, completion guard, fresh-authorization replan, and run-to-replan bridge regressions.

Existing foundational boundaries remain in:

- `planning/blender_capability_catalog.py`
- `planning/blender_write_authorization.py`
- `planning/blender_live_write_gate.py`
- `planning/blender_live_verification.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_execution_journal.py`
- `planning/blender_execution_recovery.py`
- `planning/blender_autonomous_admission.py`
- `planning/production_operation_lifecycle.py`
- `planning/production_completion_receipt.py`
- `planning/durable_production_operation_sequence.py`
- `planning/durable_production_sequence_rehydration.py`
- `planning/production_resume_integrity_gate.py`
- `planning/production_persistence_resume_lifecycle.py`

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh authoritative state.
- Stale, changed, missing, or unbound authorization fails closed.
- `VERIFIED` requires authoritative verification and an execution receipt.
- `COMPLETED` requires authoritative verification and a production completion receipt.
- Wrong authoritative state is `BLOCKED`, even after executor success.
- Autonomous execution is locked until startup reconciliation is complete.
- Autonomous admission and the live-write gate must share the same durable execution journal.
- Zero-write guarantees must be preserved on stale, unauthorized, and recovery-failure paths.
- Persisted registry snapshots and sequence checkpoints must be validated before resumed execution.
- Autonomous checkpoints must bind step identity, operation identity, and resume position; tampering must fail closed.
- Autonomous sequence position must not advance until checkpoint persistence has succeeded.
- A partially executed or failed `ActionPlan` must not be rebuilt as a fresh autonomous sequence; use the established resume/recovery path.
- Do not introduce parallel authorization, receipt, journal, registry, checkpoint, or completion mechanisms without a demonstrated architectural gap.
- Avoid bespoke per-tool lifecycle orchestration in place of generalized runtime boundaries.
- Goal-run and feedback records remain non-executable.
- C++ interoperability remains a future architectural requirement; subsystem contracts should remain language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.
- Do not infer live Blender success from offline pytest results.

## Session result

This session advanced the production-goal orchestration surface into an evidence-driven replanning seam. A blocked/incomplete goal run can now be paired with authoritative evidence, exposed to a proposal callback as planning-only feedback, and converted into a fresh declarative goal that must pass the existing capability validation and fresh authorization path.

The latest confirmed workflow is **Atlas Tests #1150 — passed** on `8c4d32ee46c1768c05f4283876ae3c7d758e8676`; the Blender integration job was skipped because the run was PR-triggered.

The local self-hosted Windows Actions runner is available, but live Blender validation still requires a push-triggered workflow run executing the `blender-integration` job.

## Next development target

The next step is to connect the feedback/replan seam to the existing authoritative verification/evidence sources and corrective execution boundaries without duplicating them. The proposal layer should remain declarative; Atlas must continue to compile, authorize, admit, execute, verify, persist, and recover through the existing boundaries.

Do not bypass the established `ActionAuthorization`, `BlenderAutonomousAdmission`, journal, checkpoint, verification, receipt, registry, or completion mechanisms.

## Resume

```powershell
git pull --ff-only origin feat/blender-coordinator-result-integrity-final
python -m pytest -q
```

Then inspect the current Actions runs and, because the self-hosted runner is available, establish a fresh push-triggered Blender integration result before claiming live Blender validation.

**Important:** current green CI means only what the corresponding workflow actually ran. Never report a later SHA as green without a workflow result for that SHA.

See `README.md` for the project-level status summary.
