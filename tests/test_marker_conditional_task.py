import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.marker_task import MARKER_COLLECTION, MARKER_OBJECT, marker_create_action, marker_target_evaluator
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan


def make_orchestrator():
    evidence = EvidencePlan([
        EvidenceRequest(tool="inspect_scene", arguments={"file_name": "marker.blend"}),
    ])
    action = marker_create_action("marker.blend")
    actions = ConditionalActionPlan([action])
    evaluator = marker_target_evaluator()
    return ConditionalPlanningOrchestrator(
        evidence_plan=evidence,
        conditional_plan=actions,
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )


def scene(with_marker=False):
    objects = [{"name": "Goal_Left_post", "type": "MESH"}]
    if with_marker:
        objects.append({"name": MARKER_OBJECT, "type": "EMPTY"})
    return {"objects": objects}


def test_marker_already_correct_skips_action_but_still_requires_fresh_verification():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: scene(with_marker=True))
    result = orchestrator.evaluate_target_state(scene(with_marker=True))

    assert result.satisfied
    assert orchestrator.skipped
    assert orchestrator.next_phase() == "VERIFICATION"

    verified = orchestrator.verify_post_action(scene(with_marker=True))
    assert verified.satisfied
    assert orchestrator.next_phase() == "COMPLETE"

    with pytest.raises(RuntimeError, match="already satisfied"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "created"})


def test_marker_missing_requires_explicit_authorization_then_action_and_fresh_verification():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: scene(with_marker=False))
    result = orchestrator.evaluate_target_state(scene(with_marker=False))

    assert not result.satisfied
    assert orchestrator.next_phase() == "AUTHORIZATION"

    orchestrator.authorize_execution("marker-create-001")
    assert orchestrator.next_phase() == "ACTION"

    result = orchestrator.execute_next_action(lambda tool, args: {
        "status": "created",
        "object": MARKER_OBJECT,
        "collection": MARKER_COLLECTION,
    })
    assert result["status"] == "created"
    assert orchestrator.next_phase() == "VERIFICATION"
    assert not orchestrator.verification_complete

    verified = orchestrator.verify_post_action(scene(with_marker=True))
    assert verified.satisfied
    assert orchestrator.next_phase() == "COMPLETE"


def test_marker_failed_verification_blocks_completion():
    orchestrator = make_orchestrator()
    orchestrator.acquire_next_evidence(lambda tool, args: scene(with_marker=False))
    orchestrator.evaluate_target_state(scene(with_marker=False))
    orchestrator.authorize_execution("marker-create-002")
    orchestrator.execute_next_action(lambda tool, args: {"status": "created"})

    result = orchestrator.verify_post_action(scene(with_marker=False))
    assert not result.satisfied
    assert orchestrator.blocked
    assert orchestrator.next_phase() == "BLOCKED"


def test_marker_action_shape_is_distinct_from_goalpost_move():
    action = marker_create_action("marker.blend")
    assert isinstance(action, ActionSpec)
    assert action.tool == "create_empty_marker"
    assert action.arguments == {
        "file_name": "marker.blend",
        "collection_name": MARKER_COLLECTION,
        "object_name": MARKER_OBJECT,
    }
    assert "location" not in action.arguments
