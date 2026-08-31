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
    """Translate an already-authorized ActionPlan into production operations.

    The adapter performs no execution or authorization itself. It requires the
    ActionPlan to already be authorized and delegates operation construction to
    the caller-provided factory, preserving the existing production lifecycle as
    the execution boundary.
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
        operations: Sequence[AutonomousTaskStep] = tuple(
            AutonomousTaskStep(
                action.name or action.tool,
                self.operation_factory(action),
            )
            for action in action_plan.actions
        )
        return AutonomousTaskSequence(operations, sequence_id=sequence_id)
