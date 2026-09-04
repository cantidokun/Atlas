import copy

import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_verification import BlenderVerificationError


def test_receipt_binds_request_and_successful_result():
    boundary = BlenderExecutionBoundary(
        lambda tool, args: {"ok": True, "state": "applied", "details": {"object": args["object_name"]}}
    )
    result, receipt = boundary.execute_with_receipt(
        "move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]}
    )
    assert isinstance(receipt, BlenderExecutionReceipt)
    assert receipt.matches("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]}, result)


def test_receipt_digest_is_deterministic():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
    assert receipt.digest() == receipt.digest()
    assert receipt.digest() == BlenderExecutionReceipt.create(
        "move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]}, result
    ).digest()


def test_receipt_snapshot_round_trip_preserves_integrity():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
    restored = BlenderExecutionReceipt.from_snapshot(receipt.snapshot())
    assert restored == receipt
    restored.verify_integrity(receipt.digest())


def test_receipt_snapshot_rejects_unknown_fields():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    _, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post"})
    snapshot = copy.deepcopy(receipt.snapshot())
    snapshot["authorization"] = "atlas-issued"
    with pytest.raises(ValueError, match="fields are invalid"):
        BlenderExecutionReceipt.from_snapshot(snapshot)


def test_receipt_integrity_fails_closed_after_tampering():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    _, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post"})
    digest = receipt.digest()
    tampered = BlenderExecutionReceipt(
        tool=receipt.tool,
        arguments_digest="tampered",
        result_digest=receipt.result_digest,
    )
    with pytest.raises(ValueError, match="integrity check failed"):
        tampered.verify_integrity(digest)


def test_receipt_rejects_changed_arguments():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
    assert not receipt.matches("move_object", {"object_name": "Goal_Left_post", "location": [1, 0, 0]}, result)


def test_receipt_rejects_changed_result():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": True, "state": "applied", "details": {}})
    result, receipt = boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
    changed = type(result)(result.tool, result.ok, "different", result.details)
    assert not receipt.matches("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]}, changed)


def test_failed_execution_never_produces_receipt():
    boundary = BlenderExecutionBoundary(lambda tool, args: {"ok": False, "state": "blocked", "details": {}})
    with pytest.raises(BlenderVerificationError):
        boundary.execute_with_receipt("move_object", {"object_name": "Goal_Left_post", "location": [0, 0, 0]})
