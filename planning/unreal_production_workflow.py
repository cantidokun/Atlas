"""High-level orchestration for heterogeneous Unreal production plus final render."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_executor import (
    UnrealProductionExecutionResult,
    UnrealProductionExecutor,
)
from planning.unreal_production_operation import UnrealProductionPlan
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_workflow import (
    UnrealRenderWorkflow,
    UnrealRenderWorkflowError,
    UnrealRenderWorkflowResult,
)
from planning.unreal_task_planner import UnrealTaskIntent


class UnrealProductionWorkflowError(RuntimeError):
    """Raised when a production transaction cannot reach verified render completion."""


@dataclass(frozen=True)
class UnrealProductionWorkflowResult:
    """Verified result for one heterogeneous production plus final render."""

    production: UnrealProductionExecutionResult
    render: UnrealRenderWorkflowResult

    @property
    def verified_render(self) -> bool:
        """Whether the render result contains a verified, internally consistent identity."""
        if not isinstance(self.production, UnrealProductionExecutionResult):
            if not hasattr(self.production, "success") or not self.production.success:
                return False
            production_intent_id = self.render.intent_id
        else:
            production_intent_id = self.production.production.plan.intent_id
        if not isinstance(production_intent_id, str) or not production_intent_id.strip():
            return False
        if not isinstance(self.render.intent_id, str) or not self.render.intent_id.strip():
            return False
        if self.render.intent_id != production_intent_id:
            return False
        if not isinstance(self.render.job_id, str) or not self.render.job_id.strip():
            return False
        if not isinstance(self.render.final_evidence, UnrealEvidence):
            return False
        if not self.render.final_evidence.verified:
            return False
        if self.render.final_evidence.operation_name != "inspect_render_job":
            return False
        observed_job_id = self.render.final_evidence.observed_state.get("job_id")
        if observed_job_id != self.render.job_id:
            return False
        if not isinstance(self.render.receipt, UnrealRenderReceipt):
            return False
        if self.render.receipt.job_id != self.render.job_id:
            return False
        return self.render.receipt.matches(self.render.final_evidence)

    @property
    def success(self) -> bool:
        """Whether production and the final render both completed with verified identity."""
        return self.production.success and self.verified_render


class UnrealProductionWorkflow:
    """Compose the existing production transaction and verified render workflow."""

    def __init__(
        self,
        production_executor: UnrealProductionExecutor,
        render_workflow: UnrealRenderWorkflow,
    ) -> None:
        if not isinstance(production_executor, UnrealProductionExecutor):
            raise TypeError(
                "production_executor must be a UnrealProductionExecutor instance"
            )
        if not isinstance(render_workflow, UnrealRenderWorkflow):
            raise TypeError(
                "render_workflow must be a UnrealRenderWorkflow instance"
            )

        self.production_executor = production_executor
        self.render_workflow = render_workflow

    def run(
        self,
        production: UnrealProductionPlan,
        production_authorization: UnrealPlanAuthorization,
        intent: UnrealTaskIntent,
        sequence_asset_path: str,
        render_authorization_factory: Callable[
            [object], UnrealPlanAuthorization
        ],
    ) -> UnrealProductionWorkflowResult:
        """Execute the authorized production, then submit and verify its final render."""
        if not isinstance(production, UnrealProductionPlan):
            raise TypeError("production must be a UnrealProductionPlan instance")
        if not isinstance(production_authorization, UnrealPlanAuthorization):
            raise TypeError(
                "production_authorization must be a UnrealPlanAuthorization instance"
            )
        if not production_authorization.matches(production.plan):
            raise UnrealProductionWorkflowError(
                "production authorization does not match the exact production plan"
            )
        if not isinstance(intent, UnrealTaskIntent):
            raise TypeError("intent must be a UnrealTaskIntent instance")
        if production.plan.intent_id != intent.intent_id:
            raise UnrealProductionWorkflowError(
                "production plan intent_id must match render intent_id"
            )
        if not isinstance(sequence_asset_path, str) or not sequence_asset_path.strip():
            raise ValueError("sequence_asset_path must be a non-empty string")

        production_result = self.production_executor.execute(
            production,
            production_authorization,
        )

        if not production_result.success:
            raise UnrealProductionWorkflowError(
                "heterogeneous Unreal production did not complete successfully"
            )

        submission = self.render_workflow.submit(
            intent,
            sequence_asset_path,
            render_authorization_factory,
        )

        try:
            job_id = self.render_workflow.get_submitted_job_id(submission)
        except UnrealRenderWorkflowError as exc:
            raise UnrealProductionWorkflowError(str(exc)) from exc

        final_render = self.render_workflow.wait_for_completion(
            intent,
            job_id,
            render_authorization_factory,
        )
        if not isinstance(final_render, UnrealRenderWorkflowResult):
            raise UnrealProductionWorkflowError(
                "render workflow returned an invalid result"
            )
        if final_render.intent_id != intent.intent_id:
            raise UnrealProductionWorkflowError(
                "render result intent_id does not match the production intent_id"
            )

        return UnrealProductionWorkflowResult(
            production=production_result,
            render=final_render,
        )
