from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def __call__(self, tool, arguments):
        self.calls.append((tool, arguments))
        return {"ok": True, "state": "ok", "details": {"tool": tool}}


def test_runtime_replans_from_fresh_state_after_each_receipt():
    state = {"value": 0}
    observations = []
    executor = RecordingExecutor()

    def observe():
        snapshot = dict(state)
        observations.append(snapshot)
        return snapshot

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:fresh-state", executor=executor)
    result = runtime.run(max_steps=4)

    assert result.converged
    assert len(result.receipts) == 2
    assert [call[1]["value"] for call in executor.calls] == [1, 2]
    assert observations[-1]["value"] == 2
