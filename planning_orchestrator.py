"""Small offline bridge between evidence planning and action planning.

This module does not interpret natural language and does not authorize writes.
It provides deterministic plumbing for a higher-level Atlas planner:

1. evidence requests are satisfied or reused;
2. once evidence planning is complete, an already-authorized action plan can
   be executed step by step;
3. failures remain visible instead of being hidden.

Natural-language interpretation and authorization remain outside this module.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from action_plan import ActionPlan
from evidence_plan import EvidencePlan


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


@dataclass
class PlanningOrchestrator:
    """Coordinate evidence completion before action execution."""

    evidence_plan: EvidencePlan
    action_plan: ActionPlan

    @property
    def evidence_complete(self) -> bool:
        return self.evidence_plan.complete

    @property
    def action_complete(self) -> bool:
        return self.action_plan.complete

    @property
    def blocked(self) -> bool:
        return self.evidence_plan.blocked or self.action_plan.blocked

    def next_phase(self) -> str:
        if self.blocked:
            return "BLOCKED"
        if not self.evidence_complete:
            return "EVIDENCE"
        if not self.action_complete:
            return "ACTION"
        return "COMPLETE"

    def acquire_next_evidence(
        self,
        execute: ToolExecutor,
        reused_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Acquire the next evidence item, or record an already-known result."""
        if self.evidence_plan.complete:
            raise RuntimeError("Evidence plan is already complete.")
        if self.evidence_plan.blocked:
            raise RuntimeError("Evidence plan is blocked.")

        request = self.evidence_plan.next_request
        if request is None:
            raise RuntimeError("No next evidence request is available.")

        if reused_result is not None:
            self.evidence_plan.record_result(reused_result, True, reused=True)
            return reused_result

        result = execute(request.tool, request.arguments)
        self.evidence_plan.record_result(result, "error" not in result)
        return result

    def execute_next_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        """Execute one authorized action after evidence planning is complete."""
        if not self.evidence_complete:
            raise RuntimeError("Action execution is blocked until evidence is complete.")
        if self.action_plan.complete:
            raise RuntimeError("Action plan is already complete.")
        if self.action_plan.blocked:
            raise RuntimeError("Action plan is blocked.")

        action = self.action_plan.next_action
        if action is None:
            raise RuntimeError("No next action is available.")

        result = execute(action.tool, action.arguments)
        self.action_plan.record_result(result, "error" not in result)
        return result

    def snapshot(self) -> Dict[str, Any]:
        """Return a combined state snapshot for logs and future evidence."""
        return {
            "phase": self.next_phase(),
            "blocked": self.blocked,
            "evidence": self.evidence_plan.snapshot(),
            "actions": self.action_plan.snapshot(),
        }
