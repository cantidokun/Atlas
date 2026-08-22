import pytest

from planning.unreal_reassessment_planner import UnrealReassessmentPlanner
from planning.unreal_recovery_policy import (
    UnrealFailureClass,
    UnrealRecoveryAssessment,
    UnrealRecoveryDisposition,
)


def _assessment(
    disposition=UnrealRecoveryDisposition.REASSESS_STATE,
    requires_fresh_evidence=True,
    targets=("FIELD_SURFACE",),
):
    return UnrealRecoveryAssessment(
        failure_class=UnrealFailureClass.MUTATION_FAILURE,
        disposition=disposition,
        state_uncertain=True,
        reason="test",
        target_entity_ids=targets,
        requires_fresh_evidence=requires_fresh_evidence,
    )


def test_reassessment_plan_is_read_only_and_targeted():
    plan = UnrealReassessmentPlanner().plan(_assessment())

    assert plan.operations[0].name == "inspect_target_actors"
    assert plan.operations[0].kind.value == "read"
    assert plan.operations[0].capability.value == "inspect_actor"
    assert plan.operations[0].entity_ids == ("FIELD_SURFACE",)
    assert len(plan.operations) == 1


def test_reassessment_plan_requires_reassessment_disposition():
    with pytest.raises(ValueError, match="only permitted"):
        UnrealReassessmentPlanner().plan(
            _assessment(disposition=UnrealRecoveryDisposition.HALT)
        )


def test_reassessment_plan_requires_fresh_evidence_flag():
    with pytest.raises(ValueError, match="fresh-evidence"):
        UnrealReassessmentPlanner().plan(_assessment(requires_fresh_evidence=False))


def test_reassessment_plan_requires_explicit_targets():
    with pytest.raises(ValueError, match="explicit target"):
        UnrealReassessmentPlanner().plan(_assessment(targets=()))
