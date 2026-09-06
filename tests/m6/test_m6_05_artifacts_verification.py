"""M6 §31 items 12,13,14,15 — artifact output-directory isolation, artifact hash
match/mismatch, truncated PNG rejection, and exact expected frame/output topology.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
These exercise the authoritative `verify_render_job_evidence` boundary directly.
"""

import hashlib

import pytest

from planning.unreal_evidence_contract import (
    UnrealEvidenceVerificationError,
    verify_render_job_evidence,
)
from planning.unreal_render_job_record import AtlasRenderJobRecord
import tests.m6.fault_fixtures as ff


def _record(tmp_path, start=0, end=0, width=1, height=1) -> AtlasRenderJobRecord:
    spec = {"format": "png", "width": width, "height": height, "start_frame": start, "end_frame": end}
    return ff.make_submitted_record(tmp_path, expected_output_spec=spec)


def _observed(rec, output_files, manifest, **overrides):
    data = {
        "job_id": rec.unreal_job_id,
        "atlas_job_id": rec.atlas_job_id,
        "sequence_asset_path": rec.sequence_asset_path,
        "authorization_id": rec.authorization_id,
        "canonical_digital_twin_id": rec.canonical_digital_twin_id,
        "config_digest": rec.config_digest,
        "output_directory": rec.output_directory,
        "editor_session_id": rec.origin_editor_session_id,
        "process_id": rec.origin_process_id,
        "process_creation_time_utc": rec.origin_process_creation_time,
        "expected_output_spec": dict(rec.expected_output_spec),
        "status": "finished",
        "finished": True,
        "success": True,
        "failed": False,
        "output_files": [str(f) for f in output_files],
        "output_manifest": [dict(m) for m in manifest],
    }
    data.update(overrides)
    return data


def _check(rec, observed):
    return verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("RENDER_RECOVERY",),
        observed_state=observed,
        source="unreal-recovery-coordinator",
        job_record=rec,
        evidence_source_class="ENGINE_JOURNAL_ATTESTED",
    )


# ── Item 15: exact expected frame/output topology (positive) ──────────────────
def test_m6_item15_exact_topology_verifies_single_frame(tmp_path):
    rec = _record(tmp_path, start=0, end=0)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    frame = out / "AtlasRender_0000.png"
    ff.make_valid_png(frame, width=1, height=1)
    data_bytes = frame.read_bytes()
    manifest = [{"path": str(frame), "size": len(data_bytes), "sha256": ff.sha256_of(data_bytes)}]
    ev = _check(rec, _observed(rec, [frame], manifest))
    assert ev.verified is True


def test_m6_item15_exact_frame_count_for_multiframe(tmp_path):
    rec = _record(tmp_path, start=0, end=2, width=1, height=1)  # 3 frames
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    manifests = []
    for i in range(3):
        fr = out / f"AtlasRender_{i:04d}.png"
        ff.make_valid_png(fr, width=1, height=1)
        d = fr.read_bytes()
        frames.append(fr)
        manifests.append({"path": str(fr), "size": len(d), "sha256": ff.sha256_of(d)})
    ev = _check(rec, _observed(rec, frames, manifests))
    assert ev.verified is True
    assert len(ev.observed_state["output_files"]) == 3


