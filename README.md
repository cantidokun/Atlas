# Atlas

Atlas is an AI-assisted sports virtual-production and digital-twin platform. Photogrammetry is an upstream reconstruction capability; Blender receives the initial reconstruction for analysis, cleanup, correction, and preparation.

## Execution principle

```text
Qwen / AI agents
    -> reason + propose
Python / Atlas
    -> validate + authorize + execute + verify + recover
Blender
    -> controlled production execution
Independent Atlas verification
    -> authoritative completion decision
```

Qwen never receives direct Blender execution authority.

## Current milestone

**BLENDER AGENT — AUTONOMOUS ADMISSION / RESTART-RECOVERY / GENERALIZED SEQUENCE / PRODUCTION-GOAL ORCHESTRATION**

Atlas has progressed beyond deterministic single-operation execution into a production-facing autonomous admission, sequencing, and goal-orchestration layer. GitHub Actions validates the portable Python tier; the self-hosted Windows/Blender tier remains the authority for environment-dependent Blender behavior.

### Current production-goal chain

```text
AutonomousProductionGoal
  -> AutonomousProductionGoalPlanner
  -> BlenderTaskPlanner
  -> capability + argument validation
  -> ActionPlan
  -> exact ActionAuthorization
  -> AutonomousProductionGoalPreparation
  -> ActionPlanSequenceAdapter
  -> AutonomousTaskSequence
  -> autonomous admission
  -> ProductionOperationLifecycle
  -> authoritative verification / completion receipt
  -> audit-oriented AutonomousProductionGoalRun
  -> non-executable follow-up when blocked
```

The planning and audit layers do not execute Blender work. `BlenderTaskPlanner` remains the canonical capability/schema gate; `ActionAuthorization` remains the exact authorization boundary; `AutonomousProductionOrchestrator` composes these existing boundaries with autonomous admission and sequencing.

### Autonomous sequencing chain

```text
ActionPlan
  -> must be authorized + pristine
  -> ActionPlanSequenceAdapter
  -> AutonomousTaskSequence
  -> admission check before every step
  -> ProductionOperationLifecycle
  -> authoritative completion
  -> tamper-evident checkpoint
  -> resume without replay
```

A partially executed or failed `ActionPlan` is rejected rather than rebuilt as a fresh autonomous sequence. Autonomous checkpoints bind sequence identity, ordered step names, production operation identities, resume position, and a canonical SHA-256 digest. Checkpoint persistence occurs before the in-memory sequence position advances.

## Autonomous goal preparation and audit context

`AutonomousProductionGoalPreparation` provides an execution-free record of the declarative goal, normalized compiled action names, exact authorization identity, and authorization plan digest before a sequence is executed.

`AutonomousProductionGoalRun` binds a goal identity and objective to its authorized sequence outcome. Its follow-up request is deliberately non-executable: it provides state, progress, authorization context, and the reason follow-up is required, without tool dispatch or executable arguments.

This gives the future agent/evidence loop a stable feedback boundary without creating another authorization or execution system.

## Autonomous admission boundary

```text
runtime startup
    -> durable journal inspection
    -> unresolved execution discovery
    -> authoritative reconciliation
    -> VERIFIED / BLOCKED
    -> READY only after reconciliation
    -> fresh authorization
    -> normal live-write gate
    -> durable journal
    -> authoritative verification
```

The autonomous admission boundary and live-write gate must share the **same durable execution journal instance**. Saved authorization is never replayed; recovery establishes state and a subsequent action requires fresh authorization.

## Production completion

The production completion invariant remains:

```text
executor success
+ convergence
+ authoritative final-state verification
+ ProductionCompletionReceipt
    -> COMPLETED

executor success
+ wrong authoritative state
    -> BLOCKED
```

Executor success alone is never sufficient for production completion.

## CI / testing architecture

```text
GitHub-hosted Ubuntu
    -> package installation
    -> offline Python regression suite

GitHub Actions
    -> self-hosted Windows runner
    -> Blender runner smoke/integration tests
    -> real Blender environment
```

Offline pytest results do not constitute live Blender evidence. Live Blender evidence must come from the Windows runner.

The authoritative workflow is `.github/workflows/tests.yml`.

### End-of-session CI state — September 1, 2026

**Atlas Tests #1133 — ✅ PASSED** on `0fd6a707`.

- `tests (3.12)` — passed.
- `blender-integration` — skipped.
- Therefore #1133 is green portable CI only and provides **no new live Blender evidence**.

