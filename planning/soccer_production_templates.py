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
        path = str(Path(self.file_name))
        position = ProductionTaskFragment(
            "position-goal",
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
            deliverables=("broadcast-ready goal position",),
            constraints=("preserve canonical scene geometry",),
            metadata={"production_phase": "layout"},
        )
        orientation = ProductionTaskFragment(
            "orient-goal",
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
            deliverables=("broadcast-ready goal orientation",),
            constraints=("retain the prepared goal position",),
            metadata={"production_phase": "orientation"},
            depends_on=("position-goal",),
        )
        return (position, orientation)

    def fragment_names(self) -> List[str]:
        return [fragment.name for fragment in self.fragments()]
