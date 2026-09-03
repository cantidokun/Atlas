"""Reusable declarative soccer-production workflow templates for Atlas.

Templates in this module build existing production-task fragments only. They do
not execute work, authorize actions, schedule runtime, or introduce a second
recovery path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.production_task_composition import ProductionTaskFragment


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
    depends_on: Tuple[str, ...] = ("position-goal",)

    def __post_init__(self) -> None:
        if not str(self.file_name).strip():
            raise ValueError("workflow file_name must not be empty")
        if not self.object_name.strip():
            raise ValueError("workflow object_name must not be empty")
        if len(self.target_rotation) != 3:
            raise ValueError("workflow target_rotation must contain three values")
        if any(not isinstance(item, str) or not item.strip() for item in self.depends_on):
            raise ValueError("workflow fragment dependencies must contain non-empty strings")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("workflow fragment dependencies must be unique")

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
            depends_on=self.depends_on,
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

    def fragment_names(self) -> List[str]:
        return [fragment.name for fragment in self.fragments()]


__all__ = [
    "BroadcastGoalPreparationTemplate",
    "GoalOrientationTemplate",
    "GoalPositionTemplate",
]
