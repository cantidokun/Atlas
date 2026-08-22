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

**Current milestone position: controlled execution architecture complete; real Blender mutation/persistence proof gate next.**

The current architecture is:

```text
Qwen proposal
 -> task/evidence/action validation
 -> authoritative pre-action evidence
 -> target-state evaluation
 -> conditional decision
 -> explicit authorization
 -> deterministic action
 -> Blender capability adapter
 -> normalized result
 -> fresh independent post-action evidence
 -> target-state verification
 -> immutable execution receipt
 -> completion / conservative recovery
```

The important architectural separation is:

- capability catalog defines what Atlas is authorized to use;
- schemas validate admitted arguments;
- `BlenderToolAdapter` maps authorized names to concrete Blender implementations;
- `BlenderExecutionBoundary` owns result normalization and verification;
- receipts bind the validated request to the verified result;
- generic task/runtime primitives enforce ordering and completion.

### Current real-mutation proof task

The next live gate uses the non-goalpost object-rotation task:

```text
Atlas_Rotation_Candidate
rotation = [0.0, 0.0, 90.0] degrees
```

The intended proof is:

```text
incorrect fixture
 -> inspect
 -> target unsatisfied
 -> authorize
 -> rotate
 -> save .blend
 -> receipt
 -> fresh independent inspect
 -> invariant satisfied
 -> COMPLETE
```

The already-correct fixture must remain a zero-write path followed by fresh verification. A failed or unverifiable post-action inspection must produce `BLOCKED`, never completion.

Relevant files:

- `planning/blender_tool_adapter.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_result_contract.py`
- `planning/blender_verification.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_autonomous_executor.py`
- `planning/object_rotation_task.py`
- `planning/task_runtime.py`
- `tools/blender_transform.py`
- `live_qwen_object_rotation.py`

## Verification discipline

Historical CI/live results in this repository describe earlier commits unless explicitly associated with the current branch/commit. Do not infer current success from historical results. Only actual test/workflow output establishes current verification.

## Development path

1. establish real Blender mutation + persistence proof;
2. generalize the verified loop across materially different Blender tasks;
3. expand production-facing continuation/resume across multiple task types;
4. advance Digital Twin identity/revision and photogrammetry intake contracts;
5. later integrate Unreal production workflows.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.
