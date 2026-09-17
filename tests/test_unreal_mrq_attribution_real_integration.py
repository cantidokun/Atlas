"""Live UE 5.6.1 gate: MRQ artifact attribution across submissions in ONE session.

This module is the integration half of the MRQ artifact-attribution milestone and
it deliberately does NOT use a fresh editor session per submission. The engine's
Movie Render Pipeline executor renders every job already present in the queue, so
the second submission in the same editor session runs with a queue that still
contains the first job - exactly the condition under which the previous
implementation attributed the earlier job's artifacts to the new job.

What is proven against the real engine:

    submission 1 (authorized 1-2) and submission 2 (authorized 1-5) in ONE session
      -> submission 2's final evidence carries exactly its own artifacts
      -> submission 1's evidence is unchanged after submission 2 finished
      -> exact job identity remains bound on both
      -> the continuity receipt stays coherent with the fresh evidence

    submission 3 (authorized 1-2) and submission 4 (authorized 1-2) in ONE session
      -> the SAME-RANGE case, where frame-set-only verification previously
         accepted another job's artifact paths

    every observed artifact is inside its own authorized output directory

The tracked render-configuration fixture is restored in ``finally`` and the
disposable output directories are removed; tracked assets are verified
byte-identical outside the test.
"""

import shutil
from pathlib import Path

import pytest

from planning.unreal_adapter_production import UnrealAdapterError, UnrealAdapterProduction
from planning.unreal_agent import UnrealCapability
from planning.unreal_composite_operation import build_composite_actor_operation
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_production_executor import UnrealProductionExecutor
from planning.unreal_production_operation import UnrealProductionSpec, build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_workflow import UnrealProductionWorkflow
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_verifier import resolve_render_job_state
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_render_workflow import UnrealRenderWorkflow
from planning.unreal_shot_continuity import (
    canonicalize_artifact_path,
    is_inside_directory,
    resolve_artifact_frame_number,
    verify_shot_continuity_completeness,
)
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    WindowsNamedPipeTransport,
)
from tests.test_agent_controller_production_real_integration import (
    ENTITY_ID,
    SEQUENCE_ASSET_PATH,
    _intent,
    _read_variant_plan,
    _render_inspection_plan,
    _sequencer_inspection_plan,
    _state,
    _variant,
)

pytestmark = pytest.mark.integration

FIRST_DIRECTORY = "Saved/AtlasMrqAttributionFirst"
SECOND_DIRECTORY = "Saved/AtlasMrqAttributionSecond"
SAME_RANGE_FIRST_DIRECTORY = "Saved/AtlasMrqAttributionSameRangeA"
SAME_RANGE_SECOND_DIRECTORY = "Saved/AtlasMrqAttributionSameRangeB"


def _build(transport):
    adapter = UnrealAdapterProduction(transport, "mrq-attribution-live-gate")
    raw_executor = UnrealPlanExecutor(adapter)

    return adapter, raw_executor


def _originals(raw_executor, planner):
    """Capture the live fixture values this gate will write again unchanged."""
    originals = {}

    originals["state"] = _state(
        raw_executor.execute(
            planner.plan_inspection(_intent("attribution-original")),
            "attribution-original-auth",
        ).evidence_ledger[0]
    )
    originals["sequencer"] = dict(
        _state(
            raw_executor.execute(
                _sequencer_inspection_plan(_intent("attribution-original-sequencer")),
                "attribution-original-sequencer-auth",
            ).evidence_ledger[0]
        )["sequencer"]
    )
    originals["render"] = dict(
        _state(
            raw_executor.execute(
                _render_inspection_plan(_intent("attribution-original-render")),
                "attribution-original-render-auth",
            ).evidence_ledger[0]
        )["render"]
    )
    originals["material"] = _variant(
        raw_executor.execute(
            _read_variant_plan(
                "attribution-original-material",
                UnrealCapability.MATERIAL,
                "inspect_material_state",
            ),
            "attribution-original-material-auth",
        ).evidence_ledger[0],
        "material",
    )
    originals["niagara"] = _variant(
        raw_executor.execute(
            _read_variant_plan(
                "attribution-original-niagara",
                UnrealCapability.NIAGARA,
                "inspect_niagara_state",
            ),
            "attribution-original-niagara-auth",
        ).evidence_ledger[0],
        "niagara",
    )

    return originals


