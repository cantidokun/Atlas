"""Deterministic one-step-at-a-time planner for object transform goals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from action_plan import ActionSpec


@dataclass(frozen=True)
class TransformTarget:
    object_name: str
    location: tuple[float, float, float]
    rotation_degrees: tuple[float, float, float]


def plan_transform_correction(
    evidence: Mapping[str, Mapping[str, Sequence[float]]],
    targets: Sequence[TransformTarget],
    file_name: str,
) -> list[ActionSpec]:
    """Return exactly the next necessary mutation, or no action when converged."""
    for target in targets:
        current = evidence.get(target.object_name)
        if current is None:
            raise RuntimeError(f"missing transform evidence for {target.object_name}")

        if list(current["location"]) != list(target.location):
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

        if list(current["rotation"]) != list(target.rotation_degrees):
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