def test_m6_item15_frame_count_mismatch_rejected(tmp_path):
    rec = _record(tmp_path, start=0, end=2)  # expects 3 frames
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    only = out / "AtlasRender_0000.png"
    ff.make_valid_png(only)
    d = only.read_bytes()
    manifest = [{"path": str(only), "size": len(d), "sha256": ff.sha256_of(d)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="output file count mismatch"):
        _check(rec, _observed(rec, [only], manifest))


def test_m6_item15_required_spec_keys_missing_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    ff.make_valid_png(fr)
    d = fr.read_bytes()
    manifest = [{"path": str(fr), "size": len(d), "sha256": ff.sha256_of(d)}]
    bad_spec = {"format": "png", "width": 1}  # missing height/start/end
    with pytest.raises(UnrealEvidenceVerificationError, match="expected_output_spec"):
        _check(rec, _observed(rec, [fr], manifest, expected_output_spec=bad_spec))


def test_m6_item15_bool_misused_as_int_dimension_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    ff.make_valid_png(fr)
    d = fr.read_bytes()
    manifest = [{"path": str(fr), "size": len(d), "sha256": ff.sha256_of(d)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="'width' must be an integer"):
        _check(rec, _observed(rec, [fr], manifest, expected_output_spec={"format": "png", "width": True, "height": 1, "start_frame": 0, "end_frame": 0}))


# ── Item 13: artifact hash match/mismatch ─────────────────────────────────────
def test_m6_item13_hash_mismatch_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    ff.make_valid_png(fr)
    d = fr.read_bytes()
    bad_manifest = [{"path": str(fr), "size": len(d), "sha256": "0" * 64}]
    with pytest.raises(UnrealEvidenceVerificationError, match="sha256 mismatch"):
        _check(rec, _observed(rec, [fr], bad_manifest))


def test_m6_item13_size_mismatch_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    ff.make_valid_png(fr)
    d = fr.read_bytes()
    bad_manifest = [{"path": str(fr), "size": len(d) + 5, "sha256": ff.sha256_of(d)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="manifest size mismatch"):
        _check(rec, _observed(rec, [fr], bad_manifest))


def test_m6_item13_hash_replayed_from_stale_artifact_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    ff.make_valid_png(fr)
    stale_bytes = b"STALE_ARTIFACT_DATA"  # not the real file bytes
    manifest = [{"path": str(fr), "size": len(stale_bytes), "sha256": hashlib.sha256(stale_bytes).hexdigest()}]
    with pytest.raises(UnrealEvidenceVerificationError):
        _check(rec, _observed(rec, [fr], manifest))


# ── Item 14: truncated PNG rejection ──────────────────────────────────────────
def test_m6_item14_truncated_png_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    full = ff.make_valid_png(fr)
    truncated = ff.make_truncated_png_bytes(full, cut=20)
    fr.write_bytes(truncated)
    d = truncated
    manifest = [{"path": str(fr), "size": len(d), "sha256": ff.sha256_of(d)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        _check(rec, _observed(rec, [fr], manifest))


def test_m6_item14_corrupt_idat_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    full = ff.make_valid_png(fr)
    # Corrupt a byte in the middle of the compressed IDAT stream
    data = bytearray(full)
    # find IDAT data region (after 8-byte sig + 25-byte IHDR)
    data[8 + 25 + 8 : 8 + 25 + 8 + 4] = b"\xff\xff\xff\xff"
    corrupted = bytes(data)
    fr.write_bytes(corrupted)
    manifest = [{"path": str(fr), "size": len(corrupted), "sha256": ff.sha256_of(corrupted)}]
    with pytest.raises(UnrealEvidenceVerificationError):
        _check(rec, _observed(rec, [fr], manifest))


def test_m6_item14_nonsignature_file_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    fr = out / "AtlasRender_0000.png"
    bad = b"NOT_A_PNG_AT_ALL" * 10
    fr.write_bytes(bad)
    manifest = [{"path": str(fr), "size": len(bad), "sha256": ff.sha256_of(bad)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="PNG completeness check failed"):
        _check(rec, _observed(rec, [fr], manifest))


# ── Item 12: artifact output-directory isolation & path defenses ──────────────
def test_m6_item12_path_traversal_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    legit = out / "AtlasRender_0000.png"
    ff.make_valid_png(legit)
    d = legit.read_bytes()
    manifest = [{"path": str(legit), "size": len(d), "sha256": ff.sha256_of(d)}]
    observed = _observed(rec, [legit], manifest)
    observed["output_files"] = [f"{rec.sequence_asset_path}/../../etc/passwd"]
    with pytest.raises(UnrealEvidenceVerificationError, match="path traversal|outside authorized"):
        _check(rec, observed)


def test_m6_item12_file_outside_output_dir_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.png"
    ff.make_valid_png(outside)
    d = outside.read_bytes()
    manifest = [{"path": str(outside), "size": len(d), "sha256": ff.sha256_of(d)}]
    with pytest.raises(UnrealEvidenceVerificationError, match="outside authorized output directory"):
        _check(rec, _observed(rec, [outside], manifest))


def test_m6_item12_ntfs_ads_and_device_namespace_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    legit = out / "AtlasRender_0000.png"
    ff.make_valid_png(legit)
    d = legit.read_bytes()
    manifest = [{"path": str(legit), "size": len(d), "sha256": ff.sha256_of(d)}]
    # Alternate data stream
    observed = _observed(rec, [legit], manifest)
    observed["output_files"] = [str(legit) + ":zone.stream"]
    with pytest.raises(UnrealEvidenceVerificationError, match="alternate data stream"):
        _check(rec, observed)
    # Device namespace
    observed2 = _observed(rec, [legit], manifest)
    observed2["output_files"] = [r"\\.\pipe\evil"]
    with pytest.raises(UnrealEvidenceVerificationError, match="device namespace"):
        _check(rec, observed2)


def test_m6_item12_extra_undisclosed_disk_artifact_rejected(tmp_path):
    rec = _record(tmp_path)
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    legit = out / "AtlasRender_0000.png"
    ff.make_valid_png(legit)
    d = legit.read_bytes()
    manifest = [{"path": str(legit), "size": len(d), "sha256": ff.sha256_of(d)}]
    # A stray, undisclosed file in the output dir must fail verification
    stray = out / "stray.foo"
    stray.write_bytes(b"unexpected")
    with pytest.raises(UnrealEvidenceVerificationError, match="unexpected extra files"):
        _check(rec, _observed(rec, [legit], manifest))


def test_m6_item12_duplicate_output_path_rejected(tmp_path):
    rec = _record(tmp_path, start=0, end=1)  # expects 2 frames
    out = ff.Path(rec.output_directory)
    out.mkdir(parents=True, exist_ok=True)
    a = out / "a.png"
    b = out / "b.png"
    ff.make_valid_png(a)
    ff.make_valid_png(b)
    # Duplicate canonical path in declared outputs must fail closed
    observed = _observed(rec, [a, a], [])
    observed["output_manifest"] = []
    with pytest.raises(UnrealEvidenceVerificationError, match="duplicate output file path"):
        _check(rec, observed)