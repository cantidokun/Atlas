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

**Current milestone: generalized Blender task-execution architecture established; third live mutation proof is the next gate.**

Atlas has now demonstrated real Blender rotation and marker-creation workflows and migrated both onto the shared `TaskRuntimeSession` lifecycle. The next operation, object movement, is implemented and regression-tested but has not yet received live Windows/Blender proof.

The generic lifecycle is:

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

### Proven live mutations

**Rotation**

```text
Atlas_Rotation_Candidate
rotation = [0.0, 0.0, 90.0] degrees
```

**Marker creation**

```text
Atlas_Marker
EMPTY
inside Atlas_Test
```

Both use the shared task/runtime architecture and require fresh independent Blender evidence before completion.

### Next live gate: object movement

The third task is declaratively defined as:

```text
Goal_Left_post
location = [1.0, 2.0, 0.0]
```

The intended proof is:

```text
incorrect fixture
 -> inspect location
 -> target unsatisfied
 -> authorize
 -> move
 -> save .blend
 -> fresh independent inspect
 -> location invariant satisfied
 -> receipt validated
 -> COMPLETE
```

The already-correct path must remain zero-write followed by fresh verification. Any failed or unverifiable post-action inspection must produce `BLOCKED`, never completion.

Relevant files include:

- `planning/task_runtime.py`
- `planning/object_rotation_task.py`
- `planning/marker_task.py`
- `planning/object_move_task.py`
- `planning/blender_tool_adapter.py`
- `planning/blender_execution_boundary.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_autonomous_executor.py`

## Verification discipline

Historical CI/live results describe earlier commits unless explicitly associated with the current branch/commit. The current movement task has **104 focused/regression tests passing**, but that does not constitute live Windows/Blender proof. Only actual current workflow/test output establishes live verification.

## Development path

1. prove a third materially different Blender mutation through the shared runtime;
2. generalize continuation/resume and multi-task production composition;
3. advance Digital Twin identity/revision and photogrammetry intake contracts;
4. later integrate Unreal production workflows.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.
