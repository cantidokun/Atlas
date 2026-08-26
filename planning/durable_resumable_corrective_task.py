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
from planning.production_checkpoint_lifecycle import ProductionCheckpointLifecycle
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
        checkpoint_lifecycle: ProductionCheckpointLifecycle | None = None,
    ) -> None:
        if checkpoint_lifecycle is not None and registry is not None and checkpoint_lifecycle.registry is not registry:
            raise ValueError("checkpoint lifecycle and registry must refer to the same Digital Twin registry")
        if checkpoint_lifecycle is None and registry is not None:
            checkpoint_lifecycle = ProductionCheckpointLifecycle(registry)
        if checkpoint_lifecycle is None and checkpoint.parent_checkpoint_digest is not None:
            raise ValueError("checkpoint with parent lineage requires a production checkpoint lifecycle")
        if checkpoint_lifecycle is not None:
            checkpoint = checkpoint_lifecycle.validate_checkpoint(checkpoint, revision)
        elif checkpoint.twin_id != revision.twin_id:
            raise ValueError("checkpoint belongs to a different Digital Twin")
        elif checkpoint.revision_id != revision.revision_id:
            raise ValueError("checkpoint belongs to a different Digital Twin revision")

        self.checkpoint = checkpoint
        self.revision = revision
        self.observe = observe
        self.plan = plan
        self.executor = executor
        self.checkpoint_lifecycle = checkpoint_lifecycle
        self.registry = checkpoint_lifecycle.registry if checkpoint_lifecycle is not None else registry

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
        if self.checkpoint_lifecycle is not None:
            self.checkpoint_lifecycle.registry.require_canonical_revision(self.revision)
        elif self.registry is not None:
            self._require_current_canonical_revision(self.registry, self.revision)

    def resume(self, max_steps: int = 16) -> CorrectiveTaskResult:
        self._require_current_revision()
        fresh = self.observe()
        if self.checkpoint.matches_evidence(fresh):
            raise RuntimeError("durable resume requires fresh evidence before resume")
        remaining = list(self.plan(fresh))
        if not remaining:
            raise ValueError("durable resume requires at least one remaining action")
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
