"""Deterministic tests for the thin Blender adapter (normalizes inspection payloads into the
canonical kernel model WITHOUT validating). No bpy, no live Blender."""

import pytest

from planning.blender import run_scene_health
from planning.blender.blender_adapter import (
    build_scene_model_from_blender,
    evaluate_blender_inspection,
    report_from_verified_result,
    scene_from_inspect_payload,
)
from planning.blender.scene_model import MeshModel, SceneModel
from planning.blender_result_contract import BlenderExecutionResult


def _inspect_payload():
    return {
        "objects": [
            {
                "object_id": "pitch",
                "name": "pitch",
                "location": [0, 0, 0],
                "mesh": {
                    "mesh_id": "pitch_mesh",
                    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
                    "faces": [[0, 1, 2], [1, 3, 2]],
                },
            },
            {"object_id": "goal_left", "name": "goal_left"},
            {"object_id": "goal_right", "name": "goal_right"},
        ]
    }


def test_scene_from_inspect_payload_is_canonical():
    scene = scene_from_inspect_payload(_inspect_payload())
    assert isinstance(scene, SceneModel)
    assert scene.scene_id == "atlas_scene"
    assert isinstance(scene.objects[0].mesh, MeshModel)


def test_adapter_invoke_kernel_no_validation_duplication():
    report = evaluate_blender_inspection(_inspect_payload())
    # The report came from the same deterministic kernel; it is a SceneReport with a state.
    assert report.validation_state in {"production_ready", "analyzed", "needs_review"}
    assert report.scene_id == "atlas_scene"


def test_report_from_verified_result_uses_details_only():
    result = BlenderExecutionResult(
        tool="inspect_scene", ok=True, state="inspected", details=_inspect_payload()
    )
    report = report_from_verified_result(result)
    assert report.scene_id == "atlas_scene"


def test_adapter_rejects_non_dict():
    with pytest.raises(TypeError):
        scene_from_inspect_payload([1, 2])


def test_adapter_thin_no_semantics():
    # The adapter must NOT impose validation: an invalid mesh passes through to the kernel,
    # which (not the adapter) emits the finding.
    payload = {
        "objects": [
            {
                "object_id": "pitch",
                "name": "pitch",
                "mesh": {"mesh_id": "m", "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 99]]},
            },
            {"object_id": "goal_left", "name": "goal_left"},
            {"object_id": "goal_right", "name": "goal_right"},
        ]
    }
    report = evaluate_blender_inspection(payload)
    codes = {f.code.value for f in report.findings}
    assert "MESH_INVALID_INDEX" in codes  # kernel emitted it, adapter did not block
    assert report.validation_state == "needs_review"