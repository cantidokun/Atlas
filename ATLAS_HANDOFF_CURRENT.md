# Atlas Current Development Handoff

**Updated:** August 26, 2026 — durable checkpoint/resume layer added; test-contract fix committed, post-fix validation pending  
**Branch:** `feat/replan-race-gate`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current verified milestone

The latest completed full offline suite was:

```text
FULL OFFLINE PYTEST SUITE: 662 passed, 0 failed
```

That 662-test run included the new `planning/production_task_checkpoint.py` and durable-resume production code, but it occurred **before** the subsequent correction to `tests/test_durable_resumable_corrective_task.py`. Therefore 662/0 is the latest authoritative result for the previous tree, not a current post-test-fix baseline. The focused durable-resume suite must be rerun, followed by the full suite, before establishing a newer baseline.

## Live Blender validation already proven

Five production write capabilities have both legitimate authoritative-success and adversarial mismatch evidence:

| Capability | Legitimate | Adversarial |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

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

The live continuation proof covered real Blender observation V1, authorized mutation, receipt-bound checkpoint, external world interruption, fresh observation V2, stale authorization rejection with zero writes, fresh replan authorization, resumed mutation, authorization-bound resumed receipt, and authoritative final verification.

A real defect was found during that proof: `BlenderExecutionBoundary.execute_authorized_replan()` initially returned a generic receipt without authorization binding. It was corrected so resumed/replanned writes return authorization-bound receipts. The subsequent full suite reached 660/0, and the next checkpoint additions reached 662/0 before the later test-contract correction described below.

## Current durable checkpoint/resume architecture

Added and integrated after the 660-test baseline:

- `planning/production_task_checkpoint.py` — immutable, serializable checkpoint contract binding a production task to a Digital Twin revision, completed actions, evidence digest, authorization identity, and optional parent checkpoint digest.
- `planning/durable_resumable_corrective_task.py` — durable checkpoint-to-resume boundary; requires checkpoint/revision compatibility, fresh evidence, and a newly issued resume authorization.
- `tests/test_production_task_checkpoint.py` — checkpoint contract tests.
- `tests/test_durable_resumable_corrective_task.py` — durable resume boundary tests.

The durable resume design preserves a critical invariant: a checkpoint is durable state/audit lineage, **not an execution credential**. Saved authorization is never replayed. Fresh observation must produce a new authorization before resumed writes.

The durable-resume tests initially failed because the tests used an obsolete `DigitalTwinIdentity` constructor (`name=...`) that did not match the established identity contract. The tests were corrected in commit `01a54518db9b7faff115ac6f7df66f4f73d2c9ef` to use `DigitalTwinIdentity(twin_id=..., entity_type=..., anchors=...)` with `IdentityAnchor` instances. **Those corrected tests have not yet been rerun in the recorded conversation.**

## Existing continuation architecture

- `planning/continuation_resume.py` — fail-closed continuation checkpoint and fresh-resume authorization.
- `planning/resumable_corrective_task.py` — production resume boundary; saved authorization is never replayed.
- `live_blender_continuation_resume.py` — live Blender continuation proof.
- `planning/blender_execution_boundary.py` — authorized replans now return authorization-bound receipts.

The new durable checkpoint layer is intended to persist this lineage rather than replace these already-proven live safety boundaries.

## Digital Twin state architecture

Atlas already has conservative Digital Twin identity/revision primitives:

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

1. `tests/test_durable_resumable_corrective_task.py` was corrected after three constructor-contract failures, but the corrected focused suite has not yet been rerun.
2. The 662/0 full-suite result therefore predates the test correction and must not be presented as the current post-fix baseline.
3. Durable checkpoint persistence has contract coverage, but the full durable checkpoint/restart workflow has not yet been re-proven through the real Blender runner.
4. The already-proven live continuation/resume path must remain unchanged and fail closed while durable persistence is integrated.
5. No newer live Blender result has been established after the durable checkpoint/test-contract changes.

## Exact resume sequence

Start from the synchronized branch:

```powershell
git pull --ff-only origin feat/replan-race-gate
```

Then run the corrected durable-resume focused suite:

```powershell
python -m pytest -q tests/test_durable_resumable_corrective_task.py
```

Also validate the checkpoint contract explicitly:

```powershell
python -m pytest -q tests/test_production_task_checkpoint.py
```

If both focused suites pass, run the full suite:

```powershell
python -m pytest -q
```

Only after that establishes a fresh green baseline, continue with the real production proof:

1. Integrate durable checkpoint persistence into the existing continuation/resume boundary without replaying saved authorization.
2. Exercise a real Blender interruption/restart using a persisted checkpoint.
3. Prove stale checkpoint/evidence cannot write after an external world change.
4. Prove fresh observation creates a new authorization and the resumed mutation returns an authorization-bound receipt.
5. Re-run authoritative final-state verification and require `VERIFIED` for success.
6. Preserve the existing zero-write `BLOCKED` invariant for stale/mismatched authorization.
7. Only after the real durable resume proof is green, expand Digital Twin revision persistence and downstream production workflow integration.

Do not reopen already-proven live authorization/recovery work unless new evidence requires it, and do not claim a new validation result until the commands above have actually been run.
