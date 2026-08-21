import pytest

from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS
from tools import TOOLS


def test_public_tools_capabilities_and_schemas_are_exactly_aligned():
    public_tools = set(TOOLS)
    capabilities = {capability.name for capability in BLENDER_CAPABILITIES}
    schemas = set(BLENDER_TOOL_SCHEMAS)

    assert public_tools == capabilities == schemas


def test_every_public_blender_tool_is_callable():
    assert TOOLS
    assert all(callable(tool) for tool in TOOLS.values())


def test_unknown_tool_cannot_be_validated():
    from planning.blender_tool_schema import validate_blender_tool_call

    with pytest.raises(ValueError, match="unsupported Blender tool"):
        validate_blender_tool_call("not_a_real_tool", {})


def test_schema_rejects_missing_required_arguments():
    from planning.blender_tool_schema import validate_blender_tool_call

    with pytest.raises(ValueError, match="missing required argument"):
        validate_blender_tool_call("inspect_scene", {})
