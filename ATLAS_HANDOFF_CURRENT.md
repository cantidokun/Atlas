# Atlas Current Development Handoff

**Updated:** August 26, 2026 — durable checkpoint/resume is live-proven; full offline suite 665 passed  
**Branch:** `feat/replan-race-gate`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current verified milestone

Latest completed full offline suite:

```text
FULL OFFLINE PYTEST SUITE: 665 passed, 0 failed
```

This includes the durable checkpoint/resume contract and the corrected durable-resume tests.

## Live Blender validation proven

Production write capabilities with legitimate authoritative success and adversarial mismatch evidence:

| Capability | Legitimate | Adversarial |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

Live marker:

```text
ATLAS BLENDER LIVE MARKER VERIFIED: PASS
```

Live collection:

```text
ATLAS BLENDER LIVE COLLECTION ADVERSARIAL GATE: PASS
ATLAS BLENDER LIVE COLLECTION VERIFIED: PASS
```

Live multi-operation composition:

```text
ATLAS BLENDER LIVE MULTI-OPERATION COMPOSITION: PASS
ATLAS BLENDER LIVE STALE AUTHORIZATION ZERO-WRITE GATE: PASS
```

Live continuation/resume:

```text
ATLAS BLENDER LIVE CONTINUATION STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE CONTINUATION RESUME: PASS
```

Live durable checkpoint/resume:

```text
ATLAS BLENDER LIVE DURABLE CHECKPOINT STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE DURABLE CHECKPOINT RESUME: PASS
```

The durable live proof established checkpoint integrity after serialization/reload, an external Blender-world interruption, stale authorization rejection with zero writes, fresh evidence, fresh resume authorization, successful resumed mutation, authorization-bound resumed receipt, and authoritative final target verification.

## Durable checkpoint architecture

- `planning/production_task_checkpoint.py` — immutable serializable checkpoint binding a production task to Digital Twin identity/revision, completed actions, evidence digest, authorization lineage, and optional parent checkpoint digest.
- `planning/durable_resumable_corrective_task.py` — durable checkpoint-to-resume boundary requiring compatible identity/revision, fresh evidence, and fresh resume authorization.
- `tests/test_production_task_checkpoint.py` — checkpoint contract coverage.
- `tests/test_production_task_checkpoint_rehydration.py` — persisted snapshot rehydration and integrity coverage.
- `tests/test_durable_resumable_corrective_task.py` — durable resume boundary coverage.
- `live_blender_durable_checkpoint_resume.py` — live Blender checkpoint/reload/interruption/resume proof.

A checkpoint is durable state/audit lineage, **not an execution credential**. Saved authorization is never replayed. Fresh observation must produce fresh authorization before resumed writes.

## Existing continuation architecture

- `planning/continuation_resume.py` — fail-closed continuation checkpoint and fresh-resume authorization.
- `planning/resumable_corrective_task.py` — production resume boundary; saved authorization is never replayed.
- `live_blender_continuation_resume.py` — live Blender continuation proof.
- `planning/blender_execution_boundary.py` — authorized replans return authorization-bound receipts.

The durable layer persists this lineage without replacing the already-proven continuation safety boundaries.

## Digital Twin state architecture

Atlas has conservative Digital Twin identity/revision primitives:

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

## Current remaining validation / development gaps

1. The durable checkpoint/resume boundary is now live-proven, so it should not be treated as merely contract-tested.
2. The next work should consolidate the newly proven durable path into the production-facing task/checkpoint lifecycle rather than creating another parallel resume mechanism.
3. Digital Twin revision persistence and production workflow integration remain the next substantive architectural boundary.
4. Preserve all existing live zero-write, receipt-binding, authoritative-verification, and fresh-replan invariants while integrating persistence.
5. No new capability should be admitted merely to satisfy a test; production capability admission remains explicit.

## Exact resume sequence

Start from the synchronized branch:

```powershell
git pull --ff-only origin feat/replan-race-gate
```

Confirm the clean offline baseline:

```powershell
python -m pytest -q
```

The expected current baseline is **665 passed** unless new work has intentionally changed the suite.

Then continue with the next production boundary:

1. Consolidate durable checkpoint persistence with the existing production continuation/resume lifecycle.
2. Persist canonical Digital Twin revision identity alongside durable task state.
3. Prove reload against the canonical revision rejects mismatched/tampered state before any write.
4. Re-run the live durable checkpoint/resume proof after that integration.
5. Preserve stale-state zero-write and authorization-bound receipt invariants.
6. Only then expand downstream production workflow integration.

Do not reopen already-proven live authorization, marker, collection, composition, continuation, or durable-resume work unless new evidence requires it. Do not claim a validation result until the corresponding command has actually been run.
