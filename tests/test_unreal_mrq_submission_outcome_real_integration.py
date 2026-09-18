"""Live UE 5.6.1 gate: submission outcome propagation (accepted / rejected).

ONE editor session. Proves against the real engine that:

A. an idle editor accepts a submission and observes the supplied executor as the
   active executor (the accepted response keeps the existing job identity and
   status contract, and the job genuinely reaches its own ``rendering`` state);
B. a submission attempted while another render is active produces an explicit
   rejected/ambiguous Atlas result instead of the 300 s poll timeout -
   measured, with the elapsed time asserted far below the timeout and the error
   text asserted not to be a timeout;
C. no receipt is produced for the rejected submission;
D. accepted submissions in the same non-empty-queue session still attribute
   artifacts exactly (multi-job queue);
E. the same-range case still isolates artifacts by directory;
F. exact job identity and continuity verification remain unchanged for accepted
   jobs, and the rejected submission never becomes a pollable Atlas job.

Helpers are imported from the Slice 1/2 and Slice D live modules so those modules
stay byte-identical.
"""

import time
from pathlib import Path

import pytest

from planning.unreal_adapter_production import UnrealAdapterError
from planning.unreal_plan_executor import UnrealPlanExecutionError
from planning.unreal_render_job_verifier import resolve_render_job_state
from planning.unreal_shot_continuity import verify_shot_continuity_completeness
from planning.unreal_task_planner import UnrealTaskPlanner
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportError,
    WindowsNamedPipeTransport,
)
from tests.test_unreal_mrq_attribution_real_integration import (
    _assert_artifacts,
    _build,
    _fresh_job_read,
    _originals,
    _remove_output_directories,
    _restore,
)
from tests.test_unreal_mrq_started_identity_real_integration import (
    _complete,
    _sample_statuses,
    _sample_until_started,
    _submit_and_hold,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.integration

# A long first render keeps the editor rendering while the second submission is
# attempted (the refusal only exists while a render is genuinely active).
LONG_DIRECTORY = "Saved/AtlasMrqOutcomeLong"
REJECTED_DIRECTORY = "Saved/AtlasMrqOutcomeRejected"
ACCEPTED_C_DIRECTORY = "Saved/AtlasMrqOutcomeAcceptedC"
ACCEPTED_D_DIRECTORY = "Saved/AtlasMrqOutcomeAcceptedD"

LONG_START_FRAME = 1
LONG_END_FRAME = 24

REJECTED_MARKERS = ("render submission rejected:", "render submission outcome ambiguous:")
TIMEOUT_MARKER = "did not complete within"

ENGINE_LOG = (
    REPO_ROOT
    / "unreal/AtlasUnrealHarness/Saved/Logs/AtlasUnrealHarness.log"
)

# Harness-only synchronisation: the engine releases the active executor a moment
# after the last job reports finished, and the executor-finished line is printed
# inside that same release path. The wait below uses it purely to establish the
# "editor is idle again" precondition between the two tests; no product decision
# anywhere in this slice reads a log (see the design review's finding F3).
def _executor_finished_count() -> int:
    return ENGINE_LOG.read_text(encoding="utf-8", errors="replace").count(
        "MoviePipelineLinearExecutorBase finished"
    )


def _wait_for_executor_release(previous: int, timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if _executor_finished_count() > previous:
            return True
        time.sleep(0.25)

    return False


def test_real_mrq_submission_outcome_is_propagated(tmp_path):
    """Scenarios A, B, C: accepted while idle, rejected while rendering, no receipt."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()
    rejected_receipt = tmp_path / "rejected-receipt.json"

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(LONG_DIRECTORY, REJECTED_DIRECTORY)

        # ── A. idle editor: the submission is accepted and the job is pollable ──
        long_held = _submit_and_hold(
            raw_executor,
            originals,
            label="outcome-long",
            start_frame=LONG_START_FRAME,
            end_frame=LONG_END_FRAME,
            output_directory=LONG_DIRECTORY,
            receipt_path=tmp_path / "long-receipt.json",
        )

        long_intent, _, _, _, long_job_id = long_held

        # the accepted response keeps the existing identity/status contract
        accepted_state = _fresh_job_read(raw_executor, planner, long_intent, long_job_id)
        assert accepted_state["job_id"] == long_job_id
        assert accepted_state["status"] in {"submitted", "rendering"}

        print("accepted submission job id:", long_job_id)

        # the supplied executor is genuinely the engine's active executor: the job
        # reaches its OWN rendering state (Slice D property, engine-side effect)
        watch = _sample_until_started(raw_executor, planner, long_intent, long_job_id)
        assert watch[-1] == "rendering", watch
        print("long render reached rendering:", watch[-3:])

        # ── B. submission while a render is active: explicit rejection ──────────
        started = time.monotonic()
        raised = False
        message = ""

        try:
            _submit_and_hold(
                raw_executor,
                originals,
                label="outcome-rejected",
                start_frame=1,
                end_frame=2,
                output_directory=REJECTED_DIRECTORY,
                receipt_path=rejected_receipt,
            )
        except UnrealPlanExecutionError as exc:
            raised = True
            message = str(exc)

        elapsed = time.monotonic() - started

        assert raised is True, (
            "the second submission was accepted although a render was active: "
            "the rejection scenario was not exercised"
        )
        assert any(marker in message for marker in REJECTED_MARKERS), message
        assert TIMEOUT_MARKER not in message, message
        assert elapsed < 60.0, (
            f"the rejection took {elapsed:.1f}s: it must not consume the render timeout"
        )

        print(f"rejected submission surfaced in {elapsed:.2f}s: {message.splitlines()[0][:160]}")

        # ── C. no receipt for the rejected submission ───────────────────────────
        assert not rejected_receipt.exists()

        # ── F. the accepted job is unaffected and still completes with exact evidence ──
        releases_before = _executor_finished_count()

        long_result = _complete(long_held)
        long_state = resolve_render_job_state(long_result.final_evidence)

        _assert_artifacts(
            long_state,
            frames=set(range(LONG_START_FRAME, LONG_END_FRAME + 1)),
            directory=LONG_DIRECTORY,
        )
        assert long_state["job_id"] == long_job_id == long_result.receipt.job_id
        assert (
            verify_shot_continuity_completeness(
                long_result.final_evidence,
                long_held[1].continuity,
            )
            is long_result.final_evidence
        )
        assert long_result.receipt.matches(long_result.final_evidence) is True

        # harness precondition for the following test: the editor is idle again
        assert _wait_for_executor_release(releases_before) is True, (
            "the engine did not release the active executor within 120s"
        )

        print("accepted job artifacts:", len(long_state["output_files"]))

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        msg = str(exc).lower()
        if any(token in msg for token in ("not available", "pipe not found", "disconnected")):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in msg:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and originals:
            _restore(raw_executor, planner, originals)
        _remove_output_directories(LONG_DIRECTORY, REJECTED_DIRECTORY)


def test_real_mrq_accepted_submissions_still_attribute_exactly(tmp_path):
    """Scenarios D, E, F: multi-job queue and same-range attribution stay exact."""
    adapter = None
    originals = {}
    planner = UnrealTaskPlanner()

    try:
        adapter, raw_executor = _build(WindowsNamedPipeTransport())
        originals = _originals(raw_executor, planner)

        _remove_output_directories(ACCEPTED_C_DIRECTORY, ACCEPTED_D_DIRECTORY)

        # D: accepted in a session whose queue already holds earlier jobs
        c_held = _submit_and_hold(
            raw_executor,
            originals,
            label="outcome-accepted-c",
            start_frame=1,
            end_frame=2,
            output_directory=ACCEPTED_C_DIRECTORY,
            receipt_path=tmp_path / "accepted-c-receipt.json",
        )

        c_intent = c_held[0]
        c_job_id = c_held[4]

        early = _sample_statuses(
            raw_executor,
            planner,
            c_intent,
            c_job_id,
            samples=4,
            interval=0.06,
        )
        assert set(early) <= {"submitted", "rendering"}, early

        c_result = _complete(c_held)
        c_state = resolve_render_job_state(c_result.final_evidence)

        _assert_artifacts(c_state, frames={1, 2}, directory=ACCEPTED_C_DIRECTORY)
        assert c_state["job_id"] == c_job_id == c_result.receipt.job_id
        assert c_result.receipt.matches(c_result.final_evidence) is True

        # E: the mandatory same-range case, different authorized directory
        d_held = _submit_and_hold(
            raw_executor,
            originals,
            label="outcome-accepted-d",
            start_frame=1,
            end_frame=2,
            output_directory=ACCEPTED_D_DIRECTORY,
            receipt_path=tmp_path / "accepted-d-receipt.json",
        )

        d_result = _complete(d_held)
        d_state = resolve_render_job_state(d_result.final_evidence)

        _assert_artifacts(d_state, frames={1, 2}, directory=ACCEPTED_D_DIRECTORY)
        assert d_state["job_id"] == d_held[4] == d_result.receipt.job_id
        assert d_result.receipt.matches(d_result.final_evidence) is True
        assert set(d_state["output_files"]).isdisjoint(set(c_state["output_files"]))

        # F: the earlier accepted job was not rewritten by the later render
        reread_c = _fresh_job_read(raw_executor, planner, c_intent, c_job_id)
        _assert_artifacts(reread_c, frames={1, 2}, directory=ACCEPTED_C_DIRECTORY)
        assert set(reread_c["output_files"]) == set(c_state["output_files"])

        # receipts exist only for accepted submissions
        receipts = sorted(path.name for path in tmp_path.glob("*.json"))
        assert receipts == ["accepted-c-receipt.json", "accepted-d-receipt.json"], receipts

        print("accepted C job:", c_job_id, sorted(c_state["output_files"]))
        print("accepted D job:", d_held[4], sorted(d_state["output_files"]))
        print("receipts present:", receipts)

    except (NamedPipeTransportError, UnrealAdapterError) as exc:
        msg = str(exc).lower()
        if any(token in msg for token in ("not available", "pipe not found", "disconnected")):
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in msg:
            pytest.skip("Required Unreal production fixture is unavailable")
        raise

    finally:
        if adapter is not None and originals:
            _restore(raw_executor, planner, originals)
        _remove_output_directories(ACCEPTED_C_DIRECTORY, ACCEPTED_D_DIRECTORY)
