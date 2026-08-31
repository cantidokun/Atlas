"""Capability-constrained planning primitives for Blender tasks.

This module deliberately does not ask an LLM to execute tools. It converts a
prevalidated task intent into an ActionPlan only when every proposed Blender
action exists in the canonical capability surface and its arguments satisfy the
canonical tool schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List

from controller.blender_capabilities import BLENDER_CAPABILITIES
from planning.action_plan import ActionPlan, ActionSpec
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.blender_tool_schema import validate_blender_tool_call


class BlenderPlanningError(ValueError):
    """Raised when a proposed Blender task cannot produce a safe plan."""


@dataclass(frozen=True)
class BlenderTaskIntent:
    """Normalized task intent supplied by an upstream reasoning component."""

    task_id: str
    objective: str
    actions: tuple[ActionSpec, ...]


class BlenderTaskPlanner:
    """Compile normalized Blender intent into a capability-valid action plan."""

    def __init__(self, capabilities: Iterable[Any] = BLENDER_CAPABILITIES):
        self._capabilities = {capability.name: capability for capability in capabilities}

    def plan(self, intent: BlenderTaskIntent) -> ActionPlan:
        if not isinstance(intent, BlenderTaskIntent):
            raise BlenderPlanningError("intent must be a BlenderTaskIntent")
        if not isinstance(intent.task_id, str) or not intent.task_id.strip():
            raise BlenderPlanningError("task_id must be non-empty")
        if not isinstance(intent.objective, str) or not intent.objective.strip():
            raise BlenderPlanningError("objective must be non-empty")
        if not intent.actions:
            raise BlenderPlanningError("task must contain at least one action")

        validated: List[ActionSpec] = []
        for action in intent.actions:
            if not isinstance(action, ActionSpec):
                raise BlenderPlanningError("all task actions must be ActionSpec objects")

            capability = self._capabilities.get(action.tool)
            if capability is None:
                raise BlenderPlanningError(f"Blender capability is not registered: {action.tool}")

            try:
                arguments = validate_blender_tool_call(action.tool, action.arguments)
            except (TypeError, ValueError) as exc:
                raise BlenderPlanningError(
                    f"invalid arguments for Blender action '{action.tool}': {exc}"
                ) from exc

            validated.append(
                ActionSpec(
                    tool=action.tool,
                    arguments=arguments,
                    name=action.name or action.tool,
                    requires_success=action.requires_success,
                )
            )

        return ActionPlan(actions=validated)

    def plan_goal(self, goal: AutonomousProductionGoal) -> ActionPlan:
        """Compile a production goal through the same capability/schema gates."""
        if not isinstance(goal, AutonomousProductionGoal):
            raise BlenderPlanningError("goal must be an AutonomousProductionGoal")
        return self.plan(
            BlenderTaskIntent(
                task_id=goal.goal_id,
                objective=goal.objective,
                actions=goal.actions,
            )
        )

    def capability_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))
