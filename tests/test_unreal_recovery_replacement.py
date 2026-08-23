from planning.unreal_adapter_production import UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability, UnrealOperationKind
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutionFailure,
    UnrealRecoveryAssessment,
    UnrealPlanExecutor,
)


def _failure():
    return UnrealPlanExecutionFailure(
        intent_id="composite-live",
        operation_index=5,
        operation_name="verify_actor_location",
        completed_evidence=(),
        error="verification failed",
        operation_entity_ids=("FIELD_SURFACE",),
        operation_arguments={
            "entity_ids": ("FIELD_SURFACE",),
            "expected_location": {"x": 10.0, "y": 20.0, "z": 30.0},
        },
    )


class NoTransport:
    def send(self, request):
        raise AssertionError("transport must not be reached when authorization is stale")


def test_replacement_plan_reconstructs_a_fresh_location_write_and_verification():
    failure = _failure()
    assessment = UnrealRecoveryAssessment(
        "replacement_required",
        "verify_actor_location",
        ("FIELD_SURFACE",),
        "fresh Unreal state does not match the failed operation's requested state",
    )

    plan = failure.replacement_plan(assessment)

    assert plan.intent_id == "composite-live:recovery-replacement"
    assert [operation.name for operation in plan.operations] == [
        "set_actor_location",
        "verify_actor_location",
    ]
    assert [operation.kind for operation in plan.operations] == [
        UnrealOperationKind.WRITE,
        UnrealOperationKind.VERIFY,
    ]
    assert all(operation.capability is UnrealCapability.MODIFY_ACTOR for operation in plan.operations)
    assert plan.operations[0].arguments["location"] == {"x": 10.0, "y": 20.0, "z": 30.0}
    assert plan.operations[1].arguments["expected_location"] == {"x": 10.0, "y": 20.0, "z": 30.0}


def test_replacement_plan_rejects_non_replacement_dispositions():
    failure = _failure()
    assessment = UnrealRecoveryAssessment(
        "already_applied",
        "verify_actor_location",
        ("FIELD_SURFACE",),
        "fresh Unreal state already matches the failed operation's requested state",
    )

    try:
        failure.replacement_plan(assessment)
    except ValueError as exc:
        assert str(exc) == "replacement_plan requires a replacement_required assessment"
    else:
        raise AssertionError("replacement plan must not be created for an already-applied disposition")


def test_replacement_execution_rejects_stale_reassessment_authorization_before_transport():
    failure = _failure()
    assessment = UnrealRecoveryAssessment(
        "replacement_required",
        "verify_actor_location",
        ("FIELD_SURFACE",),
        "fresh Unreal state does not match the failed operation's requested state",
    )
    replacement = failure.replacement_plan(assessment)
    stale = UnrealPlanAuthorization.issue(failure.reassessment_plan(), "stale-reassessment-auth")
    executor = UnrealPlanExecutor(UnrealAdapterProduction(NoTransport()))

    try:
        executor.execute_authorized(replacement, stale)
    except UnrealPlanExecutionError as exc:
        assert str(exc) == "authorization receipt does not match the exact Unreal task plan"
    else:
        raise AssertionError("replacement execution must reject the stale reassessment authorization")


def test_replacement_plan_requires_failed_entity_scope():
    failure = _failure()
    assessment = UnrealRecoveryAssessment(
        "replacement_required",
        "verify_actor_location",
        ("OTHER_ACTOR",),
        "fresh Unreal state does not match the failed operation's requested state",
    )

    try:
        failure.replacement_plan(assessment)
    except ValueError as exc:
        assert str(exc) == "assessment entity_ids must match failed operation entity_ids"
    else:
        raise AssertionError("replacement plan must preserve the failed operation entity scope")
