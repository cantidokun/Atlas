"""Narrow shot-level production continuity contract for the Atlas Unreal Agent.

This module freezes the values that must stay identical from the authorized
production intent through the fresh render-job evidence that closes one shot,
and it verifies that continuity at the evidence boundary.

It is deliberately a value contract plus a verification boundary only. It
creates no authorization, performs no transport call, caches no entity state,
and introduces no transport operation. The contract stays language-agnostic:
the canonical payload and digest rule below can be re-implemented by a non
Python boundary without changing the semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from planning.unreal_render_contract import canonicalize_output_directory
from planning.unreal_render_job_verifier import resolve_render_job_state

PNG_OUTPUT_FORMAT = "png"

# The render-job artifact naming convention terminates each per-frame artifact
# with its frame number before the file extension.
_FRAME_NUMBER_SUFFIX = re.compile(r"(\d+)(?=\.[^.]+$)")


def resolve_artifact_frame_number(value: str) -> int:
    """Return the frame number encoded in one render artifact path."""
    match = _FRAME_NUMBER_SUFFIX.search(str(value))
    if match is None:
        raise ValueError(
            f"render artifact does not expose a frame number: {value!r}"
        )
    return int(match.group(1))


def _require_frame(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _require_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_canonical_path(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a non-empty canonical Unreal package path")
    if not value.startswith("/"):
        raise ValueError(f"{name} must be a non-empty canonical Unreal package path")
    return value


@dataclass(frozen=True)
class UnrealShotContinuity:
    """Authorization-bound values that span production, submission, and evidence.

    The record is declared once, at the production level, and is then compared
    against fresh engine evidence instead of being echoed back into a
    verification decision.
    """

    sequence_asset_path: str
    start_frame: int
    end_frame: int
    output_directory: str
    output_format: str

    def __post_init__(self) -> None:
        _require_canonical_path("sequence_asset_path", self.sequence_asset_path)
        _require_frame("start_frame", self.start_frame)
        _require_frame("end_frame", self.end_frame)
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must not exceed end_frame")
        _require_string("output_directory", self.output_directory)
        _require_string("output_format", self.output_format)

    @property
    def expected_frame_count(self) -> int:
        """Number of frames the authorized range covers, inclusive."""
        return self.end_frame - self.start_frame + 1

    @property
    def end_frame_exclusive(self) -> int:
        """Half-open boundary form of the authorized inclusive end frame.

        Atlas authorizes inclusive frame ranges. An engine that stores its
        effective range half-open (``[start, end_exclusive)``) translates the
        authorized end frame at its own boundary; this property is that
        translation, so the boundary rule is explicit and testable instead of
        implicit in one transport implementation.
        """
        return self.end_frame + 1

    @property
    def normalized_output_format(self) -> str:
        """Case-insensitive comparison form of the authorized output format."""
        return self.output_format.strip().lower()

    def canonical_payload(self) -> dict:
        """Return the exact value graph that defines this continuity identity."""
        return {
            "sequence_asset_path": self.sequence_asset_path,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "output_directory": self.output_directory,
            "output_format": self.output_format,
        }

    @property
    def continuity_digest(self) -> str:
        """Deterministic identity of this exact continuity contract."""
        canonical = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def snapshot(self) -> dict:
        """Return a detached JSON-compatible continuity snapshot."""
        return dict(self.canonical_payload())


def _observed_string(state: Mapping, name: str, evidence_label: str) -> str:
    value = state.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{evidence_label} does not expose {name}"
        )
    return value


def verify_shot_continuity_identity(evidence, expected: UnrealShotContinuity):
    """Verify authorized shot identity against fresh render-job evidence.

    Compares the authorized sequence asset path, frame range, output
    directory, and output format with what the engine reports for the exact
    submitted job. Missing fields fail closed: absence of a value in fresh
    evidence is never treated as agreement.
    """
    if not isinstance(expected, UnrealShotContinuity):
        raise TypeError("expected must be an UnrealShotContinuity instance")

    state = resolve_render_job_state(evidence)

    observed_path = _observed_string(
        state,
        "sequence_asset_path",
        "render job evidence",
    )
    if observed_path != expected.sequence_asset_path:
        raise ValueError(
            "render job sequence_asset_path mismatch: "
            f"expected sequence_asset_path={expected.sequence_asset_path!r}, "
            f"observed sequence_asset_path={observed_path!r}"
        )

    if "start_frame" not in state or "end_frame" not in state:
        raise ValueError(
            "render job evidence does not expose the effective "
            "start_frame/end_frame range"
        )

    observed_start = state["start_frame"]
    observed_end = state["end_frame"]

    if isinstance(observed_start, bool) or not isinstance(observed_start, int):
        raise TypeError("render job start_frame must be an integer")
    if isinstance(observed_end, bool) or not isinstance(observed_end, int):
        raise TypeError("render job end_frame must be an integer")

    if (observed_start, observed_end) != (expected.start_frame, expected.end_frame):
        raise ValueError(
            "render job effective frame range mismatch: "
            f"expected frames={expected.start_frame}-{expected.end_frame}, "
            f"observed frames={observed_start}-{observed_end}"
        )

    if "end_frame_exclusive" in state:
        observed_exclusive = state["end_frame_exclusive"]

        if isinstance(observed_exclusive, bool) or not isinstance(observed_exclusive, int):
            raise TypeError("render job end_frame_exclusive must be an integer")

        if observed_exclusive != expected.end_frame_exclusive:
            raise ValueError(
                "render job effective half-open boundary does not correspond to the "
                "authorized inclusive frame range: "
                f"expected end_frame_exclusive={expected.end_frame_exclusive}, "
                f"observed end_frame_exclusive={observed_exclusive}"
            )

    observed_directory = _observed_string(
        state,
        "output_directory",
        "render job evidence",
    )
    if canonicalize_output_directory(
        observed_directory
    ) != canonicalize_output_directory(expected.output_directory):
        raise ValueError(
            "render job output_directory mismatch: "
            f"expected output_directory={expected.output_directory!r}, "
            f"observed output_directory={observed_directory!r}"
        )

    observed_format = _observed_string(
        state,
        "output_format",
        "render job evidence",
    )
    if observed_format.strip().lower() != expected.normalized_output_format:
        raise ValueError(
            "render job output_format mismatch: "
            f"expected output_format={expected.output_format!r}, "
            f"observed output_format={observed_format!r}"
        )

    return evidence


def verify_shot_continuity_completeness(evidence, expected: UnrealShotContinuity):
    """Verify shot identity plus authorized frame coverage of the artifacts.

    Coverage is defined only for the current PNG image-sequence boundary: the
    observed artifact set must cover exactly the authorized inclusive frame
    range - one unique file per authorized frame, with the frame number parsed
    from the artifact name, no duplicate frames, and no extra frames. The count
    check runs first, so a short or inflated artifact list fails before frame
    identity is read. Other output formats keep the existing existence and
    non-empty validation only, because they have no authorized per-frame
    artifact contract.
    """
    verify_shot_continuity_identity(evidence, expected)

    if expected.normalized_output_format != PNG_OUTPUT_FORMAT:
        return evidence

    state = resolve_render_job_state(evidence)
    output_files = state.get("output_files", [])

    if not isinstance(output_files, (list, tuple)):
        raise TypeError("render job output_files must be a list")

    unique = set()
    observed_frames = set()

    for value in output_files:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "render job output_files must contain non-empty strings"
            )
        unique.add(value)

        frame = resolve_artifact_frame_number(value)

        if frame in observed_frames:
            raise ValueError(
                f"render job PNG artifacts contain duplicate frame {frame}"
            )

        observed_frames.add(frame)

    expected_count = expected.expected_frame_count

    if len(unique) != expected_count:
        raise ValueError(
            "render job PNG frame coverage mismatch: "
            f"expected unique_output_files={expected_count} for frames "
            f"{expected.start_frame}-{expected.end_frame}, "
            f"observed unique_output_files={len(unique)}"
        )

    expected_frames = set(
        range(expected.start_frame, expected.end_frame + 1)
    )

    if observed_frames != expected_frames:
        raise ValueError(
            "render job PNG frame set mismatch: "
            f"missing={sorted(expected_frames - observed_frames)}, "
            f"extra={sorted(observed_frames - expected_frames)}"
        )

    return evidence
