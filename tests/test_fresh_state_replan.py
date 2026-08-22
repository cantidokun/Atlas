from action_plan import ActionSpec
from planning.fresh_state_replan import FreshStateReplan


def _planner(evidence):
    if evidence["moved"]:
        return [ActionSpec("create_marker", {"name": "Atlas_Marker"}, "create marker")]
    return [ActionSpec("move", {"name": "Atlas_Target"}, "move target")]


def test_replan_binds_replacement_actions_to_fresh_evidence():
    state = {"moved": True}
    plan = FreshStateReplan.create(lambda: dict(state), _planner, "recovery-1")
    assert plan.actions[0].tool == "create_marker"
    plan.validate_before_execution(dict(state), list(plan.actions))


def test_replan_rejects_changed_world_state():
    state = {"moved": True}
    plan = FreshStateReplan.create(lambda: dict(state), _planner, "recovery-2")
    state["moved"] = False
    try:
        plan.validate_before_execution(dict(state), list(plan.actions))
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale replacement plan was accepted")


def test_replan_rejects_changed_replacement_actions():
    state = {"moved": True}
    plan = FreshStateReplan.create(lambda: dict(state), _planner, "recovery-3")
    changed = [ActionSpec("delete", {"name": "Atlas_Target"}, "delete target")]
    try:
        plan.validate_before_execution(dict(state), changed)
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("changed replacement plan was accepted")
