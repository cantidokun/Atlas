"""Canonical declarative catalog for reusable Atlas soccer-production workflows.

The catalog is a proposal-resolution surface only. It does not execute work,
authorize actions, schedule runtime, or provide a second recovery path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from planning.soccer_production_templates import BroadcastGoalPreparationTemplate


@dataclass(frozen=True)
class SoccerProductionWorkflowSpec:
    """Stable descriptor for one reusable soccer-production workflow."""

    name: str
    objective: str
    template_name: str
    required_parameters: Tuple[str, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("workflow spec name must not be empty")
        if not self.objective.strip():
            raise ValueError("workflow spec objective must not be empty")
        if not self.template_name.strip():
            raise ValueError("workflow spec template_name must not be empty")
        if any(not isinstance(item, str) or not item.strip() for item in self.required_parameters):
            raise ValueError("workflow spec parameters must contain non-empty strings")
        if len(set(self.required_parameters)) != len(self.required_parameters):
            raise ValueError("workflow spec parameters must be unique")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ValueError("workflow spec version must be a positive integer")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "objective": self.objective,
            "template_name": self.template_name,
            "required_parameters": list(self.required_parameters),
            "version": self.version,
        }


_BROADCAST_GOAL = SoccerProductionWorkflowSpec(
    name="broadcast-goal-preparation",
    objective="Prepare the soccer goal for a broadcast shot.",
    template_name="BroadcastGoalPreparationTemplate",
    required_parameters=(
        "file_name",
        "object_name",
        "target_location",
        "target_rotation",
    ),
    version=1,
)


_WORKFLOWS = (_BROADCAST_GOAL,)


def available_soccer_production_workflows() -> Tuple[SoccerProductionWorkflowSpec, ...]:
    """Return the canonical immutable workflow descriptors in stable order."""
    return _WORKFLOWS


def get_soccer_production_workflow(name: str, version: int | None = None) -> SoccerProductionWorkflowSpec:
    """Resolve a workflow descriptor by exact canonical name and optional version."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("workflow name must be a non-empty string")
    if version is not None and (not isinstance(version, int) or isinstance(version, bool) or version < 1):
        raise ValueError("workflow version must be a positive integer")
    for workflow in _WORKFLOWS:
        if workflow.name != name:
            continue
        if version is not None and workflow.version != version:
            raise KeyError(f"unsupported version for soccer production workflow: {name}@{version}")
        return workflow
    raise KeyError(f"unknown soccer production workflow: {name}")


def validate_soccer_production_workflow_parameters(
    name: str,
    parameters: Dict[str, Any],
    version: int | None = None,
) -> SoccerProductionWorkflowSpec:
    """Validate a proposal parameter envelope without constructing or executing a template."""
    spec = get_soccer_production_workflow(name, version=version)
    if not isinstance(parameters, dict):
        raise TypeError("workflow parameters must be a dictionary")
    missing = [key for key in spec.required_parameters if key not in parameters]
    if missing:
        raise ValueError(f"workflow {name} is missing required parameters: {missing}")
    unexpected = sorted(set(parameters) - set(spec.required_parameters))
    if unexpected:
        raise ValueError(f"workflow {name} received unexpected parameters: {unexpected}")
    return spec


def build_soccer_production_workflow(
    name: str,
    parameters: Dict[str, Any],
    version: int | None = None,
) -> BroadcastGoalPreparationTemplate:
    """Build a validated reusable template from a canonical workflow contract.

    This function only constructs the declarative template. Execution remains
    outside the catalog and continues through the existing Atlas task runtime.
    """
    spec = validate_soccer_production_workflow_parameters(name, parameters, version=version)

    if spec.name == _BROADCAST_GOAL.name:
        target_location = parameters["target_location"]
        target_rotation = parameters["target_rotation"]
        for field_name, values in (
            ("target_location", target_location),
            ("target_rotation", target_rotation),
        ):
            if not isinstance(values, (list, tuple)):
                raise TypeError(f"workflow {field_name} must be a list or tuple")
            if len(values) != 3:
                raise ValueError(f"workflow {field_name} must contain three values")

        return BroadcastGoalPreparationTemplate(
            file_name=parameters["file_name"],
            object_name=parameters["object_name"],
            target_location=tuple(target_location),
            target_rotation=tuple(target_rotation),
        )

    raise RuntimeError(f"workflow catalog entry has no builder: {spec.name}")


__all__ = [
    "SoccerProductionWorkflowSpec",
    "available_soccer_production_workflows",
    "build_soccer_production_workflow",
    "get_soccer_production_workflow",
    "validate_soccer_production_workflow_parameters",
]
