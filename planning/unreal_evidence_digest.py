"""Canonical, deterministic digests for Unreal execution evidence.

The digest is an identity for an ordered evidence ledger. It is deliberately
separate from authorization: evidence describes what the Unreal boundary
reported, while authorization decides what Atlas is allowed to execute.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from planning.unreal_evidence_contract import UnrealEvidence


class UnrealEvidenceDigestError(ValueError):
    """Raised when evidence contains a value that cannot be canonically encoded."""


def _canonicalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise UnrealEvidenceDigestError("evidence cannot contain non-finite floats")
        return value
    if isinstance(value, Mapping):
        items = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise UnrealEvidenceDigestError("evidence mapping keys must be strings")
            items.append((key, _canonicalize(item)))
        return {key: item for key, item in sorted(items)}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    raise UnrealEvidenceDigestError(
        f"unsupported evidence value type: {type(value).__name__}"
    )


def _evidence_material(evidence: UnrealEvidence) -> dict[str, Any]:
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence instance")
    return {
        "operation_name": evidence.operation_name,
        "entity_ids": tuple(evidence.entity_ids),
        "observed_state": evidence.observed_state,
        "source": evidence.source,
        "verified": evidence.verified,
    }


def digest_evidence(evidence: UnrealEvidence) -> str:
    """Return a SHA-256 identity for one canonical evidence record."""
    return digest_evidence_ledger((evidence,))


def digest_evidence_ledger(evidence_ledger: Sequence[UnrealEvidence]) -> str:
    """Return a SHA-256 identity for an ordered Unreal evidence ledger.

    Ordering is significant: the same evidence records in a different order
    produce a different digest. Mapping key order is not significant.
    """
    if not isinstance(evidence_ledger, Sequence) or isinstance(evidence_ledger, (str, bytes, bytearray)):
        raise TypeError("evidence_ledger must be a sequence of UnrealEvidence instances")
    material = _canonicalize([_evidence_material(evidence) for evidence in evidence_ledger])
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
