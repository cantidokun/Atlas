"""Reusable declarative soccer-production workflow templates for Atlas.

Templates only construct semantic production-task fragments. They never execute,
authorize, schedule, or verify work; callers still compile into the canonical
ProductionTaskDefinition/AtlasTaskDefinition path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.production_task_composition import ProductionTaskFragment, compose_production_task
from planning.target_state import StateInvariant, TargetStateEvaluator


@dataclass(frozen=True)
class SoccerGoalTransformWorkflowSpec:
    """Declarative inputs for a reusable goal-preparation workflow."""

    name: str
    objective: str
    blend_file: Path
    object_name: str
    target_location: Tuple[float, float, float]
    target_rotation: Tuple[float, float, float]
    domain: str = "soccer-production"
    deliverables: Tuple[str, ...] = ("broadcast-ready goal transform",)
    constraints: Tuple[str, ...] = ("preserve canonical scene", "verify final transform")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("workflow name must not be empty")
        if not self.objective.strip():
            raise ValueError("workflow objective must not be empty")
        if not self.object_name.strip():
            raise ValueError("workflow object name must not be empty")
        if len(self.target_location) != 3 or len(self.target_rotation) != 3:
            raise ValueError("workflow transforms must contain exactly three values")


def build_broadcast_goal_preparation(
    *,
    blend_file: Path,
    object_name: str,
    target_location: Sequence[float],
    target_rotation: Sequence[float],
) -> object:
    """Build the standard broadcast-goal preparation production task."""
    location = tuple(float(value) for value in target_location)
    rotation = tuple(float(value) for value in target_rotation)
    spec = SoccerGoalTransformWorkflowSpec(
        name="prepare-broadcast-goal",
        objective="Prepare the soccer goal for a broadcast shot.",
        blend_file=blend_file,
        object_name=object_name,
        target_location=location,
        target_rotation=rotation,
    )

    def object_location(result, name=spec.object_name):
        details = result.details if hasattr(result, "details") else result
        for obj in details.get("objects", []):
            if obj.get("name") == name:
                return [float(value) for value in obj["location"]]
        raise RuntimeError(f"Object not found: {name}")

    def object_rotation(result, name=spec.object_name):
        details = result.details if hasattr(result, "details") else result
        if details.get("object_name") != name:
            raise RuntimeError("Unexpected transform object")
        return [float(value) for value in details["rotation_degrees"]]

    evaluator = TargetStateEvaluator([
        StateInvariant(
            "goal_position_ready",
            lambda evidence: object_location(evidence["scene"]) == list(spec.target_location),
        ),
        StateInvariant(
            "goal_orientation_ready",
            lambda evidence: object_rotation(evidence["transform"]) == list(spec.target_rotation),
        ),
    ])

    position = ProductionTaskFragment(
        "position-goal",
        evidence=(EvidenceRequest("inspect_scene", {"file_name": str(spec.blend_file)}, "scene"),),
        actions=(ActionSpec(
            "move_object",
            {
                "file_name": str(spec.blend_file),
                "object_name": spec.object_name,
                "location": list(spec.target_location),
            },
            "position_goal",
        ),),
        deliverables=("broadcast-ready goal position",),
        constraints=("preserve goal geometry",),
        metadata={"production_phase": "layout"},
    )
    orientation = ProductionTaskFragment(
        "orient-goal",
        evidence=(EvidenceRequest(
            "inspect_object_transform",
            {"file_name": str(spec.blend_file), "object_name": spec.object_name},
            "transform",
        ),),
        actions=(ActionSpec(
            "set_object_rotation",
            {
                "file_name": str(spec.blend_file),
                "object_name": spec.object_name,
                "rotation_degrees": list(spec.target_rotation),
            },
            "orient_goal",
            depends_on=("position_goal",),
        ),),
        deliverables=("broadcast-ready goal orientation",),
        constraints=("preserve position established by layout phase",),
        metadata={"production_phase": "orientation"},
        depends_on=("position-goal",),
    )
    return compose_production_task(
        name=spec.name,
        objective=spec.objective,
        fragments=(position, orientation),
        evaluator=evaluator,
        allowed_action_tools=("move_object", "set_object_rotation"),
        domain=spec.domain,
        deliverables=spec.deliverables,
        constraints=spec.constraints,
    )


__all__ = ["SoccerGoalTransformWorkflowSpec", "build_broadcast_goal_preparation"]
