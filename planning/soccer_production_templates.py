"""Reusable declarative soccer-production workflow templates for Atlas.

Templates in this module build existing production-task fragments only. They do
not execute work, authorize actions, schedule runtime, or introduce a second
recovery path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.production_task import ProductionTaskDefinition
from planning.production_task_composition import ProductionTaskFragment, compose_production_task
from planning.target_state import StateInvariant, TargetStateEvaluator


def _finite_transform(values: Tuple[float, ...], field_name: str) -> None:
    if any(not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
        raise ValueError(f"workflow {field_name} must contain finite numeric values")


def _object_location(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            return [float(value) for value in obj["location"]]
    raise RuntimeError(f"Object not found: {object_name}")


def _object_rotation(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    if details.get("object_name") != object_name:
        raise RuntimeError("Unexpected transform object")
    return [float(value) for value in details["rotation_degrees"]]


@dataclass(frozen=True)
class GoalPositionTemplate:
    """Reusable goal-position production fragment."""

    file_name: str
    object_name: str
    target_location: Tuple[float, float, float]

    def __post_init__(self) -> None:
        if not str(self.file_name).strip():
            raise ValueError("workflow file_name must not be empty")
        if not self.object_name.strip():
            raise ValueError("workflow object_name must not be empty")
        if len(self.target_location) != 3:
            raise ValueError("workflow target_location must contain three values")
        _finite_transform(self.target_location, "target_location")

    @property
    def name(self) -> str:
        return "position-goal"

    @property
    def deliverables(self) -> Tuple[str, ...]:
        return ("broadcast-ready goal position",)

    @property
    def constraints(self) -> Tuple[str, ...]:
        return ("preserve canonical scene geometry",)

    def fragment(self) -> ProductionTaskFragment:
        path = str(Path(self.file_name))
        return ProductionTaskFragment(
            self.name,
            evidence=(EvidenceRequest("inspect_scene", {"file_name": path}, "scene"),),
            actions=(
                ActionSpec(
                    "move_object",
                    {
                        "file_name": path,
                        "object_name": self.object_name,
                        "location": list(self.target_location),
                    },
                    "position_goal",
                ),
            ),
            deliverables=self.deliverables,
            constraints=self.constraints,
            metadata={"production_phase": "layout"},
        )


@dataclass(frozen=True)
class GoalOrientationTemplate:
    """Reusable goal-orientation production fragment."""

    file_name: str
    object_name: str
    target_rotation: Tuple[float, float, float]

    def __post_init__(self) -> None:
        if not str(self.file_name).strip():
            raise ValueError("workflow file_name must not be empty")
        if not self.object_name.strip():
            raise ValueError("workflow object_name must not be empty")
        if len(self.target_rotation) != 3:
            raise ValueError("workflow target_rotation must contain three values")
        _finite_transform(self.target_rotation, "target_rotation")

    @property
    def name(self) -> str:
        return "orient-goal"

    @property
    def deliverables(self) -> Tuple[str, ...]:
        return ("broadcast-ready goal orientation",)

    @property
    def constraints(self) -> Tuple[str, ...]:
        return ("retain the prepared goal position",)

    def fragment(self) -> ProductionTaskFragment:
        path = str(Path(self.file_name))
        return ProductionTaskFragment(
            self.name,
            evidence=(
                EvidenceRequest(
                    "inspect_object_transform",
                    {"file_name": path, "object_name": self.object_name},
                    "transform",
                ),
            ),
            actions=(
                ActionSpec(
                    "set_object_rotation",
                    {
                        "file_name": path,
                        "object_name": self.object_name,
                        "rotation_degrees": list(self.target_rotation),
                    },
                    "orient_goal",
                    depends_on=("position_goal",),
                ),
            ),
            deliverables=self.deliverables,
            constraints=self.constraints,
            metadata={"production_phase": "orientation"},
            depends_on=("position-goal",),
        )


@dataclass(frozen=True)
class BroadcastGoalPreparationTemplate:
    """Reusable two-phase goal-preparation workflow for a broadcast shot."""

    file_name: str
    object_name: str
    target_location: Tuple[float, float, float]
    target_rotation: Tuple[float, float, float]

    def __post_init__(self) -> None:
        if not str(self.file_name).strip():
            raise ValueError("workflow file_name must not be empty")
        if not self.object_name.strip():
            raise ValueError("workflow object_name must not be empty")
        if len(self.target_location) != 3:
            raise ValueError("workflow target_location must contain three values")
        if len(self.target_rotation) != 3:
            raise ValueError("workflow target_rotation must contain three values")
        _finite_transform(self.target_location, "target_location")
        _finite_transform(self.target_rotation, "target_rotation")

    @property
    def name(self) -> str:
        return "broadcast-goal-preparation"

    @property
    def objective(self) -> str:
        return "Prepare the soccer goal for a broadcast shot."

    @property
    def deliverables(self) -> Tuple[str, ...]:
        return ("broadcast-ready goal transform",)

    @property
    def constraints(self) -> Tuple[str, ...]:
        return ("preserve canonical scene", "verify final transform")

    def fragments(self) -> Tuple[ProductionTaskFragment, ...]:
        position = GoalPositionTemplate(
            file_name=self.file_name,
            object_name=self.object_name,
            target_location=self.target_location,
        ).fragment()
        orientation = GoalOrientationTemplate(
            file_name=self.file_name,
            object_name=self.object_name,
            target_rotation=self.target_rotation,
        ).fragment()
        return (position, orientation)

    def production_task(self) -> ProductionTaskDefinition:
        """Build the canonical semantic task, including its target evaluator."""
        evaluator = TargetStateEvaluator([
            StateInvariant(
                "goal_position_ready",
                lambda evidence: _object_location(evidence["scene"], self.object_name)
                == list(self.target_location),
            ),
            StateInvariant(
                "goal_orientation_ready",
                lambda evidence: _object_rotation(evidence["transform"], self.object_name)
                == list(self.target_rotation),
            ),
        ])
        return compose_production_task(
            name=self.name,
            objective=self.objective,
            fragments=self.fragments(),
            evaluator=evaluator,
            allowed_action_tools=("move_object", "set_object_rotation"),
            domain="soccer-production",
            deliverables=self.deliverables,
            constraints=self.constraints,
            metadata={"workflow_template": self.name},
        )

    def fragment_names(self) -> List[str]:
        return [fragment.name for fragment in self.fragments()]


__all__ = [
    "BroadcastGoalPreparationTemplate",
    "GoalOrientationTemplate",
    "GoalPositionTemplate",
]
