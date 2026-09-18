"""Deterministic design gate for shot-level Unreal production continuity.

This gate freezes the existing contracts before the live UE continuity test.
It deliberately does not introduce a workflow engine or change the transport.
The tests establish what is already guaranteed and expose the remaining narrow
continuity seam documented in the design review.
"""

from pathlib import Path

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_verifier import verify_render_job_completion
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlan
from planning.unreal_composite_operation import build_composite_actor_operation

TARGET = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"


def _intent(intent_id="shot-continuity-design"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="shot continuity design gate",
        target_entity_ids=(TARGET,),
    )


def _composite():
    return build_composite_actor_operation(
        [TARGET],
        [
            {"name": "set_actor_location", "location": {"x": 10.0, "y": 20.0, "z": 30.0}},
            {"name": "set_actor_rotation", "rotation": {"pitch": 0.0, "yaw": 15.0, "roll": 0.0}},
            {"name": "set_actor_scale", "scale": {"x": 1.1, "y": 1.1, "z": 1.1}},
            {"name": "apply_material_variant", "variant": "liquid_surface"},
            {"name": "apply_niagara_variant", "variant": "goal_burst"},
        ],
    )


def _spec():
    return UnrealProductionSpec(
        composite=_composite(),
        start_frame=1,
        end_frame=24,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=1,
            end_frame=24,
            output_directory="Saved/AtlasProductionOutput",
            output_format="png",
        ),
        sequence_asset_path=SEQUENCE,
        blueprint_asset_path=None,
    )


def _production():
    return build_unreal_production_plan(_intent(), _spec())


def _job_evidence(tmp_path, *, sequence=SEQUENCE, job_id="job-design", start=1, end=24):
    outputs = []
    for frame in range(start, end + 1):
        path = tmp_path / f"frame_{frame:04d}.png"
        path.write_bytes(b"png")
        outputs.append(str(path.resolve()))
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": job_id,
            "sequence_asset_path": sequence,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_files": outputs,
        },
        source="shot-continuity-design-gate",
        verified=True,
    )


def test_design_gate_requires_exact_sequencer_render_frame_continuity():
    production = _production()
    operations = production.plan.operations

    sequencer_write = next(op for op in operations if op.name == "set_sequencer_playback_range")
    render_write = next(op for op in operations if op.name == "configure_render")

    assert {
        "start_frame": sequencer_write.arguments["start_frame"],
        "end_frame": sequencer_write.arguments["end_frame"],
    } == {
        "start_frame": render_write.arguments["start_frame"],
        "end_frame": render_write.arguments["end_frame"],
    }


def test_design_gate_authorizes_the_existing_heterogeneous_production_plan():
    production = _production()
    authorization = UnrealPlanAuthorization.issue(
        production.plan,
        "shot-continuity-design-auth",
    )

    assert authorization.matches(production.plan)
    assert production.plan.intent_id == _intent().intent_id
    assert all(tuple(operation.entity_ids) == (TARGET,) for operation in production.plan.operations)


def test_design_gate_render_submission_plan_binds_sequence_asset_path():
    planner = __import__("planning.unreal_task_planner", fromlist=["UnrealTaskPlanner"]).UnrealTaskPlanner()
    plan = planner.plan_render_submission(_intent("submission-binding"), SEQUENCE)

    assert isinstance(plan, UnrealTaskPlan)
    assert plan.operations[0].name == "submit_render"
    assert plan.operations[0].arguments["sequence_asset_path"] == SEQUENCE
    assert plan.operations[1].name == "verify_render_job"
    assert plan.operations[1].arguments["job_id"] == "$previous.submit_render.job_id"


def test_design_gate_job_identity_and_artifact_existence_are_already_verified(tmp_path):
    evidence = _job_evidence(tmp_path)

    verified = verify_render_job_completion(
        evidence,
        expected_job_id="job-design",
        require_artifacts=True,
    )

    assert verified is evidence


def test_design_gate_receipt_binds_job_and_sequence_but_exposes_the_remaining_contract_gap(tmp_path):
    evidence = _job_evidence(tmp_path, end=1)
    receipt = UnrealRenderReceipt.issue(evidence)

    assert receipt.job_id == "job-design"
    assert receipt.sequence_asset_path == SEQUENCE
    assert set(receipt.snapshot()) == {
        "job_id",
        "sequence_asset_path",
        "evidence_digest",
    }
    # The receipt intentionally does not yet bind frame range/output config;
    # those are the next continuity fields to add and verify.
    assert "start_frame" not in receipt.snapshot()
    assert "end_frame" not in receipt.snapshot()
    assert "output_directory" not in receipt.snapshot()
    assert "output_format" not in receipt.snapshot()


@pytest.mark.parametrize(
    "start,end",
    [(1, 24), (24, 24), (0, 1)],
)
def test_design_gate_png_frame_count_model_is_deterministic(tmp_path, start, end):
    evidence = _job_evidence(tmp_path, start=start, end=end)
    observed_count = len(evidence.observed_state["output_files"])
    expected_count = end - start + 1
    assert observed_count == expected_count
