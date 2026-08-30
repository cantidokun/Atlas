from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionSpec
from planning.blender_execution_coordinator import BlenderExecutionCoordinator
from planning.blender_task_planner import BlenderTaskIntent, BlenderTaskPlanner


def test_blender_task_can_flow_from_intent_to_authorized_verified_execution():
    intent = BlenderTaskIntent(
        task_id="soccer-cleanup-001",
        objective="Inspect the reconstructed field scene before making changes.",
        actions=(
            ActionSpec("inspect_scene", {"file_name": "reconstructed_field.blend"}),
            ActionSpec("inspect_scene_health", {"file_name": "reconstructed_field.blend"}),
        ),
    )

    plan = BlenderTaskPlanner().plan(intent)
    authorization = ActionAuthorization.issue(plan.actions, "operator-approval-001")
    plan.authorize(authorization)

    calls = []

    def execute(tool, arguments):
        calls.append((tool, arguments))
        if tool == "inspect_scene":
            return {"status": "ok", "object_count": 1200}
        return {"status": "ok", "health": "valid"}

    coordinator = BlenderExecutionCoordinator(
        plan,
        execute,
        verify=lambda tool, arguments, result: result.get("status") == "ok",
    )
    steps = coordinator.run()

    assert len(steps) == 2
    assert plan.complete is True
    assert all(step.verified for step in steps)
    assert calls == [
        ("inspect_scene", {"file_name": "reconstructed_field.blend"}),
        ("inspect_scene_health", {"file_name": "reconstructed_field.blend"}),
    ]
    assert plan.authorization_id == "operator-approval-001"
