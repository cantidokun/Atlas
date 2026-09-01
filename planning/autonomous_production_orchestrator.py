"""High-level autonomous production orchestration over existing Atlas boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from planning.action_plan import ActionPlan
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_planner import AutonomousProductionGoalPlanner
from planning.autonomous_task_sequence import AutonomousTaskSequence, AutonomousTaskSequenceResult
from planning.blender_autonomous_admission import BlenderAutonomousAdmission


@dataclass(frozen=True)
class AutonomousProductionOrchestrator:
    """Bridge production goals and authorized plans into autonomous sequencing.

    This facade owns no execution, authorization, verification, checkpoint,
    journal, or receipt mechanism. Goal compilation is delegated to the
    canonical goal/task planning boundary; action execution is delegated to
    the existing autonomous sequence and admission boundaries.
    """

    adapter: ActionPlanSequenceAdapter
    admission: BlenderAutonomousAdmission
    goal_planner: Optional[AutonomousProductionGoalPlanner] = None

    def __post_init__(self) -> None:
        if not isinstance(self.adapter, ActionPlanSequenceAdapter):
            raise TypeError("adapter must be an ActionPlanSequenceAdapter")
        if not isinstance(self.admission, BlenderAutonomousAdmission):
            raise TypeError("admission must be a BlenderAutonomousAdmission")
        if self.goal_planner is not None and not isinstance(self.goal_planner, AutonomousProductionGoalPlanner):
            raise TypeError("goal_planner must be an AutonomousProductionGoalPlanner")

    def prepare(self, action_plan: ActionPlan, sequence_id: str = "default") -> AutonomousTaskSequence:
        """Build a production sequence without executing any operation."""
        return self.adapter.to_sequence(action_plan, sequence_id=sequence_id)

    def prepare_goal(self, goal: AutonomousProductionGoal, sequence_id: str = "default") -> AutonomousTaskSequence:
        """Compile a production goal through canonical planning, then adapt it."""
        if self.goal_planner is None:
            raise RuntimeError("goal_planner is required for goal orchestration")
        action_plan = self.goal_planner.compile(goal)
        return self.prepare(action_plan, sequence_id=sequence_id)

    def run(
        self,
        action_plan: ActionPlan,
        sequence_id: str = "default",
        max_steps: int = 16,
        before_step: Optional[Callable[[int, Any], None]] = None,
        checkpoint_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> AutonomousTaskSequenceResult:
        """Prepare and run only when the canonical admission boundary is ready."""
        sequence = self.prepare(action_plan, sequence_id=sequence_id)
        return sequence.run_admitted(
            lambda: self.admission.ready,
            max_steps=max_steps,
            before_step=before_step,
            checkpoint_sink=checkpoint_sink,
        )

    def run_goal(
        self,
        goal: AutonomousProductionGoal,
        sequence_id: str = "default",
        max_steps: int = 16,
        before_step: Optional[Callable[[int, Any], None]] = None,
        checkpoint_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> AutonomousTaskSequenceResult:
        """Compile a goal through canonical planning and run it through admission."""
        sequence = self.prepare_goal(goal, sequence_id=sequence_id)
        return sequence.run_admitted(
            lambda: self.admission.ready,
            max_steps=max_steps,
            before_step=before_step,
            checkpoint_sink=checkpoint_sink,
        )
