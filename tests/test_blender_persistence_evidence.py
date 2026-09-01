import pytest

from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_result_contract import BlenderExecutionResult


def _inspection(location):
    return BlenderExecutionResult(
        tool="inspect_scene",
        ok=True,
        state="inspected",
        details={"objects": [{"name": "Goal_Left_post", "location": list(location)}]},
    )


def test_persistence_evidence_binds_operation_and_fresh_state():
    arguments = {
        "file_name": "atlas_live_mutation.blend",
        "object_name": "Goal_Left_post",
        "location": [0.25, 5.302, 0.0],
    }
    expected_state = {"Goal_Left_post": [0.25, 5.302, 0.0]}
    inspection = _inspection([0.25, 5.302, 0.0])

    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", expected_state, inspection
    )

    assert evidence.matches(
        "move_object", arguments, expected_state, inspection
    )


def test_persistence_evidence_rejects_different_observed_state():
    arguments = {"file_name": "fixture.blend", "object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]}
    expected_state = {"Goal_Left_post": [0.25, 0.0, 0.0]}
    original_inspection = _inspection([0.25, 0.0, 0.0])
    evidence = BlenderPersistenceEvidence.create(
        "move_object", arguments, "inspect_scene", expected_state, original_inspection
    )

    changed_inspection = _inspection([0.0, 0.0, 0.0])
    assert not evidence.matches(
        "move_object", arguments, expected_state, changed_inspection
    )


def test_persistence_evidence_requires_successful_inspection():
    inspection = BlenderExecutionResult(
        tool="inspect_scene",
        ok=False,
        state="failed",
        details={"error": "inspection failed"},
    )

    evidence = BlenderPersistenceEvidence.create(
        "move_object", {"file_name": "fixture.blend"}, "inspect_scene", {}, inspection
    )

    assert not evidence.matches(
        "move_object", {"file_name": "fixture.blend"}, {}, inspection
    )
