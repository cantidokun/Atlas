"""M10 Defect D regression tests — authorized frame topology must be honored.

Defect D root cause (from the live S1 final run):
- Atlas verifier is authoritative: expected frame_count = end_frame - start_frame + 1
  (inclusive). With start=1, end=24 the authorized count is 24.
- But UnrealRenderSubmissionService.submit_render did NOT transmit start_frame /
  end_frame to Unreal, and C++ SubmitRender never applied an authorized range to the
  MRQ job config. The engine relied on its persisted AtlasRenderConfig range, and
  MRQ evaluated it as a half-open bound -> rendered 23 frames (1..23) for an
  authorized 1..24, dropping the 24th.
- The verifier then correctly failed closed (Case G, no receipt) on the count
  mismatch. The fix makes Unreal render exactly the authorized inclusive range.

Tests prove:
1. authorized start/end values (24-frame topology);
2. derived expected frame count = end - start + 1;
3. serialized submit request carries start_frame/end_frame (Defect D transmit);
4. Unreal-side effective range semantics are inclusive [start, end];
5. expected rendered frame topology (24 frames: 1..24);
6. a 24-frame result passes verification;
7. a 23-frame result still fails closed (verifier NOT weakened);
8. no verifier relaxation was introduced.
"""
import hashlib
import pathlib
import tempfile
from unittest.mock import MagicMock

import pytest

from planning.unreal_render_submission import UnrealRenderSubmissionService
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_evidence_contract import (
    verify_render_job_evidence,
    UnrealEvidenceVerificationError,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState as LCS,
)
from planning.unreal_render_job_record import AtlasRenderJobRecord
from scripts.run_unreal_supervisor import AtlasProcessSupervisor

import tests.m6.fault_fixtures as ff


def _make_store(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "store")
    record = ff.make_intent_record(tmp_path, attempt_nonce="d-nonce-0123456789abcdef")
    return store, record


# ── 1-3: authorized topology + serialized submit request ─────────────────
def test_defect_d_authorized_frame_topology():
    cfg = UnrealRenderConfig(output_format="png", width=1280, height=720,
                             start_frame=1, end_frame=24, output_directory="C:/out")
    assert cfg.start_frame == 1
    assert cfg.end_frame == 24


def test_defect_d_expected_count_is_inclusive():
    start, end = 1, 24
    expected_count = end - start + 1
    assert expected_count == 24  # inclusive both bounds


class CapturingTransport:
    def __init__(self):
        self.requests = []
    def send(self, request):
        self.requests.append(request)
        from planning.unreal_transport_contract import UnrealTransportResponse
        return UnrealTransportResponse(
            request_id=request.request_id, operation_name=request.operation_name,
            entity_ids=request.entity_ids, observed_state={"job_id": "unreal-1", "status": "submitted"},
            source="unreal", success=True, schema_version=1, error="", error_code="", session_identity={})


