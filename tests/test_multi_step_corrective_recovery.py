from action_plan import ActionSpec
from planning.multi_step_corrective_recovery import MultiStepCorrectiveRecovery


def _action(name):
    return ActionSpec(
        tool="create_empty_marker",
        arguments={"file_name": "multi.blend", "collection_name": "Atlas_Test", "object_name": name},
        name=name,
        requires_success=True,
    )


def test_each_step_is_bound_to_fresh_evidence():
    state = {"revision": 1, "step": 0}
    planner_calls = []

    def observe():
        return dict(state)

    def plan(evidence):
        planner_calls.append(evidence)
        if evidence["step"] == 0:
            return [_action("step-one")]
        return [_action("step-two")]

    recovery = MultiStepCorrectiveRecovery(observe, plan, "multi-step-test")
    first = recovery.next_step()
    assert first is not None
    recovery.validate_step(first, dict(state))

    state.update(revision=2, step=1)
    try:
        recovery.validate_step(first, dict(state))
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("step-one authorization survived a world change")

    second = recovery.next_step()
    assert second is not None
    assert second.action.name == "step-two"
    recovery.validate_step(second, dict(state))
    assert [entry["revision"] for entry in planner_calls] == [1, 2]
