"""Bridge task evidence state into the authorized action runtime.

This layer connects the existing evidence planner to deterministic action
execution without giving the reasoning model direct execution authority.
Evidence must be complete before actions can be authorized.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from evidence_plan import EvidencePlan
from task_execution import TaskExecutionError, TaskExecutionRuntime
from task_planner import TaskPlanProposal
from tool_capabilities import ALL_TOOLS, WRITE_TOOLS


class TaskRuntimeBridgeError(RuntimeError):
    """Raised when evidence or action execution cannot continue."""


@dataclass
class TaskRuntimeBridge:
    """Coordinate evidence acquisition before authorized action execution."""

    proposal: TaskPlanProposal
    evidence_plan: EvidencePlan = field(init=False)
    execution: TaskExecutionRuntime = field(init=False)

    def __post_init__(self) -> None:
        self.evidence_plan = EvidencePlan(list(self.proposal.evidence))
        self.execution = TaskExecutionRuntime(
            self.proposal,
            evidence_complete=self.evidence_plan.complete,
            allowed_action_tools=set(ALL_TOOLS),
            write_action_tools=set(WRITE_TOOLS),
        )

    @property
    def evidence_complete(self) -> bool:
        return self.evidence_plan.complete

    @property
    def complete(self) -> bool:
        return self.execution.verification_complete

    def acquire_next_evidence(
        self,
        executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        *,
        reused: bool = False,
    ) -> Dict[str, Any]:
        """Acquire exactly one evidence request, or record an existing result."""
        request = self.evidence_plan.next_request
        if request is None:
            raise TaskRuntimeBridgeError("No evidence request remains.")

        try:
            result = executor(request.tool, request.arguments)
        except Exception as exc:
            result = {"error": str(exc)}
            self.evidence_plan.record_result(result, success=False, reused=reused)
            raise TaskRuntimeBridgeError(str(exc)) from exc

        if not isinstance(result, dict):
            raise TaskRuntimeBridgeError("Evidence executor must return a dictionary result.")

        success = bool(result.get("success", True))
        self.evidence_plan.record_result(result, success=success, reused=reused)
        if not success:
            raise TaskRuntimeBridgeError(
                f"Evidence acquisition failed: {request.name or request.tool}"
            )

        self.execution.evidence_complete = self.evidence_complete
        return result

    def authorize_actions(self) -> None:
        """Authorize actions only after all required evidence is complete."""
        if not self.evidence_complete:
            raise TaskRuntimeBridgeError(
                "Cannot authorize actions before required evidence is complete."
            )
        try:
            self.execution.authorize()
        except TaskExecutionError as exc:
            raise TaskRuntimeBridgeError(str(exc)) from exc

    def execute_next_action(
        self,
        executor: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute exactly one authorized action."""
        try:
            return self.execution.execute_next(executor)
        except TaskExecutionError as exc:
            raise TaskRuntimeBridgeError(str(exc)) from exc

    def mark_verified(self, verification: Dict[str, Any]) -> None:
        """Pass independent verification into the finalization gate."""
        try:
            self.execution.mark_verified(verification)
        except TaskExecutionError as exc:
            raise TaskRuntimeBridgeError(str(exc)) from exc

    def snapshot(self) -> Dict[str, Any]:
        """Return combined evidence and action state for audit logging."""
        return {
            "evidence_plan": self.evidence_plan.snapshot(),
            "execution": self.execution.snapshot(),
        }
