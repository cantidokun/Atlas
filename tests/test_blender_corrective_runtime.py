from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute_authorized_replan(self, authorized_step, fresh_evidence):
        action = authorized_step.actions[0]
        self.calls.append((action.tool, action.arguments, fresh_evidence))
        return {"ok": True, "state": "ok"}, {"tool": action.tool}


def test_blender_corrective_runtime_converges_through_authorized_executor():
    state = {"value": 0}
    executor = FakeExecutor()

    def observe():
        return {"value": state["value"]}

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        next_value = evidence["value"] + 1
        state["value"] = next_value
        return [ActionSpec(tool="set_value", arguments={"value": next_value})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:blender-runtime", executor=executor)
    result = runtime.run(max_steps=4)

    assert result.converged is True
    assert len(result.receipts) == 2
    assert [call[0] for call in executor.calls] == ["set_value", "set_value"]
