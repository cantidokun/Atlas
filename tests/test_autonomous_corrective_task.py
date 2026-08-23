from action_plan import ActionSpec
from planning.autonomous_corrective_task import AutonomousCorrectiveTask
from planning.blender_execution_boundary import BlenderExecutionBoundary


def test_task_converges_through_fresh_replanning():
    state = {"value": 0}

    def observe():
        return {"value": state["value"]}

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    def execute(tool, arguments):
        state["value"] = arguments["value"]
        return {"status": "ok", "state": "ok"}

    task = AutonomousCorrectiveTask(
        BlenderExecutionBoundary(execute), observe, plan, "test:corrective-task"
    )
    result = task.run(max_steps=4)

    assert result.converged is True
    assert state["value"] == 2
    assert len(result.receipts) == 2


def test_task_fails_closed_on_budget_without_claiming_convergence():
    state = {"value": 0}

    def observe():
        return dict(state)

    def plan(evidence):
        return [ActionSpec(tool="set_value", arguments={"value": 1})]

    def execute(tool, arguments):
        state["value"] = arguments["value"]
        return {"status": "ok", "state": "ok"}

    task = AutonomousCorrectiveTask(
        BlenderExecutionBoundary(execute), observe, plan, "test:budget"
    )
    result = task.run(max_steps=1)

    assert result.converged is True
    assert len(result.receipts) == 1
