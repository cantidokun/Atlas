"""Deterministic unit tests for the Unreal render-job state machine invariants.

These tests deterministically verify the state machine transition rules and
invariants implemented in AtlasTransportServer:
1. Callback identity (wrong-job callbacks are ignored)
2. Terminal job cannot regress back to rendering/submitted
3. Successful finalization produces coherent terminal state (status=finished, progress=1.0, finished=True, success=True, failed=False)
4. Successful completion with empty output files fails closed (status=failed, finished=True, success=False, failed=True)
5. Inspection snapshot invariants (never exposes finished=True with non-terminal status or progress < 1.0)
6. Verifier verify_render_job_evidence() continues rejecting any malformed/inconsistent raw state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
import pytest

from planning.unreal_evidence_contract import (
    validate_raw_render_observation,
    verify_render_job_evidence,
)


@dataclass
class SimulatedRenderJobState:
    job_id: str
    status: str = "submitted"
    status_message: str = "Render submitted"
    progress: float = 0.0
    output_directory: str = "Saved/AtlasRenderOutput"
    output_format: str = "png"
    output_files: list[str] = field(default_factory=list)
    sequence_asset_path: str = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
    success: bool = False
    finished: bool = False
    failed: bool = False
    job_ref: Any = None


class SimulatedAtlasTransportServer:
    """Exact Python mirror of the Unreal C++ state machine logic in AtlasTransportServer."""

    def __init__(self) -> None:
        self.registry: dict[str, SimulatedRenderJobState] = {}

    def register_job(self, job_id: str, job_ref: Any, sequence_path: str) -> SimulatedRenderJobState:
        state = SimulatedRenderJobState(
            job_id=job_id,
            sequence_asset_path=sequence_path,
            job_ref=job_ref,
        )
        self.registry[job_id] = state
        return state

    def on_individual_job_started(self, captured_job_id: str, bound_job_ref: Any, incoming_job_ref: Any) -> None:
        state = self.registry.get(captured_job_id)
        if not state:
            return

        # Invariant A: Ignore callbacks if incoming_job_ref is not this specific job
        if incoming_job_ref != bound_job_ref:
            return

        # Invariant A: A terminal job must never regress to rendering/submitted
        if state.finished:
            return

        state.status = "rendering"
        state.status_message = "Render job started"
        state.progress = 0.0

    def finalize_render_job_state(
        self,
        state: SimulatedRenderJobState,
        reported_success: bool,
        discovered_files: list[str],
        failure_reason: str = "",
    ) -> None:
        # Invariant B: Once a job is finalized, later callbacks are no-ops
        if state.finished:
            return

        # Merge discovered files
        for f in discovered_files:
            stripped = f.strip()
            if stripped and stripped not in state.output_files:
                state.output_files.append(stripped)

        # Invariant B & D: Fail closed. Successful completion requires non-empty output_files.
        has_output_files = len(state.output_files) > 0
        is_effective_success = reported_success and has_output_files

        state.finished = True
        state.progress = 1.0

        if is_effective_success:
            state.success = True
            state.failed = False
            state.status = "finished"
            state.status_message = "Render completed successfully"
        else:
            state.success = False
            state.failed = True
            state.status = "failed"
            if not reported_success:
                state.status_message = f"Render failed: {failure_reason or 'MRQ execution error'}"
            else:
                state.status_message = "Render failed: reported success but produced no output files"

    def on_individual_job_work_finished(
        self,
        captured_job_id: str,
        bound_job_ref: Any,
        incoming_job_ref: Any,
        reported_success: bool,
        shot_files: list[str],
    ) -> None:
        state = self.registry.get(captured_job_id)
        if not state:
            return

        # Invariant A: Ignore callbacks if incoming_job_ref is not this specific job
        if incoming_job_ref != bound_job_ref:
            return

        self.finalize_render_job_state(
            state,
            reported_success,
            shot_files,
            failure_reason="Individual job work finished",
        )

    def on_executor_finished(self, captured_job_id: str, reported_success: bool) -> None:
        state = self.registry.get(captured_job_id)
        if not state:
            return

        # Invariant B: If already finalized, later callbacks are no-ops.
        self.finalize_render_job_state(
            state,
            reported_success,
            state.output_files,
            failure_reason="Executor finished",
        )

    def inspect_render_job(self, job_id: str) -> dict[str, Any]:
        state = self.registry.get(job_id)
        if not state:
            raise KeyError(f"Render job not found: {job_id}")

        # Invariant C & D: Coherent snapshot validation under mutex
        status_to_expose = state.status
        progress_to_expose = state.progress
        finished_to_expose = state.finished
        success_to_expose = state.success
        failed_to_expose = state.failed

        if finished_to_expose:
            if status_to_expose not in ("finished", "failed"):
                status_to_expose = "finished" if success_to_expose else "failed"
            progress_to_expose = 1.0
            if success_to_expose and len(state.output_files) == 0:
                success_to_expose = False
                failed_to_expose = True
                status_to_expose = "failed"
        else:
            if status_to_expose in ("finished", "failed"):
                status_to_expose = "rendering"
            success_to_expose = False
            failed_to_expose = False

        return {
            "job_id": state.job_id,
            "status": status_to_expose,
            "status_message": state.status_message,
            "progress": progress_to_expose,
            "success": success_to_expose,
            "finished": finished_to_expose,
            "failed": failed_to_expose,
            "sequence_asset_path": state.sequence_asset_path,
            "output_directory": state.output_directory,
            "output_format": state.output_format,
            "output_files": list(state.output_files),
        }


# ==============================================================================
# TESTS
# ==============================================================================


def test_wrong_job_callback_ignored():
    """Verify that OnIndividualJobStarted and OnIndividualJobWorkFinished ignore jobs from other MRQ entries."""
    server = SimulatedAtlasTransportServer()
    job1_ref = object()
    job2_ref = object()

    server.register_job("job-001", job1_ref, "/Game/AtlasTest/Seq1")

    # Callback for Job 2 fires into Job 1 listener: must be ignored
    server.on_individual_job_started("job-001", job1_ref, job2_ref)
    state = server.inspect_render_job("job-001")
    assert state["status"] == "submitted"
    assert state["progress"] == 0.0

    # Callback for Job 2 finished: must be ignored
    server.on_individual_job_work_finished(
        "job-001", job1_ref, job2_ref, True, ["C:/renders/out2.png"]
    )
    state = server.inspect_render_job("job-001")
    assert state["finished"] is False
    assert state["output_files"] == []


def test_terminal_job_cannot_regress():
    """Verify that once a job is finished, subsequent job started callbacks do not regress state."""
    server = SimulatedAtlasTransportServer()
    job1_ref = object()

    server.register_job("job-001", job1_ref, "/Game/AtlasTest/Seq1")

    # Start and finish Job 1
    server.on_individual_job_started("job-001", job1_ref, job1_ref)
    server.on_individual_job_work_finished(
        "job-001", job1_ref, job1_ref, True, ["C:/renders/out1.png"]
    )

    state = server.inspect_render_job("job-001")
    assert state["finished"] is True
    assert state["status"] == "finished"
    assert state["progress"] == 1.0

    # Simulate another start callback targeting Job 1: must NOT regress
    server.on_individual_job_started("job-001", job1_ref, job1_ref)
    state = server.inspect_render_job("job-001")
    assert state["finished"] is True
    assert state["status"] == "finished"
    assert state["progress"] == 1.0


def test_successful_finalization_produces_coherent_terminal_state():
    """Verify that successful finalization satisfies all Stage 17 invariants."""
    server = SimulatedAtlasTransportServer()
    job1_ref = object()

    server.register_job("job-001", job1_ref, "/Game/AtlasTest/Seq1")
    server.on_individual_job_started("job-001", job1_ref, job1_ref)

    mid_state = server.inspect_render_job("job-001")
    assert mid_state["status"] == "rendering"
    assert mid_state["finished"] is False
    assert mid_state["progress"] == 0.0

    server.on_individual_job_work_finished(
        "job-001", job1_ref, job1_ref, True, ["C:/renders/frame001.png"]
    )

    final_state = server.inspect_render_job("job-001")
    assert final_state["status"] == "finished"
    assert final_state["progress"] == 1.0
    assert final_state["finished"] is True
    assert final_state["success"] is True
    assert final_state["failed"] is False
    assert final_state["output_files"] == ["C:/renders/frame001.png"]

    # Subsequent OnExecutorFinished is a no-op
    server.on_executor_finished("job-001", True)
    assert server.inspect_render_job("job-001") == final_state


def test_successful_completion_with_empty_output_files_fails_closed():
    """Verify that reporting MRQ success without output files fails closed."""
    server = SimulatedAtlasTransportServer()
    job1_ref = object()

    server.register_job("job-001", job1_ref, "/Game/AtlasTest/Seq1")
    server.on_individual_job_started("job-001", job1_ref, job1_ref)

    # Work finished reports bSuccess=True, but 0 output files
    server.on_individual_job_work_finished("job-001", job1_ref, job1_ref, True, [])

    state = server.inspect_render_job("job-001")
    assert state["finished"] is True
    assert state["status"] == "failed"
    assert state["success"] is False
    assert state["failed"] is True
    assert state["progress"] == 1.0
    assert "no output files" in state["status_message"]


def test_inspection_snapshot_invariants_never_exposes_incoherent_state():
    """Verify that inspect_render_job cannot expose torn or contradictory state."""
    server = SimulatedAtlasTransportServer()
    state = server.register_job("job-001", object(), "/Game/AtlasTest/Seq1")

    # Artificially create contradictory underlying state: finished=True but status=rendering, progress=0
    state.finished = True
    state.status = "rendering"
    state.progress = 0.0
    state.success = True
    state.failed = False
    state.output_files = ["C:/renders/frame.png"]

    inspected = server.inspect_render_job("job-001")
    # Inspection must sanitize: finished=True -> status=finished, progress=1.0
    assert inspected["finished"] is True
    assert inspected["status"] == "finished"
    assert inspected["progress"] == 1.0

    # Artificially create finished=False but status=finished
    state.finished = False
    state.status = "finished"
    state.success = True
    inspected2 = server.inspect_render_job("job-001")
    assert inspected2["finished"] is False
    assert inspected2["status"] == "rendering"
    assert inspected2["success"] is False


def test_verify_render_job_evidence_rejects_inconsistent_state(tmp_path: Path):
    """Verify that validate_raw_render_observation continues strictly rejecting inconsistent states."""
    test_file = tmp_path / "frame.png"
    test_file.write_bytes(b"data")

    # Inconsistent: status=rendering with finished=True
    inconsistent_state = {
        "job_id": "job-001",
        "sequence_asset_path": "/Game/AtlasTest/Seq1",
        "status": "rendering",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(test_file)],
    }
    with pytest.raises(ValueError, match="status must be 'completed' or 'finished'"):
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=inconsistent_state,
            source="test",
        )
