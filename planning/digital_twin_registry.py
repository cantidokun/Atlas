"""Fail-closed registry for canonical Digital Twin revisions.

The registry intentionally stores canonical revisions separately from production
representations. A representation can never become a canonical revision merely
because a tool generated or modified it.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityMatchStatus, evaluate_identity
from planning.digital_twin_revision import DigitalTwinRevision, next_revision_sequence


@dataclass(frozen=True)
class RevisionRegistration:
    identity: DigitalTwinIdentity
    revision: DigitalTwinRevision


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
