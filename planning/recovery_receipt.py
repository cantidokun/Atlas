"""Immutable recovery authorization receipt binding recovery to its inputs."""

from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class RecoveryReceipt:
    evidence_digest: str
    plan_digest: str
    authorization_digest: str

    def __post_init__(self) -> None:
        for name, value in (("evidence_digest", self.evidence_digest), ("plan_digest", self.plan_digest), ("authorization_digest", self.authorization_digest)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def receipt_digest(self) -> str:
        material = "|".join((self.evidence_digest, self.plan_digest, self.authorization_digest))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def matches(self, evidence_digest: str, plan_digest: str, authorization_digest: str) -> bool:
        return (
            self.evidence_digest == evidence_digest
            and self.plan_digest == plan_digest
            and self.authorization_digest == authorization_digest
        )
