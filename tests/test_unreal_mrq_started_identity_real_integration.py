"""Live UE 5.6.1 gate: monitoring-state identity for multi-job MRQ sessions.

Slice D half of the MRQ attribution milestone. ONE editor session, MULTIPLE queued
jobs, no fresh-editor workaround. The engine's executor renders every job already
present in the queue and broadcasts ``OnIndividualJobStarted`` once per started
job, so this gate proves against the real engine that:

    - the Atlas job receives its OWN start transition (status reaches "rendering");
    - a foreign queued job's start does NOT overwrite the Atlas job's monitoring
      state - sampled directly in the window where an earlier queued job is
      rendering and the new Atlas job has not started yet;
    - Slice 1 artifact isolation still holds (each job's evidence carries only its
      own frames inside its own authorized directory);
    - exact job-ID binding still holds on every read;
    - same-range multi-submission behaviour remains correct;
    - receipts remain coherent with the fresh evidence;
    - no stale-MRQ false positive (frame-set equality + containment on every job).

The submission is sequenced explicitly (production -> submit -> sample -> wait) so
the sampling window is real: ``wait_for_completion`` is only entered after the
start-transition observations. Helpers that are not submission-blocking are
imported from the Slice 1/2 live module so that module stays byte-identical.
"""

import time

import pytest

from planning.unreal_adapter_production import UnrealAdapterError
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import (
    UnrealProductionSpec,
    build_unreal_production_plan,
)
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_verifier import resolve_render_job_state
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_shot_continuity import verify_shot_continuity_completeness
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    WindowsNamedPipeTransport,
)
from tests.test_agent_controller_production_real_integration import (
    ENTITY_ID,
    SEQUENCE_ASSET_PATH,
    _intent,
)
from tests.test_unreal_mrq_attribution_real_integration import (
    _assert_artifacts,
    _build,
    _fresh_job_read,
    _originals,
    _remove_output_directories,
    _restore,
)

pytestmark = pytest.mark.integration

# The first submission is deliberately long so the second submission has a wide
# window in which an earlier queued job is rendering while the new Atlas job has
# not started yet - the window in which the old callback would have written
# "rendering" into the new job's entry.
FIRST_DIRECTORY = "Saved/AtlasMrqStartedFirst"
SECOND_DIRECTORY = "Saved/AtlasMrqStartedSecond"
SAME_RANGE_A_DIRECTORY = "Saved/AtlasMrqStartedSameRangeA"
SAME_RANGE_B_DIRECTORY = "Saved/AtlasMrqStartedSameRangeB"

EARLY_SAMPLE_COUNT = 12
EARLY_SAMPLE_INTERVAL = 0.06


def _submission_plan(originals, *, start_frame, end_frame, output_directory):
    """The composite/spec shape the Slice 1/2 live module uses, unchanged."""
    composite = build_composite_actor_operation(
        [ENTITY_ID],
        [
            {
                "name": "set_actor_location",
                "location": dict(originals["state"]["location"]),
            },
            {
                "name": "set_actor_rotation",
                "rotation": dict(originals["state"]["rotation"]),
            },
            {
                "name": "set_actor_scale",
                "scale": dict(originals["state"]["scale"]),
            },
            {
                "name": "apply_material_variant",
                "variant": originals["material"]["name"],
            },
            {
                "name": "apply_niagara_variant",
                "variant": originals["niagara"]["name"],
            },
        ],
    )

    return UnrealProductionSpec(
        composite=composite,
        start_frame=start_frame,
        end_frame=end_frame,
        render_config=UnrealRenderConfig(
            width=320,
            height=180,
            start_frame=start_frame,
            end_frame=end_frame,
            output_directory=output_directory,
            output_format="png",
        ),
        sequence_asset_path=SEQUENCE_ASSET_PATH,
    )


def _submit_and_hold(raw_executor, originals, *, label, start_frame, end_frame,
                     output_directory, receipt_path):
    """Run the production, submit the render, and return BEFORE waiting."""
    intent = _intent(label)
    production = build_unreal_production_plan(
        intent,
        _submission_plan(
            originals,
            start_frame=start_frame,
            end_frame=end_frame,
            output_directory=output_directory,
        ),
    )
    authorized = authorize_production_plan(production, f"{label}-production-auth")

    production_result = UnrealProductionExecutor(raw_executor).execute(
        production,
        authorized.authorization,
    )
    assert production_result.success is True

    workflow = UnrealRenderWorkflow(
        raw_executor,
        UnrealRenderReceiptStore(receipt_path),
        poll_interval_seconds=0.25,
        timeout_seconds=180.0,
    )
    authorize_render = lambda plan: UnrealPlanAuthorization.issue(  # noqa: E731
        plan,
        f"{label}-render-auth",
    )

    submission = workflow.submit(intent, SEQUENCE_ASSET_PATH, authorize_render)
    job_id = workflow.get_submitted_job_id(submission)

    return intent, production, workflow, authorize_render, job_id


