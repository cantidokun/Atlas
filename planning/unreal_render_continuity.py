"""Fail-closed continuity verification for one authorized Unreal render.

This module stays above the transport boundary. It compares fresh final render-job
 evidence with the values already authorized in the production plan and verifies
that the reported PNG artifacts cover the complete inclusive frame range.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from planning.unreal_render_contract import UNREAL_PROJECT_ROOT
from planning.unreal_evidence_contract import UnrealEvidence


_FRAME_RE = re.compile(r"(?:^|[_.-])(-?\d+)\.png$", re.IGNORECASE)


def _job_state(evidence: UnrealEvidence) -> Mapping:
    state = evidence.observed_state
    if not isinstance(state, Mapping):
        raise ValueError("render-job evidence observed_state must be a mapping")

    if "job_id" in state:
        job_state = state
    elif len(state) == 1:
        candidate = next(iter(state.values()))
        job_state = candidate.get("render_job") if isinstance(candidate, Mapping) else None
    else:
        job_state = None

    if not isinstance(job_state, Mapping):
        raise ValueError("render-job evidence does not contain a render_job object")
    return job_state


def _canonical_directory(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("output_directory must be a non-empty string")
    path = Path(value.strip())
    if not path.is_absolute():
        path = UNREAL_PROJECT_ROOT / path
    return str(path.resolve()).replace("\\", "/").rstrip("/")


def _frame_number(path: str) -> int:
    match = _FRAME_RE.search(Path(path).name)
    if not match:
        raise ValueError(f"render artifact does not contain a terminal PNG frame number: {path!r}")
    return int(match.group(1))


def verify_render_job_continuity(
    evidence: UnrealEvidence,
    *,
    expected_sequence_asset_path: str,
    expected_start_frame: int,
    expected_end_frame: int,
    expected_output_directory: str,
    expected_output_format: str,
) -> UnrealEvidence:
    """Verify final render evidence against the authorized production values."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence instance")
    if evidence.operation_name != "inspect_render_job":
        raise ValueError("render continuity requires inspect_render_job evidence")
    if not isinstance(expected_sequence_asset_path, str) or not expected_sequence_asset_path.strip():
        raise ValueError("expected_sequence_asset_path must be a non-empty string")
    if isinstance(expected_start_frame, bool) or not isinstance(expected_start_frame, int):
        raise TypeError("expected_start_frame must be an integer")
    if isinstance(expected_end_frame, bool) or not isinstance(expected_end_frame, int):
        raise TypeError("expected_end_frame must be an integer")
    if expected_start_frame > expected_end_frame:
        raise ValueError("expected_start_frame must not exceed expected_end_frame")
    if not isinstance(expected_output_format, str) or not expected_output_format.strip():
        raise ValueError("expected_output_format must be a non-empty string")

    state = _job_state(evidence)

    sequence = state.get("sequence_asset_path")
    if sequence != expected_sequence_asset_path:
        raise ValueError(
            "render sequence continuity mismatch: "
            f"expected={expected_sequence_asset_path!r}, observed={sequence!r}"
        )

    actual_start = state.get("start_frame")
    actual_end = state.get("end_frame")
    if isinstance(actual_start, bool) or not isinstance(actual_start, int):
        raise ValueError("final render evidence must contain an integer start_frame")
    if isinstance(actual_end, bool) or not isinstance(actual_end, int):
        raise ValueError("final render evidence must contain an integer end_frame")
    if (actual_start, actual_end) != (expected_start_frame, expected_end_frame):
        raise ValueError(
            "render frame continuity mismatch: "
            f"expected={expected_start_frame}-{expected_end_frame}, "
            f"observed={actual_start}-{actual_end}"
        )

    actual_directory = _canonical_directory(state.get("output_directory"))
    expected_directory = _canonical_directory(expected_output_directory)
    if actual_directory != expected_directory:
        raise ValueError(
            "render output directory continuity mismatch: "
            f"expected={expected_directory!r}, observed={actual_directory!r}"
        )

    actual_format = state.get("output_format")
    if not isinstance(actual_format, str) or actual_format.strip().lower() != expected_output_format.strip().lower():
        raise ValueError(
            "render output format continuity mismatch: "
            f"expected={expected_output_format!r}, observed={actual_format!r}"
        )

    output_files = state.get("output_files")
    if not isinstance(output_files, (list, tuple)) or not output_files:
        raise ValueError("final render evidence must contain output_files")

    expected_frames = set(range(expected_start_frame, expected_end_frame + 1))
    observed_frames = set()

    for value in output_files:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("render output_files must contain non-empty strings")
        path = Path(value)
        if not path.is_absolute():
            path = Path(actual_directory) / path
        if path.suffix.lower() != ".png":
            raise ValueError(f"render artifact is not a PNG file: {value!r}")
        if not path.exists() or not path.is_file():
            raise ValueError(f"render artifact does not exist: {str(path)!r}")
        frame = _frame_number(value)
        if frame in observed_frames:
            raise ValueError(f"duplicate render artifact frame: {frame}")
        observed_frames.add(frame)

    if observed_frames != expected_frames:
        missing = sorted(expected_frames - observed_frames)
        extra = sorted(observed_frames - expected_frames)
        raise ValueError(
            "render artifact frame coverage mismatch: "
            f"missing={missing!r}, extra={extra!r}"
        )

    return evidence
