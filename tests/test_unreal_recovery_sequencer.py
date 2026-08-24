from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult
from planning.unreal_recovery_sequence import assess_reassessment_sequence, build_reassessment_plan, build_replacement_plan
from planning.unreal_task_planner import UnrealTaskPlan


ENTITY_IDS = ("FIELD_SURFACE",)


def _plan():
    return UnrealTaskPlan("sequencer-recovery", (
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.WRITE,
            "set_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "start_frame": 10, "end_frame": 110},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.VERIFY,
            "verify_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "expected_start_frame": 10, "expected_end_frame": 110},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.MATERIAL,
            UnrealOperationKind.WRITE,
            "apply_material_variant",
            {"entity_ids": ENTITY_IDS, "material_variant": {"name": "liquid_surface"}},
            ENTITY_IDS,
        ),
    ))


def _failure():
    return UnrealPlanExecutionFailure(
        "sequencer-recovery",
        2,
        "apply_material_variant",
        (),
        "material mutation failed",
        ENTITY_IDS,
        {"entity_ids": ENTITY_IDS, "material_variant": {"name": "liquid_surface"}},
        (),
    )


def _sequencer_evidence(start_frame, end_frame):
    return UnrealEvidence(
        "inspect_sequencer_state",
        ENTITY_IDS,
        {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": start_frame, "end_frame": end_frame}}},
        "unreal-editor-atlas-transport",
    )


def _material_evidence(name):
    return UnrealEvidence(
        "inspect_material_state",
        ENTITY_IDS,
        {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": name}}}},
        "unreal-editor-atlas-transport",
    )


def test_reassessment_plan_includes_sequencer_read():
    reassessment = build_reassessment_plan(_plan(), _failure())
    assert [operation.name for operation in reassessment.operations] == ["inspect_sequencer_state", "inspect_material_state"]
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)


def test_sequencer_recovery_marks_matching_range_already_applied():
    result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(10, 110), _material_evidence("wet_surface")),
        True,
    )
    assessment = assess_reassessment_sequence(_plan(), _failure(), result)
    by_name = {step.operation_name: step for step in assessment.steps}
    assert by_name["set_sequencer_playback_range"].disposition == "already_applied"
    assert by_name["set_sequencer_playback_range"].reason == "fresh Unreal state matches the requested state"


def test_sequencer_recovery_rebuilds_only_mismatched_range():
    result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("liquid_surface")),
        True,
    )
    assessment = assess_reassessment_sequence(_plan(), _failure(), result)
    assert assessment.disposition == "replacement_required"
    replacement = build_replacement_plan(_plan(), assessment)
    assert [operation.name for operation in replacement.operations] == [
        "set_sequencer_playback_range",
        "verify_sequencer_playback_range",
    ]
    assert replacement.operations[0].arguments["start_frame"] == 10
    assert replacement.operations[0].arguments["end_frame"] == 110
    assert replacement.operations[1].arguments["expected_start_frame"] == 10
    assert replacement.operations[1].arguments["expected_end_frame"] == 110
