import copy

import pytest

from planning.action_authorization import ActionAuthorization
from qwen.production_handoff import QwenProductionHandoffError, QwenProductionTaskHandoff
from qwen.production_proposal import QwenProductionProposal


VALID_PROPOSAL = {
    "workflow": "broadcast-goal-preparation",
    "version": 1,
    "parameters": {
        "file_name": "scene.blend",
        "object_name": "Goal_Left_post",
        "target_location": [0.25, 5.302, 0.0],
        "target_rotation": [0.0, 0.0, 15.0],
    },
}


def test_qwen_handoff_is_inert_until_explicit_authorization():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    snapshot = handoff.snapshot()
    assert snapshot["proposal"]["workflow"] == "broadcast-goal-preparation"
    assert snapshot["semantic_task"]["metadata"]["workflow_catalog"]["version"] == 1
    assert snapshot["compiled_task"]["metadata"]["workflow_catalog"]["name"] == "broadcast-goal-preparation"
    assert snapshot["authorization"] == "not_requested"
    assert snapshot["execution"] == "not_attempted"


def test_qwen_handoff_reuses_existing_authorization_path():
    handoff = QwenProductionTaskHandoff.from_proposal(QwenProductionProposal(**VALID_PROPOSAL))
    action_plan, authorization = handoff.authorize("atlas-qwen-handoff-test")
    assert isinstance(authorization, ActionAuthorization)
    assert action_plan.authorized is True
    assert action_plan.authorization_id == "atlas-qwen-handoff-test"
    assert action_plan.actions == list(handoff.compiled_task.actions)


def test_authorization_is_not_model_supplied():
    proposal = dict(VALID_PROPOSAL)
    proposal["authorization_id"] = "model-supplied"
    with pytest.raises(ValueError, match="unexpected fields"):
        QwenProductionTaskHandoff.from_proposal(proposal)


def test_executor_is_not_exposed_by_handoff():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    assert not hasattr(handoff, "execute")
    assert not hasattr(handoff, "run")


def test_handoff_fails_closed_when_semantic_task_metadata_changes():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    handoff.semantic_task.metadata["workflow_catalog"]["name"] = "tampered"
    with pytest.raises(QwenProductionHandoffError, match="semantic task integrity"):
        handoff.verify_integrity()


def test_handoff_fails_closed_when_catalog_provenance_is_recompiled_differently():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    handoff.semantic_task.metadata["workflow_parameters"]["object_name"] = "OtherObject"
    with pytest.raises(QwenProductionHandoffError):
        handoff.task_plan_proposal()


def test_authorization_rechecks_integrity_before_crossing_boundary():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    handoff.compiled_task.metadata["workflow_catalog"]["version"] = 999
    with pytest.raises(QwenProductionHandoffError, match="compiled task integrity"):
        handoff.authorize("must-not-authorize")


def test_qwen_handoff_round_trips_through_persisted_snapshot():
    original = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    persisted = original.snapshot()
    restored = QwenProductionTaskHandoff.from_snapshot(copy.deepcopy(persisted))
    assert restored.snapshot() == persisted
    restored.verify_integrity()


def test_qwen_handoff_rejects_tampered_persisted_semantic_snapshot():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    persisted = handoff.snapshot()
    persisted["semantic_task"]["metadata"]["workflow_parameters"]["object_name"] = "OtherObject"
    with pytest.raises(QwenProductionHandoffError, match="semantic task"):
        QwenProductionTaskHandoff.from_snapshot(persisted)


def test_qwen_handoff_rejects_tampered_persisted_compiled_digest():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    persisted = handoff.snapshot()
    persisted["compiled_task_digest"] = "tampered"
    with pytest.raises(QwenProductionHandoffError, match="compiled_task digest integrity"):
        QwenProductionTaskHandoff.from_snapshot(persisted)


def test_qwen_handoff_rejects_persisted_runtime_state_that_requests_execution():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    persisted = handoff.snapshot()
    persisted["authorization"] = "atlas-issued"
    with pytest.raises(QwenProductionHandoffError, match="unexpected runtime state"):
        QwenProductionTaskHandoff.from_snapshot(persisted)


def test_recovery_recommendation_must_match_canonical_task():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    candidate = handoff.validate_recovery_recommendation(VALID_PROPOSAL)
    assert candidate.snapshot() == handoff.proposal.snapshot()


def test_recovery_recommendation_cannot_change_target():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    candidate = copy.deepcopy(VALID_PROPOSAL)
    candidate["parameters"]["target_rotation"] = [0.0, 0.0, 30.0]
    with pytest.raises(QwenProductionHandoffError, match="changed the canonical production task"):
        handoff.validate_recovery_recommendation(candidate)


def test_recovery_recommendation_cannot_change_executable_scope():
    handoff = QwenProductionTaskHandoff.from_proposal(VALID_PROPOSAL)
    candidate = copy.deepcopy(VALID_PROPOSAL)
    candidate["parameters"]["object_name"] = "Goal_Right_post"
    with pytest.raises(QwenProductionHandoffError, match="changed the canonical production task"):
        handoff.validate_recovery_recommendation(candidate)
