from planning.blender_task_verifier import verify_object_location
from planning.blender_result_contract import BlenderExecutionResult


def result(location):
    return BlenderExecutionResult(
        tool="inspect_object_transform",
        ok=True,
        state="completed",
        details={"object_name": "Goal_Left_post", "location": location},
    )


def test_location_verification_passes_within_tolerance():
    decision = verify_object_location(
        result([0.25005, 0.0, 0.0]),
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    assert decision.ok is True


def test_location_verification_accepts_canonical_mapping():
    decision = verify_object_location(
        {
            "ok": True,
            "state": "completed",
            "details": {"object_name": "Goal_Left_post", "location": [0.25, 0.0, 0.0]},
        },
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    assert decision.ok is True


def test_location_verification_rejects_wrong_object():
    decision = verify_object_location(
        result([0.25, 0.0, 0.0]),
        object_name="Goal_Right_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    assert decision.ok is False


def test_location_verification_rejects_wrong_position():
    decision = verify_object_location(
        result([0.30, 0.0, 0.0]),
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    assert decision.ok is False
