import pytest

from planning.unreal_agent import UnrealOperationKind, UnrealTaskIntent
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner


def test_compose_plans_preserves_subplan_order_for_one_intent():
    planner = UnrealTaskPlanner()
    intent = UnrealTaskIntent(
        "compound-1",
        "inspect then move field surface",
        ("FIELD_SURFACE",),
    )

    inspection = planner.plan_inspection(intent)
    movement = planner.plan_actor_location_write(
        intent,
        {"x": 100.0, "y": 200.0, "z": 300.0},
    )

    composed = planner.compose_plans(intent, (inspection, movement))

    assert composed.intent_id == intent.intent_id
    assert composed.operations == inspection.operations + movement.operations
    assert [operation.kind for operation in composed.operations] == [
        UnrealOperationKind.READ,
        UnrealOperationKind.VERIFY,
        UnrealOperationKind.READ,
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]


def test_compose_plans_rejects_mixed_intents():
    planner = UnrealTaskPlanner()
    intent = UnrealTaskIntent("compound-2", "compose field work", ("FIELD_SURFACE",))
    other_intent = UnrealTaskIntent("other-2", "other work", ("FIELD_SURFACE",))

    with pytest.raises(ValueError, match="same intent_id"):
        planner.compose_plans(
            intent,
            (
                planner.plan_inspection(intent),
                planner.plan_actor_location_write(
                    other_intent,
                    {"x": 1.0, "y": 2.0, "z": 3.0},
                ),
            ),
        )


def test_compose_plans_rejects_empty_or_invalid_inputs():
    planner = UnrealTaskPlanner()
    intent = UnrealTaskIntent("compound-3", "compose field work", ("FIELD_SURFACE",))

    with pytest.raises(ValueError, match="at least one UnrealTaskPlan"):
        planner.compose_plans(intent, ())

    with pytest.raises(TypeError, match="UnrealTaskPlan"):
        planner.compose_plans(intent, (object(),))
