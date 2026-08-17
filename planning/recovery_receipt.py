"""Immutable, fail-closed recovery authorization receipt."""

from dataclasses import dataclass
import hashlib
import hmac
from typing import Tuple


def _validate_identity(name: str, value: str) -> str:
    """Validate identity input without rewriting its canonical value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _canonical_material(values: Tuple[str, str, str]) -> bytes:
    """Encode each identity with its byte length to prevent boundary ambiguity."""
    encoded = []
    for value in values:
        raw = value.encode("utf-8")
        encoded.append(len(raw).to_bytes(8, "big"))
        encoded.append(raw)
    return b"".join(encoded)


@dataclass(frozen=True)
class RecoveryReceipt:
    evidence_digest: str
    plan_digest: str
    authorization_digest: str

    def __post_init__(self) -> None:
        _validate_identity("evidence_digest", self.evidence_digest)
        _validate_identity("plan_digest", self.plan_digest)
        _validate_identity("authorization_digest", self.authorization_digest)

    @property
    def receipt_digest(self) -> str:
        return hashlib.sha256(
            _canonical_material(
                (self.evidence_digest, self.plan_digest, self.authorization_digest)
            )
        ).hexdigest()

    def matches(
        self,
        evidence_digest: str,
        plan_digest: str,
        authorization_digest: str,
    ) -> bool:
        """Return true only for an exact, independently valid identity triple."""
        try:
            values = (
                _validate_identity("evidence_digest", evidence_digest),
                _validate_identity("plan_digest", plan_digest),
                _validate_identity("authorization_digest", authorization_digest),
            )
        except (TypeError, ValueError):
            return False

        return all(
            hmac.compare_digest(expected, actual)
            for expected, actual in zip(
                (self.evidence_digest, self.plan_digest, self.authorization_digest),
                values,
            )
        )
