"""Durable, serializable checkpoint contract for production task continuation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional, Tuple

from action_plan import ActionSpec
from planning.digital_twin_revision import DigitalTwinRevision


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _action_snapshot(action: ActionSpec) -> dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
        "requires_success": action.requires_success,
    }


@dataclass(frozen=True)
class ProductionTaskCheckpoint:
    task_id: str
    twin_id: str
    revision_id: str
    completed_actions: Tuple[ActionSpec, ...]
    evidence_digest: str
    authorization_id: str
    checkpoint_digest: str
    parent_checkpoint_digest: Optional[str] = None

    @classmethod
    def create(
        cls,
        task_id: str,
        revision: DigitalTwinRevision,
        completed_actions: Tuple[ActionSpec, ...],
        evidence: Any,
        authorization_id: str,
        parent_checkpoint_digest: Optional[str] = None,
    ) -> "ProductionTaskCheckpoint":
        if not task_id.strip():
            raise ValueError("task_id must be non-empty")
        if not isinstance(revision, DigitalTwinRevision):
            raise TypeError("revision must be a DigitalTwinRevision")
        if not authorization_id.strip():
            raise ValueError("authorization_id must be non-empty")
        actions = tuple(completed_actions)
        if any(not isinstance(action, ActionSpec) for action in actions):
            raise TypeError("completed_actions must contain ActionSpec values")
        evidence_digest = _digest(evidence)
        payload = {
            "task_id": task_id,
            "twin_id": revision.twin_id,
            "revision_id": revision.revision_id,
            "completed_actions": [_action_snapshot(action) for action in actions],
            "evidence_digest": evidence_digest,
            "authorization_id": authorization_id,
            "parent_checkpoint_digest": parent_checkpoint_digest,
        }
        return cls(
            task_id=task_id,
            twin_id=revision.twin_id,
            revision_id=revision.revision_id,
            completed_actions=actions,
            evidence_digest=evidence_digest,
            authorization_id=authorization_id,
            checkpoint_digest=_digest(payload),
            parent_checkpoint_digest=parent_checkpoint_digest,
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        revision: DigitalTwinRevision,
    ) -> "ProductionTaskCheckpoint":
        """Rehydrate only when the immutable digest and revision binding validate."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("checkpoint snapshot must be an object")
        required = (
            "task_id",
            "twin_id",
            "revision_id",
            "completed_actions",
            "evidence_digest",
            "authorization_id",
            "checkpoint_digest",
        )
        missing = [key for key in required if key not in snapshot]
        if missing:
            raise ValueError(f"checkpoint snapshot missing required fields: {', '.join(missing)}")
        if snapshot["twin_id"] != revision.twin_id:
            raise ValueError("checkpoint belongs to a different Digital Twin")
        if snapshot["revision_id"] != revision.revision_id:
            raise ValueError("checkpoint belongs to a different Digital Twin revision")
        if not isinstance(snapshot["completed_actions"], (list, tuple)):
            raise TypeError("checkpoint completed_actions must be an array")

        actions = []
        for raw in snapshot["completed_actions"]:
            if not isinstance(raw, Mapping):
                raise TypeError("checkpoint action must be an object")
            actions.append(
                ActionSpec(
                    tool=str(raw.get("tool", "")),
                    arguments=dict(raw.get("arguments", {})),
                    name=str(raw.get("name", "")),
                    requires_success=bool(raw.get("requires_success", True)),
                )
            )

        task_id = str(snapshot["task_id"])
        evidence_digest = str(snapshot["evidence_digest"])
        authorization_id = str(snapshot["authorization_id"])
        parent_checkpoint_digest = snapshot.get("parent_checkpoint_digest")
        payload = {
            "task_id": task_id,
            "twin_id": revision.twin_id,
            "revision_id": revision.revision_id,
            "completed_actions": [_action_snapshot(action) for action in actions],
            "evidence_digest": evidence_digest,
            "authorization_id": authorization_id,
            "parent_checkpoint_digest": parent_checkpoint_digest,
        }
        expected_digest = _digest(payload)
        if str(snapshot["checkpoint_digest"]) != expected_digest:
            raise ValueError("checkpoint snapshot digest does not match its contents")
        return cls(
            task_id=task_id,
            twin_id=revision.twin_id,
            revision_id=revision.revision_id,
            completed_actions=tuple(actions),
            evidence_digest=evidence_digest,
            authorization_id=authorization_id,
            checkpoint_digest=expected_digest,
            parent_checkpoint_digest=parent_checkpoint_digest,
        )

    def matches_evidence(self, evidence: Any) -> bool:
        return _digest(evidence) == self.evidence_digest

    def snapshot(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "twin_id": self.twin_id,
            "revision_id": self.revision_id,
            "completed_actions": [_action_snapshot(action) for action in self.completed_actions],
            "evidence_digest": self.evidence_digest,
            "authorization_id": self.authorization_id,
            "checkpoint_digest": self.checkpoint_digest,
            "parent_checkpoint_digest": self.parent_checkpoint_digest,
        }
