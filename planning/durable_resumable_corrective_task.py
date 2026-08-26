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
        registry: Any = None,
    ) -> None:
        if checkpoint.twin_id != revision.twin_id:
            raise ValueError("checkpoint belongs to a different Digital Twin")
        if checkpoint.revision_id != revision.revision_id:
            raise ValueError("checkpoint belongs to a different Digital Twin revision")
        if registry is not None:
            self._require_current_canonical_revision(registry, revision)
        self.checkpoint = checkpoint
        self.revision = revision
        self.observe = observe
        self.plan = plan
        self.executor = executor
        self.registry = registry

    @staticmethod
    def _require_current_canonical_revision(registry: Any, revision: DigitalTwinRevision) -> None:
        require = getattr(registry, "require_canonical_revision", None)
        if callable(require):
            require(revision)
            return
        canonical_revision = getattr(registry, "canonical_revision", None)
        if not callable(canonical_revision):
            raise TypeError("registry must provide canonical_revision or require_canonical_revision")
        canonical = canonical_revision(revision.twin_id)
        if canonical.revision_id != revision.revision_id:
            raise ValueError("checkpoint revision is not the current canonical Digital Twin revision")
        if canonical.sequence != revision.sequence or canonical.source_fingerprint != revision.source_fingerprint:
            raise ValueError("checkpoint revision does not match canonical Digital Twin revision")

    def _require_current_revision(self) -> None:
        if self.registry is not None:
            self._require_current_canonical_revision(self.registry, self.revision)

    def resume(self, max_steps: int = 16) -> CorrectiveTaskResult:
        self._require_current_revision()
        fresh = self.observe()
        if self.checkpoint.matches_evidence(fresh):
            raise RuntimeError("durable resume requires fresh evidence before resume")
        remaining = list(self.plan(fresh))
        if not remaining:
            raise ValueError("durable resume requires at least one remaining action")
        # Replanning can itself expose a newly advanced canonical revision.
        # Recheck immediately before issuing fresh authorization so stale
        # revision state cannot cross the durable resume gate.
        self._require_current_revision()

        authorization = ReplanAuthorization.issue(fresh, remaining, self.checkpoint.authorization_id)
        continuation = ResumableCorrectiveTask(
            self._continuation_state(fresh),
            self.observe,
            self.plan,
            authorization.authorization_id,
            executor=self.executor,
        )
        return continuation.runtime.run(max_steps=max_steps)

    def issue_resume_authorization(self, evidence: Any) -> ReplanAuthorization:
        self._require_current_revision()
        if self.checkpoint.matches_evidence(evidence):
            raise RuntimeError("durable resume requires fresh evidence before authorization")
        remaining = list(self.plan(evidence))
        if not remaining:
            raise ValueError("durable resume requires at least one remaining action")
        # The planner is untrusted application logic and may observe or trigger
        # canonical-state changes. Never issue authorization against a revision
        # that became stale while planning.
        self._require_current_revision()
        return ReplanAuthorization.issue(evidence, remaining, self.checkpoint.authorization_id)

    def _continuation_state(self, evidence: Any):
        from planning.continuation_resume import ContinuationState

        return ContinuationState.create(
            self.checkpoint.task_id,
            self.checkpoint.completed_actions,
            evidence,
            self.checkpoint.authorization_id,
        )
