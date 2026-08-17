import pytest

from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_verification import BlenderVerificationError, verify_blender_execution


def result(tool="move_object", ok=True, state="applied"):
    return BlenderExecutionResult(tool, ok, state, {})


def test_accepts_successful_expected_tool():
    checked = verify_blender_execution(result(), "move_object")
    assert checked.ok is True


def test_rejects_wrong_tool():
    with pytest.raises(BlenderVerificationError):
        verify_blender_execution(result(), "inspect_object")


def test_rejects_unsuccessful_execution():
    with pytest.raises(BlenderVerificationError):
        verify_blender_execution(result(ok=False, state="blocked"), "move_object")


def test_rejects_wrong_result_type():
    with pytest.raises(TypeError):
        verify_blender_execution({"ok": True}, "move_object")


def test_rejects_empty_expected_tool():
    with pytest.raises(ValueError):
        verify_blender_execution(result(), "   ")
