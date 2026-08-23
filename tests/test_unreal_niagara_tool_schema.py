import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def _args(name="goal_burst"):
    return {"entity_ids": ("FIELD_SURFACE",), "authorization_id": "niagara-auth", "niagara_variant": {"name": name}}


def test_niagara_write_schema_normalizes_name():
    assert validate_unreal_tool_call("apply_niagara_variant", _args("  goal_burst  "))["niagara_variant"] == {"name": "goal_burst"}


def test_niagara_schema_rejects_extra_keys():
    args = _args()
    args["niagara_variant"] = {"name": "goal_burst", "system": "x"}
    with pytest.raises(ValueError, match="exactly name"):
        validate_unreal_tool_call("apply_niagara_variant", args)


def test_niagara_schema_rejects_empty_name():
    args = _args("   ")
    with pytest.raises(ValueError, match="non-empty string"):
        validate_unreal_tool_call("apply_niagara_variant", args)
