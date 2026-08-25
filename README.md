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

**PROVEN MILESTONE: full offline suite green + generalized authorization-bound live-write gate proven across five Blender mutation capabilities.**

The complete Atlas Python test suite now passes:

```text
652 passed in 1.26s
```

This is a fresh result after the corrective-runtime, authorization, receipt, result-normalization, marker, and multi-step compatibility work. Previous `622 passed / 30 failed` and `649 passed / 3 failed` results are superseded.

The shared live-write gate has also been proven against five real Blender-backed mutation capabilities, with both legitimate authoritative-success and adversarial authoritative-mismatch outcomes:

| Capability | Legitimate live proof | Adversarial live proof |
| --- | --- | --- |
| `rotate_object` | `VERIFIED` | `BLOCKED` |
| `move_object` | `VERIFIED` | `BLOCKED` |
| `delete_object` | `VERIFIED` | `BLOCKED` |
| `create_empty_marker` | `VERIFIED` | `BLOCKED` |
| `move_object_to_collection` | `VERIFIED` | `BLOCKED` |

The demonstrated production flow is:

```text
ActionSpec
 -> capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized result
 -> authorization-bound immutable receipt
 -> fresh authoritative final-state verification
 -> VERIFIED / BLOCKED
```

An executor-success signal is not sufficient when authoritative evidence disagrees with the requested final state. The gate fails closed as `BLOCKED`, does not expose a successful receipt, and does not perform an implicit second write.

## Corrective runtime

The generalized corrective runtime now has a clean separation between:

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
- `planning/blender_execution_receipt.py` — immutable receipt with optional authorization binding.
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, authorized-write, and corrective-replan execution APIs.
- `planning/blender_tool_adapter.py` — legacy-result normalization boundary; strict result contracts remain structured.
- `planning/replan_authorization.py` — immutable corrective authorization bound to fresh evidence and the exact replacement action list.

Direct live probes include:

- `live_blender_write_gate_rotation.py`
- `live_blender_write_gate_move.py`
- `live_blender_write_gate_delete.py`
- `live_blender_write_gate_marker.py`
- `live_blender_write_gate_collection.py`

## Validation discipline

The current verified offline baseline is:

```text
FULL OFFLINE PYTEST SUITE: 652 passed, 0 failed
```

The live Blender results are separate evidence. The green offline suite does not itself constitute a live Blender proof; the five capability results above are explicitly backed by observed runner output.

Focused verified clusters from the same development increment include:

```text
receipt / authorization / live-verification: 12 passed
corrective-runtime: 6 passed
final adapter/runtime compatibility: 6 passed
```

Live claims must continue to be backed by actual Windows/Blender runner output.

## Next development milestone

With the complete offline suite green and five generalized live write capabilities proven, the next target is **production-facing multi-operation corrective composition**.

The sequence is:

1. Compose multiple already-proven Blender capabilities through the generalized corrective runtime rather than bespoke per-tool lifecycle code.
2. Demonstrate fresh observation and exact authorization separately for each mutation.
3. Inject a world change between operations and prove stale authorization cannot execute.
4. Replan from fresh evidence and continue through protected execution.
5. Demonstrate authoritative final `VERIFIED` completion for the composed task.
6. Demonstrate adversarial final-state disagreement producing `BLOCKED` with no successful receipt.
7. Preserve the zero-second-write invariant on authoritative mismatch.
8. Then move into continuation/resume integrity across interrupted production tasks.

Do not skip directly to continuation/resume before the multi-operation production composition has an explicit end-to-end proof.

## Authority and verification boundary

Qwen proposes; Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender is an execution target, never an authority.

```text
Qwen proposal
 -> task/evidence/action validation
 -> authoritative fresh evidence
 -> explicit authorization
 -> deterministic capability execution
 -> normalized result
 -> immutable execution receipt
 -> fresh independent evidence
 -> target verification / replan
 -> completion or conservative recovery
```

## Development path

1. production-facing multi-operation corrective composition;
2. continuation/resume across multi-task Blender operations;
3. Digital Twin identity/revision and photogrammetry intake contracts;
4. later Unreal production workflows.

Photogrammetry remains upstream of Blender. Atlas is exclusively concerned with soccer-field-related digital twins; Blender receives the upstream reconstruction for analysis, cleanup, correction, and preparation.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.

## End-of-night checkpoint

**Working branch: `feat/replan-race-gate`**

**Offline suite: 652 passed, 0 failed.**

**Live generalized write gate: 5 capabilities proven with legitimate `VERIFIED` and adversarial `BLOCKED` outcomes.**

Development is intentionally stopping at this milestone. The next session should begin with the production-facing multi-operation composition milestone described above, not by reopening already-green authorization, receipt, or corrective-runtime work unless new evidence requires it.
