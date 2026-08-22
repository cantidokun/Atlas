import pytest

from planning.blender_tool_adapter import BlenderToolAdapter


def test_adapter_exposes_explicit_capabilities_without_normalizing_results():
    calls = []

    def move_object(**arguments):
        calls.append(arguments)
        return {"status": "moved", "object_name": arguments["object_name"]}

    adapter = BlenderToolAdapter({"move_object": move_object})

    assert adapter.supported_tools == ("move_object",)
    result = adapter("move_object", {
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 3.0],
    })

    assert result == {
        "status": "moved",
        "object_name": "Goal_Left_post",
    }
    assert calls == [{
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 3.0],
    }]


def test_adapter_does_not_expand_authority_or_accept_unknown_tools():
    adapter = BlenderToolAdapter({"move_object": lambda **_: {"status": "moved"}})

    with pytest.raises(ValueError, match="does not expose capability"):
        adapter("delete_object", {"file_name": "scene.blend", "object_name": "Goal_Left_post"})


def test_adapter_preserves_raw_contract_results_for_shared_boundary_normalization():
    raw = {"ok": True, "state": "moved", "details": {"verified": True}}
    adapter = BlenderToolAdapter({"move_object": lambda **_: raw})

    assert adapter("move_object", {
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 3.0],
    }) is raw


def test_adapter_forwards_error_response_without_reinterpreting_it():
    raw = {"error": "Object not found"}
    adapter = BlenderToolAdapter({"rename_object": lambda **_: raw})

    assert adapter("rename_object", {
        "file_name": "object_rename_INCORRECT.blend",
        "object_name": "Goal_Left_post",
        "new_name": "Goal_Left_Post",
    }) is raw


def test_adapter_copies_argument_mapping_before_dispatch():
    received = []

    def tool(**arguments):
        received.append(arguments)
        return {"status": "moved"}

    adapter = BlenderToolAdapter({"move_object": tool})
    arguments = {
        "object_name": "Goal_Left_post",
        "location": [1.0, 2.0, 3.0],
    }

    adapter("move_object", arguments)
    arguments["object_name"] = "Tampered"

    assert received[0]["object_name"] == "Goal_Left_post"


def test_adapter_rejects_invalid_registry_entries():
    with pytest.raises(ValueError, match="requires at least one capability"):
        BlenderToolAdapter({})

    with pytest.raises(ValueError, match="non-empty strings"):
        BlenderToolAdapter({"": lambda **_: {}})

    with pytest.raises(TypeError, match="not callable"):
        BlenderToolAdapter({"move_object": object()})