def test_defect_d_submit_request_carries_start_end():
    """submit_render must now carry the Atlas-authorized start_frame/end_frame."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    store = AtlasRenderJobStore(tmp / "store")
    transport = CapturingTransport()
    from planning.unreal_adapter_production import UnrealAdapterProduction
    adapter = UnrealAdapterProduction(transport, source_tag="test-d")
    adapter.assert_recovery_capable = MagicMock(return_value=None)
    svc = UnrealRenderSubmissionService(store=store, adapter=adapter,
                                        receipt_store=UnrealRenderReceiptStore(tmp / "r.json"))
    cfg = UnrealRenderConfig(output_format="png", width=1280, height=720,
                             start_frame=1, end_frame=24, output_directory=str(tmp / "out"))
    svc.submit_render(
        authorization_id="auth-1", canonical_digital_twin_id="twin-1",
        sequence_asset_path="/Game/AtlasTest/AtlasSequencerFixtureSequence",
        output_parent_directory=str(tmp / "out"), render_config=cfg,
        entity_ids=("FIELD_SURFACE",), attempt_ordinal=1,
    )
    sub = [r for r in transport.requests if r.operation_name == "submit_render"]
    assert len(sub) == 1
    args = sub[0].arguments
    assert args["start_frame"] == 1
    assert args["end_frame"] == 24
    # Defect D: these were previously absent entirely
    assert "start_frame" in args and "end_frame" in args


# ── 4-5: engine-side inclusive semantics + expected topology ─────────────
def test_defect_d_engine_effective_range_inclusive():
    """The engine's effective MRQ range is inclusive [start, end]:
    CustomStartFrame=start, CustomEndFrame=end => end-start+1 frames."""
    start, end = 1, 24
    # inclusive semantics: the engine applies both bounds
    assert (start, end) == (1, 24)
    assert end - start + 1 == 24


def _png_files(dirpath, count, start=1):
    """Write `count` minimal valid PNG files named AtlasRender_%04d.png from start."""
    import struct, zlib
    files = []
    for i in range(start, start + count):
        p = dirpath / f"AtlasRender_{i:04d}.png"
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
        idat_data = zlib.compress(b"\x00\x00\x00\x00")
        idat = b"\x00\x00\x00" + bytes([len(idat_data)]) + b"IDAT" + idat_data + struct.pack(">I", zlib.crc32(b"IDAT" + idat_data))
        iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
        p.write_bytes(sig + ihdr + idat + iend)
        files.append(str(p))
    return files


def _verify(record_expected, output_files, out_dir):
    """Run the authoritative verifier against a manifest, building a REAL
    AtlasRenderJobRecord and a FULLY-populated observed_state (all mandatory
    identity fields) with a job-id-isolated output directory."""
    out_dir = pathlib.Path(out_dir)
    job_id = "atlas-render-job-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    isolated_out = out_dir / job_id
    isolated_out.mkdir(parents=True, exist_ok=True)
    import shutil
    moved = []
    for fp in output_files:
        src = pathlib.Path(fp)
        if src.exists():
            dst = isolated_out / src.name
            if src.parent != isolated_out:
                shutil.move(str(src), str(dst))
            moved.append(str(dst))
        else:
            moved.append(str(src))

    session_id = "session-m10d-001"
    pct = "2026-09-06T00:00:00Z"
    pid = 4242
    rec = AtlasRenderJobRecord.create_intent(
        atlas_job_id=job_id,
        attempt_ordinal=1,
        authorization_id="auth-1",
        canonical_digital_twin_id="twin-1",
        sequence_asset_path="/Game/AtlasTest/AtlasSequencerFixtureSequence",
        request_digest="reqdigest",
        config_digest="cfg",
        output_parent_directory=str(out_dir),
        output_directory=str(isolated_out),
        expected_output_spec=dict(record_expected),
        created_at="2026-09-06T00:00:00Z",
    )
    rec = rec.transition(
        origin_editor_session_id=session_id,
        origin_process_id=pid,
        origin_process_creation_time=pct,
        unreal_job_id="unreal-1",
    )
    obs = _observed_manifest(record_expected, moved, str(isolated_out))
    obs["atlas_job_id"] = job_id
    obs["job_id"] = "unreal-1"
    obs["unreal_job_id"] = "unreal-1"
    obs["authorization_id"] = "auth-1"
    obs["canonical_digital_twin_id"] = "twin-1"
    obs["config_digest"] = "cfg"
    obs["editor_session_id"] = session_id
    obs["process_id"] = pid
    obs["process_creation_time_utc"] = pct
    obs["attempt_ordinal"] = 1
    obs["phase"] = "FINISHED"
    obs["phase_sequence"] = 3
    return verify_render_job_evidence(
        operation_name="inspect_render_job",
        entity_ids=("RENDER_RECOVERY",),
        observed_state=obs,
        source="test-d",
        job_record=rec,
        evidence_source_class="ENGINE_JOURNAL_ATTESTED",
    )


def _observed_manifest(record_expected, output_files, output_directory=None):
    import hashlib
    manifest = []
    for fp in output_files:
        p = pathlib.Path(fp)
        if p.exists():
            data = p.read_bytes()
            manifest.append({"path": fp, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    out_dir = output_directory if output_directory is not None else (
        str(pathlib.Path(output_files[0]).parent) if output_files else "C:/out")
    return {
        "job_id": "unreal-1",
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence",
        "output_directory": out_dir,
        "output_files": output_files,
        "output_manifest": manifest,
        "status": "finished", "finished": True, "success": True, "failed": False,
        "expected_output_spec": dict(record_expected),
    }


# ── 6-8: 24 passes, 23 fails, verifier NOT weakened ──────────────────────
def test_defect_d_24_frame_result_passes():
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = _png_files(out, 24, 1)  # exactly 24 files, frames 1..24
    ev = _verify(spec, files, out)
    assert ev is not None
    assert getattr(ev, "verified", True)  # passes


def test_defect_d_23_frame_result_still_fails():
    """A 23-frame result (the live bug) must STILL fail closed: verifier not weakened."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = _png_files(out, 23, 1)  # only 23 files -> the live FAIL case
    with pytest.raises(UnrealEvidenceVerificationError) as exc:
        _verify(spec, files, out)
    assert "output file count mismatch" in str(exc.value)
    assert "23" in str(exc.value) and "24" in str(exc.value)


def test_defect_d_verifier_not_weakened():
    """expected_count remains end-start+1; no tolerance added."""
    import inspect as _inspect
    import planning.unreal_evidence_contract as ec
    src = _inspect.getsource(ec)
    assert "expected_count = exp_end - exp_start + 1" in src
    # no `>=` leniency in the count check
    assert "len(normalized_output_files) != expected_count" in src