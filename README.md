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

## Current Blender Agent status

**PROVEN MILESTONE: generalized authorization-bound live writes, live multi-operation composition, and live interruption/resume recovery are proven.**

The latest completed full offline suite is:

```text
660 passed in 1.49s
```

This result predates the final authorization-bound corrective-replan receipt fix. A fresh full-suite run is required before treating 660 as the post-fix baseline.

The shared live-write gate has been proven against five real Blender-backed mutation capabilities, with both legitimate authoritative-success and adversarial authoritative-mismatch outcomes:

| Capability | Legitimate live proof | Adversarial live proof |
| --- | --- | --- |
| `set_object_rotation` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

## Live multi-operation composition

The actual Blender runner proved:

```text
ATLAS BLENDER LIVE MULTI-OPERATION COMPOSITION: PASS
ATLAS BLENDER LIVE STALE AUTHORIZATION ZERO-WRITE GATE: PASS
```

This demonstrates a real authorized mutation, external world interruption, stale authorization rejection with zero writes, fresh re-observation/replanning, replacement mutation, and authoritative final verification.

## Live continuation / resume

The actual Blender runner now also proves:

```text
ATLAS BLENDER LIVE CONTINUATION STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE CONTINUATION RESUME: PASS
```

The live continuation proof covers:

```text
Blender observation V1
 -> authorized first mutation
 -> receipt-bound checkpoint
 -> external Blender interruption
 -> fresh observation V2
 -> stale continuation rejected
 -> zero stale writes
 -> fresh ReplanAuthorization
 -> remaining mutation
 -> authorization-bound resumed receipt
 -> authoritative final verification
 -> PASS
```

During this proof, a real defect was found and corrected: corrective-replan execution initially returned a generic receipt without authorization binding. `BlenderExecutionBoundary.execute_authorized_replan()` now creates an authorization-bound `BlenderExecutionReceipt`, preserving the same receipt-binding invariant already enforced for ordinary authorized writes.

## Corrective runtime

The generalized corrective runtime has a clean separation between:

- strict production Blender execution through `BlenderExecutionBoundary`;
- generic/in-memory corrective executors through the generic corrective execution boundary.

Fresh observation, replanning, exact corrective authorization, execution, receipt binding, and re-observation are part of the corrective lifecycle. Multi-step corrective execution re-observes before each mutation and prevents stale authorization from reaching the executor.

Synthetic corrective tests may use operations such as `set_value`; `set_value` is deliberately **not** a production Blender capability.

## Current implementation

Key production boundaries include:

- `planning/blender_capability_catalog.py` — explicit read/write capability classification and fail-closed unknown capabilities.
- `planning/blender_write_authorization.py` — exact-action authorization for scene-writing capabilities.
- `planning/blender_live_write_gate.py` — final authorization-bound write choke point.
- `planning/blender_live_write_result.py` — explicit `VERIFIED` versus `BLOCKED` outcome contract.
- `planning/blender_live_verification.py` — independent authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable receipt with authorization binding for protected writes.
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, authorized-write, and corrective-replan execution APIs.
- `planning/blender_tool_adapter.py` — legacy-result normalization boundary; strict result contracts remain structured.
- `planning/replan_authorization.py` — immutable corrective authorization bound to fresh evidence and the exact replacement action list.
- `planning/continuation_resume.py` — fail-closed continuation checkpoint and fresh-resume authorization.
- `planning/resumable_corrective_task.py` — production resume boundary that never replays saved authorization.

Direct live probes include:

- `live_blender_write_gate_rotation.py`
- `live_blender_write_gate_move.py`
- `live_blender_write_gate_delete.py`
- `live_blender_write_gate_marker.py`
- `live_blender_write_gate_collection.py`
- `live_blender_multi_operation_corrective_composition.py`
- `live_blender_continuation_resume.py`

## Validation discipline

The last completed full offline suite is:

```text
FULL OFFLINE PYTEST SUITE: 660 passed, 0 failed
```

Because the final corrective-replan receipt-binding fix landed afterward, this number must not be represented as current post-fix validation until the suite is rerun.

Live evidence is separate and is backed by actual Windows/Blender runner output. The latest live continuation evidence is explicitly:

```text
ATLAS BLENDER LIVE CONTINUATION STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE CONTINUATION RESUME: PASS
```

## Next development milestone

The major Blender execution/recovery proof chain is now substantially complete. The next target is **durable production-task and Digital Twin state**, beginning with a fresh full offline suite after the final receipt-binding fix.

Sequence:

1. Run `python -m pytest -q` and establish a fresh post-fix baseline.
2. Preserve the live continuation/resume evidence and its zero-write invariant.
3. Formalize durable production-task identity, revision, checkpoint, and receipt persistence without weakening fresh-observation requirements.
4. Introduce Digital Twin identity/revision contracts for the soccer-field-focused production pipeline.
5. Define photogrammetry intake as an upstream reconstruction contract into the canonical Digital Twin.
6. Later integrate broader production workflows while preserving the same authorization, receipt, verification, and fail-closed boundaries.

## Authority and verification boundary

Qwen proposes; Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender is an execution target, never an authority.

```text
Qwen proposal
 -> task/evidence/action validation
 -> authoritative fresh evidence
 -> explicit authorization
 -> deterministic capability execution
 -> normalized result
 -> immutable authorization-bound execution receipt
 -> fresh independent evidence
 -> target verification / replan
 -> continuation checkpoint when interrupted
 -> fresh resume authorization
 -> completion or conservative recovery
```

## Development path

1. fresh post-fix full-suite validation;
2. durable production-task/checkpoint and Digital Twin identity/revision contracts;
3. photogrammetry intake contracts;
4. later Unreal production workflows.

Photogrammetry remains upstream of Blender. Atlas is exclusively concerned with soccer-field-related digital twins; Blender receives the upstream reconstruction for analysis, cleanup, correction, and preparation.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.

## Current checkpoint

**Working branch: `feat/replan-race-gate`**

**Last full offline suite: 660 passed, 0 failed — pre-final receipt-binding fix.**

**Live generalized write gate: 5 capabilities proven with legitimate `VERIFIED` and adversarial `BLOCKED` outcomes.**

**Live multi-operation composition: PASS.**

**Live stale-authorization zero-write gate: PASS.**

**Live continuation stale-state zero-write gate: PASS.**

**Live continuation/resume: PASS.**

The next session should begin with a fresh full offline suite, then move into durable production-task and Digital Twin state rather than reopening already-proven live authorization/recovery work unless new evidence requires it.
