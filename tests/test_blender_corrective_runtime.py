from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, arguments))
        return {"ok": True, "state": "ok", "details": {}}


def test_blender_corrective_runtime_converges_through_executor():
    state = {"value": 0}
    executor = FakeExecutor()

    def observe():
        return {"value": state["value"]}

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:blender-runtime", executor=executor)
    result = runtime.run(max_steps=4)

    assert result.converged is True
    assert len(result.receipts) == 2
    assert [call[0] for call in executor.calls] == ["set_value", "set_value"]
