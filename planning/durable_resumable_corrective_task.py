"""Durable production-task resume boundary.

A persisted ProductionTaskCheckpoint is progress metadata, never an execution
credential. Resumption requires the same canonical Digital Twin revision,
fresh evidence, and a newly issued corrective authorization.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from action_plan import ActionSpec
from planning.autonomous_corrective_task import CorrectiveTaskResult
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.resumable_corrective_task import ResumableCorrectiveTask
from planning.replan_authorization import ReplanAuthorization
from planning.digital_twin_revision import DigitalTwinRevision


class DurableResumableCorrectiveTask:
    def __init__(
        self,
        checkpoint: ProductionTaskCheckpoint,
        revision: DigitalTwinRevision,
        observe: Callable[[], Any],
        plan: Callable[[Any], Sequence[ActionSpec]],
        executor: Any = None,
    ) -> None:
        if checkpoint.twin_id != revision.twin_id:
            raise ValueError("checkpoint belongs to a different Digital Twin")
        if checkpoint.revision_id != revision.revision_id:
            raise ValueError("checkpoint belongs to a different Digital Twin revision")
        self.checkpoint = checkpoint
        self.revision = revision
        self.observe = observe
        self.plan = plan
        self.executor = executor

    def resume(self, max_steps: int = 16) -> CorrectiveTaskResult:
        fresh = self.observe()
        if self.checkpoint.matches_evidence(fresh):
            raise RuntimeError("durable resume requires fresh evidence before resume")
        remaining = list(self.plan(fresh))
        if not remaining:
            raise ValueError("durable resume requires at least one remaining action")

        authorization = ReplanAuthorization.issue(
            fresh,
            remaining,
            self.checkpoint.authorization_id,
        )
        continuation = ResumableCorrectiveTask(
            self._continuation_state(fresh),
            self.observe,
            self.plan,
            authorization.authorization_id,
            executor=self.executor,
        )
        return continuation.runtime.run(max_steps=max_steps)

    def issue_resume_authorization(self, evidence: Any) -> ReplanAuthorization:
        if self.checkpoint.matches_evidence(evidence):
            raise RuntimeError("durable resume requires fresh evidence before authorization")
        remaining = list(self.plan(evidence))
        if not remaining:
            raise ValueError("durable resume requires at least one remaining action")
        return ReplanAuthorization.issue(
            evidence,
            remaining,
            self.checkpoint.authorization_id,
        )

    def _continuation_state(self, evidence: Any):
        from planning.continuation_resume import ContinuationState

        return ContinuationState.create(
            self.checkpoint.task_id,
            self.checkpoint.completed_actions,
            evidence,
            self.checkpoint.authorization_id,
        )
