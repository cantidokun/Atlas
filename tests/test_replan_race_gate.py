from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.replan_authorization import ReplanAuthorization


def _action(name="correct"):
    return ActionSpec(
        tool="create_empty_marker",
        arguments={"file_name": "race.blend", "collection_name": "Atlas_Test", "object_name": name},
        name=name,
        requires_success=True,
    )


def test_stale_authorization_is_rejected_before_mutation():
    writes = []
    boundary = BlenderExecutionBoundary(lambda tool, arguments: writes.append((tool, arguments)) or {"status": "created"})
    old_evidence = {"marker": "missing", "revision": 1}
    action = _action()
    authorization = ReplanAuthorization.issue(old_evidence, [action], "race-test")
    replan = type("Replan", (), {"actions": [action], "authorization": authorization})()

    try:
        boundary.execute_authorized_replan(replan, {"marker": "missing", "revision": 2})
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale authorization unexpectedly executed")
    assert writes == []


def test_new_authorization_executes_after_fresh_replan():
    writes = []
    boundary = BlenderExecutionBoundary(lambda tool, arguments: writes.append((tool, arguments)) or {"status": "created"})
    evidence = {"marker": "missing", "revision": 2}
    action = _action("correct-after-race")
    authorization = ReplanAuthorization.issue(evidence, [action], "race-test-2")
    replan = type("Replan", (), {"actions": [action], "authorization": authorization})()

    result, receipt = boundary.execute_authorized_replan(replan, evidence)
    assert result.ok
    assert writes == [("create_empty_marker", action.arguments)]
    assert receipt.tool == "create_empty_marker"
