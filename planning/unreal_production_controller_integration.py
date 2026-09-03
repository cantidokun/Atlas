"""Agent-facing integration boundary for Unreal production transactions.

The generic Atlas controller remains provider-neutral. This module adapts the
Unreal production runtime into a small lifecycle contract that an outer agent
or orchestrator can consume without gaining a way to bypass authorization.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from controller.capability_request import CapabilityRequest
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_planning_boundary import UnrealAuthorizedProductionPlan
from planning.unreal_production_runtime_adapter import (
    UnrealProductionRuntimeAdapter,
    UnrealProductionRuntimeSnapshot,
)
from planning.unreal_production_workflow import UnrealProductionWorkflow, UnrealProductionWorkflowResult
from planning.unreal_task_planner import UnrealTaskIntent


@dataclass(frozen=True)
class UnrealProductionControllerEvent:
    """Controller-facing event emitted after each production lifecycle action."""

    operation: str
    snapshot: UnrealProductionRuntimeSnapshot
    workflow_result: Optional[UnrealProductionWorkflowResult] = None


class UnrealProductionControllerIntegration:
    """Expose Unreal production as an explicit Atlas controller capability."""

    def __init__(
        self,
        runtime: UnrealProductionRuntimeAdapter,
        *,
        workflow: Optional[UnrealProductionWorkflow] = None,
        render_authorization_factory: Optional[Callable[[object], UnrealPlanAuthorization]] = None,
    ) -> None:
        if not isinstance(runtime, UnrealProductionRuntimeAdapter):
            raise TypeError("runtime must be a UnrealProductionRuntimeAdapter")
        if workflow is not None and not isinstance(workflow, UnrealProductionWorkflow):
            raise TypeError("workflow must be a UnrealProductionWorkflow when supplied")
        if render_authorization_factory is not None and not callable(render_authorization_factory):
            raise TypeError("render_authorization_factory must be callable when supplied")

        self._runtime = runtime
        self._workflow = workflow
        self._render_authorization_factory = render_authorization_factory
        self._workflow_result: Optional[UnrealProductionWorkflowResult] = None
        self._last_event: Optional[UnrealProductionControllerEvent] = None

    @property
    def complete(self) -> bool:
        if self._workflow_result is not None:
            return self._workflow_result.success
        return self._runtime.complete

    @property
    def snapshot(self) -> UnrealProductionRuntimeSnapshot:
        return self._runtime.snapshot

    def execute(self, request: CapabilityRequest) -> UnrealProductionControllerEvent:
        """Execute one admitted production lifecycle request.

        ``production`` starts a transaction. Recovery actions are explicit and
        carry their own fresh authorization object in request context. No
        action performs capability re-selection or invents authorization.
        """
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")
        if request.normalized_provider != "unreal":
            raise ValueError("Unreal production execution requires provider='unreal'")
        if request.normalized_capability != "production":
            raise ValueError("Unreal production execution requires capability='production'")

        recovery_action = request.context.get("recovery_action")
        if recovery_action is None:
            authorized = request.context.get("authorized_production")
            if not isinstance(authorized, UnrealAuthorizedProductionPlan):
                raise TypeError(
                    "request context must contain an UnrealAuthorizedProductionPlan "
                    "under 'authorized_production'"
                )

            if self._workflow is not None:
                intent = request.context.get("intent")
                sequence_asset_path = request.context.get("sequence_asset_path")

                if not isinstance(intent, UnrealTaskIntent):
                    raise TypeError(
                        "workflow-backed production requests require an UnrealTaskIntent "
                        "under 'intent'"
                    )
                if not isinstance(sequence_asset_path, str) or not sequence_asset_path.strip():
                    raise ValueError(
                        "workflow-backed production requests require a non-empty "
                        "'sequence_asset_path'"
                    )
                if self._render_authorization_factory is None:
                    raise RuntimeError(
                        "workflow-backed production requires a render_authorization_factory"
                    )

                result = self._workflow.run(
                    authorized.production,
                    authorized.authorization,
                    intent,
                    sequence_asset_path,
                    self._render_authorization_factory,
                )

                if not isinstance(result, UnrealProductionWorkflowResult):
                    raise TypeError(
                        "UnrealProductionWorkflow.run() returned an unexpected result"
                    )

                self._workflow_result = result
                event = UnrealProductionControllerEvent(
                    operation="start",
                    snapshot=self._workflow_snapshot(),
                    workflow_result=result,
                )
                self._last_event = event
                return event

            return self.start(authorized)

        if recovery_action == "reassess":
            authorization = request.context.get("reassessment_authorization")
            if not isinstance(authorization, UnrealPlanAuthorization):
                raise TypeError(
                    "reassess requests require a UnrealPlanAuthorization under "
                    "'reassessment_authorization'"
                )
            return self.reassess(authorization)

        if recovery_action == "resume_recovery":
            authorization = request.context.get("replacement_authorization")
            if not isinstance(authorization, UnrealPlanAuthorization):
                raise TypeError(
                    "resume requests require a UnrealPlanAuthorization under "
                    "'replacement_authorization'"
                )
            return self.resume(authorization)

        raise ValueError(f"unsupported Unreal production recovery action: {recovery_action!r}")

    def _workflow_snapshot(self) -> UnrealProductionRuntimeSnapshot:
        """Expose verified workflow completion through the controller snapshot."""
        return UnrealProductionRuntimeSnapshot(
            state="complete",
            phase="complete",
            waiting_for_reassessment=False,
            waiting_for_replacement=False,
            failure=None,
            recovery=None,
            required_authorizations=(),
        )

    def start(self, authorized: UnrealAuthorizedProductionPlan) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="start",
            snapshot=self._runtime.start(authorized),
        )
        self._last_event = event
        return event

    def reassess(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="reassess",
            snapshot=self._runtime.reassess(authorization),
        )
        self._last_event = event
        return event

    def resume(
        self,
        authorization: UnrealPlanAuthorization,
    ) -> UnrealProductionControllerEvent:
        event = UnrealProductionControllerEvent(
            operation="resume_recovery",
            snapshot=self._runtime.resume(authorization),
        )
        self._last_event = event
        return event

    def next_required_authorization(self) -> Optional[str]:
        """Return the next explicit authorization class, if one is required."""
        if self._runtime.complete:
            return None
        if self._last_event is None:
            return "production"
        state = self._last_event.snapshot.state
        if state == "awaiting_reassessment":
            return "reassessment"
        if state == "awaiting_replacement":
            return "replacement"
        return None
