from action_plan import ActionSpec
from planning.continuation_resume import ContinuationState


def _action(tool="move_object"):
    return ActionSpec(tool=tool, arguments={"file_name": "scene.blend", "object_name": "Goal_Left_post", "location": [1, 2, 3]})


def test_resume_requires_fresh_evidence():
    evidence = {"location": [0, 0, 0]}
    state = ContinuationState.create("task:resume", [_action()], evidence, "auth:resume")
    try:
        state.authorize_remaining(evidence, [_action()])
    except RuntimeError as exc:
        assert "fresh evidence" in str(exc)
    else:
        raise AssertionError("resume reused stale evidence")


def test_resume_issues_new_authorization_from_fresh_evidence():
    old = {"location": [0, 0, 0]}
    fresh = {"location": [0, 1, 0]}
    state = ContinuationState.create("task:resume", [_action()], old, "auth:resume")
    authorization = state.authorize_remaining(fresh, [_action()])
    assert authorization.authorization_id == "auth:resume"
    assert authorization.matches(fresh, [_action()])
    assert not authorization.matches(old, [_action()])
