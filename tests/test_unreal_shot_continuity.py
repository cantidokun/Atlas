"""Deterministic shot-level production continuity gate.

Covers the frozen continuity invariants of
``docs/UNREAL_SHOT_CONTINUITY_DESIGN_REVIEW.md`` with no live engine, no
transport, and no render submission. The matrix exercised here is the design
review's pre-live matrix:

    1  matching sequence path passes
    2  sequence path mismatch fails before render submission
    3  matching Sequencer/render ranges pass
    4  mismatched ranges fail before render submission
    5  final job ID mismatch fails
    6  final sequence path mismatch fails
    7  final frame-range mismatch fails
    8  final output-directory mismatch fails
    9  final output-format mismatch fails
    10 PNG complete frame count passes
    11 PNG incomplete frame count fails
    12 duplicate frame outputs do not falsely satisfy uniqueness
    13 production failure blocks render submission
    14 recovery remains explicit and authorization-bound
"""

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult
from planning.unreal_production_executor import (
    UnrealProductionExecutionResult,
    UnrealProductionExecutor,
)
from planning.unreal_production_operation import (
    UnrealProductionPlan,
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_workflow import (
    UnrealProductionWorkflow,
    UnrealProductionWorkflowError,
    UnrealProductionWorkflowResult,
)
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_workflow import (
    UnrealRenderWorkflow,
    UnrealRenderWorkflowError,
    UnrealRenderWorkflowResult,
)
from planning.unreal_shot_continuity import (
    UnrealShotContinuity,
    verify_shot_continuity_completeness,
    verify_shot_continuity_identity,
)
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlanner
from tests.test_unreal_production_operation import _composite

TARGET = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
OTHER_SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequenceB"
OUTPUT_DIRECTORY = "Saved/AtlasProductionOutput"
START_FRAME = 1
END_FRAME = 24
JOB_ID = "job-shot-continuity"


def _intent(intent_id="shot-continuity-gate"):
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="shot continuity deterministic gate",
        target_entity_ids=(TARGET,),
    )


def _spec(
    *,
    sequence=SEQUENCE,
    start_frame=START_FRAME,
    end_frame=END_FRAME,
    output_directory=OUTPUT_DIRECTORY,
    output_format="png",
    render_format=None,
):
    return UnrealProductionSpec(
        composite=_composite(),
        start_frame=start_frame,
        end_frame=end_frame,
        render_config=UnrealRenderConfig(
            width=1280,
            height=720,
            start_frame=start_frame,
            end_frame=end_frame,
            output_directory=output_directory,
            output_format=render_format or output_format,
        ),
        sequence_asset_path=sequence,
    )


def _production(intent=None, **spec_kwargs):
    return build_unreal_production_plan(intent or _intent(), _spec(**spec_kwargs))


def _authorized_production(intent=None, **spec_kwargs):
    production = _production(intent, **spec_kwargs)
    return production, authorize_production_plan(
        production,
        "shot-continuity-production-auth",
    )


def _job_evidence(
    tmp_path,
    *,
    sequence=SEQUENCE,
    job_id=JOB_ID,
    start_frame=START_FRAME,
    end_frame=END_FRAME,
    output_directory=OUTPUT_DIRECTORY,
    output_format="png",
    frames=None,
    include_range=True,
    end_frame_exclusive=None,
    absolute_output_directory=False,
):
    """Build fresh render-job evidence with real on-disk artifacts."""
    if frames is None:
        frames = list(range(start_frame, end_frame + 1))

    output_files = []

    for frame in frames:
        path = tmp_path / f"frame_{frame:04d}.png"
        path.write_bytes(b"png")
        output_files.append(str(path.resolve()))

    directory = output_directory

    if absolute_output_directory:
        from planning.unreal_render_contract import UNREAL_PROJECT_ROOT

        directory = str((UNREAL_PROJECT_ROOT / output_directory).resolve())

    state = {
        "job_id": job_id,
        "sequence_asset_path": sequence,
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_directory": directory,
        "output_format": output_format,
        "output_files": output_files,
    }

    if include_range:
        state["start_frame"] = start_frame
        state["end_frame"] = end_frame
        state["end_frame_exclusive"] = (
            end_frame + 1 if end_frame_exclusive is None else end_frame_exclusive
        )

    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state=state,
        source="shot-continuity-gate",
        verified=True,
    )


