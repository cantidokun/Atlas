# Atlas Current Development Handoff

**Updated:** August 26, 2026 — checkpoint lifecycle and parent-lineage hardening complete; full offline suite 689 passed  
**Branch:** `feat/replan-race-gate`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current verified milestone

Latest completed full offline suite:

```text
FULL OFFLINE PYTEST SUITE: 689 passed, 0 failed
```

The current baseline includes the canonical Digital Twin registry race gate, durable checkpoint rehydration, durable resume authorization, checkpoint serialization integrity, and production checkpoint parent-lineage validation.

The most recent focused checkpoint lifecycle run completed successfully after two rounds of fail-closed contract corrections. The final lineage suite passed, followed by the full **689/0** suite.

## Recent checkpoint-lineage hardening

`planning/production_checkpoint_lifecycle.py` now enforces:

- checkpoint integrity before serialization;
- current canonical Digital Twin revision before checkpoint validation;
- explicit parent checkpoint validation;
- exact parent digest matching;
- same-Digital-Twin parent lineage;
- same-revision parent lineage;
- rejection of arbitrary parent digests as a substitute for a validated parent object.

`tests/test_production_checkpoint_lifecycle.py` now covers:

- valid parent lineage;
- wrong-parent rejection;
- cross-Digital-Twin parent rejection;
- cross-revision parent rejection at creation;
- arbitrary parent-digest rejection;
- tampered checkpoint serialization;
- stale canonical revision behavior;
- checkpoint rehydration and immutable identity preservation.

The implementation corrections were committed in:

```text
5eef25092026201ec673ea8f8d6a7d824a371f66
4a70d285b6a9959c1bc9f6ab8d8ab34a9a0fb9c3
1da1e324de563c1ef89528fee3e1e551c8b73800
```

## Live Blender validation already proven

Production write capabilities with legitimate authoritative success and adversarial mismatch evidence:

| Capability | Legitimate | Adversarial |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

Previously proven live gates include:

```text
ATLAS BLENDER LIVE MARKER VERIFIED: PASS
ATLAS BLENDER LIVE COLLECTION ADVERSARIAL GATE: PASS
ATLAS BLENDER LIVE COLLECTION VERIFIED: PASS
ATLAS BLENDER LIVE MULTI-OPERATION COMPOSITION: PASS
ATLAS BLENDER LIVE STALE AUTHORIZATION ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE CONTINUATION STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE CONTINUATION RESUME: PASS
ATLAS BLENDER LIVE DURABLE CHECKPOINT STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE DURABLE CHECKPOINT RESUME: PASS
```

The live registry-aware durable resume harness exists, but no current conversation result authorizes claiming its explicit registry PASS. Do not infer live registry success from the offline suite.

## Durable checkpoint and resume architecture

- `planning/production_task_checkpoint.py` — immutable serializable checkpoint binding a production task to Digital Twin identity/revision, completed actions, evidence digest, authorization lineage, and optional parent checkpoint digest.
- `planning/production_checkpoint_lifecycle.py` — production-facing checkpoint creation, serialization, rehydration, canonical-revision validation, and parent-lineage validation.
- `planning/durable_resumable_corrective_task.py` — durable checkpoint-to-resume boundary requiring compatible identity/revision, fresh evidence, fresh resume authorization, and a canonical-revision recheck immediately before issuing fresh authorization.
- `planning/digital_twin_registry.py` — persisted canonical identity/revision registry with integrity-addressed snapshots and fail-closed canonical revision checks.
- `planning/continuation_resume.py` — fail-closed continuation checkpoint and fresh-resume authorization.
- `planning/resumable_corrective_task.py` — production resume boundary; saved authorization is never replayed.
- `planning/blender_execution_boundary.py` — authorized replans return authorization-bound receipts.

Checkpoint persistence is state/audit lineage, **not an execution credential**. Saved authorization is never replayed; fresh observation must produce fresh authorization before resumed writes.

## Checkpoint and registry tests

- `tests/test_production_task_checkpoint.py` — checkpoint contract.
- `tests/test_production_task_checkpoint_rehydration.py` — persisted snapshot rehydration and integrity.
- `tests/test_production_checkpoint_lifecycle.py` — lifecycle, serialization, canonical revision, and parent-lineage hardening.
- `tests/test_durable_resumable_corrective_task.py` — durable resume boundary.
- `tests/test_durable_resume_registry_binding.py` — canonical registry binding and registry-advance race.
- `tests/test_live_durable_registry_binding.py` — registry reload, stale canonical revision rejection, and snapshot tampering.
- `live_blender_durable_checkpoint_resume.py` — live Blender checkpoint/reload/interruption/resume proof.
- `live_blender_durable_registry_resume.py` — live registry-aware durable resume harness.

