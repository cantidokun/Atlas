"""Conditional execution state for Atlas authorized action plans."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from action_plan import ActionPlan, ActionSpec


@dataclass
class ConditionalActionPlan:
    """Decide whether an authorized action plan is needed from evidence.

    Evidence evaluation is external to this class. Python records the decision;
    the class then either marks the plan skipped or exposes its deterministic
    action sequence for execution.
    """

    actions: List[ActionSpec]
    action_plan: ActionPlan = field(init=False)
    evaluated: bool = False
    target_satisfied: Optional[bool] = None

    def __post_init__(self) -> None:
        self.action_plan = ActionPlan(self.actions)

    def evaluate(self, target_satisfied: bool) -> None:
        if self.evaluated:
            raise RuntimeError("Conditional action plan has already been evaluated.")
        if not isinstance(target_satisfied, bool):
            raise TypeError("target_satisfied must be a boolean.")
        self.target_satisfied = target_satisfied
        self.evaluated = True
        if target_satisfied:
            # A satisfied target completes the conditional plan without
            # executing any action.
            self.action_plan.current_index = len(self.actions)

    @property
    def skipped(self) -> bool:
        return self.evaluated and self.target_satisfied is True

    @property
    def blocked(self) -> bool:
        """Mirror the underlying ActionPlan failure state for orchestration."""
        return self.action_plan.blocked

    @property
    def ready_to_execute(self) -> bool:
        return self.evaluated and self.target_satisfied is False and not self.action_plan.blocked

    @property
    def complete(self) -> bool:
        return self.evaluated and self.action_plan.complete

    @property
    def next_action(self) -> Optional[ActionSpec]:
        if not self.ready_to_execute:
            return None
        return self.action_plan.next_action

    def record_result(self, result: Dict[str, Any], success: bool) -> None:
        if not self.ready_to_execute:
            raise RuntimeError("Conditional action plan is not ready for execution.")
        self.action_plan.record_result(result, success)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "target_satisfied": self.target_satisfied,
            "skipped": self.skipped,
            "ready_to_execute": self.ready_to_execute,
            "complete": self.complete,
            "action_plan": self.action_plan.snapshot(),
        }
