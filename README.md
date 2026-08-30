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

**BLENDER AGENT — AUTONOMOUS ADMISSION / RESTART-RECOVERY BOUNDARY**

Atlas has progressed beyond deterministic single-operation execution into a production-facing autonomous admission boundary. GitHub Actions validates the portable Python tier and a dedicated self-hosted Windows/Blender tier.

The controller architecture covers generalized capability admission, exact write authorization, deterministic execution, authoritative verification, immutable execution receipts, corrective replanning, durable checkpoints, Digital Twin registry binding, production completion authority, persisted sequence rehydration, fail-closed resume validation, and autonomous startup admission.

The autonomous-admission work establishes that execution remains locked until startup reconciliation completes. Persisted interrupted executions can be discovered by a fresh runtime and reconciled before the runtime becomes READY. Failed reconciliation remains fail-closed. A fresh authorization is distinct from recovered authorization and must enter the normal authorization-bound write path.

The autonomous admission boundary and live-write gate must share the **same durable execution journal instance**. This prevents an admitted write from proceeding without durable execution state.

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

**End-of-session CI state — August 30, 2026:** the latest relevant Actions run for the current autonomous-sequencing work is **#1037, failed**. Its failures are in the newly added restart/identity test contract: the PR merge ref contains tests expecting `operation_identities`, while the implementation in that merge result still exposes the older checkpoint constructor/schema. No newer workflow run had been established at session close.

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

Critical invariant:

```text
STARTED
  -> reconciliation required
  -> VERIFIED
  -> autonomous admission READY
```

`BLOCKED` does not authorize autonomous continuation. Saved authorization is never replayed; recovery establishes state and a new action requires a new authorization.

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

## Durable checkpoint / registry resume

The durable production resume chain is:

```text
registry reload
 -> registry snapshot integrity validation
 -> canonical Digital Twin revision
 -> checkpoint integrity + validated parent lineage
 -> durable sequence rehydration
 -> completed-receipt/order validation
 -> resume identity validation
 -> fresh observation / authorization
 -> authorized Blender continuation
 -> authorization-bound receipt
 -> authoritative final evidence
 -> ProductionCompletionReceipt
 -> COMPLETED / BLOCKED
```

Previously proven live gates include durable checkpoint resume, stale-state zero-write behavior, registry-bound stale-revision blocking, registry snapshot rehydration/tamper rejection, durable production sequence interruption/resume, and rehydrated production completion/blocking.

## Proven live Blender capabilities

| Capability | Legitimate | Adversarial |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

## Durable production architecture

Key boundaries include:

- `planning/blender_capability_catalog.py` — explicit Blender capability admission and fail-closed unknown capabilities.
- `planning/blender_write_authorization.py` — exact-action write authorization.
- `planning/blender_live_write_gate.py` — final authorization-bound write choke point and durable journal boundary.
- `planning/blender_live_verification.py` — independent authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable authorization-bound execution receipt.
- `planning/blender_execution_boundary.py` — protected execution and corrective-replan APIs.
- `planning/replan_authorization.py` — fresh-evidence corrective authorization.
- `planning/blender_autonomous_admission.py` — startup reconciliation and autonomous readiness boundary.
- `planning/blender_execution_journal.py` — durable execution state.
- `planning/blender_execution_recovery.py` — persisted execution recovery/reconciliation.
- `planning/production_task_checkpoint.py` — immutable durable task checkpoint.
- `planning/production_checkpoint_lifecycle.py` — checkpoint persistence, canonical revision, and parent-lineage validation.
- `planning/durable_resumable_corrective_task.py` — durable fresh-resume boundary.
- `planning/digital_twin_registry.py` — canonical Digital Twin identity/revision registry with integrity-addressed snapshots.
- `planning/production_operation_lifecycle.py` — authoritative `COMPLETED` / `BLOCKED` decision.
- `planning/production_completion_receipt.py` — immutable production completion evidence.
- `planning/production_registry_resume_lifecycle.py` — registry-backed production continuation/completion.
- `planning/durable_production_operation_sequence.py` — ordered durable production sequence/checkpoint progression.
- `planning/registry_bound_durable_production_operation_sequence.py` — canonical registry revision binding.
- `planning/durable_production_sequence_rehydration.py` — persisted sequence rehydration.
- `planning/production_resume_integrity_gate.py` — fail-closed persisted resume identity validation.
- `planning/production_persistence_resume_lifecycle.py` — production-facing persisted restart boundary with resume validation.

## Architectural constraints

- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and exact replacement actions.
- Ordinary writes must match exact `BlenderWriteAuthorization`.
- Missing, stale, changed, or unbound authorization fails closed.
- `VERIFIED` requires authoritative verification and a receipt.
- `COMPLETED` requires authoritative verification and a production completion receipt.
- Wrong authoritative state is `BLOCKED`, even after executor success.
- Autonomous execution is locked until startup reconciliation is complete.
- Autonomous admission and the live-write gate must share the same durable execution journal.
- Zero-write guarantees must be preserved on stale/unauthorized/recovery-failure paths.
- Persisted registry snapshots and sequence checkpoints must be validated before resumed execution.
- Saved authorization is never replayed.
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of generalized runtime boundaries.
- C++ interoperability remains a future architectural requirement; subsystem contracts should remain language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.

## End-of-session checkpoint

**Development is paused at the end of the August 30, 2026 coding session.** Do not continue implementation until the next session begins.

The current blocker is the autonomous/generalized sequence restart test contract on PR #42. The latest established workflow result is #1037, which is red because the merge ref contains tests expecting `operation_identities` on `AutonomousTaskSequenceCheckpoint`, while the implementation in that merge result still uses the older checkpoint schema. This must be resolved against the actual PR merge state; do not assume the previously described operation-identity implementation exists until verified in GitHub.

No further architectural layer should be added while this CI contract mismatch is unresolved. Do not create parallel authorization, checkpoint, receipt, journal, registry, or completion mechanisms.

## Next-session resume

```powershell
git pull --ff-only origin feat/blender-coordinator-result-integrity-final
python -m pytest -q
```

Then:

1. Check the newest GitHub Actions workflow for PR #42.
2. Inspect the actual merge/head code before changing the checkpoint schema.
3. Resolve the `operation_identities` test/implementation mismatch on the real PR branch.
4. Run the offline suite locally.
5. Confirm the self-hosted Windows/Blender workflow remains healthy.
6. Require a green Actions result before moving upward into generalized autonomous task sequencing/orchestration.
7. Preserve the existing authorization, journal, verification, checkpoint, registry, and completion boundaries.

**Important:** do not infer live Blender success from offline pytest results, and do not report a workflow as green unless a current GitHub Actions run confirms it.

See `ATLAS_HANDOFF_CURRENT.md` for the canonical resume point.
