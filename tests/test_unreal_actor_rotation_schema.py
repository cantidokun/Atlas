import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry


def _operation(arguments):
    return UnrealOperation(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.WRITE,
        name="set_actor_rotation",
        arguments=arguments,
        entity_ids=("FIELD_SURFACE",),
    )


def test_actor_rotation_schema_accepts_exact_payload():
    registry = UnrealCapabilityRegistry()
    proposed = _operation({
        "entity_ids": ("FIELD_SURFACE",),
        "rotation": {"pitch": 10.0, "yaw": 20.0, "roll": -5.0},
    })
    assert registry.validate_operation(proposed) == proposed


def test_actor_rotation_schema_rejects_location_rotation_mixing():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(ValueError, match="schema"):
        registry.validate_operation(_operation({
            "entity_ids": ("FIELD_SURFACE",),
            "location": {"x": 1.0, "y": 2.0, "z": 3.0},
            "rotation": {"pitch": 10.0, "yaw": 20.0, "roll": -5.0},
        }))


def test_actor_rotation_schema_rejects_non_numeric_angles():
    registry = UnrealCapabilityRegistry()
    with pytest.raises(TypeError, match="rotation angles must be numeric"):
        registry.validate_operation(_operation({
            "entity_ids": ("FIELD_SURFACE",),
            "rotation": {"pitch": "10", "yaw": 20.0, "roll": -5.0},
        }))
