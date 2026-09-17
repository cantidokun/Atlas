"""Authorized-value continuity checks for one heterogeneous Unreal shot.

This module does not authorize work and does not inspect or discover Unreal
state. It only compares fresh render-job evidence against values already bound
to the caller's production intent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from planning.unreal_render_contract import UnrealRenderConfig, UNREAL_PROJECT_ROOT
from planning.unreal_task_planner import UnrealTaskPlan


_FRAME_SUFFIX = re.compile(r"(\d+)(?=\.[^.]+$)")


def _canonical_output_directory(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("output_directory must be a non-empty string")
    path = Path(value.strip())
    if not path.is_absolute():
        path = UNREAL_PROJECT_ROOT / path
    return str(path.resolve()).replace("\\", "/").rstrip("/")


@dataclass(frozen=True)
class UnrealShotContinuity:
    """Values authorized for one shot across sequencing and final render."""

    sequence_asset_path: str
    start_frame: int
    end_frame: int
    output_directory: str
    output_format: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence_asset_path, str) or not self.sequence_asset_path.strip():
            raise ValueError("sequence_asset_path must be a non-empty string")
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise TypeError("start_frame must be an integer")
        if isinstance(self.end_frame, bool) or not isinstance(self.end_frame, int):
            raise TypeError("end_frame must be an integer")
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must not exceed end_frame")
        if not isinstance(self.output_format, str) or not self.output_format.strip():
            raise ValueError("output_format must be a non-empty string")
        object.__setattr__(self, "sequence_asset_path", self.sequence_asset_path.strip())
        object.__setattr__(self, "output_format", self.output_format.strip().lower())
        object.__setattr__(self, "output_directory", _canonical_output_directory(self.output_directory))

    @property
    def expected_frame_count(self) -> int:
        return self.end_frame - self.start_frame + 1

    @classmethod
    def from_production_plan(
        cls,
        plan: UnrealTaskPlan,
        sequence_asset_path: str,
    ) -> "UnrealShotContinuity":
        if not isinstance(plan, UnrealTaskPlan):
            raise TypeError("plan must be a UnrealTaskPlan instance")
        configure = next(
            (operation for operation in plan.operations if operation.name == "configure_render"),
            None,
        )
        if configure is None:
            raise ValueError("production plan does not contain configure_render")
        args = configure.arguments
        required = {
            "start_frame",
            "end_frame",
            "output_directory",
            "output_format",
        }
        if not required.issubset(args):
            raise ValueError("configure_render does not contain complete continuity fields")
        return cls(
            sequence_asset_path=sequence_asset_path,
            start_frame=args["start_frame"],
            end_frame=args["end_frame"],
            output_directory=args["output_directory"],
            output_format=args["output_format"],
        )

    def verify_job_state(self, state: Mapping[str, object]) -> None:
        if not isinstance(state, Mapping):
            raise ValueError("render job state must be a mapping")
        checks = {
            "sequence_asset_path": self.sequence_asset_path,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "output_format": self.output_format,
        }
        for key, expected in checks.items():
            observed = state.get(key)
            if key == "output_format" and isinstance(observed, str):
                observed = observed.strip().lower()
            if observed != expected:
                raise ValueError(
                    f"render continuity mismatch for {key}: expected={expected!r}, observed={observed!r}"
                )

        observed_directory = _canonical_output_directory(state.get("output_directory", ""))
        if observed_directory != self.output_directory:
            raise ValueError(
                "render continuity mismatch for output_directory: "
                f"expected={self.output_directory!r}, observed={observed_directory!r}"
            )

    def verify_artifacts(self, output_files: Sequence[str], *, require_files=True) -> None:
        if not isinstance(output_files, (list, tuple)):
            raise TypeError("render job output_files must be a list")
        if len(output_files) != self.expected_frame_count:
            raise ValueError(
                "render artifact frame count does not match authorized range: "
                f"expected={self.expected_frame_count}, observed={len(output_files)}"
            )

        if self.output_format != "png":
            raise ValueError(
                f"render artifact continuity is only defined for png output, observed={self.output_format!r}"
            )

        observed_frames = []
        for value in output_files:
            if not isinstance(value, str) or not value.strip():
                raise ValueError("render job output_files must contain non-empty strings")
            path = Path(value)
            if require_files and path.is_absolute():
                if not path.exists() or not path.is_file():
                    raise ValueError(f"render artifact does not exist: {path}")
                if path.stat().st_size <= 0:
                    raise ValueError(f"render artifact is empty: {path}")
            match = _FRAME_SUFFIX.search(path.name)
            if match is None:
                raise ValueError(f"render artifact does not expose a frame number: {path.name}")
            observed_frames.append(int(match.group(1)))

        expected_frames = list(range(self.start_frame, self.end_frame + 1))
        if sorted(observed_frames) != expected_frames:
            raise ValueError(
                "render artifact frame coverage does not match authorized range: "
                f"expected={expected_frames!r}, observed={sorted(observed_frames)!r}"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence_asset_path": self.sequence_asset_path,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "expected_frame_count": self.expected_frame_count,
            "output_directory": self.output_directory,
            "output_format": self.output_format,
        }
