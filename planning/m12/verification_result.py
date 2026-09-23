"""Immutable producer-owned result contract for Atlas M12.5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple


VERIFIER_REVISION = "m12.5-v1"
TRUST_SEMANTIC = "TRANSPORT_CORRELATED"
TRUST_RENDER = frozenset({
    "DURABLE_RECORD_BACKED",
    "NOT_ESTABLISHED",
    "NOT_APPLICABLE",
})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class ObservationIdentity:
    contract_revision: int
    extractor_identity: str
    engine_identity: str
    session_identity: Mapping[str, Any]
    scope_identity: Mapping[str, Any]
    request_identity: str
    canonical_state_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_identity", _freeze(dict(self.session_identity)))
        object.__setattr__(self, "scope_identity", _freeze(dict(self.scope_identity)))


@dataclass(frozen=True, slots=True)
class EvidenceTrustBasis:
    semantic_observation: str
    render_evidence: str

    def __post_init__(self) -> None:
        if self.semantic_observation != TRUST_SEMANTIC:
            raise ValueError("semantic_observation must be TRANSPORT_CORRELATED")
        if self.render_evidence not in TRUST_RENDER:
            raise ValueError("unsupported render trust basis")


@dataclass(frozen=True, slots=True)
class UnrealSemanticVerificationResult:
    verifier_revision: str
    task_identity: str
    task_version: int
    digital_twin_id: str
    plan_id: str
    source_content_digest: str
    runtime_mapping_digest: Optional[str]
    required_invariant_names: Tuple[str, ...]
    observation_identity: Optional[ObservationIdentity]
    observation_digests: Tuple[str, ...]
    render_job_identity: Optional[str]
    render_attempt_identity: Optional[int]
    render_evidence_identity: Optional[str]
    evidence_trust_basis: EvidenceTrustBasis
    invariant_results: Tuple[Mapping[str, Any], ...]
    semantic_state: str
    render_state: str
    overall_state: str
    failure_codes: Tuple[str, ...]
    provenance: Mapping[str, Any]
    _canonical_source: Any = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("UnrealSemanticVerificationResult is sealed")

    def __post_init__(self) -> None:
        if self.verifier_revision != VERIFIER_REVISION:
            raise ValueError("unsupported verifier revision")
        if len(self.source_content_digest) != 64:
            raise ValueError("source_content_digest must be a SHA-256 digest")
        if self.semantic_state not in {
            "SATISFIED", "NOT_SATISFIED", "UNKNOWN", "INVALID_OBSERVATION"
        }:
            raise ValueError("invalid semantic state")
        if self.render_state not in {
            "NOT_REQUIRED", "NOT_VERIFIED", "VERIFIED", "INVALID",
            "RENDER_EVIDENCE_REQUIRED"
        }:
            raise ValueError("invalid render state")
        if self.overall_state not in {"SATISFIED", "NOT_ESTABLISHED", "UNKNOWN"}:
            raise ValueError("invalid overall state")
        object.__setattr__(self, "invariant_results", tuple(
            _freeze(dict(v)) for v in self.invariant_results
        ))
        object.__setattr__(self, "failure_codes", tuple(sorted(set(self.failure_codes))))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))
        source = {
            "verifier_revision": self.verifier_revision,
            "task_identity": self.task_identity,
            "task_version": self.task_version,
            "digital_twin_id": self.digital_twin_id,
            "plan_id": self.plan_id,
            "source_content_digest": self.source_content_digest,
            "runtime_mapping_digest": self.runtime_mapping_digest,
            "required_invariant_names": list(self.required_invariant_names),
            "observation_identity": None if self.observation_identity is None else {
                "contract_revision": self.observation_identity.contract_revision,
                "extractor_identity": self.observation_identity.extractor_identity,
                "engine_identity": self.observation_identity.engine_identity,
                "session_identity": _thaw(self.observation_identity.session_identity),
                "scope_identity": _thaw(self.observation_identity.scope_identity),
                "request_identity": self.observation_identity.request_identity,
                "canonical_state_digest": self.observation_identity.canonical_state_digest,
            },
            "observation_digests": list(self.observation_digests),
            "render_job_identity": self.render_job_identity,
            "render_attempt_identity": self.render_attempt_identity,
            "render_evidence_identity": self.render_evidence_identity,
            "evidence_trust_basis": {
                "semantic_observation": self.evidence_trust_basis.semantic_observation,
                "render_evidence": self.evidence_trust_basis.render_evidence,
            },
            "invariant_results": [_thaw(v) for v in self.invariant_results],
            "semantic_state": self.semantic_state,
            "render_state": self.render_state,
            "overall_state": self.overall_state,
            "failure_codes": list(self.failure_codes),
            "provenance": _thaw(self.provenance),
        }
        object.__setattr__(self, "_canonical_source", _freeze(source))

    @property
    def canonical_dict(self) -> Mapping[str, Any]:
        return _thaw(self._canonical_source)

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    @property
    def canonical_digest(self) -> str:
        return hashlib.sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()


__all__ = [
    "VERIFIER_REVISION",
    "ObservationIdentity",
    "EvidenceTrustBasis",
    "UnrealSemanticVerificationResult",
]
