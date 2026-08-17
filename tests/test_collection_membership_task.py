import pytest

from action_plan import ActionSpec
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.collection_membership_task import (
    TARGET_COLLECTION,
    TARGET_OBJECT,
    collection_membership_action,
    collection_membership_target_evaluator,
)
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan


def make_orchestrator():
    evidence = EvidencePlan([
        EvidenceRequest(
            tool="inspect_object_collections",
            arguments={"file_name": "collection-membership.blend", "object_name": TARGET_OBJECT},
        ),
    ])
    action = collection_membership_action("collection-membership.blend")
    return ConditionalPlanningOrchestrator(
        evidence_plan=evidence,
        conditional_plan=ConditionalActionPlan([action]),
        target_evaluator=collection_membership_target_evaluator(),
        verification_plan=VerificationPlan(collection_membership_target_evaluator()),
    )


def evidence(collections):
    return {"object_name": TARGET_OBJECT, "collections": list(collections)}


def test_already_member_skips_write_and_requires_fresh_verification():
    orchestrator = make_orchestrator()
    initial = evidence([TARGET_COLLECTION])
    orchestrator.acquire_next_evidence(lambda tool, args: initial)
    result = orchestrator.evaluate_target_state(initial)

    assert result.satisfied
    assert orchestrator.skipped
    assert orchestrator.next_phase() == "VERIFICATION"

    verified = orchestrator.verify_post_action(evidence([TARGET_COLLECTION]))
    assert verified.satisfied
    assert orchestrator.next_phase() == "COMPLETE"

    with pytest.raises(RuntimeError, match="already satisfied"):
        orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})


def test_wrong_membership_requires_authorization_then_write_and_verification():
    orchestrator = make_orchestrator()
    initial = evidence(["Scene Collection"])
    orchestrator.acquire_next_evidence(lambda tool, args: initial)
    result = orchestrator.evaluate_target_state(initial)

    assert not result.satisfied
    assert orchestrator.next_phase() == "AUTHORIZATION"

    orchestrator.authorize_execution("collection-membership-001")
    result = orchestrator.execute_next_action(
        lambda tool, args: {"status": "moved", "collection": TARGET_COLLECTION}
    )
    assert result["status"] == "moved"
    assert orchestrator.next_phase() == "VERIFICATION"

    verified = orchestrator.verify_post_action(evidence([TARGET_COLLECTION]))
    assert verified.satisfied
    assert orchestrator.next_phase() == "COMPLETE"


def test_failed_membership_verification_blocks_completion():
    orchestrator = make_orchestrator()
    initial = evidence(["Scene Collection"])
    orchestrator.acquire_next_evidence(lambda tool, args: initial)
    orchestrator.evaluate_target_state(initial)
    orchestrator.authorize_execution("collection-membership-002")
    orchestrator.execute_next_action(lambda tool, args: {"status": "moved"})

    result = orchestrator.verify_post_action(evidence(["Scene Collection"]))
    assert not result.satisfied
    assert orchestrator.blocked
    assert orchestrator.next_phase() == "BLOCKED"


def test_collection_membership_action_shape_is_distinct_from_creation_and_parenting():
    action = collection_membership_action("collection-membership.blend")
    assert isinstance(action, ActionSpec)
    assert action.tool == "move_object_to_collection"
    assert action.arguments == {
        "file_name": "collection-membership.blend",
        "object_name": TARGET_OBJECT,
        "collection_name": TARGET_COLLECTION,
    }
    assert "location" not in action.arguments
    assert "parent_name" not in action.arguments
