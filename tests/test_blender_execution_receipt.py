import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_verification import BlenderVerificationError


MOVE = {"file_name": "test_scene.blend", "object_name": "Goal_Left_post", "location": [0, 0, 0]}


def test_receipt_binds_request_and_successful_result():
    boundary = BlenderExecutionBoundary(
        lambda tool, args: {"ok": True, "state": "applied", "details": {"object": args["object_name"]}}
    )
    result, receipt = boundary.execute_with_receipt("move_object", MOVE)
    assert isinstance(receipt, BlenderExecutionReceipt)
    assert receipt.matches("move_object", MOVE, result)


def test_receipt_rejects_changed_arguments():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", MOVE)
    changed = {**MOVE, "location": [1, 0, 0]}
    assert not receipt.matches("move_object", changed, result)


def test_receipt_rejects_changed_result():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", MOVE)
    changed = type(result)(result.tool, result.ok, "different", result.details)
    assert not receipt.matches("move_object", MOVE, changed)


def test_failed_execution_never_produces_receipt():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": False, "state": "blocked", "details": {}})
    with pytest.raises(BlenderVerificationError):
        boundary.execute_with_receipt("move_object", MOVE)
