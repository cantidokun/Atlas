import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult
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


def test_receipt_binds_explicit_mutation_evidence():
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True},
    )
    receipt = BlenderExecutionReceipt.create_authorized(
        "move_object", MOVE, result, "live-auth"
    )
    tampered = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": False},
    )

    assert receipt.matches("move_object", MOVE, result)
    assert not receipt.matches("move_object", MOVE, tampered)


def test_receipt_detects_detail_tampering_beyond_mutation_evidence():
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True},
    )
    receipt = BlenderExecutionReceipt.create("move_object", MOVE, result)
    tampered = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True, "extra": "tampered"},
    )

    assert not receipt.matches("move_object", MOVE, tampered)


def test_receipt_accepts_mapping_arguments():
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True},
    )
    arguments = {"file_name": "test_scene.blend"}
    receipt = BlenderExecutionReceipt.create("move_object", arguments, result)
    assert receipt.matches("move_object", arguments, result)


def test_receipt_rejects_non_mapping_arguments():
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True},
    )

    with pytest.raises(TypeError, match="receipt arguments must be an object"):
        BlenderExecutionReceipt.create("move_object", [], result)
    assert not BlenderExecutionReceipt.create("move_object", MOVE, result).matches(
        "move_object", [], result
    )


def test_receipt_rejects_invalid_authorization_in_match():
    result = BlenderExecutionResult(
        tool="move_object",
        ok=True,
        state="moved",
        details={"mutation_performed": True},
    )
    receipt = BlenderExecutionReceipt.create_authorized(
        "move_object", MOVE, result, "live-auth"
    )
    assert not receipt.matches_authorization("")
    assert not receipt.matches_authorization(None)


def test_failed_execution_never_produces_receipt():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": False, "state": "blocked", "details": {}})
    with pytest.raises(BlenderVerificationError):
        boundary.execute_with_receipt("move_object", MOVE)
