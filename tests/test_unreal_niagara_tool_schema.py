import pytest

from planning.unreal_tool_schema import validate_unreal_tool_call


def test_niagara_write_schema_normalizes_name():
    result = validate_unreal_tool_call("apply_niagara_variant", {
        "entity_ids": ["FIELD_SURFACE"],
        "authorization_id": "auth",
        "niagara_variant": {"name": "  sparks  "},
    })
    assert result["niagara_variant"] == {"name": "sparks"}


@pytest.mark.parametrize("tool", ["apply_niagara_variant", "verify_niagara_variant"])
def test_niagara_schema_rejects_extra_fields(tool):
    with pytest.raises(ValueError, match="exactly name"):
        validate_unreal_tool_call(tool, {
            "entity_ids": ["FIELD_SURFACE"],
            "authorization_id": "auth",
            "niagara_variant": {"name": "sparks", "enabled": True},
        })