def _completed_render(intent, evidence, *, job_id=JOB_ID):
    receipt = UnrealRenderReceipt.issue(evidence)

    return UnrealRenderWorkflowResult(
        intent_id=intent.intent_id,
        job_id=job_id,
        final_evidence=evidence,
        receipt=receipt,
        persisted_receipt={
            "job_id": receipt.job_id,
            "sequence_asset_path": receipt.sequence_asset_path,
            "evidence_digest": receipt.evidence_digest,
            "receipt_digest": receipt.receipt_digest,
        },
    )


class FakeProductionExecutor(UnrealProductionExecutor):
    """Deterministic production boundary that records calls and never mutates."""

    def __init__(self, *, success=True):
        self.calls = []
        self.success = success

    def execute(self, production, authorization, **kwargs):
        self.calls.append((production, authorization))
        initial = (
            UnrealPlanExecutionResult(
                intent_id=production.plan.intent_id,
                evidence_ledger=(),
                success=True,
            )
            if self.success
            else None
        )

        return UnrealProductionExecutionResult(
            production=production,
            initial_result=initial,
            failure=None if self.success else object(),
            recovery=None,
        )


class RecordingRenderWorkflow(UnrealRenderWorkflow):
    """Deterministic render boundary that records what production submitted."""

    def __init__(self, *, final_result=None, submit_failure=False):
        self.submit_calls = []
        self.wait_calls = []
        self.final_result = final_result
        self.submit_failure = submit_failure

    def submit(self, intent, sequence_asset_path, authorization_factory):
        self.submit_calls.append(sequence_asset_path)

        if self.submit_failure:
            raise UnrealRenderWorkflowError("render submission failed")

        evidence = UnrealEvidence(
            operation_name="verify_render_job",
            entity_ids=(TARGET,),
            observed_state={
                "job_id": JOB_ID,
                "status": "queued",
                "finished": False,
                "success": False,
                "failed": False,
                "output_files": [],
            },
            source="shot-continuity-gate",
            verified=True,
        )

        return UnrealPlanExecutionResult(
            intent_id=intent.intent_id,
            evidence_ledger=(evidence,),
            success=True,
        )

    def wait_for_completion(
        self,
        intent,
        job_id,
        authorization_factory,
        *,
        expected_continuity=None,
    ):
        self.wait_calls.append((job_id, expected_continuity))

        if self.final_result is None:
            raise UnrealRenderWorkflowError(
                "shot continuity gate did not supply a final render result"
            )

        return self.final_result


def _workflow(*, production_success=True, final_result=None, submit_failure=False):
    production = FakeProductionExecutor(success=production_success)
    render = RecordingRenderWorkflow(
        final_result=final_result,
        submit_failure=submit_failure,
    )

    return UnrealProductionWorkflow(production, render), production, render


# --------------------------------------------------------------------------
# 1 / 2  sequence asset path continuity
# --------------------------------------------------------------------------


def test_matching_sequence_path_passes_and_production_submits_the_authorized_value(
    tmp_path,
):
    production, authorized = _authorized_production()
    evidence = _job_evidence(tmp_path)
    intent = _intent()
    workflow, production_executor, render = _workflow(
        final_result=_completed_render(intent, evidence),
    )

    result = workflow.run(
        production,
        authorized.authorization,
        intent,
        SEQUENCE,
        lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
    )

    assert result.success is True
    # The submission path is the authorization-bound value, never a caller echo.
    assert render.submit_calls == [SEQUENCE]
    assert production.continuity.sequence_asset_path == SEQUENCE
    # The final fresh evidence was verified against the authorized continuity.
    assert render.wait_calls == [(JOB_ID, production.continuity)]
    assert len(production_executor.calls) == 1


