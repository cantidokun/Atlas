"""Closed-loop state for the Blender Agent.

The state is deliberately small: the agent reasons from verified evidence and
never treats a proposed action as evidence that the scene changed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planning.blender_agent_cycle import BlenderCycleResult
from planning.blender_task_planner import BlenderTaskIntent


@dataclass(frozen=True)
class BlenderObservation:
    source: str
    facts: Dict[str, Any]
    verified: bool = True


@dataclass
class BlenderAgentState:
    task: BlenderTaskIntent
    observations: List[BlenderObservation] = field(default_factory=list)
    cycle_results: List[BlenderCycleResult] = field(default_factory=list)

    def record_observation(self, observation: BlenderObservation) -> None:
        if not observation.verified:
            raise ValueError("unverified observations cannot enter agent state")
        self.observations.append(observation)

    def record_cycle(self, result: BlenderCycleResult) -> None:
        if result.step is None:
            raise ValueError("cycle result must contain an execution step")
        if not result.step.verified:
            raise ValueError("unverified execution cannot advance agent state")
        self.cycle_results.append(result)

    @property
    def latest_observation(self) -> Optional[BlenderObservation]:
        return self.observations[-1] if self.observations else None

    @property
    def latest_cycle(self) -> Optional[BlenderCycleResult]:
        return self.cycle_results[-1] if self.cycle_results else None

    @property
    def objective_satisfied(self) -> bool:
        latest = self.latest_cycle
        return bool(latest and latest.step and latest.step.complete)
