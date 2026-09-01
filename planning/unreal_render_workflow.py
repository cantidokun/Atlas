"""High-level orchestration for completed Unreal render production."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_render_job_verifier import verify_render_job_completion
from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_task_planner import UnrealTaskIntent, UnrealTaskPlan, UnrealTaskPlanner


class UnrealRenderWorkflowError(RuntimeError):
    """Raised when a render workflow cannot reach verified completion."""


@dataclass(frozen=True)
class UnrealRenderWorkflowResult:
    """Verified completion record returned by the render workflow."""

    intent_id: str
    job_id: str
    final_evidence: UnrealEvidence
    receipt: UnrealRenderReceipt
    persisted_receipt: dict


class UnrealRenderWorkflow:
    """Coordinate the existing Unreal planning/execution/receipt boundaries."""

    def __init__(
        self,
        executor: UnrealPlanExecutor,
        receipt_store: UnrealRenderReceiptStore,
        *,
        planner: Optional[UnrealTaskPlanner] = None,
        poll_interval_seconds: float = 1.0,
        timeout_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not callable(getattr(executor, "execute_authorized", None)):
            raise TypeError(
                "executor must provide an execute_authorized(plan, authorization) method"
            )
        if not isinstance(receipt_store, UnrealRenderReceiptStore):
            raise TypeError("receipt_store must be a UnrealRenderReceiptStore instance")
        if planner is not None and not isinstance(planner, UnrealTaskPlanner):
            raise TypeError("planner must be a UnrealTaskPlanner instance")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        self.executor = executor
        self.receipt_store = receipt_store
        self.planner = planner or UnrealTaskPlanner()
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.timeout_seconds = float(timeout_seconds)
        self.clock = clock
        self.sleeper = sleeper

    @staticmethod
    def _authorize(
        plan: UnrealTaskPlan,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealPlanAuthorization:
        authorization = authorization_factory(plan)
        if not isinstance(authorization, UnrealPlanAuthorization):
            raise TypeError(
                "authorization_factory must return an UnrealPlanAuthorization instance"
            )
        if not authorization.matches(plan):
            raise UnrealRenderWorkflowError(
                "authorization_factory returned a receipt that does not match the exact render plan"
            )
        return authorization

    def configure(
        self,
        intent: UnrealTaskIntent,
        render_config,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealPlanExecutionResult:
        """Execute the exact render configuration plan under external authorization."""
        plan = self.planner.plan_render_configuration(intent, render_config)
        authorization = self._authorize(plan, authorization_factory)
        return self.executor.execute_authorized(plan, authorization)

    def submit(
        self,
        intent: UnrealTaskIntent,
        sequence_asset_path: str,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealPlanExecutionResult:
        """Submit a render job and verify that Unreal accepted the submission."""
        plan = self.planner.plan_render_submission(intent, sequence_asset_path)
        authorization = self._authorize(plan, authorization_factory)
        return self.executor.execute_authorized(plan, authorization)

    def inspect_job(
        self,
        intent: UnrealTaskIntent,
        job_id: str,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealPlanExecutionResult:
        """Perform one fresh render-job inspection under external authorization."""
        plan = self.planner.plan_render_job_inspection(intent, job_id)
        authorization = self._authorize(plan, authorization_factory)
        return self.executor.execute_authorized(plan, authorization)

    @staticmethod
    def _job_state(evidence: UnrealEvidence) -> dict:
        state = evidence.observed_state
        if not isinstance(state, dict):
            raise UnrealRenderWorkflowError(
                "render-job evidence observed_state must be a mapping"
            )

        if "job_id" in state:
            job_state = state
        elif len(state) == 1:
            candidate = next(iter(state.values()))
            job_state = candidate.get("render_job") if isinstance(candidate, dict) else None
        else:
            job_state = None

        if not isinstance(job_state, dict):
            raise UnrealRenderWorkflowError(
                "render-job evidence does not contain a render_job object"
            )
        return job_state

    def wait_for_completion(
        self,
        intent: UnrealTaskIntent,
        job_id: str,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealRenderWorkflowResult:
        """Poll fresh job evidence until verified terminal completion."""
        start = self.clock()

        while True:
            result = self.inspect_job(intent, job_id, authorization_factory)
            if not isinstance(result, UnrealPlanExecutionResult) or not result.success:
                raise UnrealRenderWorkflowError(
                    "render-job inspection did not produce a successful execution result"
                )
            if not result.evidence_ledger:
                raise UnrealRenderWorkflowError(
                    "render-job inspection returned no evidence"
                )

            evidence = result.evidence_ledger[-1]
            state = self._job_state(evidence)

            if state.get("failed") is True:
                raise UnrealRenderWorkflowError(
                    f"render job failed: status={state.get('status')!r}"
                )

            status = state.get("status")
            if state.get("finished") is True:
                try:
                    verified = verify_render_job_completion(evidence, require_artifacts=True)
                except (TypeError, ValueError) as exc:
                    raise UnrealRenderWorkflowError(str(exc)) from exc

                receipt = UnrealRenderReceipt.issue(verified)
                persisted = self.receipt_store.save(receipt)

                return UnrealRenderWorkflowResult(
                    intent_id=intent.intent_id,
                    job_id=job_id,
                    final_evidence=verified,
                    receipt=receipt,
                    persisted_receipt=persisted,
                )

            elapsed = self.clock() - start
            if elapsed >= self.timeout_seconds:
                raise UnrealRenderWorkflowError(
                    f"render job did not complete within {self.timeout_seconds:g} seconds"
                )

            if status not in {"submitted", "queued", "rendering"}:
                raise UnrealRenderWorkflowError(
                    f"render job entered an unsupported terminal state: {status!r}"
                )

            remaining = self.timeout_seconds - elapsed
            self.sleeper(min(self.poll_interval_seconds, remaining))

    def run(
        self,
        intent: UnrealTaskIntent,
        render_config,
        sequence_asset_path: str,
        authorization_factory: Callable[[UnrealTaskPlan], UnrealPlanAuthorization],
    ) -> UnrealRenderWorkflowResult:
        """Configure, submit, poll, verify, receipt, and persist one render."""
        self.configure(intent, render_config, authorization_factory)
        submission = self.submit(intent, sequence_asset_path, authorization_factory)

        if not submission.evidence_ledger:
            raise UnrealRenderWorkflowError("render submission returned no evidence")

        submission_state = self._job_state(submission.evidence_ledger[-1])
        job_id = submission_state.get("job_id")
        if not isinstance(job_id, str) or not job_id.strip():
            raise UnrealRenderWorkflowError(
                "render submission evidence did not contain a non-empty job_id"
            )

        return self.wait_for_completion(intent, job_id, authorization_factory)