def test_declared_submission_path_that_differs_is_rejected_before_execution():
    production, authorized = _authorized_production()
    workflow, production_executor, render = _workflow()

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="does not match the authorization-bound production sequence_asset_path",
    ):
        workflow.run(
            production,
            authorized.authorization,
            _intent(),
            OTHER_SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls == []
    assert render.submit_calls == []
    assert render.wait_calls == []


def test_production_authorization_binds_one_exact_sequence_path():
    production, authorized = _authorized_production()

    swapped = UnrealProductionPlan(
        plan=production.plan,
        phases=production.phases,
        continuity=UnrealShotContinuity(
            sequence_asset_path=OTHER_SEQUENCE,
            start_frame=START_FRAME,
            end_frame=END_FRAME,
            output_directory=OUTPUT_DIRECTORY,
            output_format="png",
        ),
    )

    # The same inner plan under a different authorized sequence identity is not
    # covered by the receipt the authorization boundary issued.
    assert authorized.authorization.matches(
        production.plan,
        continuity_digest=production.continuity.continuity_digest,
    )
    assert not authorized.authorization.matches(
        swapped.plan,
        continuity_digest=swapped.continuity.continuity_digest,
    )

    workflow, production_executor, render = _workflow()

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="does not match the exact production plan",
    ):
        workflow.run(
            swapped,
            authorized.authorization,
            _intent(),
            OTHER_SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls == []
    assert render.submit_calls == []


def test_plan_only_authorization_cannot_authorize_a_shot_continuity():
    production = _production()
    plan_only = UnrealPlanAuthorization.issue(production.plan, "plan-only-auth")

    assert plan_only.matches(production.plan) is True
    assert (
        plan_only.matches(
            production.plan,
            continuity_digest=production.continuity.continuity_digest,
        )
        is False
    )

    workflow, production_executor, render = _workflow()

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="does not match the exact production plan",
    ):
        workflow.run(
            production,
            plan_only,
            _intent(),
            SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert production_executor.calls == []
    assert render.submit_calls == []


def test_continuity_digest_identity_is_stable_and_distinguishing():
    first = _production().continuity
    second = _production().continuity
    other = _production(sequence=OTHER_SEQUENCE).continuity
    other_range = _production(end_frame=23).continuity

    assert first.continuity_digest == second.continuity_digest
    assert first.continuity_digest != other.continuity_digest
    assert first.continuity_digest != other_range.continuity_digest

    production, authorized = _authorized_production()
    plan_only = UnrealPlanAuthorization.issue(production.plan, "identity-auth")
    bound = UnrealPlanAuthorization.issue(
        production.plan,
        "identity-auth",
        continuity_digest=production.continuity.continuity_digest,
    )

    assert authorized.authorization.continuity_bound is True
    assert plan_only.continuity_bound is False
    # Continuous identity is part of the receipt identity, not an attribute.
    assert bound.authorization_digest != plan_only.authorization_digest
    assert bound.snapshot()["continuity_digest"] == (
        production.continuity.continuity_digest
    )


# --------------------------------------------------------------------------
# 3 / 4  frame-range continuity
# --------------------------------------------------------------------------


def test_matching_sequencer_render_and_continuity_frame_ranges_pass():
    production = _production()
    operations = production.plan.operations

    sequencer_write = next(
        operation for operation in operations
        if operation.name == "set_sequencer_playback_range"
    )
    render_write = next(
        operation for operation in operations if operation.name == "configure_render"
    )

    assert production.continuity.start_frame == START_FRAME
    assert production.continuity.end_frame == END_FRAME
    assert sequencer_write.arguments["start_frame"] == START_FRAME
    assert sequencer_write.arguments["end_frame"] == END_FRAME
    assert render_write.arguments["start_frame"] == START_FRAME
    assert render_write.arguments["end_frame"] == END_FRAME


def test_render_range_that_differs_from_production_range_is_rejected():
    with pytest.raises(ValueError, match="frame range"):
        UnrealProductionSpec(
            composite=_composite(),
            start_frame=START_FRAME,
            end_frame=END_FRAME,
            render_config=UnrealRenderConfig(
                width=1280,
                height=720,
                start_frame=START_FRAME,
                end_frame=END_FRAME + 1,
                output_directory=OUTPUT_DIRECTORY,
                output_format="png",
            ),
            sequence_asset_path=SEQUENCE,
        )


def test_continuity_that_disagrees_with_render_configuration_is_rejected():
    production = _production()
    operations = []

    for operation in production.plan.operations:
        if operation.name == "configure_render":
            arguments = dict(operation.arguments)
            arguments["end_frame"] = END_FRAME - 1
            arguments["output_directory"] = "Saved/AtlasOtherOutput"
            operations.append(
                type(operation)(
                    capability=operation.capability,
                    kind=operation.kind,
                    name=operation.name,
                    arguments=arguments,
                    entity_ids=operation.entity_ids,
                )
            )
        else:
            operations.append(operation)

    operations = tuple(operations)

    with pytest.raises(ValueError, match="does not match the declared shot continuity"):
        UnrealProductionPlan(
            plan=type(production.plan)(production.plan.intent_id, operations),
            phases=(("inspection", 0, len(operations)),),
            continuity=production.continuity,
        )


def test_continuity_that_disagrees_with_sequencer_range_is_rejected():
    production = _production()
    operations = []

    for operation in production.plan.operations:
        if operation.name == "set_sequencer_playback_range":
            arguments = dict(operation.arguments)
            arguments["end_frame"] = END_FRAME - 1
            operations.append(
                type(operation)(
                    capability=operation.capability,
                    kind=operation.kind,
                    name=operation.name,
                    arguments=arguments,
                    entity_ids=operation.entity_ids,
                )
            )
        else:
            operations.append(operation)

    operations = tuple(operations)

    with pytest.raises(ValueError, match="sequencer range"):
        UnrealProductionPlan(
            plan=type(production.plan)(production.plan.intent_id, operations),
            phases=(("inspection", 0, len(operations)),),
            continuity=production.continuity,
        )


def test_spec_rejects_non_canonical_or_missing_sequence_identity():
    with pytest.raises(ValueError, match="sequence_asset_path"):
        _spec(sequence="AtlasSequencerFixtureSequence")

    with pytest.raises(ValueError, match="sequence_asset_path"):
        _spec(sequence="")

    with pytest.raises(ValueError, match="sequence_asset_path"):
        _spec(sequence=" /Game/AtlasTest/AtlasSequencerFixtureSequence ")


def test_continuity_contract_rejects_invalid_values():
    with pytest.raises(TypeError, match="start_frame"):
        UnrealShotContinuity(SEQUENCE, True, END_FRAME, OUTPUT_DIRECTORY, "png")

    with pytest.raises(TypeError, match="end_frame"):
        UnrealShotContinuity(SEQUENCE, START_FRAME, "24", OUTPUT_DIRECTORY, "png")

    with pytest.raises(ValueError, match="must not exceed"):
        UnrealShotContinuity(SEQUENCE, END_FRAME, START_FRAME, OUTPUT_DIRECTORY, "png")

    with pytest.raises(ValueError, match="output_directory"):
        UnrealShotContinuity(SEQUENCE, START_FRAME, END_FRAME, "  ", "png")

    with pytest.raises(ValueError, match="output_format"):
        UnrealShotContinuity(SEQUENCE, START_FRAME, END_FRAME, OUTPUT_DIRECTORY, "")


# --------------------------------------------------------------------------
# 6 / 7 / 8 / 9  final evidence continuity
# --------------------------------------------------------------------------


def test_final_evidence_must_reproduce_the_authorized_continuity(tmp_path):
    production, authorized = _authorized_production()
    continuity = production.continuity
    intent = _intent()

    evidence = _job_evidence(tmp_path)
    assert verify_shot_continuity_completeness(evidence, continuity) is evidence

    absolute = _job_evidence(tmp_path, absolute_output_directory=True)
    assert verify_shot_continuity_identity(absolute, continuity) is absolute


def test_final_sequence_path_mismatch_fails(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, sequence=OTHER_SEQUENCE)

    with pytest.raises(ValueError, match="sequence_asset_path mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_final_frame_range_mismatch_fails(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, start_frame=START_FRAME, end_frame=END_FRAME - 1)

    with pytest.raises(ValueError, match="frame range mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_final_output_directory_mismatch_fails(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, output_directory="Saved/AtlasOtherOutput")

    with pytest.raises(ValueError, match="output_directory mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_final_output_format_mismatch_fails(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, output_format="jpg")

    with pytest.raises(ValueError, match="output_format mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_final_evidence_without_effective_frame_range_fails_closed(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, include_range=False)

    with pytest.raises(ValueError, match="effective"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_final_evidence_with_non_integer_frame_range_fails_closed(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path)
    state = dict(evidence.observed_state)
    state["start_frame"] = str(START_FRAME)
    coerced = UnrealEvidence(
        operation_name=evidence.operation_name,
        entity_ids=evidence.entity_ids,
        observed_state=state,
        source=evidence.source,
        verified=True,
    )

    with pytest.raises(TypeError, match="start_frame"):
        verify_shot_continuity_completeness(coerced, production.continuity)


def test_render_workflow_rejects_continuity_violation_before_issuing_a_receipt(
    tmp_path,
):
    production, authorized = _authorized_production()
    intent = _intent()
    evidence = _job_evidence(tmp_path, sequence=OTHER_SEQUENCE)
    workflow, production_executor, render = _workflow(
        final_result=_completed_render(intent, evidence),
    )

    with pytest.raises(UnrealProductionWorkflowError) as error:
        workflow.run(
            production,
            authorized.authorization,
            intent,
            SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert "sequence_asset_path mismatch" in str(error.value)


def test_continuity_bound_receipt_requires_continuity_verified_evidence(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path)
    verified = verify_shot_continuity_completeness(evidence, production.continuity)
    receipt = UnrealRenderReceipt.issue(verified)

    assert receipt.matches(evidence) is True
    assert set(receipt.snapshot()) == {
        "job_id",
        "sequence_asset_path",
        "evidence_digest",
    }
    assert receipt.sequence_asset_path == production.continuity.sequence_asset_path
    assert receipt.job_id == JOB_ID


# --------------------------------------------------------------------------
# 5  final job identity continuity
# --------------------------------------------------------------------------


def test_workflow_success_requires_exact_final_job_identity(tmp_path):
    production, authorized = _authorized_production()
    intent = _intent()
    evidence = _job_evidence(tmp_path, job_id="job-somewhere-else")
    result = UnrealProductionWorkflowResult(
        production=production_executor_result(production),
        render=_completed_render(intent, evidence),
    )

    assert result.verified_render is False
    assert result.success is False


def test_workflow_success_requires_observable_continuity_in_final_evidence(tmp_path):
    production, _ = _authorized_production()
    intent = _intent()

    for evidence in (
        _job_evidence(tmp_path, sequence=OTHER_SEQUENCE),
        _job_evidence(tmp_path, output_format="exr"),
        _job_evidence(tmp_path, output_directory="Saved/AtlasOtherOutput"),
        _job_evidence(tmp_path, include_range=False),
    ):
        result = UnrealProductionWorkflowResult(
            production=production_executor_result(production),
            render=_completed_render(intent, evidence),
        )

        assert result.verified_render is False
        assert result.success is False


def production_executor_result(production):
    """Return the typed production execution result for one production plan."""

    return UnrealProductionExecutionResult(
        production=production,
        initial_result=UnrealPlanExecutionResult(
            intent_id=production.plan.intent_id,
            evidence_ledger=(),
            success=True,
        ),
        failure=None,
        recovery=None,
    )


# --------------------------------------------------------------------------
# 10 / 11 / 12  PNG artifact completeness
# --------------------------------------------------------------------------


def test_png_complete_frame_count_passes(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path)

    assert production.continuity.expected_frame_count == END_FRAME - START_FRAME + 1
    assert (
        verify_shot_continuity_completeness(evidence, production.continuity)
        is evidence
    )


def test_png_incomplete_frame_count_fails(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(tmp_path, frames=list(range(START_FRAME, END_FRAME)))

    with pytest.raises(ValueError, match="PNG frame coverage mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_duplicate_frame_outputs_do_not_satisfy_uniqueness(tmp_path):
    production, _ = _authorized_production()
    evidence = _job_evidence(
        tmp_path,
        frames=[START_FRAME] * (END_FRAME - START_FRAME + 1),
    )

    # A repeated artifact path collapses to one unique file; the artifact frame
    # guard now fires first with a more specific error than the count guard.
    with pytest.raises(ValueError, match="duplicate frame 1"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_png_frame_set_must_equal_the_authorized_inclusive_frames(tmp_path):
    production, _ = _authorized_production(start_frame=START_FRAME, end_frame=5)
    # Five unique artifacts, so any count-only rule would accept them, but frame
    # 5 is missing and frame 6 is extra.
    evidence = _job_evidence(
        tmp_path,
        start_frame=START_FRAME,
        end_frame=5,
        frames=[1, 2, 3, 4, 6],
    )

    assert len(set(evidence.observed_state["output_files"])) == 5

    with pytest.raises(ValueError, match="frame set mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_duplicate_frame_numbers_in_distinct_paths_fail(tmp_path):
    production, _ = _authorized_production(start_frame=START_FRAME, end_frame=2)
    paths = []

    for directory, frame in (("a", 1), ("b", 1), ("c", 2)):
        path = tmp_path / directory / f"frame_{frame:04d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        paths.append(str(path.resolve()))

    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": JOB_ID,
            "sequence_asset_path": SEQUENCE,
            "start_frame": START_FRAME,
            "end_frame": 2,
            "end_frame_exclusive": 3,
            "output_directory": OUTPUT_DIRECTORY,
            "output_format": "png",
            "output_files": paths,
        },
        source="shot-continuity-gate",
        verified=True,
    )

    with pytest.raises(ValueError, match="duplicate frame 1"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_png_artifact_without_a_frame_number_fails(tmp_path):
    production, _ = _authorized_production(start_frame=START_FRAME, end_frame=2)
    path = tmp_path / "atlas_render.png"
    path.write_bytes(b"png")
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": JOB_ID,
            "sequence_asset_path": SEQUENCE,
            "start_frame": START_FRAME,
            "end_frame": 2,
            "end_frame_exclusive": 3,
            "output_directory": OUTPUT_DIRECTORY,
            "output_format": "png",
            "output_files": [str(path.resolve())],
        },
        source="shot-continuity-gate",
        verified=True,
    )

    with pytest.raises(ValueError, match="does not expose a frame number"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_frame_count_rule_is_not_generalized_to_other_formats(tmp_path):
    production, _ = _authorized_production(output_format="exr", render_format="exr")
    assert production.continuity.normalized_output_format == "exr"

    # Only one artifact for a 24-frame range: the PNG rule must not apply.
    evidence = _job_evidence(tmp_path, output_format="exr", frames=[START_FRAME])

    assert (
        verify_shot_continuity_completeness(evidence, production.continuity)
        is evidence
    )


@pytest.mark.parametrize(
    "start,end,expected_count",
    [(1, 1, 1), (1, 2, 2), (1, 5, 5), (5, 5, 1)],
)
def test_png_complete_frame_count_matches_the_authorized_inclusive_range(
    tmp_path, start, end, expected_count
):
    production, _ = _authorized_production(start_frame=start, end_frame=end)
    evidence = _job_evidence(tmp_path, start_frame=start, end_frame=end)

    assert production.continuity.expected_frame_count == expected_count
    assert len(set(evidence.observed_state["output_files"])) == expected_count
    assert (
        verify_shot_continuity_completeness(evidence, production.continuity)
        is evidence
    )


@pytest.mark.parametrize(
    "start,end,expected_count",
    [(1, 1, 1), (1, 2, 2), (1, 5, 5)],
)
def test_incomplete_png_coverage_fails_for_every_authorized_range(
    tmp_path, start, end, expected_count
):
    production, _ = _authorized_production(start_frame=start, end_frame=end)
    frames = list(range(start, end))

    if not frames:
        pytest.skip("a single-frame range has no strictly smaller valid range")

    evidence = _job_evidence(tmp_path, start_frame=start, end_frame=end, frames=frames)

    assert len(set(evidence.observed_state["output_files"])) == expected_count - 1

    with pytest.raises(ValueError, match="PNG frame coverage mismatch"):
        verify_shot_continuity_completeness(evidence, production.continuity)


@pytest.mark.parametrize(
    "start,end,end_frame_exclusive",
    [(1, 2, 3), (1, 5, 6), (1, 24, 25), (5, 5, 6)],
)
def test_authorized_inclusive_range_maps_to_a_half_open_engine_boundary(
    start, end, end_frame_exclusive
):
    production, _ = _authorized_production(start_frame=start, end_frame=end)
    continuity = production.continuity

    # Atlas 1-2 -> engine [1,3); Atlas 1-5 -> engine [1,6).
    assert continuity.start_frame == start
    assert continuity.end_frame == end
    assert continuity.end_frame_exclusive == end_frame_exclusive
    assert continuity.expected_frame_count == end_frame_exclusive - start


def test_engine_boundary_that_contradicts_the_inclusive_range_fails(tmp_path):
    production, _ = _authorized_production(start_frame=START_FRAME, end_frame=2)
    # A half-open boundary of [1,2) would mean the engine rendered one frame for
    # an authorized two-frame inclusive range; that must fail closed.
    evidence = _job_evidence(tmp_path, end_frame=2, end_frame_exclusive=2)

    with pytest.raises(ValueError, match="half-open boundary"):
        verify_shot_continuity_completeness(evidence, production.continuity)


def test_engine_boundary_field_must_be_an_integer(tmp_path):
    production, _ = _authorized_production(start_frame=START_FRAME, end_frame=2)
    evidence = _job_evidence(tmp_path, end_frame=2)
    state = dict(evidence.observed_state)
    state["end_frame_exclusive"] = "3"
    coerced = UnrealEvidence(
        operation_name=evidence.operation_name,
        entity_ids=evidence.entity_ids,
        observed_state=state,
        source=evidence.source,
        verified=True,
    )

    with pytest.raises(TypeError, match="end_frame_exclusive"):
        verify_shot_continuity_completeness(coerced, production.continuity)


# --------------------------------------------------------------------------
# 13 / 14  failure and recovery continuity
# --------------------------------------------------------------------------


def test_failed_production_blocks_render_submission():
    production, authorized = _authorized_production()
    workflow, production_executor, render = _workflow(production_success=False)

    with pytest.raises(
        UnrealProductionWorkflowError,
        match="heterogeneous Unreal production did not complete",
    ):
        workflow.run(
            production,
            authorized.authorization,
            _intent(),
            SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert len(production_executor.calls) == 1
    assert render.submit_calls == []
    assert render.wait_calls == []


def test_render_submission_failure_is_not_retried():
    production, authorized = _authorized_production()
    workflow, production_executor, render = _workflow(submit_failure=True)

    with pytest.raises(UnrealRenderWorkflowError, match="render submission failed"):
        workflow.run(
            production,
            authorized.authorization,
            _intent(),
            SEQUENCE,
            lambda plan: UnrealPlanAuthorization.issue(plan, "render-auth"),
        )

    assert len(production_executor.calls) == 1
    assert render.submit_calls == [SEQUENCE]
    assert render.wait_calls == []


def test_recovery_does_not_reuse_the_production_continuity_authorization():
    production, authorized = _authorized_production(sequence=OTHER_SEQUENCE)
    planner = UnrealTaskPlanner()

    reassessment_plan = planner.plan_inspection(
        _intent("shot-continuity-recovery")
    )

    # The production receipt binds one exact production plan and continuity; it
    # never authorizes a later reassessment or replacement plan.
    assert authorized.authorization.matches(reassessment_plan) is False
    assert (
        authorized.authorization.matches(
            reassessment_plan,
            continuity_digest=production.continuity.continuity_digest,
        )
        is False
    )


def test_recovery_authorization_is_separate_from_the_production_continuity():
    production, authorized = _authorized_production()
    replacement = UnrealTaskPlanner().plan_composite_actor_production(
        _intent("shot-continuity-recovery"),
        _composite(),
    )
    replacement_authorization = UnrealPlanAuthorization.issue(
        replacement,
        "shot-continuity-recovery-auth",
    )

    assert replacement_authorization.matches(replacement) is True
    assert replacement_authorization.continuity_bound is False
    assert (
        replacement_authorization.matches(
            replacement,
            continuity_digest=production.continuity.continuity_digest,
        )
        is False
    )
    assert authorized.authorization.matches(replacement) is False
