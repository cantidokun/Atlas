"""Immutable recovery authorization receipt binding recovery to its inputs."""

from dataclasses import dataclass
import hashlib
import hmac


@dataclass(frozen=True)
class RecoveryReceipt:
    evidence_digest: str
    plan_digest: str
    authorization_digest: str

    def __post_init__(self) -> None:
        for name, value in (
            ("evidence_digest", self.evidence_digest),
            ("plan_digest", self.plan_digest),
            ("authorization_digest", self.authorization_digest),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def receipt_digest(self) -> str:
        """Return an unambiguous deterministic digest of all bound identities."""
        parts = (
            self.evidence_digest,
            self.plan_digest,
            self.authorization_digest,
        )
        material = b"".join(len(part.encode("utf-8")).to_bytes(8, "big") + part.encode("utf-8") for part in parts)
        return hashlib.sha256(material).hexdigest()

    def matches(self, evidence_digest: str, plan_digest: str, authorization_digest: str) -> bool:
        """Require an exact match across every recovery identity."""
        if not all(isinstance(value, str) and value.strip() for value in (evidence_digest, plan_digest, authorization_digest)):
            return False
        return all(
            hmac.compare_digest(expected, actual)
            for expected, actual in (
                (self.evidence_digest, evidence_digest),
                (self.plan_digest, plan_digest),
                (self.authorization_digest, authorization_digest),
            )
        )
