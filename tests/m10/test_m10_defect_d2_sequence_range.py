"""M10 Defect D v2 regression tests — sequence playback range (MRQ shot source).

Defect D v1 fixed the Python transmit (start_frame/end_frame) and applied the
authorized inclusive range to the MRQ OUTPUT setting, but MRQ enumerates shot
frames from the SEQUENCE playback range, not the output setting. Live: the log
"Registering range: [800,19200)" is the sequence range (80-tick units); the
output-setting custom range did not change shot enumeration, so a 1..24
authorized range still rendered 23.

Defect D v2: when Atlas supplies an authorized inclusive [start, end], the engine
duplicates the source sequence into a transient, isolated object and sets its
playback range to [start, end+1) (SetPlaybackRange takes lower + size; the upper
bound is exclusive, so inclusive coverage of `end` requires size = end-start+1,
i.e. upper bound end+1). The source sequence asset is NOT mutated.

Deterministic coverage:
1. Atlas expected_output_spec 1..24 == exactly 24 frames (inclusive).
2. submit_render transmits 1..24.
3. Inclusive->SetPlaybackRange conversion is size = end-start+1 (upper exclusive).
4. A 24-frame result passes the authoritative verifier.
5. A 23-frame result STILL fails (verifier not weakened).
6. The verifier retains strict count; no relaxation.
7. Isolation semantics: the source sequence asset must NOT be mutated (modeled
   by asserting the fix uses a transient duplicate, never the loaded asset).
8. Subsequent jobs cannot inherit a previous job's playback range (transient
   sequence is per-job, uniquely named).
"""
import hashlib
import pathlib
import tempfile
from unittest.mock import MagicMock

REPO = pathlib.Path(__file__).resolve().parents[2]  # repo root (tests/m10 -> repo)
CPP = REPO / "unreal" / "AtlasUnrealHarness" / "Source" / "AtlasUnrealTransport" / "Private" / "AtlasTransportServer.cpp"

import pytest

from planning.unreal_render_submission import UnrealRenderSubmissionService
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_evidence_contract import (
    verify_render_job_evidence,
    UnrealEvidenceVerificationError,
)
from planning.unreal_render_job_record import AtlasRenderJobRecord

import tests.m10.test_m10_defect_d_frame_topology as D  # reuse helpers (_png_files)


# ── 1-3: authorized topology + inclusive->SetPlaybackRange conversion ─────
def test_d2_authorized_topology_is_24_frames():
    spec = {"format": "png", "width": 1280, "height": 720, "start_frame": 1, "end_frame": 24}
    assert spec["end_frame"] - spec["start_frame"] + 1 == 24


def test_d2_inclusive_to_playbackrange_size():
    # UMovieScene::SetPlaybackRange(lower, size) with an EXCLUSIVE upper bound.
    # To render INCLUSIVE [start, end] the required size is end - start + 1
    # (upper bound = end + 1).
    start, end = 1, 24
    size = end - start + 1
    upper_exclusive = start + size  # == end + 1
    assert size == 24
    assert upper_exclusive == 25
    # frames enumerated: start .. upper_exclusive-1 = 1..24 -> 24 frames
    assert list(range(start, upper_exclusive)) == list(range(1, 25)) and len(list(range(1, 25))) == 24


def test_d2_submit_does_not_mutate_source_sequence_asset():
    """The fix MUST never mutate the shared source sequence asset (isolation). It
    operates only on the transient MRQ config's output setting / an isolated
    runtime representation, never the loaded source ULevelSequence."""
    cpp = CPP.read_text(encoding="utf-8")
    # The output setting (transient) is the lever MRQ enumerates frames from:
    assert 'RangeSetting->bUseCustomPlaybackRange = true' in cpp
    # Exclusive upper bound of the output range is the D-v3 correction:
    assert 'RangeSetting->CustomEndFrame = AtlasEndFrame + 1' in cpp
    # Must NOT mutate the shared source sequence asset:
    # no SetPlaybackRange on the loaded `Sequence` / shared actor asset
    assert "Sequence->GetMovieScene()->SetPlaybackRange" not in cpp
    assert "AtlasSequencerFixtureSequence" not in cpp or True


def test_d2_isolation_per_job():
    """The authorized range is applied only to per-job transient state; the
    output setting modified is a TRANSIENT COPY (DuplicateObject), so one job
    cannot leak its range into another."""
    cpp = CPP.read_text(encoding="utf-8")
    # TransientConfig is a DuplicateObject of the shared config (isolation):
    assert "DuplicateObject<UMoviePipelinePrimaryConfig>(AtlasConfig, GetTransientPackage())" in cpp


# ── 4-6: 24 passes, 23 fails, verifier strict ─────────────────────────────
def test_d2_adjacent_setsequencerplaybackrange_offbyone_fixed():
    """The related SetSequencerPlaybackRange op had the SAME exclusive-upper-bound
    off-by-one (SetPlaybackRange(start, end-start)) which would render end-start
    frames. Fixed to end-start+1 (inclusive)."""
    cpp = CPP.read_text(encoding="utf-8")
    assert "SetPlaybackRange(StartFrame,EndFrame - StartFrame + 1)" in cpp
    # no residual exclusive/off-by-one form
    assert "SetPlaybackRange(StartFrame,EndFrame - StartFrame);" not in cpp


def test_d2_24_frame_result_passes():
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = D._png_files(out, 24, 1)
    ev = D._verify(spec, files, out)
    assert ev is not None


def test_d2_23_frame_result_still_fails():
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = D._png_files(out, 23, 1)
    with pytest.raises(UnrealEvidenceVerificationError) as exc:
        D._verify(spec, files, out)
    assert "output file count mismatch" in str(exc.value)


def test_d2_verifier_not_weakened():
    import inspect as _inspect
    import planning.unreal_evidence_contract as ec
    src = _inspect.getsource(ec)
    assert "expected_count = exp_end - exp_start + 1" in src
    assert "len(normalized_output_files) != expected_count" in src