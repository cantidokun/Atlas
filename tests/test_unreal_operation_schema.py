import pytest

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
)
from planning.unreal_capability_registry import UnrealCapabilityRegistry


def operation(arguments, kind=UnrealOperationKind.WRITE, entity_ids=("FIELD_SURFACE",)):
    return UnrealOperation(
        capability=UnrealCapability.MATERIAL,
        kind=kind,
        name={
            UnrealOperationKind.READ: "inspect_material_state",
            UnrealOperationKind.WRITE: "apply_material_variant",
            UnrealOperationKind.VERIFY: "verify_material_variant",
        }[kind],
        arguments=arguments,
        entity_ids=entity_ids,
    )


def test_material_read_schema_accepts_entity_ids_only():
    registry = UnrealCapabilityRegistry()
    proposed = operation({"entity_ids": ("FIELD_SURFACE",)}, UnrealOperationKind.READ)
    assert registry.validate_operation(proposed) == proposed


def test_material_write_schema_accepts_explicit_variant():
    registry = UnrealCapabilityRegistry()
    proposed = operation(
        {"entity_ids": ("FIELD_SURFACE",), "material_variant": {"name": "liquid_surface"}}
    )
    assert registry.validate_operation(proposed) == proposed


def test_material_verify_schema_accepts_explicit_variant():
    registry = UnrealCapabilityRegistry()
    proposed = operation(
        {"entity_ids": ("FIELD_SURFACE",), "material_variant": {"name": "liquid_surface"}},
        UnrealOperationKind.VERIFY,
    )
    assert registry.validate_operation(proposed) == proposed


def test_operation_schema_rejects_unknown_argument_keys():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="schema"):
        registry.validate_operation(operation({"entity_ids": ("FIELD_SURFACE",), "material": "liquid"}))


def test_operation_schema_rejects_missing_entity_ids():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="schema"):
        registry.validate_operation(operation({}))


def test_operation_schema_rejects_missing_material_variant_for_write():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="schema"):
        registry.validate_operation(operation({"entity_ids": ("FIELD_SURFACE",)}))


def test_operation_schema_rejects_payload_target_mismatch():
    registry = UnrealCapabilityRegistry()
    proposed = operation({"entity_ids": ("OTHER_TARGET",), "material_variant": {"name": "liquid_surface"}})
    with pytest.raises(ValueError, match="match"):
        registry.validate_operation(proposed)


def test_operation_schema_rejects_non_string_targets():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="non-empty strings"):
        registry.validate_operation(operation({"entity_ids": (123,), "material_variant": {"name": "liquid_surface"}}))
