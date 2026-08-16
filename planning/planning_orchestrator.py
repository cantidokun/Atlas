"""Deterministic bridge between evidence planning and action planning."""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from action_plan import ActionPlan
from evidence_plan import EvidencePlan

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]

@dataclass
class PlanningOrchestrator:
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
        if self.blocked: return "BLOCKED"
        if not self.evidence_complete: return "EVIDENCE"
        if not self.action_complete: return "ACTION"
        return "COMPLETE"
    def acquire_next_evidence(self, execute: ToolExecutor, reused_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.evidence_plan.complete: raise RuntimeError("Evidence plan is already complete.")
        if self.evidence_plan.blocked: raise RuntimeError("Evidence plan is blocked.")
        request = self.evidence_plan.next_request
        if request is None: raise RuntimeError("No next evidence request is available.")
        if reused_result is not None:
            self.evidence_plan.record_result(reused_result, True, reused=True)
            return reused_result
        result = execute(request.tool, request.arguments)
        self.evidence_plan.record_result(result, "error" not in result)
        return result
    def execute_next_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        if not self.evidence_complete: raise RuntimeError("Action execution is blocked until evidence is complete.")
        if self.action_plan.complete: raise RuntimeError("Action plan is already complete.")
        if self.action_plan.blocked: raise RuntimeError("Action plan is blocked.")
        action = self.action_plan.next_action
        if action is None: raise RuntimeError("No next action is available.")
        result = execute(action.tool, action.arguments)
        self.action_plan.record_result(result, "error" not in result)
        return result
    def snapshot(self) -> Dict[str, Any]:
        return {"phase": self.next_phase(), "blocked": self.blocked, "evidence": self.evidence_plan.snapshot(), "actions": self.action_plan.snapshot()}
