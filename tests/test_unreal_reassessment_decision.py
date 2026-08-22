import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_reassessment_decision import (
    UnrealReassessmentOutcome,
    decide_reassessment,
)
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryAssessment,
    UnrealRecoveryDisposition,
)


TARGETS = ("FIELD_SURFACE",)
EXPECTED = {"x": 100.0, "y": 200.0, "z": 0.0}


def _assessment():
    return UnrealRecoveryAssessment(
        failure_class=UnrealFailureClass.MUTATION_FAILURE,
        disposition=UnrealRecoveryDisposition.REASSESS_STATE,
        state_uncertain=True,
        reason="write outcome uncertain",
        target_entity_ids=TARGETS,
        requires_fresh_evidence=True,
    )


def _evidence(location):
    return UnrealEvidence(
        operation_name="inspect_target_actors",
        entity_ids=TARGETS,
        observed_state={"FIELD_SURFACE": {"location": location}},
        source="unreal-editor",
    )


def test_matching_fresh_state_confirms_and_resolves_uncertainty():
    decision = decide_reassessment(_assessment(), _evidence(EXPECTED), EXPECTED)

    assert decision.outcome is UnrealReassessmentOutcome.CONFIRMED
    assert decision.state_uncertain is False


def test_changed_fresh_state_never_authorizes_retry():
    decision = decide_reassessment(
        _assessment(), _evidence({"x": 101.0, "y": 200.0, "z": 0.0}), EXPECTED
    )

    assert decision.outcome is UnrealReassessmentOutcome.STATE_CHANGED
    assert decision.state_uncertain is False
    assert decision.retry_authorized is False
    assert decision.mutation_authorized is False
    assert "requested location" in decision.reason


def test_malformed_fresh_state_remains_uncertain():
    decision = decide_reassessment(
        _assessment(),
        _evidence({"x": 100.0, "y": "unknown", "z": 0.0}),
        EXPECTED,
    )

    assert decision.outcome is UnrealReassessmentOutcome.INSUFFICIENT_EVIDENCE
    assert decision.state_uncertain is True
    assert decision.retry_authorized is False
    assert decision.mutation_authorized is False


def test_reassessment_rejects_wrong_targets():
    evidence = UnrealEvidence(
        operation_name="inspect_target_actors",
        entity_ids=("OTHER_ACTOR",),
        observed_state={"OTHER_ACTOR": {"location": EXPECTED}},
        source="unreal-editor",
    )

    with pytest.raises(ValueError, match="targets"):
        decide_reassessment(_assessment(), evidence, EXPECTED)


def test_reassessment_rejects_halt_assessment():
    assessment = UnrealRecoveryAssessment(
        failure_class=UnrealFailureClass.UNKNOWN_FAILURE,
        disposition=UnrealRecoveryDisposition.HALT,
        state_uncertain=True,
        reason="halt",
        target_entity_ids=TARGETS,
        requires_fresh_evidence=True,
    )

    with pytest.raises(ValueError, match="REASSESS_STATE"):
        decide_reassessment(assessment, _evidence(EXPECTED), EXPECTED)


def test_confirmed_reassessment_never_authorizes_mutation():
    decision = decide_reassessment(_assessment(), _evidence(EXPECTED), EXPECTED)

    assert decision.outcome is UnrealReassessmentOutcome.CONFIRMED
    assert decision.retry_authorized is False
    assert decision.mutation_authorized is False
