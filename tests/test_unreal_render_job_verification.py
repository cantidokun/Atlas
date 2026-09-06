"""Deterministic tests for the authoritative Unreal render-job verification boundary."""

import pytest
from pathlib import Path

from planning.unreal_evidence_contract import (
    UnrealEvidence,
    UnrealEvidenceVerificationError,
    VALID_EVIDENCE_SOURCE_CLASSES,
    validate_raw_render_observation,
    verify_png_completeness,
    verify_render_job_evidence,
)
from planning.unreal_render_job_record import AtlasRenderJobRecord
from planning.unreal_render_receipt import UnrealRenderReceipt


def _create_test_png(path: Path, width: int = 1, height: int = 1) -> bytes:
    import struct
    import zlib
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    # Valid IDAT scanlines
    raw_scanlines = b"\x00" * (1 + width * 3) * height
    compressed_idat = zlib.compress(raw_scanlines)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed_idat) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed_idat)) + b"IDAT" + compressed_idat + idat_crc
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    content = sig + ihdr + idat + iend
    path.write_bytes(content)
    return content


def _sample_job_record(tmp_path: Path, atlas_job_id: str = "atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee") -> AtlasRenderJobRecord:
    out_parent = str(tmp_path / "renders")
    out_dir = str(tmp_path / "renders" / atlas_job_id)
    return AtlasRenderJobRecord.create_intent(
        atlas_job_id=atlas_job_id,
        attempt_ordinal=1,
        authorization_id="auth-m5-test",
        canonical_digital_twin_id="twin-m5-test",
        sequence_asset_path="/Game/AtlasTest/AtlasSequencerFixtureSequence",
        request_digest="req-digest-1234",
        config_digest="cfg-digest-1234",
        output_parent_directory=out_parent,
        output_directory=out_dir,
        expected_output_spec={"format": "png", "width": 1, "height": 1, "start_frame": 0, "end_frame": 0},
        created_at="2026-09-06T00:00:00Z",
    )


def _valid_record_observed_state(record: AtlasRenderJobRecord, output_file: Path, bytes_data: bytes) -> dict:
    import hashlib
    file_sha = hashlib.sha256(bytes_data).hexdigest()
    return {
        "job_id": record.unreal_job_id or "job-stage17-001",
        "atlas_job_id": record.atlas_job_id,
        "sequence_asset_path": record.sequence_asset_path,
        "authorization_id": record.authorization_id,
        "canonical_digital_twin_id": record.canonical_digital_twin_id,
        "config_digest": record.config_digest,
        "output_directory": record.output_directory,
        "editor_session_id": record.origin_editor_session_id or "session-uuid-1",
        "process_id": record.origin_process_id if record.origin_process_id is not None else 12345,
        "process_creation_time_utc": record.origin_process_creation_time or "2026-09-06T00:00:00Z",
        "expected_output_spec": dict(record.expected_output_spec),
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(output_file)],
        "output_manifest": [{"path": str(output_file), "size": len(bytes_data), "sha256": file_sha}],
    }


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
    rec = _sample_job_record(tmp_path)
    output_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(output_file)

    state = _valid_record_observed_state(rec, output_file, bytes_data)
    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_LIVE",
        job_record=rec,
        evidence_source_class="ENGINE_LIVE",
    )

    assert isinstance(evidence, UnrealEvidence)
    assert evidence.verified is True
    assert evidence.operation_name == "inspect_render_job"
    assert evidence.entity_ids == ("FIELD_SURFACE",)
    assert evidence.observed_state["job_id"] == "job-stage17-001"
    assert evidence.observed_state["output_files"] == (str(output_file),)

    # Confirm that UnrealRenderReceipt.issue() accepts this verified evidence
    receipt = UnrealRenderReceipt.issue(
        evidence,
        atlas_job_id=rec.atlas_job_id,
        attempt_ordinal=rec.attempt_ordinal,
        authorization_id=rec.authorization_id,
        canonical_digital_twin_id=rec.canonical_digital_twin_id,
        config_digest=rec.config_digest,
        output_directory=rec.output_directory,
    )
    assert receipt.matches(evidence)
    assert receipt.evidence_digest


