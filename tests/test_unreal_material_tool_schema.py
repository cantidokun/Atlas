import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def _arguments(name="blue"):
    return {
        "entity_ids": ["FIELD_SURFACE"],
        "authorization_id": "material-auth",
        "material_variant": {"name": name},
    }


def test_apply_material_variant_accepts_valid_arguments():
    result = validate_unreal_tool_call("apply_material_variant", _arguments())
    assert result["entity_ids"] == ("FIELD_SURFACE",)
    assert result["material_variant"] == {"name": "blue"}


def test_verify_material_variant_accepts_valid_arguments():
    result = validate_unreal_tool_call("verify_material_variant", _arguments("red"))
    assert result["material_variant"] == {"name": "red"}


def test_apply_material_variant_requires_variant():
    arguments = _arguments()
    del arguments["material_variant"]
    with pytest.raises(ValueError, match="missing required argument: material_variant"):
        validate_unreal_tool_call("apply_material_variant", arguments)


def test_material_variant_rejects_extra_keys():
    arguments = _arguments()
    arguments["material_variant"]["slot"] = "body"
    with pytest.raises(ValueError, match="exactly name"):
        validate_unreal_tool_call("apply_material_variant", arguments)


def test_material_variant_rejects_empty_name():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_unreal_tool_call("apply_material_variant", _arguments("   "))