def _submit_and_complete(
    raw_executor,
    planner,
    originals,
    *,
    label,
    start_frame,
    end_frame,
    output_directory,
    receipt_path,
):
    """Run one authorized production + render submission to verified completion."""
    intent = _intent(label)

    # The composite writes the values the fixture already holds, so the actor
    # fixture is never left mutated by this gate.
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

    production = build_unreal_production_plan(
        intent,
        UnrealProductionSpec(
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
        ),
    )
    authorized = authorize_production_plan(production, f"{label}-production-auth")

    workflow = UnrealProductionWorkflow(
        UnrealProductionExecutor(raw_executor),
        UnrealRenderWorkflow(
            raw_executor,
            UnrealRenderReceiptStore(receipt_path),
            poll_interval_seconds=0.25,
            timeout_seconds=180.0,
        ),
    )

    result = workflow.run(
        production,
        authorized.authorization,
        intent,
        SEQUENCE_ASSET_PATH,
        lambda plan: UnrealPlanAuthorization.issue(plan, f"{label}-render-auth"),
    )

    return intent, production, result


def _fresh_job_read(raw_executor, planner, intent, job_id):
    """Read one exact job identity again, independently, in the same session."""
    plan = planner.plan_render_job_inspection(intent, job_id)
    result = raw_executor.execute(plan, f"{intent.intent_id}-fresh-read-auth")

    assert result.success is True
    assert result.evidence_ledger

    return resolve_render_job_state(result.evidence_ledger[-1])


def _assert_artifacts(state, *, frames, directory):
    """Assert exact frame coverage AND that every artifact is this job's own."""
    files = [str(value) for value in state["output_files"] if str(value).strip()]

    assert files, "render job evidence reported no artifacts"

    canonical_directory = canonicalize_artifact_path(directory)

    for value in files:
        artifact = canonicalize_artifact_path(value)

        assert is_inside_directory(artifact, canonical_directory), (
            f"artifact outside its own authorized directory: {value!r} "
            f"(directory {directory!r})"
        )

    parsed = [resolve_artifact_frame_number(value) for value in files]

    assert len(set(files)) == len(parsed), f"duplicate artifact paths: {files}"
    assert len(set(parsed)) == len(parsed), f"duplicate frame numbers: {sorted(parsed)}"
    assert set(parsed) == set(frames), (
        f"observed frames {sorted(parsed)} != authorized frames {sorted(frames)}"
    )


def _restore(raw_executor, planner, originals):
    restore_intent = _intent("attribution-restore")

    raw_executor.execute(
        planner.plan_sequencer_playback_range(
            restore_intent,
            int(originals["sequencer"]["start_frame"]),
            int(originals["sequencer"]["end_frame"]),
        ),
        "attribution-restore-sequencer-auth",
    )
    raw_executor.execute(
        planner.plan_render_configuration(
            restore_intent,
            {
                "width": originals["render"]["width"],
                "height": originals["render"]["height"],
                "start_frame": originals["render"]["start_frame"],
                "end_frame": originals["render"]["end_frame"],
                "output_directory": originals["render"]["output_directory"],
                "output_format": originals["render"]["output_format"],
            },
        ),
        "attribution-restore-render-auth",
    )


def _remove_output_directories(*directories):
    from planning.unreal_render_contract import UNREAL_PROJECT_ROOT

    for directory in directories:
        shutil.rmtree(Path(UNREAL_PROJECT_ROOT) / directory, ignore_errors=True)


