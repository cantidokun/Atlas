from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        return {"ok": True, "state": "ok", "details": dict(arguments)}


def test_corrective_runtime_preserves_action_sequence():
    state = {"value": 0}
    executor = RecordingExecutor()

    def observe():
        return {"value": state["value"]}

    def plan(evidence):
        if evidence["value"] >= 3:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:receipt-sequence", executor=executor)
    result = runtime.run(max_steps=4)

    assert result.converged
    assert len(result.receipts) == 3
    assert [args["value"] for _, args in executor.calls] == [1, 2, 3]
