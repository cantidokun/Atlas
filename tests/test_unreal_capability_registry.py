import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind
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