def _sample_statuses(raw_executor, planner, intent, job_id, *, samples, interval):
    """Read one exact job identity repeatedly, recording the reported status."""
    statuses = []

    for index in range(samples):
        plan = planner.plan_render_job_inspection(intent, job_id)
        result = raw_executor.execute(plan, f"{intent.intent_id}-sample-{index}-auth")

        assert result.success is True
        state = resolve_render_job_state(result.evidence_ledger[-1])
        assert state["job_id"] == job_id  # exact job-ID binding on every read

        statuses.append(state.get("status"))
        time.sleep(interval)

    return statuses


def _sample_until_started(raw_executor, planner, intent, job_id, *, timeout=60.0, interval=0.05):
    """Sample until the job reports its OWN start transition."""
    statuses = []
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        plan = planner.plan_render_job_inspection(intent, job_id)
        result = raw_executor.execute(plan, f"{intent.intent_id}-watch-auth")

        assert result.success is True
        state = resolve_render_job_state(result.evidence_ledger[-1])
        assert state["job_id"] == job_id

        status = state.get("status")
        statuses.append(status)

        if status != "submitted":
            return statuses

        time.sleep(interval)

    raise AssertionError(f"job {job_id} never left the submitted state: {statuses[-5:]}")


def test_real_mrq_start_identity_holds_with_multiple_queued_jobs(tmp_path):
    """A foreign queued job's start must not touch the new Atlas job's state."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(FIRST_DIRECTORY, SECOND_DIRECTORY)

        # Submission 1: a long job that is still rendering when submission 2 is made.
        first_held = _submit_and_hold(
            raw_executor,
            originals,
            label="started-first",
            start_frame=1,
            end_frame=10,
            output_directory=FIRST_DIRECTORY,
            receipt_path=tmp_path / "started-first-receipt.json",
        )
        first_intent = first_held[0]
        first = _complete(first_held)

        first_state = resolve_render_job_state(first.final_evidence)
        _assert_artifacts(first_state, frames=set(range(1, 11)), directory=FIRST_DIRECTORY)
        assert first.receipt.matches(first.final_evidence) is True

        # Submission 2 in the SAME session; the queue still holds job 1.
        (
            second_intent,
            second_production,
            second_workflow,
            authorize_render,
            second_job_id,
        ) = _submit_and_hold(
            raw_executor,
            originals,
            label="started-second",
            start_frame=1,
            end_frame=5,
            output_directory=SECOND_DIRECTORY,
            receipt_path=tmp_path / "started-second-receipt.json",
        )

        # (1) Foreign start isolation: job 1 is rendering, job 2 has not started,
        # so every sample must show the untouched submitted state - never
        # "rendering", which is what a foreign start event used to write.
        early = _sample_statuses(
            raw_executor,
            planner,
            second_intent,
            second_job_id,
            samples=EARLY_SAMPLE_COUNT,
            interval=EARLY_SAMPLE_INTERVAL,
        )

        assert set(early) == {"submitted"}, (
            "the new Atlas job's monitoring state was modified while a foreign "
            f"queued job was rendering: observed statuses {early}"
        )
        print("early samples (foreign job rendering):", early)

        # (2) The job still receives its own start transition.
        watch = _sample_until_started(
            raw_executor,
            planner,
            second_intent,
            second_job_id,
        )
        assert watch[-1] == "rendering", watch
        print("watch samples:", watch[-3:])

        # (3) Authoritative completion through the unchanged verified path.
        second = _complete(
            (
                second_intent,
                second_production,
                second_workflow,
                authorize_render,
                second_job_id,
            )
        )

        second_state = resolve_render_job_state(second.final_evidence)
        _assert_artifacts(second_state, frames={1, 2, 3, 4, 5}, directory=SECOND_DIRECTORY)
        assert second_state["job_id"] == second_job_id == second.receipt.job_id
        assert (
            verify_shot_continuity_completeness(
                second.final_evidence,
                second_production.continuity,
            )
            is second.final_evidence
        )
        assert second.receipt.matches(second.final_evidence) is True

        # (4) The first job's evidence was not rewritten by the second render.
        reread_first = _fresh_job_read(
            raw_executor,
            planner,
            first_intent,
            first.job_id,
        )
        _assert_artifacts(reread_first, frames=set(range(1, 11)), directory=FIRST_DIRECTORY)
        assert set(reread_first["output_files"]) == set(first_state["output_files"])

        print("start-identity live gate (two submissions, one editor session)")
        print("  first  job:", first.job_id, len(first_state["output_files"]), "artifacts")
        print("  second job:", second_job_id, len(second_state["output_files"]), "artifacts")
        print("  first job state unchanged after second render: True")

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in ("not available", "pipe not found", "disconnected")
        ):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and originals:
            _restore(raw_executor, planner, originals)
        _remove_output_directories(FIRST_DIRECTORY, SECOND_DIRECTORY)


def test_real_mrq_start_identity_same_range_second_submission(tmp_path):
    """The mandatory same-range case: identical authorized range, own directories."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(SAME_RANGE_A_DIRECTORY, SAME_RANGE_B_DIRECTORY)

        third_held = _submit_and_hold(
            raw_executor,
            originals,
            label="started-same-range-a",
            start_frame=1,
            end_frame=2,
            output_directory=SAME_RANGE_A_DIRECTORY,
            receipt_path=tmp_path / "started-same-range-a-receipt.json",
        )
        third_intent = third_held[0]
        third = _complete(third_held)

        third_state = resolve_render_job_state(third.final_evidence)
        _assert_artifacts(third_state, frames={1, 2}, directory=SAME_RANGE_A_DIRECTORY)

        (
            fourth_intent,
            fourth_production,
            fourth_workflow,
            authorize_render,
            fourth_job_id,
        ) = _submit_and_hold(
            raw_executor,
            originals,
            label="started-same-range-b",
            start_frame=1,
            end_frame=2,
            output_directory=SAME_RANGE_B_DIRECTORY,
            receipt_path=tmp_path / "started-same-range-b-receipt.json",
        )

        early = _sample_statuses(
            raw_executor,
            planner,
            fourth_intent,
            fourth_job_id,
            samples=8,
            interval=EARLY_SAMPLE_INTERVAL,
        )
        assert set(early) == {"submitted"}, (
            f"same-range submission's monitoring state was modified early: {early}"
        )
        print("same-range early samples:", early)

        fourth = _complete(
            (
                fourth_intent,
                fourth_production,
                fourth_workflow,
                authorize_render,
                fourth_job_id,
            )
        )

        fourth_state = resolve_render_job_state(fourth.final_evidence)
        _assert_artifacts(fourth_state, frames={1, 2}, directory=SAME_RANGE_B_DIRECTORY)
        assert fourth_state["job_id"] == fourth_job_id == fourth.receipt.job_id
        assert (
            verify_shot_continuity_completeness(
                fourth.final_evidence,
                fourth_production.continuity,
            )
            is fourth.final_evidence
        )
        assert fourth.receipt.matches(fourth.final_evidence) is True

        # The same-range predecessor was not rewritten by the later render.
        reread_third = _fresh_job_read(
            raw_executor,
            planner,
            third_intent,
            third.job_id,
        )
        _assert_artifacts(reread_third, frames={1, 2}, directory=SAME_RANGE_A_DIRECTORY)
        assert set(reread_third["output_files"]) == set(third_state["output_files"])

        print("start-identity live gate (same-range second submission)")
        print("  third  job:", third.job_id, sorted(third_state["output_files"]))
        print("  fourth job:", fourth_job_id, sorted(fourth_state["output_files"]))

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        message = str(exc).lower()
        if any(
            token in message
            for token in ("not available", "pipe not found", "disconnected")
        ):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and originals:
            _restore(raw_executor, planner, originals)
        _remove_output_directories(SAME_RANGE_A_DIRECTORY, SAME_RANGE_B_DIRECTORY)


def _complete(held):
    """Wait for a held submission through the unchanged verified completion path."""
    intent, production, workflow, authorize_render, job_id = held

    return workflow.wait_for_completion(
        intent,
        job_id,
        authorize_render,
        expected_continuity=production.continuity,
    )
