"""High-level Unreal production-shot orchestration.

This module composes existing authorized Unreal planning primitives into one
ordered shot-production plan. It deliberately introduces no new transport
primitive and does not authorize or execute anything itself.
"""
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from planning.unreal_composite_operation import CompositeActorProductionOperation
from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner
from planning.unreal_agent import UnrealTaskIntent


@dataclass(frozen=True)
class UnrealProductionShotRequest:
    """Validated inputs for a complete derived production-shot plan."""

    composite: CompositeActorProductionOperation
    start_frame: int
    end_frame: int
    render_config: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.composite, CompositeActorProductionOperation):
            raise TypeError("composite must be a CompositeActorProductionOperation")
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise TypeError("start_frame must be an integer")
        if isinstance(self.end_frame, bool) or not isinstance(self.end_frame, int):
            raise TypeError("end_frame must be an integer")
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must not exceed end_frame")
        if not isinstance(self.render_config, Mapping):
            raise TypeError("render_config must be a mapping")


def build_production_shot_plan(
    planner: UnrealTaskPlanner,
    intent: UnrealTaskIntent,
    request: UnrealProductionShotRequest,
) -> UnrealTaskPlan:
    """Compose actor state, shot range, and render configuration in order.

    The returned plan remains a normal ``UnrealTaskPlan``. Each mutation keeps
    the existing immediate verification boundary, while Sequencer and Render
    retain their own inspection/write/verify contracts.
    """
    if not isinstance(planner, UnrealTaskPlanner):
        raise TypeError("planner must be an UnrealTaskPlanner")
    if not isinstance(intent, UnrealTaskIntent):
        raise TypeError("intent must be an UnrealTaskIntent")
    if not isinstance(request, UnrealProductionShotRequest):
        raise TypeError("request must be an UnrealProductionShotRequest")
    if tuple(intent.target_entity_ids) != request.composite.entity_ids:
        raise ValueError("composite entity_ids must exactly match intent target_entity_ids")

    actor_plan = planner.plan_composite_actor_production(intent, request.composite)
    sequencer_plan = planner.plan_sequencer_playback_range(
        intent, request.start_frame, request.end_frame
    )
    render_plan = planner.plan_render_configuration(intent, request.render_config)
    return planner.compose_plans(intent, (actor_plan, sequencer_plan, render_plan))
