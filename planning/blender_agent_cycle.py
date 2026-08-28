"""One deterministic reasoning/execution cycle for the Blender Agent.

The cycle keeps model reasoning separate from execution authority: a reasoning
adapter proposes normalized intent, the planner constrains it, authorization is
required before execution, and the coordinator owns verified action progress.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan
from planning.blender_execution_coordinator import BlenderExecutionCoordinator, BlenderExecutionStep
from planning.blender_task_planner import BlenderTaskIntent, BlenderTaskPlanner


class BlenderAgentCycleError(RuntimeError):
    """Raised when a Blender agent cycle cannot safely advance."""


Authorize = Callable[[ActionPlan], ActionAuthorization]


@dataclass(frozen=True)
class BlenderCycleResult:
    plan: ActionPlan
    step: Optional[BlenderExecutionStep]


class BlenderAgentCycle:
    """Compile one proposed task intent and advance one authorized action."""

    def __init__(
        self,
        planner: Optional[BlenderTaskPlanner] = None,
        authorize: Optional[Authorize] = None,
    ):
        self.planner = planner or BlenderTaskPlanner()
        self._authorize = authorize

    def build_plan(self, intent: BlenderTaskIntent) -> ActionPlan:
        return self.planner.plan(intent)

    def authorize_plan(self, plan: ActionPlan) -> ActionPlan:
        if self._authorize is None:
            raise BlenderAgentCycleError("an authorization provider is required")
        authorization = self._authorize(plan)
        if not isinstance(authorization, ActionAuthorization):
            raise BlenderAgentCycleError("authorization provider must return ActionAuthorization")
        if not authorization.matches(plan.actions):
            raise BlenderAgentCycleError("authorization does not match the exact action plan")
        try:
            plan.authorize(authorization)
        except (RuntimeError, TypeError) as exc:
            raise BlenderAgentCycleError(str(exc)) from exc
        return plan

    def advance(
        self,
        plan: ActionPlan,
        execute,
        verify=None,
        checkpoint=None,
    ) -> BlenderCycleResult:
        coordinator = BlenderExecutionCoordinator(
            plan=plan,
            execute=execute,
            verify=verify,
            checkpoint=checkpoint,
        )
        step = coordinator.step()
        return BlenderCycleResult(plan=plan, step=step)
