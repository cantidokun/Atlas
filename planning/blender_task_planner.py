"""Deterministic planning helpers for constrained Blender objectives.

The planner converts a small, explicit objective into an authorized ActionPlan.
It deliberately does not execute Blender tools or infer arbitrary Python calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from planning.action_plan import ActionPlan, ActionSpec


_ALLOWED_TOOLS = frozenset({"inspect_object_transform", "move_object"})


@dataclass(frozen=True)
class MoveObjectGoal:
    """High-level request to move one Blender object by a relative delta."""

    object_name: str
    delta: tuple[float, float, float]
    authorization_id: str


def _vector(value: Sequence[float], field: str) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)) or len(value) != 3:
        raise ValueError(f"{field} must contain exactly three numeric values")
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must contain numeric values") from exc
    return result  # type: ignore[return-value]


def plan_move_object(
    goal: MoveObjectGoal,
    *,
    observed_locations: Mapping[str, Sequence[float]],
) -> ActionPlan:
    """Compile a relative move objective into inspect/move/inspect actions.

    The starting location must come from fresh scene evidence supplied by the
    caller; the planner never invents Blender state.
    """
    if not isinstance(goal.object_name, str) or not goal.object_name.strip():
        raise ValueError("object_name must be a non-empty string")
    if not isinstance(observed_locations, Mapping):
        raise TypeError("observed_locations must be a mapping")
    if goal.object_name not in observed_locations:
        raise ValueError(f"no observed location for target object: {goal.object_name}")

    before = _vector(observed_locations[goal.object_name], "observed location")
    delta = _vector(goal.delta, "delta")
    target = tuple(before[index] + delta[index] for index in range(3))

    actions = [
        ActionSpec(
            tool="inspect_object_transform",
            arguments={"object_name": goal.object_name},
            name="verify_target_before_move",
        ),
        ActionSpec(
            tool="move_object",
            arguments={"object_name": goal.object_name, "location": list(target)},
            name="apply_relative_move",
        ),
        ActionSpec(
            tool="inspect_object_transform",
            arguments={"object_name": goal.object_name},
            name="verify_target_after_move",
        ),
    ]
    if any(action.tool not in _ALLOWED_TOOLS for action in actions):
        raise ValueError("planner produced a tool outside the approved Blender surface")

    plan = ActionPlan(actions)
    plan.authorize_with_id(goal.authorization_id)
    return plan
