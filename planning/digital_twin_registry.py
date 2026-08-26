"""Fail-closed registry for canonical Digital Twin revisions.

The registry intentionally stores canonical revisions separately from production
representations. A representation can never become a canonical revision merely
because a tool generated or modified it.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Mapping, Tuple

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor, IdentityMatchStatus, evaluate_identity
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind, next_revision_sequence


@dataclass(frozen=True)
class RevisionRegistration:
    identity: DigitalTwinIdentity
    revision: DigitalTwinRevision


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _identity_snapshot(identity: DigitalTwinIdentity) -> dict[str, Any]:
    return {
        "twin_id": identity.twin_id,
        "entity_type": identity.entity_type,
        "anchors": [
            {
                "namespace": anchor.namespace,
                "key": anchor.key,
                "value": anchor.value,
                "required": anchor.required,
            }
            for anchor in identity.anchors
        ],
    }


def _revision_snapshot(revision: DigitalTwinRevision) -> dict[str, Any]:
    return {
        "twin_id": revision.twin_id,
        "revision_id": revision.revision_id,
        "sequence": revision.sequence,
        "kind": revision.kind.value,
        "source_revision_id": revision.source_revision_id,
        "source_fingerprint": revision.source_fingerprint,
    }


class DigitalTwinRegistry:
    def __init__(self) -> None:
        self._identities: Dict[str, DigitalTwinIdentity] = {}
        self._revisions: Dict[str, Tuple[DigitalTwinRevision, ...]] = {}

    def register_identity(self, identity: DigitalTwinIdentity) -> None:
        existing = self._identities.get(identity.twin_id)
        if existing is not None and existing.stable_fingerprint() != identity.stable_fingerprint():
            raise ValueError("Digital Twin identity cannot be silently replaced")
        self._identities[identity.twin_id] = identity
        self._revisions.setdefault(identity.twin_id, ())

    def identify(self, twin_id: str, observed_anchors) -> IdentityMatchStatus:
        identity = self._identities[twin_id]
        return evaluate_identity(identity, observed_anchors).status

    def register_revision(self, revision: DigitalTwinRevision) -> RevisionRegistration:
        identity = self._identities.get(revision.twin_id)
        if identity is None:
            raise ValueError("Digital Twin identity must be registered first")

        revisions = self._revisions.setdefault(revision.twin_id, ())
        expected = next_revision_sequence(revisions)
        if revision.sequence != expected:
            raise ValueError(f"revision sequence must be {expected}")
        if revision.source_fingerprint != identity.stable_fingerprint():
            raise ValueError("revision fingerprint does not match canonical Digital Twin")

        self._revisions[revision.twin_id] = revisions + (revision,)
        return RevisionRegistration(identity, revision)

    def revisions(self, twin_id: str) -> Tuple[DigitalTwinRevision, ...]:
        return self._revisions.get(twin_id, ())

    def snapshot(self) -> dict[str, Any]:
        """Return a deterministic, integrity-addressed registry snapshot."""
        identities = {
            twin_id: _identity_snapshot(self._identities[twin_id])
            for twin_id in sorted(self._identities)
        }
        revisions = {
            twin_id: [_revision_snapshot(revision) for revision in self._revisions.get(twin_id, ())]
            for twin_id in sorted(self._identities)
        }
        payload = {"identities": identities, "revisions": revisions}
        return {**payload, "snapshot_digest": _digest(payload)}

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "DigitalTwinRegistry":
        """Rehydrate only an untampered canonical registry snapshot."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("registry snapshot must be an object")
        if "identities" not in snapshot or "revisions" not in snapshot or "snapshot_digest" not in snapshot:
            raise ValueError("registry snapshot missing required fields")

        payload = {
            "identities": snapshot["identities"],
            "revisions": snapshot["revisions"],
        }
        if str(snapshot["snapshot_digest"]) != _digest(payload):
            raise ValueError("registry snapshot digest does not match its contents")
        if not isinstance(snapshot["identities"], Mapping) or not isinstance(snapshot["revisions"], Mapping):
            raise TypeError("registry snapshot identities and revisions must be objects")

        registry = cls()
        for twin_id, raw_identity in snapshot["identities"].items():
            if not isinstance(raw_identity, Mapping):
                raise TypeError("registry identity must be an object")
            anchors = tuple(
                IdentityAnchor(
                    namespace=str(raw.get("namespace", "")),
                    key=str(raw.get("key", "")),
                    value=str(raw.get("value", "")),
                    required=bool(raw.get("required", True)),
                )
                for raw in raw_identity.get("anchors", ())
            )
            identity = DigitalTwinIdentity(
                twin_id=str(raw_identity.get("twin_id", twin_id)),
                entity_type=str(raw_identity.get("entity_type", "")),
                anchors=anchors,
            )
            if identity.twin_id != str(twin_id):
                raise ValueError("registry identity key does not match twin_id")
            registry.register_identity(identity)

        for twin_id, raw_revisions in snapshot["revisions"].items():
            if twin_id not in registry._identities:
                raise ValueError("registry revision references an unregistered Digital Twin")
            if not isinstance(raw_revisions, (list, tuple)):
                raise TypeError("registry revisions must be an array")
            for raw in raw_revisions:
                if not isinstance(raw, Mapping):
                    raise TypeError("registry revision must be an object")
                try:
                    kind = RevisionKind(str(raw["kind"]))
                except (KeyError, ValueError) as exc:
                    raise ValueError("registry revision has invalid kind") from exc
                revision = DigitalTwinRevision(
                    twin_id=str(raw.get("twin_id", "")),
                    revision_id=str(raw.get("revision_id", "")),
                    sequence=int(raw.get("sequence", 0)),
                    kind=kind,
                    source_revision_id=raw.get("source_revision_id"),
                    source_fingerprint=raw.get("source_fingerprint"),
                )
                if revision.twin_id != twin_id:
                    raise ValueError("registry revision twin_id does not match registry key")
                registry.register_revision(revision)

        return registry