def test_real_mrq_attribution_survives_two_submissions_in_one_editor_session(tmp_path):
    """Two submissions, one editor session: artifacts stay job-scoped."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(FIRST_DIRECTORY, SECOND_DIRECTORY)

        first_intent, _, first = _submit_and_complete(
            raw_executor,
            planner,
            originals,
            label="attribution-first",
            start_frame=1,
            end_frame=2,
            output_directory=FIRST_DIRECTORY,
            receipt_path=tmp_path / "attribution-first-receipt.json",
        )

        first_state = resolve_render_job_state(first.render.final_evidence)
        _assert_artifacts(first_state, frames={1, 2}, directory=FIRST_DIRECTORY)
        assert first.render.receipt.matches(first.render.final_evidence) is True

        # Second submission in the SAME editor session: the queue still holds the
        # first job, so the executor renders both.
        second_intent, second_production, second = _submit_and_complete(
            raw_executor,
            planner,
            originals,
            label="attribution-second",
            start_frame=1,
            end_frame=5,
            output_directory=SECOND_DIRECTORY,
            receipt_path=tmp_path / "attribution-second-receipt.json",
        )

        second_state = resolve_render_job_state(second.render.final_evidence)

        # (1) the second job reports exactly its own five artifacts, and not one
        #     of the first job's paths leaked into its evidence.
        _assert_artifacts(second_state, frames={1, 2, 3, 4, 5}, directory=SECOND_DIRECTORY)

        canonical_first = canonicalize_artifact_path(FIRST_DIRECTORY)
        inherited = [
            value
            for value in second_state["output_files"]
            if is_inside_directory(canonicalize_artifact_path(value), canonical_first)
        ]
        assert inherited == [], f"second job inherited first job artifacts: {inherited}"

        # (2) exact job identity remains bound on the second submission.
        assert (
            second_state["job_id"]
            == second.render.job_id
            == second.render.receipt.job_id
        )
        assert second_state["job_id"] != first.render.job_id

        # (3) fresh-evidence verification and receipt coherence are unchanged.
        assert second.render.final_evidence.verified is True
        assert (
            verify_shot_continuity_completeness(
                second.render.final_evidence,
                second_production.continuity,
            )
            is second.render.final_evidence
        )
        assert second.render.receipt.matches(second.render.final_evidence) is True

        # (4) the first job's state was NOT rewritten by the second render.
        reread = _fresh_job_read(raw_executor, planner, first_intent, first.render.job_id)
        _assert_artifacts(reread, frames={1, 2}, directory=FIRST_DIRECTORY)
        assert reread["job_id"] == first.render.job_id
        assert set(reread["output_files"]) == set(first_state["output_files"])

        print("MRQ attribution live gate (two submissions, one editor session)")
        print("  first  job:", first.render.job_id, sorted(first_state["output_files"]))
        print("  second job:", second.render.job_id, sorted(second_state["output_files"]))
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


def test_real_mrq_attribution_same_range_second_submission_does_not_inherit(tmp_path):
    """The mandatory same-range case: frame-set-only verification used to pass."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(
            SAME_RANGE_FIRST_DIRECTORY,
            SAME_RANGE_SECOND_DIRECTORY,
        )

        third_intent, _, third = _submit_and_complete(
            raw_executor,
            planner,
            originals,
            label="attribution-same-range-first",
            start_frame=1,
            end_frame=2,
            output_directory=SAME_RANGE_FIRST_DIRECTORY,
            receipt_path=tmp_path / "attribution-same-range-first-receipt.json",
        )

        third_state = resolve_render_job_state(third.render.final_evidence)
        _assert_artifacts(
            third_state,
            frames={1, 2},
            directory=SAME_RANGE_FIRST_DIRECTORY,
        )

        # Same authorized frame range, different directory: a frame-set-only rule
        # cannot tell the two jobs apart.
        fourth_intent, fourth_production, fourth = _submit_and_complete(
            raw_executor,
            planner,
            originals,
            label="attribution-same-range-second",
            start_frame=1,
            end_frame=2,
            output_directory=SAME_RANGE_SECOND_DIRECTORY,
            receipt_path=tmp_path / "attribution-same-range-second-receipt.json",
        )

        fourth_state = resolve_render_job_state(fourth.render.final_evidence)
        _assert_artifacts(
            fourth_state,
            frames={1, 2},
            directory=SAME_RANGE_SECOND_DIRECTORY,
        )

        canonical_third = canonicalize_artifact_path(SAME_RANGE_FIRST_DIRECTORY)
        inherited = [
            value
            for value in fourth_state["output_files"]
            if is_inside_directory(canonicalize_artifact_path(value), canonical_third)
        ]
        assert inherited == [], f"same-range job inherited artifacts: {inherited}"

        assert (
            fourth_state["job_id"]
            == fourth.render.job_id
            == fourth.render.receipt.job_id
        )
        assert fourth_state["job_id"] != third.render.job_id
        assert fourth.render.receipt.matches(fourth.render.final_evidence) is True
        assert (
            verify_shot_continuity_completeness(
                fourth.render.final_evidence,
                fourth_production.continuity,
            )
            is fourth.render.final_evidence
        )

        reread = _fresh_job_read(raw_executor, planner, third_intent, third.render.job_id)
        _assert_artifacts(
            reread,
            frames={1, 2},
            directory=SAME_RANGE_FIRST_DIRECTORY,
        )
        assert set(reread["output_files"]) == set(third_state["output_files"])

        print("MRQ attribution live gate (same-range second submission)")
        print("  third  job:", third.render.job_id, sorted(third_state["output_files"]))
        print("  fourth job:", fourth.render.job_id, sorted(fourth_state["output_files"]))

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
        _remove_output_directories(
            SAME_RANGE_FIRST_DIRECTORY,
            SAME_RANGE_SECOND_DIRECTORY,
        )
