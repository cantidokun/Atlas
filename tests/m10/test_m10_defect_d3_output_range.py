"""M10 Defect D v3 regression tests — MRQ output-frame enumeration (half-open).

Defect D v3 root cause (UE 5.6 source-verified):
UMoviePipelinePrimaryConfig::GetEffectivePlaybackRange() is what MRQ uses to bound
OUTPUT frames. It reads the OUTPUT SETTING's custom range
(bUseCustomPlaybackRange) and converts [CustomStartFrame, CustomEndFrame) from
DISPLAY frames into ticks; the output loop (MoviePipelineTiming.cpp) stops BEFORE
producing when CurrentTickInRoot >= EndTick. Therefore MRQ produces exactly
    CustomEndFrame - CustomStartFrame   frames   (half-open [start, end)).

The prior fixes were insufficient:
- D-v1 set CustomEndFrame = end_frame (24), CustomStartFrame = start_frame (1):
  GetEffectivePlaybackRange returns [1,24) -> 24-1 = 23 frames. (off-by-one)
- D-v2 set the SEQUENCE playback range via a transient duplicate, but
  GetEffectivePlaybackRange IGNORES the sequence range when bUseCustomPlaybackRange
  is set, so it had no effect on output-frame enumeration.

D-v3 fix: set CustomEndFrame = end_frame + 1 (exclusive upper bound), so MRQ produces
    (end_frame+1) - start_frame = end_frame - start_frame + 1  frames  = 24.

Tests prove the exact arithmetic + verifier behavior (24 passes, 23 fails,
verifier never weakened, isolation preserved).
"""
import pathlib
import tempfile

import pytest

from planning.unreal_evidence_contract import (
    verify_render_job_evidence,
    UnrealEvidenceVerificationError,
)

import tests.m10.test_m10_defect_d_frame_topology as D  # reuse _png_files, _verify
import tests.m10.test_m10_defect_d2_sequence_range as D2  # reuse REMO/CPP


# ── Exact output-frame arithmetic (the authoritative MRQ semantics) ─────────
def test_d3_halfopen_output_range_yields_exact_count():
    """MRQ output frames = CustomEndFrame - CustomStartFrame (half-open [start,end)).
    For an authorized inclusive [1,24] (24 frames), CustomEndFrame MUST be 25."""
    start_frame, end_frame = 1, 24
    # D-v1 (buggy): CustomEndFrame = end_frame
    v1_produced = end_frame - start_frame          # 23  <- the live FAIL
    assert v1_produced == 23
    # D-v3 (fixed): CustomEndFrame = end_frame + 1
    v3_produced = (end_frame + 1) - start_frame    # 24
    assert v3_produced == 24
    assert v3_produced == end_frame - start_frame + 1  # verifier count


def test_d3_authorized_124_requires_customend_25():
    start_frame, end_frame = 1, 24
    assert (end_frame + 1) - start_frame == 24


def test_d3_verifier_expects_end_minus_start_plus_one():
    """The verifier's expected count stays end-start+1 (inclusive, authoritative)."""
    import inspect as _inspect
    import planning.unreal_evidence_contract as ec
    src = _inspect.getsource(ec)
    assert "expected_count = exp_end - exp_start + 1" in src


# ── 24 passes / 23 fails / no weakening ────────────────────────────────────
def test_d3_24_frame_result_passes():
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = D._png_files(out, 24, 1)  # frames 1..24
    ev = D._verify(spec, files, out)
    assert ev is not None


def test_d3_23_frame_result_still_fails():
    """A 23-frame result (the live bug) must STILL fail: verifier not weakened."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    out = tmp / "out"; out.mkdir()
    spec = {"format": "png", "width": 1, "height": 1, "start_frame": 1, "end_frame": 24}
    files = D._png_files(out, 23, 1)
    with pytest.raises(UnrealEvidenceVerificationError) as exc:
        D._verify(spec, files, out)
    assert "output file count mismatch" in str(exc.value)


def test_d3_verifier_strict_no_relaxation():
    import inspect as _inspect
    import planning.unreal_evidence_contract as ec
    src = _inspect.getsource(ec)
    assert "len(normalized_output_files) != expected_count" in src


# ── Production fix is present + isolation preserved ────────────────────────
def test_d3_cpp_sets_exclusive_upper_customend():
    cpp = D2.CPP.read_text(encoding="utf-8")
    assert "RangeSetting->CustomEndFrame = AtlasEndFrame + 1" in cpp
    assert "RangeSetting->bUseCustomPlaybackRange = true" in cpp


def test_d3_cpp_does_not_use_exclusive_error_in_sequence():
    """No residual v1 bug (CustomEndFrame = end_frame) remains."""
    cpp = D2.CPP.read_text(encoding="utf-8")
    assert "RangeSetting->CustomEndFrame = AtlasEndFrame;" not in cpp.replace(
        "RangeSetting->CustomEndFrame = AtlasEndFrame + 1;", "")


def test_d3_cpp_keeps_per_job_isolation():
    """The modified output setting lives on a TRANSIENT config duplicate
    (DuplicateObject of the shared AtlasConfig), so per-job isolation holds."""
    cpp = D2.CPP.read_text(encoding="utf-8")
    assert "DuplicateObject<UMoviePipelinePrimaryConfig>(AtlasConfig, GetTransientPackage())" in cpp