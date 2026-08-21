import pytest

from planning.action_plan import ActionSpec
from planning.blender_task_planner import BlenderTaskIntent, BlenderTaskPlanner, BlenderPlanningError


def test_planner_compiles_valid_intent_into_schema_valid_plan():
    intent = BlenderTaskIntent(
        task_id="task-001",
        objective="Inspect the target object transform.",
        actions=(
            ActionSpec(
                tool="inspect_object_transform",
                arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post"},
                name="Inspect goal post transform",
            ),
        ),
    )
    plan = BlenderTaskPlanner().plan(intent)
    assert plan.next_action is not None
    assert plan.next_action.tool == "inspect_object_transform"
    assert plan.next_action.arguments == {"file_name": "scene.blend", "object_name": "Goal_Left_post"}
    assert plan.authorized is False


def test_planner_rejects_unknown_blender_capability():
    intent = BlenderTaskIntent("task-002", "Do something unsupported.", (ActionSpec("delete_everything", {}),))
    with pytest.raises(BlenderPlanningError, match="capability is not registered"):
        BlenderTaskPlanner().plan(intent)


def test_planner_rejects_schema_invalid_action_before_execution():
    intent = BlenderTaskIntent(
        "task-003",
        "Inspect a target object.",
        (ActionSpec("inspect_object_transform", {"file_name": "scene.blend"}),),
    )
    with pytest.raises(BlenderPlanningError, match="invalid arguments"):
        BlenderTaskPlanner().plan(intent)


def test_planner_preserves_multi_step_order():
    intent = BlenderTaskIntent(
        "task-004",
        "Inspect scene and then inspect its health.",
        (
            ActionSpec("inspect_scene", {"file_name": "scene.blend"}),
            ActionSpec("inspect_scene_health", {"file_name": "scene.blend"}),
        ),
    )
    plan = BlenderTaskPlanner().plan(intent)
    assert [action.tool for action in plan.actions] == ["inspect_scene", "inspect_scene_health"]


def test_planner_requires_real_task_identity_and_objective():
    with pytest.raises(BlenderPlanningError, match="task_id must be non-empty"):
        BlenderTaskPlanner().plan(BlenderTaskIntent("", "Inspect scene", (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),)))
    with pytest.raises(BlenderPlanningError, match="objective must be non-empty"):
        BlenderTaskPlanner().plan(BlenderTaskIntent("task-005", "", (ActionSpec("inspect_scene", {"file_name": "scene.blend"}),)))
