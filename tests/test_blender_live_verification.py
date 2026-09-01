from planning.action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_live_verification import verify_authoritative_write


def _action():
    return ActionSpec(
        tool="move_object",
        arguments={"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]},
    )


def _receipt(action):
    result = type("Result", (), {"ok": True, "state": "ok", "details": {}})()
    return BlenderExecutionReceipt.create(action.tool, action.arguments, result)


def test_authoritative_verification_accepts_matching_state():
    action = _action()
    receipt = _receipt(action)
    ok, state = verify_authoritative_write(
        action,
        receipt,
        lambda _: {"ok": True, "state": {"file_name": "scene.blend", "object_name": "Cube", "location": [1, 2, 3]}},
    )
    assert ok is True
    assert state["ok"] is True


def test_authoritative_verification_blocks_mismatched_state():
    action = _action()
    receipt = _receipt(action)
    ok, state = verify_authoritative_write(
        action,
        receipt,
        lambda _: {"ok": True, "state": {"file_name": "scene.blend", "object_name": "Cube", "location": [9, 9, 9]}},
    )
    assert ok is False
    assert state["ok"] is True


def test_authoritative_verification_blocks_failed_verifier():
    action = _action()
    receipt = _receipt(action)
    ok, _ = verify_authoritative_write(action, receipt, lambda _: {"ok": False})
    assert ok is False


def test_authoritative_verification_blocks_missing_expected_state():
    action = _action()
    receipt = _receipt(action)
    ok, state = verify_authoritative_write(
        action,
        receipt,
        lambda _: {"ok": True, "state": {"object_name": "Cube"}},
    )
    assert ok is False
    assert state["verification_error"] == "missing_authoritative_fields"
    assert "location" in state["missing_fields"]
