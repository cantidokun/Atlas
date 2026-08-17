import pytest

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_result_contract import BlenderExecutionResult
from planning.blender_tool_schema import validate_blender_tool_call


def test_generic_collection_tool_is_admitted_by_blender_schema():
    args = validate_blender_tool_call(
        "create_collection",
        {"file_name": "collection_task_INCORRECT.blend", "collection_name": "Atlas_Test"},
    )
    assert args == {
        "file_name": "collection_task_INCORRECT.blend",
        "collection_name": "Atlas_Test",
    }


def test_generic_collection_tool_rejects_empty_collection_name():
    with pytest.raises(ValueError):
        validate_blender_tool_call(
            "create_collection",
            {"file_name": "collection_task_INCORRECT.blend", "collection_name": ""},
        )


def test_generic_collection_write_can_be_receipt_bound():
    boundary = BlenderExecutionBoundary(
        lambda tool, arguments: {
            "ok": True,
            "state": "created",
            "details": {"collection": arguments["collection_name"]},
        }
    )
    result, receipt = boundary.execute_with_receipt(
        "create_collection",
        {"file_name": "collection_task_INCORRECT.blend", "collection_name": "Atlas_Test"},
    )
    assert isinstance(result, BlenderExecutionResult)
    assert result.ok is True
    assert receipt.matches(
        "create_collection",
        {"file_name": "collection_task_INCORRECT.blend", "collection_name": "Atlas_Test"},
        result,
    )


def test_generic_collection_receipt_detects_argument_mutation():
    boundary = BlenderExecutionBoundary(
        lambda tool, arguments: {
            "ok": True,
            "state": "created",
            "details": {"collection": arguments["collection_name"]},
        }
    )
    arguments = {
        "file_name": "collection_task_INCORRECT.blend",
        "collection_name": "Atlas_Test",
    }
    result, receipt = boundary.execute_with_receipt("create_collection", arguments)
    arguments["collection_name"] = "Tampered"
    assert not receipt.matches("create_collection", arguments, result)
