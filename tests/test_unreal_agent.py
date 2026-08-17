import pytest

from planning.unreal_agent import (
    UnrealAgent,
    UnrealCapability,
    UnrealOperationKind,
    UnrealTaskIntent,
)


def test_unreal_agent_requires_explicit_atlas_targets():
    with pytest.raises(ValueError, match="target entities"):
        UnrealAgent().propose_operations(
            UnrealTaskIntent("intent-1", "inspect the goal", ())
        )


def test_unreal_agent_proposes_read_before_write():
    intent = UnrealTaskIntent("intent-1", "inspect the left goal", ("GOAL_LEFT",))
    operations = UnrealAgent().propose_operations(intent)
    assert len(operations) == 1
    operation = operations[0]
    assert operation.capability is UnrealCapability.INSPECT_ACTOR
    assert operation.kind is UnrealOperationKind.READ
    assert operation.entity_ids == ("GOAL_LEFT",)
    assert operation.arguments["entity_ids"] == ("GOAL_LEFT",)
