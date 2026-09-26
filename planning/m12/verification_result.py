"""Immutable producer-owned result contract for Atlas M12.6.

R2-A keeps M12.5 as the sole semantic-verdict owner while replacing the
open-ended result containers with the closed R6 result contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple


VERIFIER_REVISION = "m12.6-v1"
EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"
RESOLVER_REVISION = "m12.6-resolver-v1"
TRUST_SEMANTIC = "TRANSPORT_CORRELATED"
TRUST_SEMANTIC_UNESTABLISHED = "NOT_ESTABLISHED"
TRUST_RENDER = frozenset({
    "DURABLE_RECORD_BACKED",
    "NOT_ESTABLISHED",
    "NOT_APPLICABLE",
})

RESULT_SCHEMA = "m12.6-result-v1"

SEMANTIC_STATES = frozenset({
    "SATISFIED", "NOT_SATISFIED", "UNKNOWN", "INVALID_OBSERVATION", "NOT_ESTABLISHED"
})
OVERALL_STATES = frozenset({
    "SATISFIED", "NOT_SATISFIED", "UNKNOWN", "NOT_ESTABLISHED"
})
INVARIANT_STATES = frozenset({
    "SATISFIED", "NOT_SATISFIED", "UNKNOWN", "MISSING"
})
REASON_CLASSES = frozenset({
    "SATISFIED",
    "EVALUATED_MISMATCH",
    "EVIDENCE_INSUFFICIENT",
    "BINDING_ABSENT",
    "AUTHORITY_ABSENT",
    "INTERNAL_FAILURE",
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class EvidenceTrustBasis:
    semantic_observation: str
    render_evidence: str

    def __post_init__(self) -> None:
        if self.semantic_observation not in {
            TRUST_SEMANTIC, TRUST_SEMANTIC_UNESTABLISHED
        }:
            raise ValueError("unsupported semantic observation trust basis")
        if self.render_evidence not in TRUST_RENDER:
            raise ValueError("unsupported render trust basis")


@dataclass(frozen=True)
class InvariantVerificationResult:
    invariant_name: str
    definition_id: str
    definition_revision: int
    definition_digest: str
    authority_class: str
    subject_scope: Tuple[str, ...]
    expected_value_identity: str
    comparison: str
    admissible_value_type: str
    observed_path_patterns: Tuple[str, ...]
    value_state: str
    resolved_observables: Tuple[Any, ...]
    observation_bound: bool
    observation_identity: Optional[ObservationIdentity]
    invariant_state: str
    mismatch_reason: Optional[str]
    evidence_identity: str
    invariant_result_digest: str

    def __post_init__(self) -> None:
        if self.invariant_state not in INVARIANT_STATES:
            raise ValueError("invalid invariant state")
        if self.value_state not in {"PRESENT", "PRESENT_NULL", "ABSENT"}:
            raise ValueError("invalid value state")
        if self.authority_class != "CODE_CONSTANT":
            raise ValueError("R2-A authority_class must be CODE_CONSTANT")
        if tuple(self.subject_scope) != tuple(sorted(set(self.subject_scope))):
            raise ValueError("subject_scope must be sorted and unique")
        if tuple(self.observed_path_patterns) != tuple(sorted(set(self.observed_path_patterns))):
            raise ValueError("observed_path_patterns must be sorted and unique")
        if self.value_state == "ABSENT":
            if self.resolved_observables:
                raise ValueError("ABSENT invariant result cannot contain resolved observables")
        elif not self.resolved_observables:
            raise ValueError("present invariant result requires resolved observables")
        if not self.observation_bound and self.observation_identity is not None:
            raise ValueError("unbound invariant result cannot contain observation_identity")
        if self.observation_bound and self.observation_identity is None:
            raise ValueError("bound invariant result requires observation_identity")
        if self.invariant_state != "NOT_SATISFIED" and self.mismatch_reason is not None:
            raise ValueError("mismatch_reason is only valid for NOT_SATISFIED")
        if self.invariant_state == "NOT_SATISFIED" and not self.mismatch_reason:
            raise ValueError("NOT_SATISFIED requires mismatch_reason")

    @property
    def observed_value(self) -> Any:
        if not self.resolved_observables:
            return None
        if len(self.resolved_observables) == 1:
            return getattr(self.resolved_observables[0], "value", None)
        return tuple(getattr(item, "value", None) for item in self.resolved_observables)

    @property
    def observed_path(self) -> Optional[str]:
        if not self.resolved_observables:
            return None
        if len(self.resolved_observables) == 1:
            return getattr(self.resolved_observables[0], "concrete_path", None)
        return None

    def __getitem__(self, key: str) -> Any:
        # Compatibility-only access for legacy tests; this object is not a Mapping.
        if key == "name":
            return self.invariant_name
        if key == "status":
            return self.invariant_state
        if key == "failure_code":
            return self.mismatch_reason
        raise KeyError(key)

    def canonical_member_dict(self) -> Mapping[str, Any]:
        def obs_payload(obs: Any) -> Mapping[str, Any]:
            return {
                "concrete_path": obs.concrete_path,
                "value": obs.value,
            }

        return {
            "invariant_name": self.invariant_name,
            "definition_id": self.definition_id,
            "definition_revision": self.definition_revision,
            "definition_digest": self.definition_digest,
            "authority_class": self.authority_class,
            "subject_scope": list(self.subject_scope),
            "expected_value_identity": self.expected_value_identity,
            "comparison": self.comparison,
            "admissible_value_type": self.admissible_value_type,
            "observed_path_patterns": list(self.observed_path_patterns),
            "value_state": self.value_state,
            "resolved_observables": [obs_payload(v) for v in self.resolved_observables],
            "observation_bound": self.observation_bound,
            "observation_identity": (
                None if self.observation_identity is None
                else {
                    "contract_revision": self.observation_identity.contract_revision,
                    "extractor_identity": self.observation_identity.extractor_identity,
                    "engine_identity": self.observation_identity.engine_identity,
                    "session_identity": _thaw(self.observation_identity.session_identity),
                    "scope_identity": _thaw(self.observation_identity.scope_identity),
                    "request_identity": self.observation_identity.request_identity,
                    "canonical_state_digest": self.observation_identity.canonical_state_digest,
                }
            ),
            "invariant_state": self.invariant_state,
            "mismatch_reason": self.mismatch_reason,
            "evidence_identity": self.evidence_identity,
        }


@dataclass(frozen=True)
class UnrealSemanticVerificationResult:
    verifier_revision: str
    expectation_identity: Mapping[str, Any]
    expectation_digest: str
    task_identity: str
    task_version: int
    digital_twin_id: str
    catalog_entry_name: str
    catalog_entry_version: int
    vocabulary_digest: str
    plan_id: str
    source_content_digest: str
    plan_content_digest: str
    render_task: bool
    required_invariant_names: Tuple[str, ...]
    observation_identity: Optional[ObservationIdentity]
    observation_digests: Tuple[str, ...]
    render_job_identity: Optional[str]
    render_attempt_identity: Optional[int]
    render_evidence_identity: Optional[str]
    evidence_trust_basis: EvidenceTrustBasis
    invariant_results: Tuple[InvariantVerificationResult, ...]
    semantic_state: str
    render_state: str
    overall_state: str
    outcome_reason_class: str
    failure_codes: Tuple[str, ...]
    origin_status: str = "NOT_ESTABLISHED"
    runtime_mapping_digest: Optional[str] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        if self.verifier_revision != VERIFIER_REVISION:
            raise ValueError("unsupported verifier revision")
        if self.semantic_state not in SEMANTIC_STATES:
            raise ValueError("invalid semantic state")
        if self.overall_state not in OVERALL_STATES:
            raise ValueError("invalid overall state")
        if self.outcome_reason_class not in REASON_CLASSES:
            raise ValueError("invalid outcome reason class")
        if self.origin_status != "NOT_ESTABLISHED":
            raise ValueError("origin_status is fixed to NOT_ESTABLISHED")
        if tuple(self.required_invariant_names) != tuple(
            sorted(set(self.required_invariant_names))
        ):
            raise ValueError("required invariant names must be sorted and unique")
        if tuple(self.observation_digests) != tuple(
            sorted(set(self.observation_digests))
        ):
            raise ValueError("observation_digests must be sorted and unique")
        if self.overall_state == "SATISFIED":
            if self.semantic_state != "SATISFIED":
                raise ValueError("overall SATISFIED requires semantic SATISFIED")
            if self.render_state not in {"VERIFIED", "NOT_REQUIRED"}:
                raise ValueError("overall SATISFIED requires non-blocking render state")
        if any(
            entry.invariant_state in {"SATISFIED", "NOT_SATISFIED"}
            for entry in self.invariant_results
        ):
            # R2-A has no registered definitions, so evaluation states must remain unreachable.
            if not all(entry.invariant_state == "SATISFIED" for entry in self.invariant_results):
                raise ValueError("mixed evaluated and non-evaluated R2-A result states are forbidden")
            raise ValueError("evaluated invariant state is unreachable in R2-A")
        object.__setattr__(self, "expectation_identity", _freeze(dict(self.expectation_identity)))
        object.__setattr__(self, "failure_codes", tuple(sorted(set(self.failure_codes))))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))

    def _validate_coherence(self) -> None:
        if self.semantic_state == "SATISFIED":
            if self.overall_state != "SATISFIED":
                raise ValueError("semantic SATISFIED requires overall SATISFIED")
            if not self.required_invariant_names:
                raise ValueError("SATISFIED requires a non-empty invariant set")
            if any(entry.invariant_state != "SATISFIED" for entry in self.invariant_results):
                raise ValueError("SATISFIED requires every invariant result to be SATISFIED")
        if self.overall_state == "SATISFIED" and self.semantic_state != "SATISFIED":
            raise ValueError("overall SATISFIED requires semantic SATISFIED")
        for entry in self.invariant_results:
            expected = entry.canonical_member_dict()
            from planning.m12.expectation import compute_invariant_result_digest
            if compute_invariant_result_digest(expected) != entry.invariant_result_digest:
                raise ValueError("invariant result digest is not coherent")
        canonical = self._canonical_member_dict()
        from planning.m12.expectation import compute_result_digest
        compute_result_digest(canonical)

    def _canonical_member_dict(self) -> Mapping[str, Any]:
        identity = _thaw(self.expectation_identity)
        identity = dict(identity)
        identity.pop("expectation_digest", None)
        return {
            "schema": RESULT_SCHEMA,
            "verifier_revision": self.verifier_revision,
            "expectation_contract_revision": EXPECTATION_CONTRACT_REVISION,
            "resolver_revision": RESOLVER_REVISION,
            "registry_revision": identity["registry_revision"],
            "registry_digest": identity["registry_digest"],
            "target_table_revision": identity["target_table_revision"],
            "target_table_digest": identity["target_table_digest"],
            "production_target_id": identity["production_target_id"],
            "target_revision": identity["target_revision"],
            "target_digest": identity["target_digest"],
            "task_identity": self.task_identity,
            "task_version": self.task_version,
            "digital_twin_id": self.digital_twin_id,
            "catalog_entry_name": self.catalog_entry_name,
            "catalog_entry_version": self.catalog_entry_version,
            "vocabulary_digest": self.vocabulary_digest,
            "plan_id": self.plan_id,
            "source_content_digest": self.source_content_digest,
            "plan_content_digest": self.plan_content_digest,
            "render_task": self.render_task,
            "required_invariant_names": list(self.required_invariant_names),
            "expectation_identity": _thaw(self.expectation_identity),
            "expectation_digest": self.expectation_digest,
            "observation_identity": (
                None if self.observation_identity is None
                else {
                    "contract_revision": self.observation_identity.contract_revision,
                    "extractor_identity": self.observation_identity.extractor_identity,
                    "engine_identity": self.observation_identity.engine_identity,
                    "session_identity": _thaw(self.observation_identity.session_identity),
                    "scope_identity": _thaw(self.observation_identity.scope_identity),
                    "request_identity": self.observation_identity.request_identity,
                    "canonical_state_digest": self.observation_identity.canonical_state_digest,
                }
            ),
            "observation_digests": list(self.observation_digests),
            "render_job_identity": self.render_job_identity,
            "render_attempt_identity": self.render_attempt_identity,
            "render_evidence_identity": self.render_evidence_identity,
            "evidence_trust_basis": {
                "semantic_observation": self.evidence_trust_basis.semantic_observation,
                "render_evidence": self.evidence_trust_basis.render_evidence,
            },
            "invariant_results": [
                entry.canonical_member_dict()
                | {"invariant_result_digest": entry.invariant_result_digest}
                for entry in self.invariant_results
            ],
            "semantic_state": self.semantic_state,
            "render_state": self.render_state,
            "overall_state": self.overall_state,
            "outcome_reason_class": self.outcome_reason_class,
            "failure_codes": list(self.failure_codes),
            "origin_status": self.origin_status,
        }

    @property
    def canonical_dict(self) -> Mapping[str, Any]:
        self._validate_coherence()
        return dict(self._canonical_member_dict())

    def canonical_json(self) -> str:
        self._validate_coherence()
        from planning.unreal_state_extraction.jcs import canonicalize
        return canonicalize(self._canonical_member_dict())

    @property
    def result_digest(self) -> str:
        self._validate_coherence()
        from planning.m12.expectation import compute_result_digest
        return compute_result_digest(self._canonical_member_dict())

    @property
    def canonical_digest(self) -> str:
        return self.result_digest


__all__ = [
    "VERIFIER_REVISION",
    "EXPECTATION_CONTRACT_REVISION",
    "RESOLVER_REVISION",
    "RESULT_SCHEMA",
    "SEMANTIC_STATES",
    "OVERALL_STATES",
    "INVARIANT_STATES",
    "REASON_CLASSES",
    "ObservationIdentity",
    "EvidenceTrustBasis",
    "InvariantVerificationResult",
    "UnrealSemanticVerificationResult",
]
