"""Deterministic tests for the authoritative Unreal render-job verification boundary."""

import pytest
from pathlib import Path

from planning.unreal_evidence_contract import UnrealEvidence, verify_render_job_evidence
from planning.unreal_render_receipt import UnrealRenderReceipt


def _valid_observed_state(output_file: Path) -> dict:
    return {
        "job_id": "job-stage17-001",
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(output_file)],
    }


def test_successful_render_job_verification(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"\x89PNG\r\n\x1a\nfake-image-data")

    state = _valid_observed_state(output_file)
    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="real-unreal-5.6-live-boundary",
    )

    assert isinstance(evidence, UnrealEvidence)
    assert evidence.verified is True
    assert evidence.operation_name == "inspect_render_job"
    assert evidence.entity_ids == ("FIELD_SURFACE",)
    assert evidence.observed_state["job_id"] == "job-stage17-001"
    assert evidence.observed_state["output_files"] == (str(output_file),)

    # Confirm that UnrealRenderReceipt.issue() accepts this verified evidence
    receipt = UnrealRenderReceipt.issue(evidence)
    assert receipt.job_id == "job-stage17-001"
    assert receipt.sequence_asset_path == "/Game/AtlasTest/AtlasSequencerFixtureSequence"
    assert receipt.evidence_digest


def test_unfinished_job_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")

    # Status not finished/completed
    state = _valid_observed_state(output_file)
    state["status"] = "rendering"
    with pytest.raises(ValueError, match="status must be 'completed' or 'finished'"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    # Finished flag is False
    state2 = _valid_observed_state(output_file)
    state2["finished"] = False
    with pytest.raises(ValueError, match="finished flag must be True"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state2,
            source="test",
        )


def test_failed_job_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")

    # success is False
    state = _valid_observed_state(output_file)
    state["success"] = False
    with pytest.raises(ValueError, match="success flag must be True"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    # failed is True
    state2 = _valid_observed_state(output_file)
    state2["failed"] = True
    with pytest.raises(ValueError, match="failed flag must be False"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state2,
            source="test",
        )


def test_missing_output_file_rejection(tmp_path: Path):
    non_existent = tmp_path / "non_existent.png"
    state = _valid_observed_state(non_existent)

    with pytest.raises(FileNotFoundError, match="does not exist on disk"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )


def test_empty_output_files_sequence_rejection():
    state = {
        "job_id": "job-stage17-001",
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [],
    }
    with pytest.raises(ValueError, match="output_files must not be empty"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )


def test_zero_byte_output_file_rejection(tmp_path: Path):
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")

    state = _valid_observed_state(empty_file)
    with pytest.raises(ValueError, match="zero or negative size"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )


def test_wrong_operation_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")
    state = _valid_observed_state(output_file)

    with pytest.raises(ValueError, match="operation_name == 'inspect_render_job'"):
        verify_render_job_evidence(
            operation_name="submit_render",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )


def test_wrong_entity_ids_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")
    state = _valid_observed_state(output_file)

    with pytest.raises(ValueError, match="entity_ids cannot be empty"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=(),
            observed_state=state,
            source="test",
        )

    with pytest.raises(ValueError, match="entity_id must be a non-empty canonical string"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("",),
            observed_state=state,
            source="test",
        )


def test_malformed_job_identity_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")

    state = _valid_observed_state(output_file)
    state["job_id"] = "   "
    with pytest.raises(ValueError, match="job_id must be a non-empty canonical string"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    state2 = _valid_observed_state(output_file)
    state2["sequence_asset_path"] = ""
    with pytest.raises(ValueError, match="sequence_asset_path must be a non-empty canonical string"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state2,
            source="test",
        )


def test_callers_cannot_obtain_verified_evidence_on_any_failure(tmp_path: Path):
    # Output file does not exist
    missing_file = tmp_path / "does_not_exist.png"
    state = _valid_observed_state(missing_file)

    with pytest.raises(Exception):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )
