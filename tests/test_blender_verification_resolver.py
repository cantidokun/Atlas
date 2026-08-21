import pytest

from planning.blender_verification_resolver import (
    object_location_resolver,
    object_locations_resolver,
)
from planning.future_generator import FutureStep


def test_object_location_resolver_uses_fresh_inspection():
    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        return type(
            "Result",
            (),
            {
                "ok": True,
                "details": {
                    "object_name": "Goal_Left_post",
                    "location": [0.25, 0.0, 0.0],
                },
            },
        )()

    resolve = object_location_resolver(
        file_name="fixture.blend",
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    result = resolve(FutureStep(0, "verification.pending", "VERIFICATION", "Verify."), execute)

    assert result["satisfied"] is True
    assert calls == [("inspect_object_transform", {"file_name": "fixture.blend", "object_name": "Goal_Left_post"})]


def test_object_location_resolver_rejects_non_verification_step():
    resolve = object_location_resolver(
        file_name="fixture.blend",
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    with pytest.raises(ValueError, match="VERIFICATION"):
        resolve(FutureStep(0, "action.0", "ACTION", "Act."), lambda *_: None)


def test_object_location_resolver_returns_failed_postcondition():
    def execute(tool, arguments):
        return type(
            "Result",
            (),
            {
                "ok": True,
                "details": {
                    "object_name": "Goal_Left_post",
                    "location": [0.0, 0.0, 0.0],
                },
            },
        )()

    resolve = object_location_resolver(
        file_name="fixture.blend",
        object_name="Goal_Left_post",
        expected_location=(0.25, 0.0, 0.0),
    )
    result = resolve(FutureStep(0, "verification.pending", "VERIFICATION", "Verify."), execute)

    assert result["satisfied"] is False
    assert result["reason"] == "object location differs from expected state"


def test_object_locations_resolver_requires_every_object_to_pass():
    def execute(tool, arguments):
        location = {
            "Goal_Left_post": [0.25, 5.0, 0.0],
            "Goal_Right_Post": [-0.25, -5.0, 0.0],
        }[arguments["object_name"]]
        return {
            "ok": True,
            "state": "completed",
            "details": {"object_name": arguments["object_name"], "location": location},
        }

    resolve = object_locations_resolver(
        file_name="fixture.blend",
        expected_locations={
            "Goal_Left_post": (0.25, 5.0, 0.0),
            "Goal_Right_Post": (-0.25, -5.0, 0.0),
        },
    )
    result = resolve(FutureStep(0, "verification.pending", "VERIFICATION", "Verify."), execute)

    assert result["satisfied"] is True
    assert set(result["evidence"]) == {"Goal_Left_post", "Goal_Right_Post"}
