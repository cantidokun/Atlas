from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor


def _action(name):
    return ActionSpec(tool="create_empty_marker", arguments={"file_name":"multi.blend","collection_name":"Atlas_Test","object_name":name}, name=name, requires_success=True)


def test_multi_step_executor_reobserves_before_each_mutation():
    state = {"revision": 1, "step": 0}
    writes = []

    def observe():
        return dict(state)

    def plan(evidence):
        return [_action("one")] if evidence["step"] == 0 else []

    boundary = BlenderExecutionBoundary(lambda tool, args: writes.append((tool, args)) or {"status":"created"})
    executor = MultiStepCorrectiveExecutor(boundary, observe, plan, "multi-exec")
    receipts = executor.execute_all()
    assert len(receipts) == 1
    assert len(writes) == 1


def test_stale_step_never_reaches_blender():
    state = {"revision": 1, "step": 0}
    writes = []
    observations = []

    def observe():
        value = dict(state)
        observations.append(value)
        if len(observations) == 2:
            state["revision"] = 2
        return value

    def plan(evidence):
        return [_action("one")]

    boundary = BlenderExecutionBoundary(lambda tool, args: writes.append((tool, args)) or {"status":"created"})
    executor = MultiStepCorrectiveExecutor(boundary, observe, plan, "race-multi")
    try:
        executor.execute_all(max_steps=1)
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale multi-step authorization executed")
    assert writes == []
