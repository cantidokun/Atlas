from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_coordinator import BlenderExecutionCoordinator


def _plan():
    plan = ActionPlan([ActionSpec("inspect_scene", {"nested": {"objects": ["Cube"]}})])
    plan.authorize(ActionAuthorization.issue(plan.actions, "coord-isolation"))
    return plan


def test_executor_cannot_mutate_plan_arguments_through_shared_input():
    plan = _plan()
    observed = {}

    def execute(tool, arguments):
        arguments["nested"]["objects"].append("Camera")
        observed["arguments"] = arguments
        return {"ok": True}

    step = BlenderExecutionCoordinator(plan, execute).step()

    assert observed["arguments"]["nested"]["objects"] == ["Cube", "Camera"]
    assert step.arguments["nested"]["objects"] == ["Cube"]
    assert plan.completed[0]["arguments"]["nested"]["objects"] == ["Cube"]


def test_verifier_cannot_mutate_recorded_result_or_arguments():
    plan = _plan()

    def execute(tool, arguments):
        return {"ok": True, "details": {"objects": ["Cube"]}}

    def verify(tool, arguments, result):
        arguments["nested"]["objects"].append("Camera")
        result["details"]["objects"].append("Camera")
        return True

    step = BlenderExecutionCoordinator(plan, execute, verify).step()

    assert step.arguments["nested"]["objects"] == ["Cube"]
    assert step.result["details"]["objects"] == ["Cube"]
    assert plan.completed[0]["result"]["details"]["objects"] == ["Cube"]
