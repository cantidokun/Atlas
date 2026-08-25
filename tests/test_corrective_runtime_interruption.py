from action_plan import ActionSpec
from planning.blender_corrective_runtime import BlenderCorrectiveRuntime


class InterruptingExecutor:
    def __init__(self, world):
        self.calls = 0
        self.world = world

    def __call__(self, tool, arguments):
        self.calls += 1
        self.world["value"] = arguments["value"]
        return {"ok": True, "state": "ok", "details": {"value": self.world["value"]}}


def test_runtime_replans_after_world_changes_between_steps():
    world = {"value": 0}
    executor = InterruptingExecutor(world)

    def observe():
        return {"value": world["value"]}

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    runtime = BlenderCorrectiveRuntime(observe, plan, "test:interruption", executor=executor)
    first = runtime.run(max_steps=1)
    assert first.converged is False
    assert world["value"] == 1

    # Simulate an external world mutation after the first run.
    world["value"] = -10
    second = runtime.run(max_steps=12)

    assert second.converged
    assert len(second.receipts) == 11
    assert world["value"] == 1
