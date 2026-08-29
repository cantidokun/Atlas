# Atlas Current Development Handoff

**Updated:** August 28, 2026 — Blender-agent development paused for the night after integrating GitHub Actions and establishing the self-hosted Windows/Blender smoke-test boundary.  
**Branch:** `feat/blender-coordinator-result-integrity-final`  
**Latest documentation commit:** `d5370a6526f5f2c5d6a3398253b74ba24df59cbc`  
**Purpose:** canonical resume point for the next Atlas development session.

## Session milestone

This session established the next major testing boundary for the Blender Agent:

```text
GitHub-hosted Ubuntu CI
    -> portable/offline Python regression tests

GitHub Actions
    -> self-hosted Windows runner
    -> Blender smoke/integration tests
    -> actual Blender environment
```

The self-hosted runner remains connected and available. It is intentionally idle when no workflow job targets its labels. The authoritative workflow is `.github/workflows/tests.yml`.

## What was completed this session

1. Added GitHub Actions as a first-class Atlas development mechanism.
2. Consolidated redundant test workflows into `.github/workflows/tests.yml`.
3. Configured the portable CI tier for Python 3.12 and Atlas's declared test dependencies.
4. Fixed package-relative controller imports exposed by CI.
5. Added explicit setuptools package discovery for Atlas's current package layout.
6. Added a dedicated self-hosted Windows/Blender CI job.
7. Added `tests/blender/test_runner_smoke.py` to validate the runner environment and Blender executable before real scene integration testing.
8. Isolated the smoke gate from the portable test suite so Blender-specific validation remains an explicit external-environment boundary.
9. Continued strengthening the deterministic controller/recovery state machine, including fail-closed recovery semantics and retry-state handling.

## Current architecture

The Blender Agent remains governed by:

```text
Qwen proposal
 -> task/evidence/action validation
 -> explicit capability admission
 -> exact authorization
 -> deterministic Blender execution
 -> immutable execution receipt
 -> fresh authoritative observation
 -> VERIFIED / BLOCKED or corrective replan
 -> durable checkpoint when interrupted
 -> checkpoint + parent-lineage validation
 -> registry snapshot integrity validation
 -> canonical Digital Twin revision
 -> durable sequence rehydration
 -> resume identity validation
 -> fresh resume authorization
 -> resumed write
 -> authoritative final verification
 -> ProductionCompletionReceipt
 -> COMPLETED / BLOCKED
```

Qwen proposes; Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender is an execution target, never the authority.

## CI boundary

Portable CI should establish deterministic Python behavior. The self-hosted job exists specifically for environment-dependent validation that cannot be faithfully reproduced on GitHub-hosted Linux.

The current self-hosted smoke gate validates:

- Windows execution;
- GitHub Actions execution context;
- presence of the configured runner identity;
- discoverability of the Blender executable;
- successful `blender --version` execution.

It intentionally performs **no scene mutation**. The next step is a controlled `.blend` fixture and real Atlas/Blender integration test.

Do not claim a live Blender result from an offline pytest result. Live evidence must come from the self-hosted runner.

## Existing proven live architecture

Previously proven live gates remain authoritative, including:

```text
multi-operation composition
stale authorization zero-write
continuation stale-state zero-write
continuation resume
Durable checkpoint stale-state zero-write
Durable checkpoint resume
registry stale-revision zero-write
registry durable resume
Durable production sequence interruption/resume
Durable production sequence final verification
registry-bound stale-revision zero-write
registry snapshot rehydration
registry snapshot tamper fail-closed
rehydrated registry stale-revision zero-write
rehydrated registry completion
rehydrated wrong-state block
```

Do not reopen these mechanisms without new evidence of an architectural gap.

## Key files

- `.github/workflows/tests.yml` — authoritative portable + self-hosted CI workflow.
- `tests/blender/test_runner_smoke.py` — self-hosted Blender environment smoke gate.
- `controller/controller_state.py` — deterministic controller state machine.
- `controller/controller_checkpoint.py` — serializable checkpoint boundary.
- `controller/controller_recovery.py` — fail-closed recovery/reconciliation boundary.
- `controller/controller_runtime.py` — deterministic execution runtime.
- `planning/blender_capability_catalog.py` — explicit Blender capability admission.
- `planning/blender_write_authorization.py` — exact write authorization.
- `planning/blender_live_write_gate.py` — authorization-bound write choke point.
- `planning/blender_live_verification.py` — authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable execution receipt.
- `planning/blender_execution_boundary.py` — protected execution/corrective-replan boundary.
- `planning/replan_authorization.py` — fresh-evidence corrective authorization.
- `planning/production_task_checkpoint.py` — durable task checkpoint.
- `planning/digital_twin_registry.py` — canonical Digital Twin identity/revision registry.
- `planning/production_operation_lifecycle.py` — authoritative completion/blocking decision.
- `planning/production_completion_receipt.py` — immutable production completion evidence.
- `planning/durable_production_operation_sequence.py` — ordered durable production sequence.
- `planning/durable_production_sequence_rehydration.py` — persisted sequence rehydration.
- `planning/production_resume_integrity_gate.py` — fail-closed persisted resume identity validation.
- `planning/production_persistence_resume_lifecycle.py` — production-facing persisted restart boundary.

## Architectural constraints

- Qwen never receives direct Blender execution authority.
- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh authoritative state.
- Stale or changed authorization fails closed.
- `VERIFIED` requires authoritative verification and an execution receipt.
- `COMPLETED` requires authoritative verification and a `ProductionCompletionReceipt`.
- Wrong authoritative state is `BLOCKED`, even after executor success.
- Zero-write guarantees must be preserved on stale/unauthorized paths.
- Persisted registry snapshots and sequence checkpoints must be validated before resumed execution.
- Saved authorization is never replayed.
- Do not introduce another checkpoint, authorization, receipt, or completion mechanism without demonstrating a concrete architectural gap.
- Avoid bespoke per-tool lifecycle orchestration in place of generalized runtime boundaries.
- C++ interoperability remains a future architectural requirement; subsystem contracts should remain language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.

## End-of-session status

**Blender Agent development is paused for the night.** No further implementation should be started until the next session unless the user explicitly resumes development.

The next meaningful validation boundary is the self-hosted Windows/Blender smoke gate, followed by creation of the controlled `.blend` integration fixture.

## Next-session resume

```powershell
git pull --ff-only origin feat/blender-coordinator-result-integrity-final
python -m pytest -q
```

Then inspect the GitHub Actions self-hosted Blender job result. If the smoke gate is green, proceed to the real Blender fixture/integration layer. If it fails, fix the runner/environment boundary before adding scene-level tests.
