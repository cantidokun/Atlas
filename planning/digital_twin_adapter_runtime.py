"""Controlled bridge between Atlas action plans and production-tool adapters.

The bridge intentionally does not create authorization. It consumes an already
-authorized ActionPlan and executes exactly its next action through the supplied
engine adapter. This keeps the existing Atlas control architecture authoritative.
"""

from typing import Any, Mapping

from planning.action_plan import ActionPlan
from planning.digital_twin_adapter_contract import DigitalTwinToolAdapter, ToolActionResult
from planning.digital_twin_adapter_contract import require_current_representation
from planning.digital_twin_representation import TwinRepresentation


class AdapterExecutionBridge:
    """Execute one already-authorized action against one current representation."""

    def __init__(self, adapter: DigitalTwinToolAdapter) -> None:
        self._adapter = adapter

    def execute_next(
        self,
        plan: ActionPlan,
        representation: TwinRepresentation,
        current_revision_id: str,
    ) -> ToolActionResult:
        """Execute only the next authorized action; never invent or reorder work."""
        require_current_representation(representation, current_revision_id)

        if not plan.authorized:
            raise RuntimeError("adapter execution requires a valid action authorization")

        action = plan.next_action
        if action is None:
            raise RuntimeError("action plan has no executable next action")

        result = self._adapter.apply_authorized_action(
            representation,
            action.name or action.tool,
            action.arguments,
        )
        plan.record_result(
            {
                "action_id": result.action_id,
                "evidence_ids": result.evidence_ids,
                "representation_id": result.representation_id,
            },
            result.success,
        )
        return result
