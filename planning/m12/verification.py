"""Atlas M12.5 deterministic, fail-closed semantic verification v1."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from planning.m12.execution_plan import (
    UnrealExecutionPlan,
    _build_plan_id,
    compute_source_content_digest,
)
from planning.m12.runtime_adapter import UnrealRuntimeMapping
from planning.m12.semantic_task import UnrealProductionTaskDefinition
from planning.m12.task_classes import is_render_task_class
from planning.m12.expectation import (
    DEFINITIONS_BY_NAME,
    EXPECTATION_VOCABULARY_BY_KEY,
    compute_evidence_identity,
    compute_expectation_digest,
    compute_expectation_identity,
    compute_expected_value_identity,
    compute_invariant_result_digest,
)
from planning.m12.verification_result import (
    EvidenceTrustBasis,
    ObservationIdentity,
    UnrealSemanticVerificationResult,
    VERIFIER_REVISION,
    InvariantVerificationResult,
)
from planning.unreal_evidence_contract import verify_render_job_evidence
from planning.unreal_state_extraction import EXTRACTION_SCHEMA_VERSION, extract
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
    validate_response_correlation,
)


class M12VerificationError(ValueError):
    """Malformed verifier input that cannot safely be evaluated."""


# §8.0.1: no non-render invariant has an admissible typed expectation source in v1.
# This is a closed registry: arbitrary/caller-supplied predicates are impossible.
REGISTERED_INVARIANTS: Mapping[str, Mapping[str, Any]] = {}

_SESSION_IDENTITY_KEYS = frozenset({
    "editor_session_id",
    "process_id",
    "process_creation_time_utc",
    "server_start_time_utc",
    "engine_version",
    "project_identity",
})


def _mapping_item_key(item: Tuple[str, Any]) -> str:
    return item[0]


def _canonical_digest(value: Any) -> str:
    if isinstance(value, Mapping):
        value = {
            k: _canonical_digest_value(v)
            for k, v in sorted(value.items(), key=_mapping_item_key)
        }
    else:
        value = _canonical_digest_value(value)
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _canonical_digest_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise M12VerificationError("canonical mapping keys must be strings")
        return {
            k: _canonical_digest_value(v)
            for k, v in sorted(value.items(), key=_mapping_item_key)
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_digest_value(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise M12VerificationError("non-finite float in canonical result input")
        return value
    raise M12VerificationError(
        f"unsupported canonical value type: {type(value).__name__}"
    )


def _response_mapping(response: UnrealTransportResponse) -> Dict[str, Any]:
    return {
        "request_id": response.request_id,
        "operation_name": response.operation_name,
        "entity_ids": tuple(response.entity_ids),
        "success": response.success,
        "observed_state": response.observed_state,
        "error": response.error,
        "source": response.source,
        "schema_version": response.schema_version,
        "error_code": response.error_code,
    }


def _scope_identity(request: UnrealTransportRequest) -> Mapping[str, Any]:
    return {
        "operation_name": request.operation_name,
        "entity_ids": list(request.entity_ids),
    }


def _derive_observation(
    request: UnrealTransportRequest,
    response: UnrealTransportResponse,
) -> Tuple[ObservationIdentity, Mapping[str, Any]]:
    if type(request) is not UnrealTransportRequest:
        raise M12VerificationError("request must be an exact UnrealTransportRequest")
    if type(response) is not UnrealTransportResponse:
        raise M12VerificationError("response must be an exact UnrealTransportResponse")

    validate_response_correlation(request, response)
    extraction = extract(_response_mapping(response))
    tree = extraction.value_tree
    if tree.get("extraction_schema_version") != EXTRACTION_SCHEMA_VERSION:
        raise M12VerificationError("EXTRACTION_CONTRACT_REVISION_MISMATCH")

    world = tree.get("world")
    if not isinstance(world, Mapping):
        raise M12VerificationError("INVALID_OBSERVATION")

    session = dict(response.session_identity)
    if set(session) != set(_SESSION_IDENTITY_KEYS):
        raise M12VerificationError("OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED")
    if (
        not isinstance(session["editor_session_id"], str)
        or not session["editor_session_id"].strip()
        or not isinstance(session["process_id"], int)
        or isinstance(session["process_id"], bool)
        or session["process_id"] < 1
        or not isinstance(session["process_creation_time_utc"], str)
        or not session["process_creation_time_utc"].strip()
        or not isinstance(session["server_start_time_utc"], str)
        or not session["server_start_time_utc"].strip()
        or not isinstance(session["engine_version"], str)
        or not session["engine_version"].strip()
        or not isinstance(session["project_identity"], str)
        or not session["project_identity"].strip()
    ):
        raise M12VerificationError("OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED")

    engine_identity = session["engine_version"]
    if engine_identity != world.get("engine_version"):
        raise M12VerificationError("OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED")

    identity = ObservationIdentity(
        contract_revision=EXTRACTION_SCHEMA_VERSION,
        extractor_identity=str(tree["extraction_kind"]),
        engine_identity=str(engine_identity),
        session_identity=session,
        scope_identity=_scope_identity(request),
        request_identity=response.request_id,
        canonical_state_digest=extraction.digest,
    )
    return identity, tree


def _invariant_results(
    names: Iterable[str],
    *,
    observation_identity: Optional[ObservationIdentity],
    code: str,
) -> Tuple[InvariantVerificationResult, ...]:
    results = []
    for name in sorted(names):
        definition = DEFINITIONS_BY_NAME[name]
        expected_value_identity = compute_expected_value_identity(definition)
        evidence_identity = compute_evidence_identity(
            invariant_name=name,
            definition=definition,
            resolved_observables=(),
            value_state="ABSENT",
            observation_bound=False,
            observation_request_id=None,
            observation_scope=None,
            canonical_state_digest=None,
        )
        entry = {
            "invariant_name": name,
            "definition_id": name,
            "definition_revision": definition.definition_revision,
            "definition_digest": definition.definition_digest,
            "authority_class": definition.authority_class,
            "subject_scope": list(sorted(definition.subject_scope)),
            "expected_value_identity": expected_value_identity,
            "comparison": definition.comparison,
            "admissible_value_type": definition.admissible_value_type,
            "observed_path_patterns": list(sorted(definition.observable_paths)),
            "value_state": "ABSENT",
            "resolved_observables": [],
            "observation_bound": False,
            "observation_identity": None,
            "invariant_state": "UNKNOWN",
            "mismatch_reason": None,
            "evidence_identity": evidence_identity,
        }
        digest = compute_invariant_result_digest(entry)
        results.append(
            InvariantVerificationResult(
                invariant_name=name,
                definition_id=name,
                definition_revision=definition.definition_revision,
                definition_digest=definition.definition_digest,
                authority_class=definition.authority_class,
                subject_scope=tuple(sorted(definition.subject_scope)),
                expected_value_identity=expected_value_identity,
                comparison=definition.comparison,
                admissible_value_type=definition.admissible_value_type,
                observed_path_patterns=tuple(sorted(definition.observable_paths)),
                value_state="ABSENT",
                resolved_observables=(),
                observation_bound=False,
                observation_identity=None,
                invariant_state="UNKNOWN",
                mismatch_reason=None,
                evidence_identity=evidence_identity,
                invariant_result_digest=digest,
            )
        )
    return tuple(results)


def _classify_result_reason(
    failure_codes: Sequence[str],
    *,
    semantic_state: str,
) -> str:
    if semantic_state == "SATISFIED":
        return "SATISFIED"
    if semantic_state == "NOT_SATISFIED":
        return "EVALUATED_MISMATCH"
    if "RESOLVER_INTERNAL_FAILURE" in failure_codes:
        return "INTERNAL_FAILURE"
    if any(
        code in {
            "OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED",
            "OBSERVATION_CORRELATION_MISMATCH",
            "EXTRACTION_CONTRACT_REVISION_MISMATCH",
            "OBSERVATION_SCOPE_DIVERGENCE",
            "EXPECTATION_SCOPE_NOT_OBSERVED",
            "CONTRADICTORY",
            "EXPECTATION_CONTRADICTORY",
            "MISSING_INVARIANT_INPUT",
        }
        for code in failure_codes
    ):
        return "EVIDENCE_INSUFFICIENT"
    if any(
        code in {
            "EXPECTED_VALUE_UNAVAILABLE",
            "PRODUCTION_TARGET_NOT_ESTABLISHED",
            "PRODUCTION_TARGET_NOT_CANONICAL",
            "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED",
            "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED",
            "SEQUENCE_AGREEMENT_NOT_ESTABLISHED",
            "RENDER_EVIDENCE_MISSING",
        }
        for code in failure_codes
    ):
        return "AUTHORITY_ABSENT"
    return "BINDING_ABSENT"


def _build_result(
    *,
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    runtime_mapping_digest: Optional[str],
    observation_identity: Optional[ObservationIdentity],
    observation_digests: Sequence[str],
    render_job_identity: Optional[str],
    render_attempt_identity: Optional[int],
    render_evidence_identity: Optional[str],
    render_trust: str,
    invariant_results: Sequence[InvariantVerificationResult],
    semantic_state: str,
    render_state: str,
    overall_state: str,
    failure_codes: Iterable[str],
) -> UnrealSemanticVerificationResult:
    failures = tuple(sorted(set(failure_codes)))
    trust = EvidenceTrustBasis(
        semantic_observation=(
            "TRANSPORT_CORRELATED"
            if observation_identity is not None
            else "NOT_ESTABLISHED"
        ),
        render_evidence=render_trust,
    )
    vocabulary = EXPECTATION_VOCABULARY_BY_KEY.get(
        (task.canonical_task_id, task.task_version)
    )
    if vocabulary is None:
        raise M12VerificationError("EXPECTATION_VOCABULARY_MISMATCH")
    identity = compute_expectation_identity(
        vocabulary=vocabulary,
        task=task,
        plan=plan,
        target=None,
    )
    expectation_digest = compute_expectation_digest(identity)
    identity = {**identity, "expectation_digest": expectation_digest}
    reason_class = _classify_result_reason(
        failures, semantic_state=semantic_state
    )
    provenance = {
        "runtime_mapping_digest": runtime_mapping_digest,
        "legacy_result_contract": "M12.5-compatibility-metadata",
    }
    return UnrealSemanticVerificationResult(
        verifier_revision=VERIFIER_REVISION,
        expectation_identity=identity,
        expectation_digest=expectation_digest,
        task_identity=task.canonical_task_id,
        task_version=task.task_version,
        digital_twin_id=task.digital_twin_id,
        catalog_entry_name=vocabulary.entry_name,
        catalog_entry_version=vocabulary.entry_version,
        vocabulary_digest=vocabulary.vocabulary_digest,
        plan_id=plan.plan_id,
        source_content_digest=plan.source_content_digest,
        plan_content_digest=identity["plan_content_digest"],
        render_task=is_render_task_class(task.task_class),
        required_invariant_names=tuple(sorted(task.target_state.to_invariant_names())),
        observation_identity=observation_identity,
        observation_digests=tuple(sorted(set(observation_digests))),
        render_job_identity=render_job_identity,
        render_attempt_identity=render_attempt_identity,
        render_evidence_identity=render_evidence_identity,
        evidence_trust_basis=trust,
        invariant_results=tuple(invariant_results),
        semantic_state=semantic_state,
        render_state=render_state,
        overall_state=overall_state,
        outcome_reason_class=reason_class,
        failure_codes=failures,
        provenance=provenance,
        runtime_mapping_digest=runtime_mapping_digest,
    )
def _validate_plan_binding(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
) -> Tuple[str, ...]:
    digest = compute_source_content_digest(task)
    if digest != plan.source_content_digest:
        return ("IDENTITY_MISMATCH",)
    if plan.source_task_id != task.canonical_task_id:
        return ("IDENTITY_MISMATCH",)
    if plan.source_task_version != task.task_version:
        return ("IDENTITY_MISMATCH",)
    if plan.digital_twin_id != task.digital_twin_id:
        return ("IDENTITY_MISMATCH",)

    derived_plan_id = _build_plan_id(
        task.canonical_task_id,
        task.task_version,
        tuple(step.semantic_operation for step in plan.steps),
        digest,
    )
    if plan.plan_id != derived_plan_id:
        return ("IDENTITY_MISMATCH",)

    required = frozenset(task.target_state.invariant_names)
    carried = frozenset(
        requirement
        for step in plan.steps
        for requirement in step.verification_requirements
    )
    if not required:
        return ("EMPTY_REQUIRED_INVARIANT_SET",)
    if required - carried:
        return ("INCOMPLETE_REQUIRED_INVARIANT_SET",)
    if carried - required:
        return ("EXTRA_PLAN_VERIFICATION_REQUIREMENT",)
    if plan.render_plan != is_render_task_class(task.task_class):
        return ("PLAN_RENDER_CLASSIFICATION_MISMATCH",)
    return ()


def _derive_runtime_mapping_digest(
    mapping: Optional[UnrealRuntimeMapping],
    plan: UnrealExecutionPlan,
) -> Optional[str]:
    if mapping is None:
        return None
    if type(mapping) is not UnrealRuntimeMapping:
        raise M12VerificationError("RUNTIME_MAPPING_INVALID")
    if (
        mapping.plan_id != plan.plan_id
        or mapping.source_task_id != plan.source_task_id
        or mapping.source_task_version != plan.source_task_version
        or mapping.digital_twin_id != plan.digital_twin_id
        or mapping.source_task_digest != plan.source_content_digest
        or mapping.render_plan != plan.render_plan
    ):
        raise M12VerificationError("RUNTIME_MAPPING_IDENTITY_MISMATCH")
    return hashlib.sha256(
        mapping.canonical_json().encode("utf-8")
    ).hexdigest()


_R2A_BINDING_FAILURE_CODES = frozenset({
    "IDENTITY_MISMATCH",
    "EMPTY_REQUIRED_INVARIANT_SET",
    "INCOMPLETE_REQUIRED_INVARIANT_SET",
    "EXTRA_PLAN_VERIFICATION_REQUIREMENT",
    "PLAN_RENDER_CLASSIFICATION_MISMATCH",
    "PLAN_STEP_NOT_CANONICAL",
    "EXPECTATION_VOCABULARY_MISMATCH",
    "EXPECTATION_IDENTITY_MISMATCH",
    "EXPECTATION_DIGEST_MISMATCH",
})


def _observation_result(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    code: str,
    runtime_mapping_digest: Optional[str],
) -> UnrealSemanticVerificationResult:
    required = tuple(task.target_state.to_invariant_names())
    render = "NOT_VERIFIED" if task.render_task else "NOT_REQUIRED"
    trust = "NOT_ESTABLISHED" if task.render_task else "NOT_APPLICABLE"
    binding_failure = code in _R2A_BINDING_FAILURE_CODES
    return _build_result(
        task=task,
        plan=plan,
        runtime_mapping_digest=runtime_mapping_digest,
        observation_identity=None,
        observation_digests=(),
        render_job_identity=None,
        render_attempt_identity=None,
        render_evidence_identity=None,
        render_trust=trust,
        invariant_results=_invariant_results(
            required, observation_identity=None, code=code
        ),
        semantic_state="NOT_ESTABLISHED" if binding_failure else "INVALID_OBSERVATION",
        render_state=render,
        overall_state="NOT_ESTABLISHED" if binding_failure else "UNKNOWN",
        failure_codes=(code,),
    )


def verify_semantic_target(
    *,
    source_task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    observation_pairs: Sequence[
        Tuple[UnrealTransportRequest, UnrealTransportResponse]
    ],
    runtime_mapping: Optional[UnrealRuntimeMapping] = None,
    claimed_observation_digest: Optional[str] = None,
    render_job_record: Any = None,
    render_observed_state: Optional[Mapping[str, Any]] = None,
    render_entity_ids: Optional[Sequence[str]] = None,
    render_source: Optional[str] = None,
) -> UnrealSemanticVerificationResult:
    """Verify the resolved task/plan pair without executing or authorizing work.

    The v1 invariant registry has no admissible non-render expectation source.
    Consequently semantic invariants remain UNKNOWN and render-bearing tasks
    remain non-verified because sequence/request identity is not established.
    """

    if type(source_task) is not UnrealProductionTaskDefinition:
        raise M12VerificationError("source_task must be an exact UnrealProductionTaskDefinition")
    if type(plan) is not UnrealExecutionPlan:
        raise M12VerificationError("plan must be an exact UnrealExecutionPlan")

    try:
        runtime_mapping_digest = _derive_runtime_mapping_digest(runtime_mapping, plan)
    except M12VerificationError as exc:
        return _observation_result(
            source_task,
            plan,
            str(exc),
            None,
        )

    binding_errors = _validate_plan_binding(source_task, plan)
    if binding_errors:
        return _observation_result(
            source_task,
            plan,
            binding_errors[0],
            runtime_mapping_digest,
        )

    if not observation_pairs:
        return _observation_result(
            source_task,
            plan,
            "MISSING_INVARIANT_INPUT",
            runtime_mapping_digest,
        )

    identities = []
    try:
        for request, response in observation_pairs:
            identity, _tree = _derive_observation(request, response)
            identities.append(identity)
    except Exception as exc:
        code = str(exc).split(":", 1)[0]
        return _observation_result(
            source_task,
            plan,
            code if code else "INVALID_OBSERVATION",
            runtime_mapping_digest,
        )

    by_request_and_scope: Dict[
        Tuple[str, str, Tuple[str, ...]], set[str]
    ] = {}
    by_request: Dict[str, set[str]] = {}
    for identity in identities:
        scope_json = json.dumps(
            dict(identity.scope_identity),
            sort_keys=True,
            separators=(",", ":"),
        )
        key = (
            source_task.canonical_task_id,
            identity.request_identity,
            tuple(identity.scope_identity["entity_ids"]),
        )
        by_request_and_scope.setdefault(key, set()).add(
            identity.canonical_state_digest
        )
        by_request.setdefault(identity.request_identity, set()).add(scope_json)

    if any(len(scopes) > 1 for scopes in by_request.values()):
        return _observation_result(
            source_task, plan, "OBSERVATION_SCOPE_DIVERGENCE", runtime_mapping_digest
        )
    if any(len(digests) > 1 for digests in by_request_and_scope.values()):
        return _observation_result(
            source_task, plan, "CONTRADICTORY", runtime_mapping_digest
        )

    unique_digests = tuple(sorted({i.canonical_state_digest for i in identities}))
    observation_identity = identities[0]

    if (
        claimed_observation_digest is not None
        and claimed_observation_digest != observation_identity.canonical_state_digest
    ):
        return _build_result(
            task=source_task,
            plan=plan,
            runtime_mapping_digest=runtime_mapping_digest,
            observation_identity=observation_identity,
            observation_digests=unique_digests,
            render_job_identity=None,
            render_attempt_identity=None,
            render_evidence_identity=None,
            render_trust=(
                "NOT_ESTABLISHED" if source_task.render_task else "NOT_APPLICABLE"
            ),
            invariant_results=_invariant_results(
                source_task.target_state.invariant_names,
                observation_identity=observation_identity,
                code="IDENTITY_MISMATCH",
            ),
            semantic_state="NOT_ESTABLISHED",
            render_state="NOT_VERIFIED" if source_task.render_task else "NOT_REQUIRED",
            overall_state="NOT_ESTABLISHED",
            failure_codes=("IDENTITY_MISMATCH",),
        )

    failures = {
        "EXPECTED_VALUE_UNAVAILABLE"
    }
    invariant_results = _invariant_results(
        source_task.target_state.invariant_names,
        observation_identity=observation_identity,
        code="EXPECTED_VALUE_UNAVAILABLE",
    )

    render_job_identity = None
    render_attempt_identity = None
    render_evidence_identity = None
    render_trust = "NOT_APPLICABLE"
    render_state = "NOT_REQUIRED"

    if source_task.render_task:
        render_trust = "NOT_ESTABLISHED"
        render_state = "NOT_VERIFIED"
        failures.update({
            "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED",
            "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED",
            "SEQUENCE_AGREEMENT_NOT_ESTABLISHED",
        })

        supplied_any_render_input = (
            render_job_record is not None
            or render_observed_state is not None
            or render_entity_ids is not None
            or render_source is not None
        )
        if supplied_any_render_input:
            if render_job_record is None or render_observed_state is None:
                failures.add("RENDER_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED")
            else:
                try:
                    evidence = verify_render_job_evidence(
                        operation_name="inspect_render_job",
                        entity_ids=tuple(render_entity_ids or ()),
                        observed_state=render_observed_state,
                        source=render_source or "ENGINE_LIVE",
                        job_record=render_job_record,
                    )
                    if (
                        getattr(render_job_record, "canonical_digital_twin_id", None)
                        != source_task.digital_twin_id
                    ):
                        failures.add("RENDER_JOB_TWIN_MISMATCH")
                    else:
                        render_job_identity = render_job_record.atlas_job_id
                        render_attempt_identity = render_job_record.attempt_ordinal
                        render_evidence_identity = _canonical_digest({
                            "operation_name": evidence.operation_name,
                            "entity_ids": list(evidence.entity_ids),
                            "observed_state": evidence.observed_state,
                            "source": evidence.source,
                        })
                        render_trust = "DURABLE_RECORD_BACKED"
                except Exception:
                    failures.add("RENDER_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED")
        else:
            failures.add("RENDER_EVIDENCE_MISSING")

    return _build_result(
        task=source_task,
        plan=plan,
        runtime_mapping_digest=runtime_mapping_digest,
        observation_identity=observation_identity,
        observation_digests=unique_digests,
        render_job_identity=render_job_identity,
        render_attempt_identity=render_attempt_identity,
        render_evidence_identity=render_evidence_identity,
        render_trust=render_trust,
        invariant_results=invariant_results,
        semantic_state="UNKNOWN",
        render_state=render_state,
        overall_state="NOT_ESTABLISHED",
        failure_codes=failures,
    )


__all__ = [
    "M12VerificationError",
    "REGISTERED_INVARIANTS",
    "verify_semantic_target",
]
