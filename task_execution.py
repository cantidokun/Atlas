"""Generic execution bridge for validated Atlas task plans.

This module connects the existing evidence and action plan primitives without
letting model output execute directly. A plan must first be validated and
explicitly authorized by Python. Execution is delegated through a caller-owned
function so this runtime does not gain arbitrary process or Blender access.

The runtime owns sequencing and state; the executor owns the actual tool call.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set

from action_plan import ActionPlan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal


class TaskExecutionError(RuntimeError):
    """Raised when a task cannot enter or continue execution."""


@dataclass
class TaskExecutionRuntime:
    """Coordinate authorized evidence completion and deterministic actions."""

    proposal: TaskPlanProposal
    evidence_complete: bool = False
    allowed_action_tools: Optional[Set[str]] = None
    allow_writes: bool = False
    write_action_tools: Optional[Set[str]] = None
    action_plan: ActionPlan = field(init=False)
    authorized: bool = field(default=False, init=False)
    verification_complete: bool = field(default=False, init=False)
    final_result: Optional[Dict[str, Any]] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.action_plan = ActionPlan(list(self.proposal.actions))

    def authorize(self) -> None:
        """Explicitly authorize the proposed actions using Python-side rules."""
        try:
            authorize_task_plan(
                self.proposal,
                evidence_complete=self.evidence_complete,
                allowed_action_tools=self.allowed_action_tools,
                allow_writes=self.allow_writes,
                write_action_tools=self.write_action_tools,
            )
        except Exception as exc:
            raise TaskExecutionError(str(exc)) from exc
        self.authorized = True

    def execute_next(
        self,
        executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute exactly the current authorized action and record its result."""
        if not self.authorized:
            raise TaskExecutionError("Task plan has not been authorized.")
        if self.verification_complete:
            raise TaskExecutionError("Task is already finalized.")

        action = self.action_plan.next_action
        if action is None:
            raise TaskExecutionError("No action remains to execute.")

        try:
            result = executor(action.tool, action.arguments)
        except Exception as exc:
            result = {"error": str(exc)}
            self.action_plan.record_result(result, success=False)
            raise TaskExecutionError(str(exc)) from exc

        if not isinstance(result, dict):
            raise TaskExecutionError("Executor must return a dictionary result.")

        success = bool(result.get("success", True))
        self.action_plan.record_result(result, success=success)
        if not success:
            raise TaskExecutionError(
                f"Action failed: {action.name or action.tool}"
            )
        return result

    def mark_verified(self, verification: Dict[str, Any]) -> None:
        """Finalize only after an independent verification result is supplied."""
        if not self.authorized:
            raise TaskExecutionError("Task plan has not been authorized.")
        if not self.action_plan.complete:
            raise TaskExecutionError("Cannot verify before all actions complete.")
        if not isinstance(verification, dict):
            raise TaskExecutionError("Verification result must be a dictionary.")
        if not bool(verification.get("success", False)):
            raise TaskExecutionError("Independent verification did not pass.")

        self.verification_complete = True
        self.final_result = verification

    def snapshot(self) -> Dict[str, Any]:
        """Return deterministic runtime state for audit/evidence logging."""
        return {
            "authorized": self.authorized,
            "evidence_complete": self.evidence_complete,
            "action_plan": self.action_plan.snapshot(),
            "verification_complete": self.verification_complete,
            "final_result": self.final_result,
        }
