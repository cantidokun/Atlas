from pathlib import Path

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_continuity import verify_render_job_continuity

TARGET = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"


def _evidence(tmp_path, *, start=1, end=3, sequence=SEQUENCE, output_directory="Saved/AtlasProductionOutput", output_format="png", frames=None):
    output_root = Path(output_directory)
    if not output_root.is_absolute():
        output_root = Path.cwd() / "unreal" / "AtlasUnrealHarness" / output_root
    output_root.mkdir(parents=True, exist_ok=True)

    frame_values = list(range(start, end + 1)) if frames is None else list(frames)
    outputs = []
    for frame in frame_values:
        path = output_root / f"shot_{frame:04d}.png"
        path.write_bytes(b"png")
        outputs.append(str(path.resolve()))

    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": "job-continuity",
            "sequence_asset_path": sequence,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "start_frame": start,
            "end_frame": end,
            "output_directory": output_directory,
            "output_format": output_format,
            "output_files": outputs,
        },
        source="render-continuity-test",
        verified=True,
    )


def _verify(evidence, output_directory="Saved/AtlasProductionOutput"):
    return verify_render_job_continuity(
        evidence,
        expected_sequence_asset_path=SEQUENCE,
        expected_start_frame=1,
        expected_end_frame=3,
        expected_output_directory=output_directory,
        expected_output_format="png",
    )


def test_render_continuity_accepts_exact_authorized_range_and_complete_png_set(tmp_path):
    assert _verify(_evidence(tmp_path)) is not None


def test_render_continuity_rejects_sequence_mismatch(tmp_path):
    with pytest.raises(ValueError, match="sequence continuity mismatch"):
        _verify(_evidence(tmp_path, sequence="/Game/AtlasTest/OtherSequence"))


def test_render_continuity_rejects_frame_range_mismatch(tmp_path):
    evidence = _evidence(tmp_path, start=1, end=4)
    with pytest.raises(ValueError, match="frame continuity mismatch"):
        _verify(evidence)


def test_render_continuity_rejects_output_directory_mismatch(tmp_path):
    evidence = _evidence(tmp_path, output_directory="Saved/OtherOutput")
    with pytest.raises(ValueError, match="output directory continuity mismatch"):
        _verify(evidence)


def test_render_continuity_rejects_output_format_mismatch(tmp_path):
    evidence = _evidence(tmp_path, output_format="jpg")
    with pytest.raises(ValueError, match="output format continuity mismatch"):
        _verify(evidence)


def test_render_continuity_rejects_missing_frame(tmp_path):
    evidence = _evidence(tmp_path, frames=[1, 3])
    with pytest.raises(ValueError, match="frame coverage mismatch"):
        _verify(evidence)


def test_render_continuity_rejects_extra_frame(tmp_path):
    evidence = _evidence(tmp_path, frames=[1, 2, 3, 4])
    with pytest.raises(ValueError, match="frame coverage mismatch"):
        _verify(evidence)


def test_render_continuity_rejects_duplicate_frame(tmp_path):
    evidence = _evidence(tmp_path, frames=[1, 2, 2])
    with pytest.raises(ValueError, match="duplicate render artifact frame"):
        _verify(evidence)


def test_render_continuity_rejects_non_png_artifact(tmp_path):
    evidence = _evidence(tmp_path)
    bad = tmp_path / "shot_0003.jpg"
    bad.write_bytes(b"jpg")
    state = evidence.snapshot()["observed_state"]
    state["output_files"][-1] = str(bad.resolve())
    evidence = UnrealEvidence.from_snapshot({**evidence.snapshot(), "observed_state": state})
    with pytest.raises(ValueError, match="not a PNG"):
        _verify(evidence)
