import pytest

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
)
from planning.unreal_capability_registry import UnrealCapabilityRegistry


def operation(arguments, entity_ids=("FIELD_SURFACE",)):
    return UnrealOperation(
        capability=UnrealCapability.MATERIAL,
        kind=UnrealOperationKind.WRITE,
        name="apply_material_variant",
        arguments=arguments,
        entity_ids=entity_ids,
    )


def test_operation_schema_accepts_matching_entity_ids():
    registry = UnrealCapabilityRegistry()
    proposed = operation({"entity_ids": ("FIELD_SURFACE",)})
    assert registry.validate_operation(proposed) == proposed


def test_operation_schema_rejects_unknown_argument_keys():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="schema"):
        registry.validate_operation(operation({"entity_ids": ("FIELD_SURFACE",), "material": "liquid"}))


def test_operation_schema_rejects_missing_entity_ids():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="entity_ids"):
        registry.validate_operation(operation({}))


def test_operation_schema_rejects_payload_target_mismatch():
    registry = UnrealCapabilityRegistry()
    proposed = operation({"entity_ids": ("OTHER_TARGET",)})
    with pytest.raises(ValueError, match="match"):
        registry.validate_operation(proposed)


def test_operation_schema_rejects_non_string_targets():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="non-empty strings"):
        registry.validate_operation(operation({"entity_ids": (123,)}))
