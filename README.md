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

**PROVEN MILESTONE: generalized Blender authorization-bound writes, corrective replanning, interruption/resume recovery, durable checkpoints, canonical Digital Twin registry binding, and production completion authority are proven offline and through the live Blender/runtime paths exercised so far.**

Latest completed full offline suite:

```text
711 passed in 1.36s
```

The latest focused registry-backed production resume suite is:

```text
3 passed
```

## Live production completion

The production completion boundary is live-proven for both terminal cases:

```text
ATLAS LIVE PRODUCTION COMPLETION VERIFIED-STATE GATE: PASS
ATLAS LIVE PRODUCTION COMPLETION WRONG-STATE BLOCK GATE: PASS
```

The invariant is:

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

The live durable checkpoint path is proven:

```text
ATLAS BLENDER LIVE DURABLE CHECKPOINT STALE-STATE ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE DURABLE CHECKPOINT RESUME: PASS
```

The registry-aware live continuation path is proven:

```text
ATLAS BLENDER LIVE REGISTRY STALE-REVISION ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE REGISTRY DURABLE RESUME: PASS
```

The rehydrated production completion path is also proven:

```text
ATLAS LIVE REGISTRY REHYDRATED COMPLETION GATE: PASS
ATLAS LIVE REGISTRY REHYDRATED WRONG-STATE BLOCK GATE: PASS
```

The durable production resume chain is:

```text
registry reload
 -> canonical Digital Twin revision
 -> checkpoint integrity + validated parent lineage
 -> fresh observation
 -> fresh resume/replan authorization
 -> authorized Blender continuation
 -> authorization-bound receipt
 -> authoritative final evidence
 -> ProductionCompletionReceipt
 -> COMPLETED / BLOCKED
```

Saved authorization is never replayed. Checkpoint persistence is state/audit lineage, not an execution credential.

## Live Blender capabilities

The shared live-write gate has been proven against five real Blender-backed mutation capabilities with both legitimate authoritative-success and adversarial authoritative-mismatch outcomes:

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
ATLAS BLENDER LIVE REGISTRY STALE-REVISION ZERO-WRITE GATE: PASS
ATLAS BLENDER LIVE REGISTRY DURABLE RESUME: PASS
```

## Corrective and completion runtime

The generalized corrective runtime maintains separation between:

- protected Blender execution through `BlenderExecutionBoundary`;
- generic/in-memory corrective execution through the generic corrective boundary;
- durable checkpoint/resume state;
- production completion authority;
- immutable production completion evidence.

Fresh observation, replanning, exact corrective authorization, execution, receipt binding, re-observation, and authoritative verification are distinct lifecycle boundaries.

Synthetic corrective tests may use operations such as `set_value`; `set_value` is deliberately **not** a production Blender capability.

## Durable production architecture

Key production boundaries include:

- `planning/blender_capability_catalog.py` — explicit read/write capability classification and fail-closed unknown capabilities.
- `planning/blender_write_authorization.py` — exact-action authorization for scene-writing capabilities.
- `planning/blender_live_write_gate.py` — final authorization-bound write choke point.
- `planning/blender_live_verification.py` — independent authoritative post-write verification.
- `planning/blender_execution_receipt.py` — immutable authorization-bound execution receipt.
- `planning/blender_execution_boundary.py` — authorized writes and corrective-replan execution APIs.
- `planning/replan_authorization.py` — immutable corrective authorization bound to fresh evidence and exact replacement actions.
- `planning/production_task_checkpoint.py` — immutable durable checkpoint contract.
- `planning/production_checkpoint_lifecycle.py` — checkpoint persistence, canonical revision, and parent-lineage validation.
- `planning/durable_resumable_corrective_task.py` — durable fresh-resume boundary.
- `planning/digital_twin_registry.py` — persisted canonical Digital Twin identity/revision registry.
- `planning/production_operation_lifecycle.py` — authoritative production `COMPLETED` / `BLOCKED` decision.
- `planning/production_completion_receipt.py` — immutable production completion receipt.
- `planning/production_autonomous_runtime_bridge.py` — narrow autonomous-runtime-to-production completion bridge.
- `planning/production_registry_resume_lifecycle.py` — registry-backed production continuation and completion lifecycle.

## Authority and verification boundary

```text
Qwen proposal
 -> task/evidence/action validation
 -> explicit capability admission
 -> fresh authoritative evidence
 -> exact authorization
 -> deterministic Blender execution
 -> normalized result
 -> immutable authorization-bound receipt
 -> fresh independent evidence
 -> target verification / corrective replan
 -> durable checkpoint when interrupted
 -> canonical revision + parent-lineage validation
 -> fresh resume authorization
 -> resumed write
 -> authoritative production completion verification
 -> ProductionCompletionReceipt
 -> COMPLETED / BLOCKED
```

Qwen proposes; Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender is an execution target, never an authority.

## Architectural constraints

- Only explicitly admitted Blender capabilities execute.
- Corrective planning uses fresh world state.
- `ReplanAuthorization` must match fresh evidence and the exact replacement action list.
- Ordinary writes must match exact `BlenderWriteAuthorization`.
- Receipts bind the executed action/result and authorization identity.
- Missing, stale, changed, or unbound authorization fails closed.
- `VERIFIED` requires authoritative verification and a receipt.
- `COMPLETED` requires authoritative verification and a production completion receipt.
- Wrong authoritative state is `BLOCKED`, even after executor success.
- Zero-write guarantees must be preserved on stale/unauthorized paths.
- Exhausting a corrective budget is not success.
- Do not add generic test operations such as `set_value` to the production Blender capability catalog.
- Avoid bespoke per-tool lifecycle orchestration in place of the generalized runtime.
- C++ interoperability remains a future architectural requirement; keep subsystem contracts language-agnostic.
- Photogrammetry is upstream of Blender; Atlas is exclusively concerned with soccer-field-related digital twins.

## Validation discipline

Live evidence is separate from offline testing and is backed by actual Windows/Blender runner output. Do not infer a live result from the pytest suite.

Current recorded offline baseline:

```text
FULL OFFLINE PYTEST SUITE: 711 passed, 0 failed
```

Current branch:

```text
feat/replan-race-gate
```

The Actions runner is active and available for workflow execution.

## End-of-session checkpoint

The durable registry-backed production resume, production completion authority, and immutable completion-receipt milestones are green. Development is paused for the night/session.

Next session:

1. `git pull --ff-only origin feat/replan-race-gate`
2. `python -m pytest -q` to re-establish the **711-test** baseline.
3. Preserve the already-proven live registry/resume/completion gates.
4. Continue with the remaining production-facing orchestration/continuation surface using the existing generic boundaries rather than creating another checkpoint, authorization, or completion mechanism.

See `ATLAS_HANDOFF_CURRENT.md` for the canonical resume point and `DEVELOPMENT_LOG.md` for chronological progress.
