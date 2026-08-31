"""High-level autonomous production orchestration over existing Atlas boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from planning.action_plan import ActionPlan
from planning.action_plan_sequence_adapter import ActionPlanSequenceAdapter
from planning.autonomous_task_sequence import AutonomousTaskSequence, AutonomousTaskSequenceResult
from planning.blender_autonomous_admission import BlenderAutonomousAdmission


@dataclass(frozen=True)
class AutonomousProductionOrchestrator:
    """Bridge an authorized ActionPlan into an admitted autonomous sequence.

    This facade owns no execution, authorization, verification, checkpoint,
    journal, or receipt mechanism. It composes the existing boundaries and
    requires the canonical BlenderAutonomousAdmission boundary rather than an
    arbitrary readiness callback.
    """

    adapter: ActionPlanSequenceAdapter
    admission: BlenderAutonomousAdmission

    def __post_init__(self) -> None:
        if not isinstance(self.adapter, ActionPlanSequenceAdapter):
            raise TypeError("adapter must be an ActionPlanSequenceAdapter")
        if not isinstance(self.admission, BlenderAutonomousAdmission):
            raise TypeError("admission must be a BlenderAutonomousAdmission")

    def prepare(self, action_plan: ActionPlan, sequence_id: str = "default") -> AutonomousTaskSequence:
        """Build a production sequence without executing any operation."""
        return self.adapter.to_sequence(action_plan, sequence_id=sequence_id)

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
