# Atlas Current Development Handoff

**Updated:** August 21, 2026 22:10 EDT  
**Branch:** `feat/blender-adapter-work`  
**Purpose:** canonical resume point for Atlas Blender-Agent development.

## Current position

**MAJOR MILESTONE PASSED: real Blender mutation + persistence proof.**

The live `Live Object Rotation Regression` workflow completed successfully on the development branch. The workflow exercises both `already-correct` and `incorrect` fixtures. The incorrect path performs the authorized rotation, saves the Blender file, performs a fresh independent transform inspection, verifies the target invariant, validates the receipt, and requires the runtime to reach `COMPLETE`. The already-correct path requires zero writes followed by fresh verification.

The live task source explicitly fails the run if the receipt mismatches, post-action verification fails, or the runtime does not reach `COMPLETE`.

## Closed-loop architecture

```text
Qwen proposal
 -> task/evidence/action validation
 -> authoritative pre-action evidence
 -> target-state evaluation
 -> conditional decision
 -> explicit authorization
 -> deterministic action
 -> concrete Blender adapter
 -> normalized execution result
 -> fresh independent post-action evidence
 -> target-state verification
 -> immutable execution receipt
 -> COMPLETE / conservative recovery
```

Qwen proposes; Python validates, authorizes, executes, tracks, and verifies. Blender is an execution adapter, not an authority.

## Adapter and authority boundary

- `planning/blender_tool_adapter.py` — explicit immutable capability-to-implementation dispatch.
- `controller/blender_capabilities.py` — authorized capability catalog.
- `planning/blender_tool_schema.py` — argument admission/schema boundary.
- `tools/__init__.py` — concrete Blender tool registry.

The adapter intentionally does not normalize or reinterpret results. Result normalization remains in `BlenderExecutionBoundary`.

Capability/schema/tool parity tests prevent authority drift.

`AtlasTaskDefinition` now freezes the permitted action-tool set at construction, preventing callers from mutating the authorization surface after validation.

## Verified execution integrity primitives

- `planning/blender_execution_boundary.py`
- `planning/blender_result_contract.py`
- `planning/blender_verification.py`
- `planning/blender_execution_receipt.py`
- `planning/blender_autonomous_executor.py`
- `tools/blender_process.py`

The Blender subprocess boundary fails closed on non-zero exit, missing result markers, malformed JSON, or non-object results. Receipts bind validated tool + arguments + verified normalized result.

## Generic task/runtime layer

`AtlasTaskDefinition` and `planning/task_runtime.py` separate task data from generic lifecycle enforcement. Task definitions declare evidence, actions, target invariants, permitted writes, and verification policy; runtime enforces ordering and completion rules.

## Proven live task: object rotation

Files:
- `planning/object_rotation_task.py`
- `tools/blender_transform.py`
- `live_qwen_object_rotation.py`
- `.github/workflows/live-object-rotation.yml`

Target:

```text
Atlas_Rotation_Candidate
rotation = [0.0, 0.0, 90.0] degrees
```

Proven loop:

```text
incorrect fixture
 -> Qwen constrained plan
 -> authoritative pre-action inspection
 -> target unsatisfied
 -> explicit authorization
 -> set_object_rotation
 -> Blender saves .blend
 -> receipt validation
 -> fresh inspect_object_transform
 -> target rotation invariant satisfied
 -> COMPLETE
```

The already-correct fixture is also exercised as a zero-write path followed by fresh verification.

## Next major milestone

**GENERALIZED MULTI-TASK LIVE BLENDER PROOF**

The next gate is to demonstrate that the same generic adapter/runtime/receipt/verification architecture works for a materially different Blender mutation, not merely object rotation.

The first candidate is the existing **marker creation** task:

```text
Atlas_Marker exists as EMPTY
inside Atlas_Test
```

Existing files already provide the declarative task and live Qwen path:

- `planning/marker_task.py`
- `live_qwen_marker_task.py`
- `scripts/provision_marker_task_fixtures.py`
- `.github/workflows/live-object-marker.yml`

The marker workflow has now been enabled on `feat/blender-adapter-work` so the same real Windows/Blender runner can prove the second task against the current adapter architecture.

Required evidence for the next milestone:

1. already-correct marker fixture produces zero writes;
2. incorrect marker fixture performs exactly one authorized creation;
3. Blender persists the marker;
4. fresh independent scene inspection proves the marker exists and is an EMPTY;
5. receipt matches execution;
6. runtime reaches `COMPLETE`.

Any failed/unverifiable post-action inspection must produce `BLOCKED`, never completion.

## Verification discipline

Historical CI/live results in older documentation are not proof of the current adapter branch. Current-branch claims must be based on actual workflow/test evidence. The rotation milestone is supported by the observed green live workflow and the live script's explicit failure assertions.

## After the next gate

Once a second materially different task passes, generalize continuation/resume across multiple task types and move toward production-facing Blender task composition rather than adding bespoke orchestration per tool.

Digital Twin identity/revision, photogrammetry intake, and Unreal production remain future stages. Photogrammetry is upstream of Blender; Atlas owns canonical Digital Twin identity/state.