def test_unfinished_job_rejection(tmp_path: Path):
    output_file = tmp_path / "AtlasRender_0001.png"
    output_file.write_bytes(b"data")

    # Status not finished/completed
    state = _valid_observed_state(output_file)
    state["status"] = "rendering"
    with pytest.raises(ValueError, match="status must be 'completed' or 'finished'"):
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    # Finished flag is False
    state2 = _valid_observed_state(output_file)
    state2["finished"] = False
    with pytest.raises(ValueError, match="finished flag must be True"):
        validate_raw_render_observation(
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
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    # failed is True
    state2 = _valid_observed_state(output_file)
    state2["failed"] = True
    with pytest.raises(ValueError, match="failed flag must be False"):
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state2,
            source="test",
        )


def test_missing_output_file_rejection(tmp_path: Path):
    non_existent = tmp_path / "non_existent.png"
    state = _valid_observed_state(non_existent)

    with pytest.raises(FileNotFoundError, match="does not exist on disk"):
        validate_raw_render_observation(
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
        validate_raw_render_observation(
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
        validate_raw_render_observation(
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
        validate_raw_render_observation(
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
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=(),
            observed_state=state,
            source="test",
        )

    with pytest.raises(ValueError, match="entity_id must be a non-empty canonical string"):
        validate_raw_render_observation(
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
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )

    state2 = _valid_observed_state(output_file)
    state2["sequence_asset_path"] = ""
    with pytest.raises(ValueError, match="sequence_asset_path must be a non-empty canonical string"):
        validate_raw_render_observation(
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
        validate_raw_render_observation(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
        )


# ==============================================================================
# M5 Contract V1 §§13-16 Focused Deterministic Test Suite
# ==============================================================================

def test_m5_source_class_allowlist_acceptance(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file, 1, 1)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    # 1. ENGINE_LIVE accepted
    ev_live = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_LIVE",
        job_record=rec,
        evidence_source_class="ENGINE_LIVE",
    )
    assert ev_live.verified is True
    assert ev_live.observed_state["evidence_source_class"] == "ENGINE_LIVE"

    # 2. ENGINE_JOURNAL_ATTESTED accepted
    ev_journal = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_JOURNAL_ATTESTED",
        job_record=rec,
        evidence_source_class="ENGINE_JOURNAL_ATTESTED",
    )
    assert ev_journal.verified is True
    assert ev_journal.observed_state["evidence_source_class"] == "ENGINE_JOURNAL_ATTESTED"


def test_m5_unknown_source_class_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)

    state = _valid_record_observed_state(rec, out_file, bytes_data)
    with pytest.raises(UnrealEvidenceVerificationError, match="unsupported evidence_source_class"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="test",
            job_record=rec,
            evidence_source_class="UNTRUSTED_ARBITRARY_SOURCE",
        )


def test_m5_identity_binding_mismatches_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    rec_bound = rec.transition(
        unreal_job_id="unreal-job-bound-777",
        origin_editor_session_id="editor-session-uuid-1",
        origin_process_id=4321,
        origin_process_creation_time="2026-09-06T00:00:00Z",
    )
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)

    base_state = {
        "job_id": "unreal-job-bound-777",
        "atlas_job_id": rec.atlas_job_id,
        "sequence_asset_path": rec.sequence_asset_path,
        "authorization_id": rec.authorization_id,
        "canonical_digital_twin_id": rec.canonical_digital_twin_id,
        "config_digest": rec.config_digest,
        "output_directory": rec.output_directory,
        "editor_session_id": "editor-session-uuid-1",
        "process_id": 4321,
        "process_creation_time_utc": "2026-09-06T00:00:00Z",
        "expected_output_spec": dict(rec.expected_output_spec),
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(out_file)],
        "output_manifest": [{"path": str(out_file), "size": len(bytes_data), "sha256": "0" * 64}],
    }

    # atlas_job_id mismatch
    st1 = dict(base_state, atlas_job_id="atlas-render-job-wrong")
    with pytest.raises(UnrealEvidenceVerificationError, match="atlas_job_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st1, source="ENGINE_LIVE", job_record=rec_bound)

    # unreal_job_id mismatch
    st2 = dict(base_state, job_id="unreal-job-WRONG")
    with pytest.raises(UnrealEvidenceVerificationError, match="unreal_job_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st2, source="ENGINE_LIVE", job_record=rec_bound)

    # sequence_asset_path mismatch
    st3 = dict(base_state, sequence_asset_path="/Game/Wrong")
    with pytest.raises(UnrealEvidenceVerificationError, match="sequence_asset_path mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st3, source="ENGINE_LIVE", job_record=rec_bound)

    # authorization_id mismatch
    st4 = dict(base_state, authorization_id="auth-WRONG")
    with pytest.raises(UnrealEvidenceVerificationError, match="authorization_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st4, source="ENGINE_LIVE", job_record=rec_bound)

    # canonical_digital_twin_id mismatch
    st_twin = dict(base_state, canonical_digital_twin_id="twin-WRONG")
    with pytest.raises(UnrealEvidenceVerificationError, match="canonical_digital_twin_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_twin, source="ENGINE_LIVE", job_record=rec_bound)

    # config_digest mismatch
    st5 = dict(base_state, config_digest="cfg-WRONG")
    with pytest.raises(UnrealEvidenceVerificationError, match="config_digest mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st5, source="ENGINE_LIVE", job_record=rec_bound)

    # editor_session_id mismatch
    st6 = dict(base_state, editor_session_id="session-WRONG")
    with pytest.raises(UnrealEvidenceVerificationError, match="editor_session_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st6, source="ENGINE_LIVE", job_record=rec_bound)

    # process_id mismatch
    st_pid = dict(base_state, process_id=99999)
    with pytest.raises(UnrealEvidenceVerificationError, match="process_id mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_pid, source="ENGINE_LIVE", job_record=rec_bound)

    # process_creation_time mismatch
    st7 = dict(base_state, process_creation_time_utc="2026-09-06T12:34:56Z")
    with pytest.raises(UnrealEvidenceVerificationError, match="process_creation_time mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st7, source="ENGINE_LIVE", job_record=rec_bound)

    # output_directory mismatch
    st_out = dict(base_state, output_directory="C:/Renders/wrong-dir")
    with pytest.raises(UnrealEvidenceVerificationError, match="output_directory mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_out, source="ENGINE_LIVE", job_record=rec_bound)


def test_m5_output_manifest_validation(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    import hashlib
    file_sha = hashlib.sha256(bytes_data).hexdigest()

    base_state = _valid_record_observed_state(rec, out_file, bytes_data)

    # Hash mismatch
    st_bad_hash = dict(base_state, output_manifest=[{"path": str(out_file), "size": len(bytes_data), "sha256": "0" * 64}])
    with pytest.raises(UnrealEvidenceVerificationError, match="manifest sha256 mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_bad_hash, source="ENGINE_LIVE", job_record=rec)

    # Size mismatch
    st_bad_size = dict(base_state, output_manifest=[{"path": str(out_file), "size": len(bytes_data) + 100, "sha256": file_sha}])
    with pytest.raises(UnrealEvidenceVerificationError, match="manifest size mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_bad_size, source="ENGINE_LIVE", job_record=rec)

    # Malformed manifest
    st_malformed = dict(base_state, output_manifest="not-a-list")
    with pytest.raises(UnrealEvidenceVerificationError, match="output_manifest must be a sequence"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_malformed, source="ENGINE_LIVE", job_record=rec)

    # Float/bool/non-integer size in manifest
    st_float_size = dict(base_state, output_manifest=[{"path": str(out_file), "size": 12.34, "sha256": file_sha}])
    with pytest.raises(UnrealEvidenceVerificationError, match="manifest entry size must be an exact positive integer"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_float_size, source="ENGINE_LIVE", job_record=rec)

    # Non-hex SHA in manifest
    st_bad_hex = dict(base_state, output_manifest=[{"path": str(out_file), "size": len(bytes_data), "sha256": "z" * 64}])
    with pytest.raises(UnrealEvidenceVerificationError, match="non-hexadecimal characters"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_bad_hex, source="ENGINE_LIVE", job_record=rec)

    # Duplicate manifest paths
    st_dup = dict(base_state, output_manifest=[
        {"path": str(out_file), "size": len(bytes_data), "sha256": file_sha},
        {"path": str(out_file), "size": len(bytes_data), "sha256": file_sha},
    ])
    with pytest.raises(UnrealEvidenceVerificationError, match="duplicate manifest path detected"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_dup, source="ENGINE_LIVE", job_record=rec)


def test_m5_path_isolation_and_traversal_rejection(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    Path(rec.output_directory).mkdir(parents=True, exist_ok=True)
    escaped_file = tmp_path / "escaped.png"
    bytes_data = _create_test_png(escaped_file)

    # Output file outside authorized output_directory
    st_outside = _valid_record_observed_state(rec, escaped_file, bytes_data)
    with pytest.raises(UnrealEvidenceVerificationError, match="outside authorized output directory"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_outside, source="ENGINE_LIVE", job_record=rec)

    # Path traversal attempt
    traversal_path = str(Path(rec.output_directory) / ".." / "escaped.png")
    st_traversal = dict(st_outside, output_files=[traversal_path], output_manifest=[{"path": traversal_path, "size": len(bytes_data), "sha256": "0"*64}])
    with pytest.raises(UnrealEvidenceVerificationError, match="(path traversal detected|outside authorized output directory)"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_traversal, source="ENGINE_LIVE", job_record=rec)


def test_m5_png_completeness_and_dimensions_validation(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"

    # Truncated PNG
    out_file.parent.mkdir(parents=True, exist_ok=True)
    trunc_bytes = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00])
    out_file.write_bytes(trunc_bytes)
    st_trunc = _valid_record_observed_state(rec, out_file, trunc_bytes)
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_trunc, source="ENGINE_LIVE", job_record=rec)

    # Wrong dimensions (expected 1x1, generate 10x10)
    bytes_10 = _create_test_png(out_file, width=10, height=10)
    st_dim = _valid_record_observed_state(rec, out_file, bytes_10)
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_dim, source="ENGINE_LIVE", job_record=rec)


def test_m5_expected_topology_and_unsupported_format(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file1 = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes1 = _create_test_png(out_file1)
    import hashlib
    sha1 = hashlib.sha256(bytes1).hexdigest()

    # Frame count mismatch (rec expected 1 frame [0..0], provide 2)
    out_file2 = Path(rec.output_directory) / "AtlasRender_0001.png"
    bytes2 = _create_test_png(out_file2)
    sha2 = hashlib.sha256(bytes2).hexdigest()
    st_count = _valid_record_observed_state(rec, out_file1, bytes1)
    st_count["output_files"] = [str(out_file1), str(out_file2)]
    st_count["output_manifest"] = [
        {"path": str(out_file1), "size": len(bytes1), "sha256": sha1},
        {"path": str(out_file2), "size": len(bytes2), "sha256": sha2},
    ]
    with pytest.raises(UnrealEvidenceVerificationError, match="output file count mismatch"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_count, source="ENGINE_LIVE", job_record=rec)

    # Unexpected extra file on disk
    extra_disk_file = Path(rec.output_directory) / "stray_file.png"
    extra_disk_file.write_bytes(b"stray")
    st_stray = _valid_record_observed_state(rec, out_file1, bytes1)
    with pytest.raises(UnrealEvidenceVerificationError, match="unexpected extra files present"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_stray, source="ENGINE_LIVE", job_record=rec)
    extra_disk_file.unlink()

    # Unsupported output format
    rec_exotic = AtlasRenderJobRecord.create_intent(
        atlas_job_id="atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-ffffffffffff",
        attempt_ordinal=1,
        authorization_id="auth-1",
        canonical_digital_twin_id="twin-1",
        sequence_asset_path="/Game/Seq",
        request_digest="req",
        config_digest="cfg",
        output_parent_directory=str(tmp_path / "renders"),
        output_directory=str(tmp_path / "renders" / "atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-ffffffffffff"),
        expected_output_spec={"format": "unsupported_exr"},
        created_at="2026-09-06T00:00:00Z",
    )
    p_exotic = Path(rec_exotic.output_directory) / "frame.exr"
    p_exotic.parent.mkdir(parents=True, exist_ok=True)
    p_exotic.write_bytes(b"exr-data")
    st_exotic = _valid_record_observed_state(rec_exotic, p_exotic, b"exr-data")
    with pytest.raises(UnrealEvidenceVerificationError, match="unsupported output format"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_exotic, source="ENGINE_LIVE", job_record=rec_exotic)


def test_m5_evidence_immutability_and_snapshot_roundtrip(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_LIVE",
        job_record=rec,
        evidence_source_class="ENGINE_LIVE",
    )

    # Immutability
    with pytest.raises(Exception):
        evidence.observed_state["job_id"] = "tampered"
    with pytest.raises(Exception):
        evidence.verified = False

    # Snapshot round-trip
    snap = evidence.snapshot()
    restored = UnrealEvidence.from_snapshot(snap)
    assert restored.verified is True
    assert restored.operation_name == evidence.operation_name
    assert restored.observed_state["job_id"] == evidence.observed_state["job_id"]
    assert restored.observed_state["output_manifest"] == evidence.observed_state["output_manifest"]


def test_m5_receipt_lineage_preservation(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    evidence = verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_LIVE",
        job_record=rec,
        evidence_source_class="ENGINE_LIVE",
    )

    receipt = UnrealRenderReceipt.issue(
        evidence,
        atlas_job_id=rec.atlas_job_id,
        attempt_ordinal=rec.attempt_ordinal,
        authorization_id=rec.authorization_id,
        canonical_digital_twin_id=rec.canonical_digital_twin_id,
        config_digest=rec.config_digest,
        output_directory=rec.output_directory,
    )
    assert receipt.matches(evidence)

    # ProductionArtifactManifest lineage
    from planning.production_artifact import ProductionArtifactManifest, verify_unreal_render_lineage
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id="art-1",
        canonical_digital_twin_id=rec.canonical_digital_twin_id,
        representation_type="unreal-render",
        artifact_path=str(out_file),
        render_receipt=receipt,
        render_evidence=evidence,
    )
    # Lineage verification must pass
    verify_unreal_render_lineage(manifest, receipt, evidence)


def test_m5_missing_mandatory_identity_field_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)
    del state["authorization_id"]

    with pytest.raises(UnrealEvidenceVerificationError, match="missing mandatory identity field 'authorization_id'"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_tampered_snapshot_fails_closed(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    evidence = verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)
    snap = evidence.snapshot()
    snap["extra_forged_key"] = "malicious"
    with pytest.raises(ValueError, match="Unreal evidence snapshot fields are invalid"):
        UnrealEvidence.from_snapshot(snap)


def test_m5_verified_flag_authority(tmp_path: Path):
    # Calling the verifier with failing condition raises error, never returning verified=True
    rec = _sample_job_record(tmp_path)
    missing_file = Path(rec.output_directory) / "non_existent.png"
    state = _valid_record_observed_state(rec, missing_file, b"data")

    with pytest.raises(FileNotFoundError):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_png_crc_failure_rejected(tmp_path: Path):
    import struct
    import zlib
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    # Deliberately corrupt CRC
    ihdr_crc = struct.pack(">I", 0x12345678)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    content = sig + ihdr + iend
    out_file.write_bytes(content)

    state = _valid_record_observed_state(rec, out_file, content)
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_missing_iend_rejected(tmp_path: Path):
    import struct
    import zlib
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    # No IEND chunk written
    content = sig + ihdr
    out_file.write_bytes(content)

    state = _valid_record_observed_state(rec, out_file, content)
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_ntfs_alternate_data_stream_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)

    st_ads = _valid_record_observed_state(rec, out_file, bytes_data)
    st_ads["output_files"] = [str(out_file) + ":hidden_stream"]
    st_ads["output_manifest"] = [{"path": str(out_file) + ":hidden_stream", "size": len(bytes_data), "sha256": "0"*64}]
    with pytest.raises(UnrealEvidenceVerificationError, match="NTFS alternate data stream detected"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_ads, source="ENGINE_LIVE", job_record=rec)


def test_m5_png_idat_decompression_failure_rejected(tmp_path: Path):
    import struct
    import zlib
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    # Corrupt compressed IDAT data
    idat_data = b"NOT_VALID_ZLIB_DATA_12345678"
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + idat_data) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + idat_crc
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    content = sig + ihdr + idat + iend
    out_file.write_bytes(content)

    state = _valid_record_observed_state(rec, out_file, content)
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG IDAT decompression integrity check failed"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_empty_png_rejected_no_idat(tmp_path: Path):
    """Test that a PNG file with valid signature and IHDR but missing any IDAT chunk is rejected."""
    import struct
    import zlib
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    content = sig + ihdr + iend
    out_file.write_bytes(content)

    state = _valid_record_observed_state(rec, out_file, content)
    with pytest.raises(UnrealEvidenceVerificationError, match="(PNG contains zero IDAT data chunks|PNG IDAT decompression integrity check failed)"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_missing_manifest_rejected_when_job_record_supplied(tmp_path: Path):
    """Test that omitting output_manifest fails closed when job_record is present."""
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)
    del state["output_manifest"]

    with pytest.raises(UnrealEvidenceVerificationError, match="missing required engine-attested 'output_manifest'"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_empty_manifest_rejected_when_outputs_required(tmp_path: Path):
    """Test that empty output_manifest fails closed when output files are declared."""
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)
    state["output_manifest"] = []

    with pytest.raises(UnrealEvidenceVerificationError, match="output_manifest cannot be empty when outputs are required"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_manifest_set_inequality_rejected(tmp_path: Path):
    """Test that manifest-only or disk-only file sets fail closed."""
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    # Manifest refers to another file not in output_files
    diff_file = str(Path(rec.output_directory) / "AtlasRender_diff.png")
    state["output_manifest"] = [{"path": diff_file, "size": len(bytes_data), "sha256": "0" * 64}]

    with pytest.raises(UnrealEvidenceVerificationError, match="(manifest paths do not exactly match declared output_files|manifest paths set does not match output_files set)"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=state, source="ENGINE_LIVE", job_record=rec)


def test_m5_source_class_missing_or_arbitrary_fails_closed(tmp_path: Path):
    """Test that arbitrary strings for evidence_source_class or source fail closed."""
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)

    # Arbitrary source string when evidence_source_class is None
    with pytest.raises(UnrealEvidenceVerificationError, match="(missing or invalid evidence_source_class|unsupported evidence_source_class)"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="arbitrary_untrusted_source",
            job_record=rec,
            evidence_source_class=None,
        )

    # Explicit invalid evidence_source_class
    with pytest.raises(UnrealEvidenceVerificationError, match="unsupported evidence_source_class"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="ENGINE_LIVE",
            job_record=rec,
            evidence_source_class="CUSTOM_ARBITRARY_CLASS",
        )


def test_m5_missing_topology_spec_fails_closed(tmp_path: Path):
    """Test that missing or uninterpretable expected_output_spec fails closed."""
    rec_no_topo = AtlasRenderJobRecord.create_intent(
        atlas_job_id="atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-111111111111",
        attempt_ordinal=1,
        authorization_id="auth-1",
        canonical_digital_twin_id="twin-1",
        sequence_asset_path="/Game/Seq",
        request_digest="req",
        config_digest="cfg",
        output_parent_directory=str(tmp_path / "renders"),
        output_directory=str(tmp_path / "renders" / "atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-111111111111"),
        expected_output_spec={},  # Empty topology
        created_at="2026-09-06T00:00:00Z",
    )
    out_file = Path(rec_no_topo.output_directory) / "frame_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec_no_topo, out_file, bytes_data)

    with pytest.raises(UnrealEvidenceVerificationError, match="(expected_output_spec cannot be empty|missing mandatory expected_output_spec)"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="ENGINE_LIVE",
            job_record=rec_no_topo,
        )


def test_m5_missing_output_directory_on_disk_fails_closed(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_dir = Path(rec.output_directory)
    # Remove output directory entirely
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)

    out_file = out_dir / "AtlasRender_0000.png"
    state = {
        "job_id": "job-stage17-001",
        "atlas_job_id": rec.atlas_job_id,
        "sequence_asset_path": rec.sequence_asset_path,
        "authorization_id": rec.authorization_id,
        "canonical_digital_twin_id": rec.canonical_digital_twin_id,
        "config_digest": rec.config_digest,
        "output_directory": rec.output_directory,
        "editor_session_id": "session-uuid-1",
        "process_id": 12345,
        "process_creation_time_utc": "2026-09-06T00:00:00Z",
        "expected_output_spec": dict(rec.expected_output_spec),
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(out_file)],
        "output_manifest": [{"path": str(out_file), "size": 100, "sha256": "0" * 64}],
    }
    with pytest.raises(FileNotFoundError):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="ENGINE_LIVE",
            job_record=rec,
        )


def test_m5_duplicate_output_files_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)
    state = _valid_record_observed_state(rec, out_file, bytes_data)
    state["output_files"] = [str(out_file), str(out_file)]

    with pytest.raises(UnrealEvidenceVerificationError, match="duplicate output file path in declared output_files"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="ENGINE_LIVE",
            job_record=rec,
        )


def test_m5_mandatory_job_record_boundary_enforced(tmp_path: Path):
    """Test that calling verify_render_job_evidence without a job_record fails immediately."""
    rec = _sample_job_record(tmp_path)
    output_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(output_file)
    state = _valid_record_observed_state(rec, output_file, bytes_data)

    # Calling with job_record=None
    with pytest.raises(UnrealEvidenceVerificationError, match="job_record is strictly mandatory"):
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=("FIELD_SURFACE",),
            observed_state=state,
            source="ENGINE_LIVE",
            job_record=None,
        )

    # Validate that raw observation helper succeeds on basic validation but DOES NOT return UnrealEvidence or verified=True
    raw_res = validate_raw_render_observation(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state=state,
        source="ENGINE_LIVE",
    )
    assert isinstance(raw_res, dict)
    assert not isinstance(raw_res, UnrealEvidence)
    assert "verified" not in raw_res


def test_m5_windows_83_short_names_and_device_namespaces_rejected(tmp_path: Path):
    rec = _sample_job_record(tmp_path)
    out_file = Path(rec.output_directory) / "AtlasRender_0000.png"
    bytes_data = _create_test_png(out_file)

    # 8.3 short name
    short_path = str(Path(rec.output_directory) / "ATLASR~1.PNG")
    st_short = _valid_record_observed_state(rec, out_file, bytes_data)
    st_short["output_files"] = [short_path]
    with pytest.raises(UnrealEvidenceVerificationError, match="Windows 8.3 short name path rejected"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_short, source="ENGINE_LIVE", job_record=rec)

    # Device namespace
    dev_path = "\\\\.\\" + str(out_file)
    st_dev = _valid_record_observed_state(rec, out_file, bytes_data)
    st_dev["output_files"] = [dev_path]
    with pytest.raises(UnrealEvidenceVerificationError, match="Windows device namespace path rejected"):
        verify_render_job_evidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state=st_dev, source="ENGINE_LIVE", job_record=rec)
