import pytest

from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.blender_capability_surface import validate_blender_capability_surface
from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS
from tools import TOOLS


def test_complete_public_blender_surface_is_consistent():
    names = validate_blender_capability_surface(
        TOOLS,
        BLENDER_CAPABILITIES,
        BLENDER_TOOL_SCHEMAS,
    )
    assert names == tuple(sorted(TOOLS))


def test_surface_gate_detects_missing_capability():
    capabilities = tuple(capability for capability in BLENDER_CAPABILITIES if capability.name != "delete_object")

    with pytest.raises(ValueError, match="Blender tool/capability drift"):
        validate_blender_capability_surface(TOOLS, capabilities, BLENDER_TOOL_SCHEMAS)


def test_surface_gate_detects_missing_schema():
    schemas = dict(BLENDER_TOOL_SCHEMAS)
    schemas.pop("rename_object")

    with pytest.raises(ValueError, match="Blender tool/schema drift"):
        validate_blender_capability_surface(TOOLS, BLENDER_CAPABILITIES, schemas)


def test_surface_gate_detects_non_callable_tool():
    tools = dict(TOOLS)
    tools["inspect_scene"] = object()

    with pytest.raises(ValueError, match="must be callable"):
        validate_blender_capability_surface(tools, BLENDER_CAPABILITIES, BLENDER_TOOL_SCHEMAS)