An earlier run (#1117) failed on goal-run authorization-context regressions; that issue was fixed and later validation runs passed. Do not use #1117 as the current baseline.

## Durable production architecture

Key boundaries include:

- `planning/blender_capability_catalog.py` — explicit Blender capability admission.
- `planning/blender_write_authorization.py` — exact-action write authorization.
- `planning/blender_live_write_gate.py` — authorization-bound write choke point and durable journal boundary.
- `planning/blender_live_verification.py` — independent authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable authorization-bound execution receipt.
- `planning/blender_execution_journal.py` — durable execution state.
- `planning/blender_execution_recovery.py` — persisted execution recovery/reconciliation.
- `planning/blender_autonomous_admission.py` — startup reconciliation and autonomous readiness boundary.
- `planning/production_operation_lifecycle.py` — authoritative `COMPLETED` / `BLOCKED` decision.
- `planning/production_completion_receipt.py` — immutable production completion evidence.
- `planning/durable_production_operation_sequence.py` — ordered durable production sequence/checkpoint progression.
- `planning/durable_production_sequence_rehydration.py` — persisted sequence rehydration.
- `planning/production_resume_integrity_gate.py` — fail-closed persisted resume identity validation.
- `planning/production_persistence_resume_lifecycle.py` — production-facing persisted restart boundary.
- `planning/autonomous_task_sequence.py` — ordered autonomous production sequencing, admission checks, checkpoint integrity, and resume semantics.
- `planning/action_plan_sequence_adapter.py` — explicit authorized-pristine ActionPlan to autonomous sequence bridge.
- `planning/autonomous_production_goal.py` — planning-only production-goal boundary.
- `planning/autonomous_production_goal_planner.py` — goal compilation through canonical Blender task validation.
- `planning/autonomous_production_orchestrator.py` — high-level goal/action-plan orchestration façade.
- `planning/autonomous_production_goal_preparation.py` — execution-free goal preparation context.
- `planning/autonomous_production_goal_run.py` — audit-oriented goal-run outcome and non-executable follow-up context.

## Architectural constraints

- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh authoritative state.
- `ActionAuthorization` must match the exact compiled action sequence.
- Missing, stale, changed, or unbound authorization fails closed.
- `VERIFIED` requires authoritative verification and a receipt.
- `COMPLETED` requires authoritative verification and a production completion receipt.
- Wrong authoritative state is `BLOCKED`, even after executor success.
- Autonomous execution is locked until startup reconciliation is complete.
- Autonomous admission and the live-write gate must share the same durable execution journal.
- Zero-write guarantees must be preserved on stale, unauthorized, and recovery-failure paths.
- Persisted registry snapshots and sequence checkpoints must be validated before resumed execution.
- Autonomous checkpoints must bind step identity, operation identity, and resume position; tampering must fail closed.
- Autonomous sequence position must not advance until checkpoint persistence has succeeded.
- A partially executed or failed `ActionPlan` must not be rebuilt as a fresh autonomous sequence; use the established resume/recovery path.
- Saved authorization is never replayed.
- Goal preparation/run records are planning/audit context only and cannot execute Blender work.
- Do not introduce parallel authorization, receipt, journal, registry, checkpoint, or completion mechanisms without a demonstrated architectural gap.
- Avoid bespoke per-tool lifecycle orchestration in place of generalized runtime boundaries.
- C++ interoperability remains a future architectural requirement; subsystem contracts should remain language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.
- Do not infer live Blender success from offline pytest results.

## End-of-session checkpoint

**Development is paused here for tonight.**

The session advanced the production-goal orchestration surface through goal preparation and audit context, with structured non-executable follow-up semantics. The latest confirmed workflow is **Atlas Tests #1133 — passed** on `0fd6a707`; the Blender integration job was skipped.

The next session must begin with a workflow check against the current branch head. Do not infer that commits after `0fd6a707` are validated unless GitHub reports a workflow for their SHA.

### Next-session resume

```powershell
git pull --ff-only origin feat/blender-coordinator-result-integrity-final
python -m pytest -q
```

Then:

1. Check the newest GitHub Actions workflow for PR #42 and the actual current branch head.
2. Verify whether the newest head has a dedicated green portable workflow.
3. Check the self-hosted Windows/Blender job separately; portable CI is not live Blender evidence.
4. Continue from the production-goal orchestration boundary toward evidence/verification feedback and corrective replanning.
5. Preserve the existing authorization, admission, journal, verification, checkpoint, registry, and completion boundaries.
6. Do not create a parallel execution or authorization system.

**Important:** current green CI means only what the corresponding workflow actually ran. Never report a later SHA as green without a workflow result for that SHA.

See `ATLAS_HANDOFF_CURRENT.md` for the canonical resume point.
