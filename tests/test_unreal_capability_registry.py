import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry


def test_registry_contains_core_unreal_domains():
    registry = UnrealCapabilityRegistry()
    capabilities = {spec.capability for spec in registry.all()}
    assert UnrealCapability.NIAGARA in capabilities
    assert UnrealCapability.SEQUENCER in capabilities
    assert UnrealCapability.RENDER in capabilities


def test_actor_modification_is_write_only():
    registry = UnrealCapabilityRegistry()
    registry.validate(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE)
    with pytest.raises(ValueError):
        registry.validate(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.READ)


def test_actor_modification_requires_location_payload():
    registry = UnrealCapabilityRegistry()

    operation = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "location": {"x": 100.0, "y": 200.0, "z": 300.0},
        },
        entity_ids=("FIELD_SURFACE",),
    )
    assert registry.validate_operation(operation) is operation

    invalid = UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_location",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
    )
    with pytest.raises(ValueError, match="capability schema"):
        registry.validate_operation(invalid)


def test_actor_inspection_does_not_allow_writes():
    registry = UnrealCapabilityRegistry()
    registry.validate(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.READ)
    registry.validate(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.VERIFY)
    with pytest.raises(ValueError):
        registry.validate(UnrealCapability.INSPECT_ACTOR, UnrealOperationKind.WRITE)


def test_unknown_capability_fails_closed():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(KeyError, match="unknown Unreal capability"):
        registry.get("not-a-capability")
