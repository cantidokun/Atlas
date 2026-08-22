import pytest

from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.blender_tool_adapter import BlenderToolAdapter
from tools import TOOLS


def test_default_adapter_matches_authorized_capability_surface():
    adapter = BlenderToolAdapter()
    declared = {capability.name for capability in BLENDER_CAPABILITIES}
    executable = set(TOOLS)

    assert set(adapter.supported_tools) == declared == executable


def test_adapter_dispatches_without_reinterpreting_result():
    raw = {"status": "moved", "object_name": "Goal_Left_post"}
    calls = []

    def move_object(**arguments):
        calls.append(arguments)
        return raw

    adapter = BlenderToolAdapter({"move_object": move_object})
    arguments = {"object_name": "Goal_Left_post", "location": [1.0, 2.0, 3.0]}

    assert adapter("move_object", arguments) is raw
    assert calls == [arguments]
    assert adapter.supported_tools == ("move_object",)


def test_adapter_rejects_unknown_capability():
    adapter = BlenderToolAdapter({"move_object": lambda **_: {"ok": True, "state": "moved"}})

    with pytest.raises(ValueError, match="does not expose capability"):
        adapter("delete_object", {"object_name": "Goal_Left_post"})


def test_adapter_copies_argument_mapping_before_dispatch():
    received = []

    def tool(**arguments):
        received.append(arguments)
        return {"ok": True, "state": "moved", "details": {}}

    adapter = BlenderToolAdapter({"move_object": tool})
    arguments = {"object_name": "Goal_Left_post", "location": [1.0, 2.0, 3.0]}
    adapter("move_object", arguments)
    arguments["object_name"] = "Tampered"

    assert received[0]["object_name"] == "Goal_Left_post"


def test_adapter_rejects_invalid_registry_entries():
    with pytest.raises(ValueError, match="at least one capability"):
        BlenderToolAdapter({})
    with pytest.raises(ValueError, match="non-empty strings"):
        BlenderToolAdapter({"": lambda **_: {}})
    with pytest.raises(TypeError, match="not callable"):
        BlenderToolAdapter({"move_object": object()})
