from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class InterruptingExecutor:
    def __init__(self):
        self.calls = 0
        self.state = 0

    def __call__(self, tool, arguments):
        self.calls += 1
        self.state = arguments["value"]
        return {"ok": True, "state": "ok", "details": {"value": self.state}}


def test_runtime_replans_after_world_changes_between_steps():
    executor = InterruptingExecutor()
    world = {"value": 0}

    def observe():
        return {"value": world["value"]}

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:interruption", executor=executor)
    first = runtime.run(max_steps=1)
    assert first.converged

    # Simulate an external world mutation after the first run.
    world["value"] = -10
    second = runtime.run(max_steps=12)

    assert second.converged
    assert len(second.receipts) == 11
    assert world["value"] == 1
