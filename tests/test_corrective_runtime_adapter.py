from action_plan import ActionSpec
from planning.corrective_runtime_adapter import CorrectiveRuntimeAdapter


def test_runtime_adapter_reaches_convergence():
    state = {"value": 0}

    def observe():
        return dict(state)

    def plan(evidence):
        if evidence["value"] >= 2:
            return []
        return [ActionSpec(tool="set_value", arguments={"value": evidence["value"] + 1})]

    def execute(tool, arguments):
        state["value"] = arguments["value"]
        return {"status": "ok", "state": "ok"}

    adapter = CorrectiveRuntimeAdapter(
        execute, observe, plan, "test:runtime-adapter"
    )
    result = adapter.run(max_steps=4)

    assert result.converged
    assert state["value"] == 2
    assert len(result.receipts) == 2
