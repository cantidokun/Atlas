"""Explicit bridge from authorized ActionPlan objects to production sequences."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from planning.action_plan import ActionPlan, ActionSpec
from planning.autonomous_task_sequence import AutonomousTaskSequence, AutonomousTaskStep
from planning.production_operation_lifecycle import ProductionOperationLifecycle

OperationFactory = Callable[[ActionSpec], ProductionOperationLifecycle]


@dataclass(frozen=True)
class ActionPlanSequenceAdapter:
    """Translate an already-authorized, pristine ActionPlan into production operations.

    The adapter performs no execution, authorization, or resume. A partially
    executed plan must use the established checkpoint/resume path rather than
    being rebuilt as a new autonomous sequence, preventing replay of completed
    actions under a fresh sequence identity.
    """

    operation_factory: OperationFactory

    def __post_init__(self) -> None:
        if not callable(self.operation_factory):
            raise TypeError("operation_factory must be callable")

    def to_sequence(self, action_plan: ActionPlan, sequence_id: str = "default") -> AutonomousTaskSequence:
        if not isinstance(action_plan, ActionPlan):
            raise TypeError("action_plan must be an ActionPlan")
        if not action_plan.authorized:
            raise RuntimeError("Action plan must be authorized before production sequencing")
        if action_plan.current_index != 0 or action_plan.completed or action_plan.failed is not None:
            raise RuntimeError("Action plan must be pristine before production sequencing")
        operations: Sequence[AutonomousTaskStep] = tuple(
            AutonomousTaskStep(
                action.name or action.tool,
                self.operation_factory(action),
            )
            for action in action_plan.actions
        )
        return AutonomousTaskSequence(operations, sequence_id=sequence_id)
