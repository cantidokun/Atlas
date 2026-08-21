from planning.blender_task_planner import MoveObjectGoal, plan_move_object


def test_plan_move_object_compiles_authorized_relative_move():
    goal = MoveObjectGoal(
        object_name="Goal_Left_post",
        delta=(0.25, 0.0, 0.0),
        authorization_id="test-move-left",
    )

    plan = plan_move_object(
        goal,
        observed_locations={"Goal_Left_post": (0.0, 5.302, 0.0)},
    )

    assert plan.authorized
    assert plan.authorization_id == "test-move-left"
    assert [action.tool for action in plan.actions] == [
        "inspect_object_transform",
        "move_object",
        "inspect_object_transform",
    ]
    assert plan.actions[1].arguments["location"] == [0.25, 5.302, 0.0]


def test_plan_move_object_requires_observed_state():
    goal = MoveObjectGoal("Goal_Left_post", (0.25, 0.0, 0.0), "test-move-left")

    try:
        plan_move_object(goal, observed_locations={})
    except ValueError as exc:
        assert "no observed location" in str(exc)
    else:
        raise AssertionError("planner must reject missing scene evidence")


def test_plan_move_object_rejects_malformed_vector():
    goal = MoveObjectGoal("Goal_Left_post", (0.25, 0.0, 0.0), "test-move-left")

    try:
        plan_move_object(goal, observed_locations={"Goal_Left_post": (0.0, 5.302)})
    except ValueError as exc:
        assert "exactly three" in str(exc)
    else:
        raise AssertionError("planner must reject malformed observed state")


def test_plan_move_object_does_not_execute_blender():
    goal = MoveObjectGoal("Goal_Left_post", (0.25, 0.0, 0.0), "test-move-left")
    plan = plan_move_object(goal, observed_locations={"Goal_Left_post": (0.0, 0.0, 0.0)})

    assert plan.current_index == 0
    assert plan.completed == []
    assert plan.failed is None
