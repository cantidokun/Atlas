"""Deterministic one-step-at-a-time planner for object transform goals."""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Mapping, Sequence

from action_plan import ActionSpec


@dataclass(frozen=True)
class TransformTarget:
    object_name: str
    location: tuple[float, float, float]
    rotation_degrees: tuple[float, float, float]


def _matches(current: Sequence[float], target: Sequence[float], tolerance: float) -> bool:
    return len(current) == len(target) and all(
        isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)
        for actual, expected in zip(current, target)
    )


def plan_transform_correction(
    evidence: Mapping[str, Mapping[str, Sequence[float]]],
    targets: Sequence[TransformTarget],
    file_name: str,
    tolerance: float = 1e-4,
) -> list[ActionSpec]:
    """Return exactly the next necessary mutation, or no action when converged."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    for target in targets:
        current = evidence.get(target.object_name)
        if current is None:
            raise RuntimeError(f"missing transform evidence for {target.object_name}")

        if not _matches(current["location"], target.location, tolerance):
            return [ActionSpec(
                tool="move_object",
                arguments={
                    "file_name": file_name,
                    "object_name": target.object_name,
                    "location": list(target.location),
                },
                name=f"move {target.object_name} to target",
                requires_success=True,
            )]

        if not _matches(current["rotation"], target.rotation_degrees, tolerance):
            return [ActionSpec(
                tool="set_object_rotation",
                arguments={
                    "file_name": file_name,
                    "object_name": target.object_name,
                    "rotation_degrees": list(target.rotation_degrees),
                },
                name=f"rotate {target.object_name} to target",
                requires_success=True,
            )]

    return []
