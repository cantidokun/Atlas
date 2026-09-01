"""High-level autonomous production orchestration over existing Atlas boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.autonomous_production_goal import AutonomousProductionGoal
from planning.autonomous_production_goal_planner import AutonomousProductionGoalPlanner
from planning.autonomous_production_goal_preparation import AutonomousProductionGoalPreparation
from planning.autonomous_production_goal_run import AutonomousProductionGoalRun
from planning.autonomous_task_sequence import AutonomousTaskSequence, AutonomousTaskSequenceResult
from planning.blender_autonomous_admission import BlenderAutonomousAdmission


AuthorizeActionPlan = Callable[[ActionPlan], ActionAuthorization]


@dataclass(frozen=True)
class AutonomousProductionOrchestrator:
    """Compose production planning, authorization, admission, and sequencing.

    This facade owns no execution, verification, checkpoint, journal, or
    receipt mechanism. Goal compilation is delegated to the canonical planning
    boundary, authorization is injected explicitly, and execution is delegated
    to the existing autonomous sequence and admission boundaries.
    """

    adapter: ActionPlanSequenceAdapter
    admission: BlenderAutonomousAdmission
    goal_planner: Optional[AutonomousProductionGoalPlanner] = None
    authorize: Optional[AuthorizeActionPlan] = None

    def __post_init__(self) -> None:
        if not isinstance(self.adapter, ActionPlanSequenceAdapter):
            raise TypeError("adapter must be an ActionPlanSequenceAdapter")
        if not isinstance(self.admission, BlenderAutonomousAdmission):
            raise TypeError("admission must be a BlenderAutonomousAdmission")
        if self.goal_planner is not None and not isinstance(self.goal_planner, AutonomousProductionGoalPlanner):
            raise TypeError("goal_planner must be an AutonomousProductionGoalPlanner")
        if self.authorize is not None and not callable(self.authorize):
            raise TypeError("authorize must be callable")

    def prepare(self, action_plan: ActionPlan, sequence_id: str = "default") -> AutonomousTaskSequence:
        """Build a production sequence from an already-authorized action plan."""
        return self.adapter.to_sequence(action_plan, sequence_id=sequence_id)

    def _authorize_plan(self, action_plan: ActionPlan) -> ActionPlan:
        """Obtain and validate fresh authorization for a pristine action plan."""
        if self.authorize is None:
            raise RuntimeError("authorize is required for goal orchestration")
        authorization = self.authorize(action_plan)
        if not isinstance(authorization, ActionAuthorization):
            raise TypeError("authorization provider must return an ActionAuthorization")
        if not authorization.matches(action_plan.actions):
            raise RuntimeError("authorization does not match the exact action plan")
        action_plan.authorize(authorization)
        return action_plan

    def compile_goal(self, goal: AutonomousProductionGoal) -> tuple[ActionPlan, ActionAuthorization]:
        """Compile and explicitly authorize a fresh production goal without execution."""
        if self.goal_planner is None:
            raise RuntimeError("goal_planner is required for goal orchestration")
        action_plan = self.goal_planner.compile(goal)
        authorized_plan = self._authorize_plan(action_plan)
        authorization = authorized_plan.authorization
        if not isinstance(authorization, ActionAuthorization):
            raise RuntimeError("authorized goal plan is missing ActionAuthorization")
        return authorized_plan, authorization

    def prepare_goal_with_context(
        self,
        goal: AutonomousProductionGoal,
    ) -> tuple[ActionPlan, AutonomousProductionGoalPreparation]:
        """Compile and authorize a goal, returning an execution-free audit record."""
        action_plan, authorization = self.compile_goal(goal)
        preparation = AutonomousProductionGoalPreparation.from_compilation(
            goal,
            action_plan,
            authorization,
        )
        return action_plan, preparation

    def prepare_goal(self, goal: AutonomousProductionGoal, sequence_id: str = "default") -> AutonomousTaskSequence:
        """Compile, explicitly authorize, then adapt a fresh production goal."""
        action_plan, _authorization = self.compile_goal(goal)
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
        """Compile, authorize, and run a production goal through admission."""
        sequence = self.prepare_goal(goal, sequence_id=sequence_id)
        return sequence.run_admitted(
            lambda: self.admission.ready,
            max_steps=max_steps,
            before_step=before_step,
            checkpoint_sink=checkpoint_sink,
        )

    def run_goal_with_context(
        self,
        goal: AutonomousProductionGoal,
        sequence_id: str = "default",
        max_steps: int = 16,
        before_step: Optional[Callable[[int, Any], None]] = None,
        checkpoint_sink: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> AutonomousProductionGoalRun:
        """Compile, authorize, execute, and retain goal/audit context for feedback loops."""
        action_plan, authorization = self.compile_goal(goal)
        sequence = self.prepare(action_plan, sequence_id=sequence_id)
        result = sequence.run_admitted(
            lambda: self.admission.ready,
            max_steps=max_steps,
            before_step=before_step,
            checkpoint_sink=checkpoint_sink,
        )
        return AutonomousProductionGoalRun.from_goal(goal, authorization, result)
