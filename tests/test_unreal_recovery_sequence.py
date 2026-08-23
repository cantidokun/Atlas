from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult
from planning.unreal_recovery_sequence import (
    UnrealRecoverySequenceAssessment,
    assess_reassessment_sequence,
    build_reassessment_plan,
    build_replacement_plan,
)
from planning.unreal_task_planner import UnrealTaskPlan


def _plan():
    entity_ids = ("FIELD_SURFACE",)
    return UnrealTaskPlan(
        "composite-live",
        (
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_location", {"entity_ids": entity_ids, "location": {"x": 10.0, "y": 20.0, "z": 30.0}}, entity_ids),
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_location", {"entity_ids": entity_ids, "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0}}, entity_ids),
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_rotation", {"entity_ids": entity_ids, "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}}, entity_ids),
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_rotation", {"entity_ids": entity_ids, "expected_rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}}, entity_ids),
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.WRITE, "set_actor_scale", {"entity_ids": entity_ids, "scale": {"x": 1.1, "y": 1.1, "z": 1.1}}, entity_ids),
            UnrealOperation(UnrealCapability.MODIFY_ACTOR, UnrealOperationKind.VERIFY, "verify_actor_scale", {"entity_ids": entity_ids, "expected_scale": {"x": 1.1, "y": 1.1, "z": 1.1}}, entity_ids),
        ),
    )


def _failure():
    return UnrealPlanExecutionFailure(
        intent_id="composite-live",
        operation_index=5,
        operation_name="verify_actor_scale",
        completed_evidence=(),
        error="verification failed",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "expected_scale": {"x": 1.1, "y": 1.1, "z": 1.1},
        },
    )


def _evidence(location, rotation, scale):
    return UnrealEvidence(
        "inspect_target_actors",
        ("FIELD_SURFACE",),
        {
            "FIELD_SURFACE": {
                "entity_id": "FIELD_SURFACE",
                "actor_name": "FieldSurface",
                "actor_class": "Actor",
                "location": location,
                "rotation": rotation,
                "scale": scale,
            }
        },
        "unreal-editor-atlas-transport",
    )


def test_reassessment_plan_covers_all_writes_through_failure_and_is_read_only():
    plan = _plan()
    reassessment = build_reassessment_plan(plan, _failure())

    assert reassessment.intent_id == "composite-live:reassess-sequence"
    assert [operation.name for operation in reassessment.operations] == [
        "inspect_target_actors",
        "inspect_target_actors",
        "inspect_target_actors",
    ]
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)
    assert all(operation.capability is UnrealCapability.MODIFY_ACTOR for operation in reassessment.operations)


def test_sequence_assessment_tracks_each_fresh_read_in_order():
    plan = _plan()
    failure = _failure()
    result = UnrealPlanExecutionResult(
        "composite-live:reassess-sequence",
        (
            _evidence({"x": 10.0, "y": 20.0, "z": 30.0}, {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}),
            _evidence({"x": 10.0, "y": 20.0, "z": 30.0}, {"pitch": 0.0, "yaw": 0.0, "roll": 5.0}, {"x": 1.0, "y": 1.0, "z": 1.0}),
            _evidence({"x": 10.0, "y": 20.0, "z": 30.0}, {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}, {"x": 1.1, "y": 1.1, "z": 1.1}),
        ),
        True,
    )

    assessment = assess_reassessment_sequence(plan, failure, result)

    assert assessment.disposition == "replacement_required"
    assert [step.operation_name for step in assessment.steps] == [
        "set_actor_location",
        "set_actor_rotation",
        "set_actor_scale",
    ]
    assert [step.disposition for step in assessment.steps] == [
        "already_applied",
        "replacement_required",
        "already_applied",
    ]


def test_sequence_replacement_contains_only_the_operations_that_need_replacement():
    plan = _plan()
    assessment = UnrealRecoverySequenceAssessment((
        type("Step", (), {"operation_index": 0, "operation_name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "disposition": "already_applied"})(),
        type("Step", (), {"operation_index": 2, "operation_name": "set_actor_rotation", "entity_ids": ("FIELD_SURFACE",), "disposition": "replacement_required"})(),
        type("Step", (), {"operation_index": 4, "operation_name": "set_actor_scale", "entity_ids": ("FIELD_SURFACE",), "disposition": "already_applied"})(),
    ))

    replacement = build_replacement_plan(plan, assessment)

    assert replacement.intent_id == "composite-live:recovery-sequence-replacement"
    assert [operation.name for operation in replacement.operations] == [
        "set_actor_rotation",
        "verify_actor_rotation",
    ]
    assert replacement.operations[0].arguments["rotation"] == {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}
    assert replacement.operations[1].arguments["expected_rotation"] == {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}


def test_sequence_replacement_requires_fully_assessable_fresh_state():
    plan = _plan()
    assessment = UnrealRecoverySequenceAssessment((
        type("Step", (), {"operation_index": 0, "operation_name": "set_actor_location", "entity_ids": ("FIELD_SURFACE",), "disposition": "manual_review"})(),
    ))

    try:
        build_replacement_plan(plan, assessment)
    except ValueError as exc:
        assert str(exc) == "replacement plan cannot be built while any recovery step requires manual review"
    else:
        raise AssertionError("replacement must stop when fresh evidence is not sufficient")
