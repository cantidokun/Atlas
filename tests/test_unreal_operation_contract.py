import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind
from planning.unreal_operation_contract import parse_unreal_operation


def payload(**overrides):
    value = {
        "capability": "material",
        "kind": "write",
        "name": "apply_material_variant",
        "arguments": {
            "entity_ids": ["FIELD_SURFACE"],
            "material_variant": {"name": "liquid_surface"},
        },
        "entity_ids": ["FIELD_SURFACE"],
    }
    value.update(overrides)
    return value


def test_contract_parses_canonical_operation():
    operation = parse_unreal_operation(payload())
    assert operation.capability is UnrealCapability.MATERIAL
    assert operation.kind is UnrealOperationKind.WRITE
    assert operation.entity_ids == ("FIELD_SURFACE",)


def test_contract_parses_actor_location_write():
    operation = parse_unreal_operation(
        payload(
            capability="modify_actor",
            kind="write",
            name="set_actor_location",
            arguments={
                "entity_ids": ["FIELD_SURFACE"],
                "location": {"x": 100.0, "y": 200.0, "z": 300.0},
            },
        )
    )
    assert operation.capability is UnrealCapability.MODIFY_ACTOR
    assert operation.kind is UnrealOperationKind.WRITE
    assert operation.name == "set_actor_location"
    assert operation.entity_ids == ("FIELD_SURFACE",)
    assert operation.arguments["location"] == {"x": 100.0, "y": 200.0, "z": 300.0}


def test_contract_rejects_actor_location_write_without_location():
    with pytest.raises(ValueError, match="capability schema"):
        parse_unreal_operation(
            payload(
                capability="modify_actor",
                kind="write",
                name="set_actor_location",
            )
        )


def test_contract_rejects_extra_top_level_keys():
    with pytest.raises(ValueError, match="contract schema"):
        parse_unreal_operation(payload(authorization="approved"))


def test_contract_rejects_unknown_capability():
    with pytest.raises(ValueError, match="unsupported Unreal capability"):
        parse_unreal_operation(payload(capability="execute_anything"))


def test_contract_rejects_unknown_operation_kind():
    with pytest.raises(ValueError, match="unsupported Unreal operation kind"):
        parse_unreal_operation(payload(kind="execute"))


def test_contract_rejects_non_object_arguments():
    with pytest.raises(TypeError, match="arguments"):
        parse_unreal_operation(payload(arguments=[]))


def test_contract_rejects_argument_entity_mismatch():
    with pytest.raises(ValueError, match="match"):
        parse_unreal_operation(payload(entity_ids=["OTHER_TARGET"]))


def test_contract_rejects_missing_required_top_level_key():
    value = payload()
    del value["entity_ids"]
    with pytest.raises(ValueError, match="contract schema"):
        parse_unreal_operation(value)