## Canonical Digital Twin registry

The registry exposes:

- `canonical_revision(twin_id)` to identify the current canonical revision;
- `require_canonical_revision(revision)` to fail closed unless revision ID, sequence, and source fingerprint match the canonical revision;
- deterministic integrity-addressed `snapshot()` / `from_snapshot()` persistence.

Durable resume checks the registry before planning and again immediately before issuing fresh authorization. This closes the race where the canonical Digital Twin revision advances during replanning.

## Digital Twin state architecture

- `planning/digital_twin_identity.py` — stable identity anchors and fail-closed `MATCH` / `NO_MATCH` / `INSUFFICIENT_EVIDENCE` evaluation.
- `planning/digital_twin_revision.py` — canonical revision and derived representation contracts.
- `planning/digital_twin_registry.py` — fail-closed canonical identity/revision registry.
- `planning/digital_twin_intake.py` / adapter contracts — upstream reconstruction intake boundaries.

Photogrammetry remains upstream of Blender. Atlas owns canonical Digital Twin identity/state for the soccer-field-focused production pipeline; Blender receives the upstream reconstruction for analysis, cleanup, correction, and preparation.

## Authority model

```text
Qwen / AI proposal
 -> ActionSpec / task validation
 -> explicit capability admission
 -> exact write or corrective authorization
 -> protected Blender execution
 -> normalized result
 -> immutable authorization-bound receipt
 -> fresh authoritative observation
 -> VERIFIED / BLOCKED or corrective replan
 -> durable checkpoint when interrupted
 -> parent-lineage validation
 -> fresh canonical revision check
 -> fresh resume authorization
 -> resumed write
 -> authoritative verification
```

Qwen never receives direct Blender execution authority. Blender is an execution target, not the authority that decides completion.

## Architectural constraints

- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and the exact replacement action list.
- Ordinary writes must match exact `BlenderWriteAuthorization`.
- Receipts bind the executed action/result and authorization identity for protected writes/replans.
- Missing, stale, changed, or unbound authorization fails closed.
- `VERIFIED` requires authoritative verification and a receipt; `BLOCKED` carries no successful receipt.
- Exhausting a corrective budget is not success.
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- C++ interoperability remains a future architectural requirement; keep subsystem contracts language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.

## Current model/runtime setup

```text
AI proposal/planning model: Qwen (proposal/reasoning layer only; no direct Blender authority)
OS / shell: Windows PowerShell
Atlas root: C:\Users\Gavin's PC\Desktop\Atlas
Branch: feat/replan-race-gate
Python invocation: python -m pytest
Blender: controlled external execution target through the Atlas runner
```

No specific Qwen model/version or Blender version is established in the current validation record; do not invent one.

## Current known issues / validation gaps

1. The offline suite is green at **689 passed / 0 failed**.
2. Parent checkpoint lineage is now covered offline and fail-closed.
3. The live registry-aware durable resume harness still requires an explicit run whose output proves both stale-revision zero-write and durable registry resume.
4. The registry/checkpoint path should next be consolidated into the production-facing task lifecycle rather than creating a parallel resume mechanism.
5. Preserve all existing live zero-write, receipt-binding, authoritative-verification, and fresh-replan invariants while integrating persistence.
6. Do not add a production capability merely to satisfy a test.

## Exact next steps to resume development

1. Synchronize the Windows checkout:

```powershell
git pull --ff-only origin feat/replan-race-gate
```

2. Establish the current baseline on the user's machine:

```powershell
python -m pytest -q
```

Expected result: **689 passed** unless new work intentionally changes the suite.

3. Run the live registry-aware durable resume proof:

```powershell
python live_blender_durable_registry_resume.py
```

Require explicit outputs:

```text
ATLAS BLENDER LIVE REGISTRY STALE-REVISION ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE REGISTRY DURABLE RESUME: PASS
```

4. If live registry resume passes, integrate `ProductionCheckpointLifecycle` with the production-facing task lifecycle and preserve the canonical-revision race gate.

5. Re-run the full suite after integration.

6. Do not reopen already-proven live authorization, marker, collection, multi-operation composition, continuation, or durable checkpoint work unless new evidence requires it.

7. Do not claim a live validation result until the corresponding command has actually been run.
