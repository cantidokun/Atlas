# Atlas Current Development Handoff

**Updated:** August 22, 2026 02:00 EDT  
**Branch:** `feat/blender-adapter-work`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current position

**MAJOR MILESTONE PASSED: generalized Blender task-execution architecture.**

Atlas has now proven two materially different live Blender mutations and migrated both onto the shared `TaskRuntimeSession` lifecycle:

1. **Object rotation** — authorized rotation, persistence, fresh independent transform inspection, invariant verification, receipt validation, and `COMPLETE`.
2. **Marker creation** — absence evidence, conditional authorized creation, persistence, fresh scene inspection, independent collection-membership verification, receipt validation, and `COMPLETE`.

The shared lifecycle is now:

```text
initial evidence
 -> target evaluation
 -> explicit authorization
 -> deterministic action
 -> fresh post-action evidence
 -> independent verification
 -> receipt/completion
```

Task-specific definitions declare evidence, actions, invariants, permitted tools, write policy, and verification policy. The runtime owns lifecycle sequencing and fail-closed completion.

## Current regression status

The latest focused/regression result reported from the runner is **104 passed** after adding the third operation's declarative task coverage.

This is current development/test evidence, but **the third movement task has not yet been proven in live Windows/Blender execution**. Do not infer live success from the 104-test result.

## Third live gate: object movement

The next materially important gate is the existing `move_object` capability through the generalized runtime.

Task contract:

```text
Goal_Left_post
location = [1.0, 2.0, 0.0]
```

Files:

- `planning/object_move_task.py`
- `planning/task_runtime.py`
- canonical Blender movement capability/tool implementation

Required live proof:

1. already-correct fixture produces zero writes;
2. incorrect fixture produces one authorized movement;
3. Blender saves the `.blend`;
4. fresh independent `inspect_object_transform` evidence proves the target location;
5. receipt matches the authorized execution;
6. runtime reaches `COMPLETE`.

A failed or unverifiable post-action inspection must produce `BLOCKED`, never completion.

## Generic runtime milestone

`TaskRuntimeSession` now centralizes:

- initial evidence acquisition;
- target evaluation;
- authorization;
- action execution;
- fresh post-action evidence acquisition;
- independent post-action verification;
- finalization/completion.

Rotation and marker live paths have been migrated onto this lifecycle. The next objective is to prove that adding movement requires only a task definition and does not require rebuilding lifecycle orchestration.

## Authority and verification boundary

- `controller/blender_capabilities.py` defines authorized capability names.
- `planning/blender_tool_schema.py` validates admitted arguments.
- `planning/blender_tool_adapter.py` dispatches authorized capabilities.
- `planning/blender_execution_boundary.py` owns result normalization.
- `planning/blender_execution_receipt.py` binds validated request to verified result.
- `planning/blender_verification.py` owns independent verification primitives.
- `planning/task_runtime.py` owns generic task lifecycle sequencing.

Qwen proposes; Atlas validates, authorizes, executes, tracks, and verifies. Blender is an execution target, never an authority.

## Verification discipline

Historical CI/live results are not proof of current-branch behavior unless explicitly associated with the current commit/workflow. Focused tests are useful regression evidence; live Blender claims require the actual Windows/Blender runner result.

## After the movement gate

If movement passes live, the next milestone is **three-operation generalized live Blender proof** followed by continuation/resume and production-facing multi-task composition. Do not add bespoke lifecycle orchestration for individual tools; extend the declarative task contract and shared runtime instead.

Digital Twin identity/revision, photogrammetry intake, and Unreal production remain later stages. Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state.
