from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.blender_tool_executor import BLENDER_TOOL_HANDLERS
from planning.blender_tool_schema import BLENDER_TOOL_SCHEMAS


def test_every_executable_tool_has_capability_and_schema():
    capabilities = {capability.name for capability in BLENDER_CAPABILITIES}

    assert set(BLENDER_TOOL_HANDLERS) == set(BLENDER_TOOL_SCHEMAS)
    assert set(BLENDER_TOOL_HANDLERS) == capabilities


def test_no_capability_can_be_advertised_without_an_executable_handler():
    capabilities = {capability.name for capability in BLENDER_CAPABILITIES}

    assert capabilities <= set(BLENDER_TOOL_HANDLERS)
