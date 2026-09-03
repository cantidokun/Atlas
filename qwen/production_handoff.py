"""Explicit handoff from Qwen semantic proposals into Atlas authorization.

Qwen remains proposal-only. This module converts an already validated Qwen
proposal into the canonical semantic task and exposes a narrow, explicit bridge
to the existing Atlas task-planner authorization path. It never accepts model-
issued authorization data and never executes tools.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan
from planning.task_definition import AtlasTaskDefinition
from planning.task_planner import TaskPlanProposal, instantiate_authorized_plans
from planning.production_task import ProductionTaskDefinition
from qwen.production_proposal import (
    QwenProductionProposal,
    compile_qwen_production_proposal,
    validate_qwen_production_proposal,
)


class QwenProductionHandoffError(ValueError):
    """Raised when a validated proposal cannot cross into Atlas safely."""


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _task_snapshot(task: ProductionTaskDefinition) -> Dict[str, Any]:
    return task.snapshot()


def _compiled_snapshot(task: AtlasTaskDefinition) -> Dict[str, Any]:
    return task.snapshot()


@dataclass(frozen=True)
class QwenProductionTaskHandoff:
    """Immutable handoff record between Qwen proposal validation and Atlas.

    The contained task objects are treated as trusted construction outputs, not
    model-owned authority. Authorization is not created during construction;
    ``authorize`` is an explicit caller operation that delegates to the
    existing Atlas ``task_planner`` boundary.
    """

    proposal: QwenProductionProposal
    semantic_task: ProductionTaskDefinition
    compiled_task: AtlasTaskDefinition
    proposal_digest: str
    semantic_task_digest: str
    compiled_task_digest: str

    @classmethod
    def from_proposal(cls, proposal: Any) -> "QwenProductionTaskHandoff":
        """Validate and compile one Qwen proposal without authorizing or executing it."""
        validated = proposal if isinstance(proposal, QwenProductionProposal) else validate_qwen_production_proposal(proposal)
        try:
            semantic_task = compile_qwen_production_proposal(validated.snapshot())
            compiled_task = semantic_task.compile()
        except (KeyError, TypeError, ValueError) as exc:
            raise QwenProductionHandoffError(str(exc)) from exc

        # The canonical semantic task and its compiled task are the only
        # objects allowed across this boundary. Bind their detached snapshots so
        # later mutation of a mutable metadata dictionary fails closed.
        proposal_snapshot = validated.snapshot()
        semantic_snapshot = _task_snapshot(semantic_task)
        compiled_snapshot = _compiled_snapshot(compiled_task)
        return cls(
            proposal=validated,
            semantic_task=semantic_task,
            compiled_task=compiled_task,
            proposal_digest=_canonical_digest(proposal_snapshot),
            semantic_task_digest=_canonical_digest(semantic_snapshot),
            compiled_task_digest=_canonical_digest(compiled_snapshot),
        )

    def verify_integrity(self) -> None:
        """Recompute the entire handoff binding and fail closed on any drift."""
        try:
            proposal_snapshot = self.proposal.snapshot()
            semantic_snapshot = _task_snapshot(self.semantic_task)
            compiled_snapshot = _compiled_snapshot(self.compiled_task)
        except (AttributeError, TypeError, ValueError) as exc:
            raise QwenProductionHandoffError("Qwen production handoff is malformed.") from exc

        if _canonical_digest(proposal_snapshot) != self.proposal_digest:
            raise QwenProductionHandoffError("Qwen production proposal integrity check failed.")
        if _canonical_digest(semantic_snapshot) != self.semantic_task_digest:
            raise QwenProductionHandoffError("Qwen semantic task integrity check failed.")
        if _canonical_digest(compiled_snapshot) != self.compiled_task_digest:
            raise QwenProductionHandoffError("Qwen compiled task integrity check failed.")

        # Recompile independently from the preserved proposal and require the
        # canonical task/provenance shape to remain byte-for-byte equivalent.
        rebuilt_semantic = compile_qwen_production_proposal(proposal_snapshot)
        rebuilt_compiled = rebuilt_semantic.compile()
        if _task_snapshot(rebuilt_semantic) != semantic_snapshot:
            raise QwenProductionHandoffError("Qwen semantic task provenance no longer matches the canonical compiler.")
        if _compiled_snapshot(rebuilt_compiled) != compiled_snapshot:
            raise QwenProductionHandoffError("Qwen compiled task provenance no longer matches the canonical compiler.")

    def task_plan_proposal(self) -> TaskPlanProposal:
        """Create the existing planner proposal without granting authorization."""
        self.verify_integrity()
        return TaskPlanProposal(
            evidence=list(self.compiled_task.evidence),
            actions=list(self.compiled_task.actions),
        )

    def authorize(self, authorization_id: str) -> Tuple[ActionPlan, ActionAuthorization]:
        """Explicitly authorize this exact task through the existing Atlas path."""
        self.verify_integrity()
        proposal = self.task_plan_proposal()
        _, action_plan = instantiate_authorized_plans(
            proposal,
            authorization_id=authorization_id,
        )
        authorization = action_plan.authorization
        if not isinstance(authorization, ActionAuthorization):
            raise QwenProductionHandoffError("Atlas authorization path did not return an ActionAuthorization.")
        return action_plan, authorization

    def snapshot(self) -> Dict[str, Any]:
        """Return detached provenance data for audit or continuation state."""
        return {
            "proposal": deepcopy(self.proposal.snapshot()),
            "semantic_task": deepcopy(self.semantic_task.snapshot()),
            "compiled_task": deepcopy(self.compiled_task.snapshot()),
            "proposal_digest": self.proposal_digest,
            "semantic_task_digest": self.semantic_task_digest,
            "compiled_task_digest": self.compiled_task_digest,
            "authorization": "not_requested",
            "execution": "not_attempted",
        }


__all__ = [
    "QwenProductionHandoffError",
    "QwenProductionTaskHandoff",
]
