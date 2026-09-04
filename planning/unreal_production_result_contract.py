"""Explicit result contract for Unreal production controller responses.

The controller may execute a production transaction, but callers should receive
an engine-neutral, typed result surface rather than depending on integration
internals. Verified render evidence and its receipt remain paired identities;
they are never treated as authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_production_controller_integration import (
    UnrealProductionControllerEvent,
)
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeSnapshot
from planning.unreal_production_workflow import UnrealProductionWorkflowResult
from planning.unreal_render_receipt import UnrealRenderReceipt


@dataclass(frozen=True)
class UnrealProductionResultContract:
    """Immutable, engine-neutral result exposed after controller execution."""

    operation: str
    snapshot: UnrealProductionRuntimeSnapshot
    success: bool
    intent_id: Optional[str] = None
    job_id: Optional[str] = None
    final_evidence: Optional[UnrealEvidence] = None
    receipt: Optional[UnrealRenderReceipt] = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("operation must be a non-empty string")
        if not isinstance(self.snapshot, UnrealProductionRuntimeSnapshot):
            raise TypeError("snapshot must be a UnrealProductionRuntimeSnapshot instance")
        if not isinstance(self.success, bool):
            raise TypeError("success must be boolean")

        if self.intent_id is not None and (
            not isinstance(self.intent_id, str) or not self.intent_id.strip()
        ):
            raise ValueError("intent_id must be a non-empty string when supplied")
        if self.job_id is not None and (
            not isinstance(self.job_id, str) or not self.job_id.strip()
        ):
            raise ValueError("job_id must be a non-empty string when supplied")

        if self.final_evidence is not None and not isinstance(
            self.final_evidence,
            UnrealEvidence,
        ):
            raise TypeError("final_evidence must be a UnrealEvidence instance")
        if self.receipt is not None and not isinstance(
            self.receipt,
            UnrealRenderReceipt,
        ):
            raise TypeError("receipt must be a UnrealRenderReceipt instance")

        if self.receipt is not None and self.final_evidence is None:
            raise ValueError("receipt requires paired final_evidence")
        if self.final_evidence is not None and not self.final_evidence.verified:
            raise ValueError("final_evidence must be verified")

        if self.final_evidence is not None:
            if self.final_evidence.operation_name != "inspect_render_job":
                raise ValueError(
                    "final_evidence must come from inspect_render_job"
                )
            observed_job_id = self.final_evidence.observed_state.get("job_id")
            if not isinstance(observed_job_id, str) or not observed_job_id.strip():
                raise ValueError("final_evidence must contain a non-empty job_id")
            if self.job_id is not None and self.job_id != observed_job_id:
                raise ValueError("job_id does not match final_evidence")

        if self.receipt is not None:
            if not self.receipt.matches(self.final_evidence):
                raise ValueError("receipt does not match final_evidence")
            if self.job_id is not None and self.receipt.job_id != self.job_id:
                raise ValueError("receipt job_id does not match result job_id")

    @property
    def verified_render(self) -> bool:
        """Whether this result carries a verified render/evidence/receipt tuple."""
        return (
            self.final_evidence is not None
            and self.receipt is not None
            and self.receipt.matches(self.final_evidence)
        )


def normalize_unreal_production_event(
    event: UnrealProductionControllerEvent,
) -> UnrealProductionResultContract:
    """Normalize one controller event without creating authorization."""
    if not isinstance(event, UnrealProductionControllerEvent):
        raise TypeError(
            "event must be a UnrealProductionControllerEvent instance"
        )

    workflow_result = event.workflow_result
    if workflow_result is None:
        return UnrealProductionResultContract(
            operation=event.operation,
            snapshot=event.snapshot,
            success=event.snapshot.state in {"complete", "recovery_complete"},
        )

    if not isinstance(workflow_result, UnrealProductionWorkflowResult):
        raise TypeError(
            "workflow_result must be a UnrealProductionWorkflowResult instance"
        )

    render_result = workflow_result.render
    result = UnrealProductionResultContract(
        operation=event.operation,
        snapshot=event.snapshot,
        success=workflow_result.success,
        intent_id=render_result.intent_id,
        job_id=render_result.job_id,
        final_evidence=render_result.final_evidence,
        receipt=render_result.receipt,
    )

    if not result.verified_render:
        raise ValueError(
            "successful Unreal workflow result must expose matching verified render evidence and receipt"
        )
    return result
