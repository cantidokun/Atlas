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

**BLENDER AGENT DEVELOPMENT — SESSION CLOSED FOR TONIGHT**

This session established the production-facing controller/recovery boundary and integrated GitHub Actions into the development loop. The repository now has a portable GitHub-hosted Python test tier plus a dedicated self-hosted Windows/Blender integration tier.

The controller architecture currently covers generalized capability admission, exact write authorization, deterministic execution, authoritative verification, immutable execution receipts, corrective replanning, durable checkpoints, Digital Twin registry binding, production completion authority, persisted sequence rehydration, and fail-closed resume identity validation.

The self-hosted Blender tier has reached its first smoke-test gate: it validates that the GitHub Actions job is executing on Windows, identifies the configured runner, and can locate and launch Blender. The next session should build the real `.blend` fixture/integration tests on top of this gate.

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

The two tiers are complementary. Offline pytest results do not constitute live Blender evidence. Live Blender evidence must come from execution through the Windows runner.

The authoritative workflow is `.github/workflows/tests.yml`. Redundant CI workflow configuration was removed during this session.

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

Saved authorization is never replayed. Checkpoint persistence is state/audit lineage, not an execution credential.

The production-facing `ProductionPersistenceResumeLifecycle` contains a fail-closed resume identity boundary for persisted `sequence_id`, `plan_id`, and Digital Twin revision, with validation available before execution and rechecked at `run()` time.

## Proven live Blender capabilities

| Capability | Legitimate | Adversarial |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

Previously proven live gates include durable checkpoint resume, stale-state zero-write behavior, registry-bound stale-revision blocking, registry snapshot rehydration/tamper rejection, durable production sequence interruption/resume, and rehydrated production completion/blocking.

## Durable production architecture

Key boundaries include:

- `planning/blender_capability_catalog.py` — explicit Blender capability admission and fail-closed unknown capabilities.
- `planning/blender_write_authorization.py` — exact-action write authorization.
- `planning/blender_live_write_gate.py` — final authorization-bound write choke point.
- `planning/blender_live_verification.py` — independent authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable authorization-bound execution receipt.
- `planning/blender_execution_boundary.py` — protected execution and corrective-replan APIs.
- `planning/replan_authorization.py` — fresh-evidence corrective authorization.
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
- Zero-write guarantees must be preserved on stale/unauthorized paths.
- Persisted registry snapshots and sequence checkpoints must be validated before resumed execution.
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of generalized runtime boundaries.
- C++ interoperability remains a future architectural requirement; subsystem contracts should remain language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.

## End-of-session checkpoint

**Development is paused for the night.** The current session's implementation work is complete. GitHub Actions is now part of the Atlas development loop, and the self-hosted Windows/Blender smoke gate is in place.

Do not start additional Blender-agent implementation tonight.

## Next-session resume

```powershell
git pull --ff-only origin feat/blender-coordinator-result-integrity-final
python -m pytest -q
```

First task next session: inspect the self-hosted runner smoke-test result, then implement the real Blender `.blend` fixture/integration gate. Do not infer live Blender success from offline pytest. Continue from the existing generalized controller, authorization, verification, recovery, registry, and resume boundaries rather than creating parallel mechanisms.

See `ATLAS_HANDOFF_CURRENT.md` for the canonical resume point.
