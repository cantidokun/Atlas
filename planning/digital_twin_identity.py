"""Conservative identity primitives for Atlas Digital Twins.

The identity layer intentionally does not guess that two captures represent the
same real-world environment. It only returns MATCH when every required stable
anchor is present and equal, NO_MATCH when a shared anchor conflicts, and
INSUFFICIENT_EVIDENCE when the observation does not contain enough stable
identity information to merge safely.
"""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable, Tuple


class IdentityMatchStatus(str, Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class IdentityAnchor:
    namespace: str
    key: str
    value: str
    required: bool = True

    def canonical(self) -> Tuple[str, str, str, bool]:
        return (
            self.namespace.strip().lower(),
            self.key.strip().lower(),
            self.value.strip(),
            self.required,
        )


@dataclass(frozen=True)
class DigitalTwinIdentity:
    twin_id: str
    entity_type: str
    anchors: Tuple[IdentityAnchor, ...]

    def stable_fingerprint(self) -> str:
        payload = {
            "entity_type": self.entity_type.strip().lower(),
            "anchors": [anchor.canonical() for anchor in self.anchors],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdentityMatch:
    status: IdentityMatchStatus
    twin_id: str
    matched_anchors: Tuple[IdentityAnchor, ...] = ()
    missing_required_anchors: Tuple[IdentityAnchor, ...] = ()
    conflicting_anchors: Tuple[IdentityAnchor, ...] = ()


def evaluate_identity(
    identity: DigitalTwinIdentity,
    observed_anchors: Iterable[IdentityAnchor],
) -> IdentityMatch:
    """Evaluate whether observed identity evidence safely identifies a twin.

    Required anchors are the safety boundary: if any required anchor is absent,
    Atlas must not silently merge the observation into the canonical twin.
    A conflicting shared anchor is an explicit NO_MATCH.
    """

    observed = {anchor.canonical()[:3]: anchor for anchor in observed_anchors}
    matched = []
    missing = []
    conflicts = []

    for expected in identity.anchors:
        key = expected.canonical()[:2]
        candidates = [anchor for anchor_key, anchor in observed.items() if anchor_key == key]

        if not candidates:
            if expected.required:
                missing.append(expected)
            continue

        actual = candidates[0]
        if actual.value.strip() != expected.value.strip():
            conflicts.append(expected)
        else:
            matched.append(expected)

    if conflicts:
        return IdentityMatch(
            status=IdentityMatchStatus.NO_MATCH,
            twin_id=identity.twin_id,
            matched_anchors=tuple(matched),
            missing_required_anchors=tuple(missing),
            conflicting_anchors=tuple(conflicts),
        )

    if missing:
        return IdentityMatch(
            status=IdentityMatchStatus.INSUFFICIENT_EVIDENCE,
            twin_id=identity.twin_id,
            matched_anchors=tuple(matched),
            missing_required_anchors=tuple(missing),
        )

    return IdentityMatch(
        status=IdentityMatchStatus.MATCH,
        twin_id=identity.twin_id,
        matched_anchors=tuple(matched),
    )
