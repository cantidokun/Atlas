"""Operator-gated M12.5 v1 live promotion evidence.

This module is intentionally not pytest-collected.  It consumes the existing
UE 5.6.1 State Extraction transport and existing M5 render-evidence authority;
M12.5 itself never executes, authorizes, submits, retries, or issues receipts.

Usage:
    python -m tests.m12.m12_5_live_promotion_gate --phase non-render --report report.json
    python -m tests.m12.m12_5_live_promotion_gate --phase render --report report.json
    python -m tests.m12.m12_5_live_promotion_gate --phase all --report report.json
"""

from __future__ import annotations

import argparse
import copy
import datetime as datetime_module
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12.verification import verify_semantic_target
from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import verify_render_job_evidence
from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_store import AtlasRenderJobStore
from planning.unreal_state_extraction import extract
from planning.unreal_transport_contract import (
    UnrealTransportRequest,
    UnrealTransportResponse,
)
from planning.unreal_transport_named_pipe import create_named_pipe_transport


LIVE_AUTH_CONTEXT = "m12-5-live-promotion-gate"
ENTITY_ID = "FIELD_SURFACE"
DIGITAL_TWIN_ID = "canonical-digital-twin-field-surface"
SEQUENCE_PATH = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
SEQUENCE_NAME = "main"
REPORT_SCHEMA = "m12.5-live-promotion-v1"


def _now() -> str:
    return datetime_module.datetime.now(
        datetime_module.timezone.utc
    ).isoformat()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def _response_identity(response: UnrealTransportResponse) -> Dict[str, Any]:
    return {
        "request_id": response.request_id,
        "operation_name": response.operation_name,
        "entity_ids": list(response.entity_ids),
        "schema_version": response.schema_version,
        "success": response.success,
        "source": response.source,
        "session_identity_keys": sorted(response.session_identity.keys()),
    }


def _make_request(
    transport: Any,
    *,
    entity_ids: Sequence[str],
    request_id: str,
) -> Tuple[UnrealTransportRequest, UnrealTransportResponse]:
    request = UnrealTransportRequest(
        request_id=request_id,
        operation_name="extract_actor_state",
        capability="inspect_actor",
        kind="read",
        arguments={"entity_ids": list(entity_ids)},
        entity_ids=tuple(entity_ids),
        authorization_id=LIVE_AUTH_CONTEXT,
    )
    return request, transport.send(request)


def _resolve_non_render_task():
    return DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.sequence-configure",
        {
            "twin_id": DIGITAL_TWIN_ID,
            "sequence_name": SEQUENCE_NAME,
            "frame_start": 0,
            "frame_end": 24,
        },
        digital_twin_id=DIGITAL_TWIN_ID,
    )


def _resolve_render_task(*, twin_id: str = DIGITAL_TWIN_ID, sequence_name: str = SEQUENCE_NAME):
    return DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.render-execute",
        {
            "twin_id": twin_id,
            "sequence_name": sequence_name,
        },
        digital_twin_id=twin_id,
    )


def _result_summary(result: Any) -> Dict[str, Any]:
    return {
        "semantic_state": result.semantic_state,
        "render_state": result.render_state,
        "overall_state": result.overall_state,
        "failure_codes": list(result.failure_codes),
        "observation_digests": list(result.observation_digests),
        "render_job_identity": result.render_job_identity,
        "render_attempt_identity": result.render_attempt_identity,
        "render_evidence_identity": result.render_evidence_identity,
        "evidence_trust_basis": {
            "semantic_observation": result.evidence_trust_basis.semantic_observation,
            "render_evidence": result.evidence_trust_basis.render_evidence,
        },
        "canonical_digest": result.canonical_digest,
        "canonical_json": result.canonical_json(),
    }


def _state_mutation_with_actor_name(response: UnrealTransportResponse, name: str) -> UnrealTransportResponse:
    state = _clone(response.observed_state)
    node = dict(state["unreal_state_extraction"])
    actors = [dict(actor) for actor in node["actors"]]
    actors[0]["actor_name"] = name
    node["actors"] = actors
    state["unreal_state_extraction"] = node
    return replace(response, observed_state=state)


def _state_revision_mismatch(response: UnrealTransportResponse) -> UnrealTransportResponse:
    state = _clone(response.observed_state)
    node = dict(state["unreal_state_extraction"])
    node["extraction_schema_version"] = 999
    state["unreal_state_extraction"] = node
    return replace(response, observed_state=state)


def _render_observed_state_with_bad_config(
    observed_state: Mapping[str, Any],
) -> Mapping[str, Any]:
    state = _clone(observed_state)
    state["config_digest"] = "0" * 64
    return state


def run_non_render_gate() -> Dict[str, Any]:
    transport = create_named_pipe_transport()
    base_request, base_response = _make_request(
        transport,
        entity_ids=(ENTITY_ID,),
        request_id="m12-5-live-baseline",
    )
    if not base_response.success:
        raise RuntimeError(
            "live extraction baseline failed: "
            f"{base_response.error_code}: {base_response.error}"
        )

    extraction = extract({
        "request_id": base_response.request_id,
        "operation_name": base_response.operation_name,
        "entity_ids": list(base_response.entity_ids),
        "success": base_response.success,
        "observed_state": base_response.observed_state,
        "error": base_response.error,
        "source": base_response.source,
        "schema_version": base_response.schema_version,
        "error_code": base_response.error_code,
    })

    task = _resolve_non_render_task()
    plan = generate_execution_plan(task)

    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(base_request, base_response)],
    )
    baseline = _result_summary(result)

    if result.semantic_state != "UNKNOWN":
        raise AssertionError(f"expected semantic UNKNOWN, got {result.semantic_state}")
    if result.overall_state != "NOT_ESTABLISHED":
        raise AssertionError(f"expected NOT_ESTABLISHED, got {result.overall_state}")
    if result.render_state != "NOT_REQUIRED":
        raise AssertionError(f"unexpected render state: {result.render_state}")
    if "EXPECTED_VALUE_UNAVAILABLE" not in result.failure_codes:
        raise AssertionError("missing EXPECTED_VALUE_UNAVAILABLE fail-closed classification")

    repeat = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(base_request, base_response)],
    )
    repeat_summary = _result_summary(repeat)
    if repeat.canonical_json() != result.canonical_json():
        raise AssertionError("repeat verification changed canonical JSON")
    if repeat.canonical_digest != result.canonical_digest:
        raise AssertionError("repeat verification changed canonical digest")

    before_json = result.canonical_json()
    before_digest = result.canonical_digest
    object.__setattr__(result, "semantic_state", "SATISFIED")
    object.__setattr__(result, "overall_state", "SATISFIED")
    if result.canonical_json() != before_json or result.canonical_digest != before_digest:
        raise AssertionError("result immutability mechanism was not preserved")

    controls: Dict[str, Any] = {}

    missing_req, missing_resp = _make_request(
        transport,
        entity_ids=("NO_SUCH_ENTITY",),
        request_id="m12-5-live-missing-entity",
    )
    missing_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(missing_req, missing_resp)],
    )
    controls["missing_entity"] = _result_summary(missing_result)

    wrong_entity_request = replace(base_request, entity_ids=("IMPL_PERM_A",))
    wrong_entity_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(wrong_entity_request, base_response)],
    )
    controls["wrong_entity_identity"] = _result_summary(wrong_entity_result)

    other_task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.lighting-configure",
        {
            "twin_id": DIGITAL_TWIN_ID,
            "lighting_rig": {"mode": "promotion-gate-negative-control"},
        },
        digital_twin_id=DIGITAL_TWIN_ID,
    )
    other_plan = generate_execution_plan(other_task)
    mismatched_task_result = verify_semantic_target(
        source_task=task,
        plan=other_plan,
        observation_pairs=[(base_request, base_response)],
    )
    controls["mismatched_semantic_task_identity"] = _result_summary(
        mismatched_task_result
    )

    tampered_plan = copy.copy(plan)
    object.__setattr__(tampered_plan, "source_content_digest", "0" * 64)
    tampered_plan_result = verify_semantic_target(
        source_task=task,
        plan=tampered_plan,
        observation_pairs=[(base_request, base_response)],
    )
    controls["source_content_digest_mismatch"] = _result_summary(
        tampered_plan_result
    )

    bad_observation_digest = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(base_request, base_response)],
        claimed_observation_digest="0" * 64,
    )
    controls["modified_observation_digest"] = _result_summary(
        bad_observation_digest
    )

    correlation_bad = replace(
        base_response,
        request_id="m12-5-live-relabeled-request-id",
    )
    correlation_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(base_request, correlation_bad)],
    )
    controls["request_correlation_mismatch"] = _result_summary(
        correlation_result
    )

    session_bad = dict(base_response.session_identity)
    session_bad["engine_version"] = "forged-session-version"
    session_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(
            base_request,
            replace(base_response, session_identity=session_bad),
        )],
    )
    controls["session_identity_mismatch"] = _result_summary(session_result)

    revision_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(
            base_request,
            _state_revision_mismatch(base_response),
        )],
    )
    controls["contract_revision_mismatch"] = _result_summary(revision_result)

    conflicting_pair = _state_mutation_with_actor_name(
        base_response,
        "ConflictingDuplicate",
    )
    contradictory_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[
            (base_request, base_response),
            (base_request, conflicting_pair),
        ],
    )
    controls["conflicting_duplicate_observations"] = _result_summary(
        contradictory_result
    )

    scope_request, scope_response = _make_request(
        transport,
        entity_ids=("IMPL_PERM_A",),
        request_id=base_request.request_id,
    )
    scope_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[
            (base_request, base_response),
            (scope_request, scope_response),
        ],
    )
    controls["scope_divergence"] = _result_summary(scope_result)

    stale_relabelled = _state_mutation_with_actor_name(
        base_response,
        "StalePayloadRelabelled",
    )
    stale_result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(base_request, stale_relabelled)],
    )
    stale_summary = _result_summary(stale_result)
    controls["stale_payload_relabelled_current_envelope"] = {
        "status": "NOT DETECTABLE",
        "result": stale_summary,
        "detection_failure_codes": [
            code
            for code in stale_result.failure_codes
            if "IDENTITY" in code or "STALE" in code or "SESSION" in code
        ],
    }
    if controls["stale_payload_relabelled_current_envelope"]["detection_failure_codes"]:
        raise AssertionError(
            "stale relabelled payload was incorrectly claimed detectable"
        )

    controls["expectation_source_control"] = {
        "status": "NOT PROVEN",
        "reason": (
            "v1 has no admissible digest-bound semantic expectation source; "
            "ambient EXPECTED_VALUE_UNAVAILABLE is not evidence that the "
            "differential control mechanism executed"
        ),
        "ambient_result": baseline,
    }
    controls["registry_mutation_control"] = {
        "status": "NOT PROVEN",
        "reason": (
            "v1 has no registered semantic invariant and therefore no "
            "registry-derived expectation mechanism to exercise"
        ),
    }
    controls["sequence_identity_control"] = {
        "status": "NOT PROVEN",
        "reason": (
            "v1 has no reviewed typed task↔render sequence binding; "
            "the render dimension remains NOT_ESTABLISHED by design"
        ),
    }
    controls["catalog_resolution_control"] = {
        "status": "NOT PROVEN",
        "reason": "Q10 reviewed resolution binding is explicitly upstream/out of scope",
    }

    report = {
        "schema": REPORT_SCHEMA,
        "phase": "non-render",
        "timestamp_utc": _now(),
        "git_head": os.environ.get("GITHUB_SHA"),
        "engine": {
            "engine_version": base_response.session_identity.get("engine_version"),
            "project_identity": base_response.session_identity.get("project_identity"),
            "session_identity_keys": sorted(base_response.session_identity.keys()),
            "request_identity": _response_identity(base_response),
        },
        "observation": {
            "canonical_state_digest": extraction.digest,
            "canonical_bytes": len(extraction.canonical_bytes),
        },
        "task": {
            "canonical_task_id": task.canonical_task_id,
            "task_version": task.task_version,
            "digital_twin_id": task.digital_twin_id,
            "render_task": task.render_task,
            "required_invariant_names": list(task.target_state.to_invariant_names()),
        },
        "plan": {
            "plan_id": plan.plan_id,
            "source_content_digest": plan.source_content_digest,
        },
        "baseline_result": baseline,
        "repeat_result": repeat_summary,
        "controls": controls,
        "non_claims": [
            "No positive SATISFIED semantic result is claimed.",
            "The stale relabelled current-looking envelope is explicitly NOT DETECTABLE in v1.",
            "NOT PROVEN control statuses are coverage statements only and are not passes.",
            "This gate did not create or issue any render receipt.",
        ],
    }
    return report


def _render_dimension_summary(
    *,
    record: Any,
    task: Any,
    observed_state: Mapping[str, Any],
    m5_verified: bool,
    m5_config_digest_checked: bool,
) -> Dict[str, str]:
    return {
        "twin_agreement": (
            "ENFORCED"
            if record.canonical_digital_twin_id == task.digital_twin_id and m5_verified
            else "NOT_ESTABLISHED"
        ),
        "config_digest_agreement": (
            "ENFORCED"
            if m5_verified and m5_config_digest_checked
            else "NOT_ESTABLISHED"
        ),
        "request_digest_agreement": "NOT_ESTABLISHED",
        "sequence_agreement": "NOT_ESTABLISHED",
        "artifact_asset_identity": "UNKNOWN",
    }


def _render_job_task_inputs() -> Tuple[Any, Any]:
    task = _resolve_render_task()
    plan = generate_execution_plan(task)
    return task, plan


def run_render_gate() -> Dict[str, Any]:
    transport = create_named_pipe_transport()

    observation_request, observation_response = _make_request(
        transport,
        entity_ids=(ENTITY_ID,),
        request_id="m12-5-live-render-observation",
    )
    if not observation_response.success:
        raise RuntimeError(
            "render-gate live observation failed: "
            f"{observation_response.error_code}: {observation_response.error}"
        )

    task, plan = _render_job_task_inputs()

    repo_root = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
    import tempfile
    output_parent = Path(
        os.environ.get(
            "ATLAS_M12_5_RENDER_OUTPUT_PARENT",
            tempfile.mkdtemp(prefix="atlas-m12-5-render-output-"),
        )
    )
    output_parent.mkdir(parents=True, exist_ok=True)

    store_root = Path(
        os.environ.get(
            "ATLAS_M12_5_RENDER_STORE_ROOT",
            tempfile.mkdtemp(prefix="atlas-m12-5-render-store-"),
        )
    )
    store = AtlasRenderJobStore(store_root)
    adapter = create_production_adapter()

    render_config = UnrealRenderConfig(
        width=640,
        height=360,
        start_frame=0,
        end_frame=2,
        output_directory=str(output_parent),
        output_format="png",
    )

    receipt_probe = repo_root / "render_receipt.json"
    receipt_existed_before = receipt_probe.exists()
    receipt_before = receipt_probe.read_bytes() if receipt_existed_before else None

    submission = adapter  # retain explicit adapter ownership in the gate
    from planning.unreal_render_submission import UnrealRenderSubmissionService

    service = UnrealRenderSubmissionService(
        store=store,
        adapter=submission,
        receipt_store=None,
        worker_id="m12-5-live-gate",
    )
    submission_result = service.submit_render(
        authorization_id=LIVE_AUTH_CONTEXT,
        canonical_digital_twin_id=DIGITAL_TWIN_ID,
        sequence_asset_path=SEQUENCE_PATH,
        output_parent_directory=str(output_parent),
        render_config=render_config,
        entity_ids=(ENTITY_ID,),
    )

    record = submission_result.record
    unreal_job_id = record.unreal_job_id
    if submission_result.acceptance_unknown or not unreal_job_id:
        raise RuntimeError(
            "render submission did not produce a bounded accepted job: "
            f"acceptance_unknown={submission_result.acceptance_unknown}, "
            f"failure_reason={record.failure_reason!r}"
        )

    inspect_request = None
    inspect_source = None
    observed_state = None
    for attempt in range(120):
        inspect_op = UnrealOperation(
            capability=UnrealCapability.RENDER,
            kind=UnrealOperationKind.READ,
            name="inspect_render_job",
            arguments={
                "entity_ids": (ENTITY_ID,),
                "job_id": unreal_job_id,
            },
            entity_ids=(ENTITY_ID,),
        )
        evidence = adapter.inspect(inspect_op, LIVE_AUTH_CONTEXT)
        inspect_request = evidence
        observed_state = evidence.observed_state
        inspect_source = evidence.source
        if observed_state.get("finished") is True:
            break
        import time
        time.sleep(1)
    if not observed_state or observed_state.get("finished") is not True:
        raise RuntimeError("render job did not reach terminal state in live promotion gate")

    config_digest_check = observed_state.get("config_digest") == record.config_digest
    m5_verified = False
    m5_failure = None
    verified_evidence = None
    try:
        verified_evidence = verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=(ENTITY_ID,),
            observed_state=observed_state,
            source=inspect_source,
            job_record=record,
            evidence_source_class="ENGINE_LIVE",
        )
        m5_verified = True
    except Exception as exc:
        m5_failure = f"{type(exc).__name__}: {exc}"

    if not m5_verified:
        raise AssertionError(
            "M5 render evidence did not verify independently: " + str(m5_failure)
        )

    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(observation_request, observation_response)],
        render_job_record=record,
        render_observed_state=observed_state,
        render_entity_ids=(ENTITY_ID,),
        render_source=inspect_source,
    )
    summary = _result_summary(result)
    dimensions = _render_dimension_summary(
        record=record,
        task=task,
        observed_state=observed_state,
        m5_verified=m5_verified,
        m5_config_digest_checked=config_digest_check,
    )

    if result.render_state == "VERIFIED":
        raise AssertionError("M12.5 v1 incorrectly produced render_state=VERIFIED")
    if result.overall_state == "SATISFIED":
        raise AssertionError("M12.5 v1 incorrectly produced overall SATISFIED")
    if dimensions["request_digest_agreement"] != "NOT_ESTABLISHED":
        raise AssertionError("request digest agreement must remain NOT_ESTABLISHED")
    if dimensions["sequence_agreement"] != "NOT_ESTABLISHED":
        raise AssertionError("sequence agreement must remain NOT_ESTABLISHED")

    wrong_twin_task = _resolve_render_task(twin_id="wrong-twin")
    wrong_twin_plan = generate_execution_plan(wrong_twin_task)
    wrong_twin_result = verify_semantic_target(
        source_task=wrong_twin_task,
        plan=wrong_twin_plan,
        observation_pairs=[(observation_request, observation_response)],
        render_job_record=record,
        render_observed_state=observed_state,
        render_entity_ids=(ENTITY_ID,),
        render_source=inspect_source,
    )

    bad_config_state = _render_observed_state_with_bad_config(observed_state)
    bad_config_m5 = "NOT PROVEN"
    bad_config_error = None
    try:
        verify_render_job_evidence(
            operation_name="inspect_render_job",
            entity_ids=(ENTITY_ID,),
            observed_state=bad_config_state,
            source=inspect_source,
            job_record=record,
            evidence_source_class="ENGINE_LIVE",
        )
        bad_config_m5 = "UNEXPECTEDLY_ACCEPTED"
    except Exception as exc:
        bad_config_error = f"{type(exc).__name__}: {exc}"
        bad_config_m5 = "REFUSED"

    report = {
        "schema": REPORT_SCHEMA,
        "phase": "render",
        "timestamp_utc": _now(),
        "git_head": os.environ.get("GITHUB_SHA"),
        "task": {
            "canonical_task_id": task.canonical_task_id,
            "task_version": task.task_version,
            "digital_twin_id": task.digital_twin_id,
            "render_task": task.render_task,
        },
        "plan": {
            "plan_id": plan.plan_id,
            "source_content_digest": plan.source_content_digest,
            "render_plan": plan.render_plan,
        },
        "m5": {
            "verified": True,
            "job_identity": record.atlas_job_id,
            "attempt_identity": record.attempt_ordinal,
            "evidence_identity": _sha256_json(
                {
                    "operation_name": verified_evidence.operation_name,
                    "entity_ids": list(verified_evidence.entity_ids),
                    "observed_state": dict(verified_evidence.observed_state),
                    "source": verified_evidence.source,
                }
            ),
            "config_digest_agreement": "ENFORCED" if config_digest_check else "NOT_ESTABLISHED",
            "request_digest_agreement": "NOT_ESTABLISHED",
        },
        "m12_5": summary,
        "render_identity_dimensions": dimensions,
        "controls": {
            "wrong_twin": {
                "status": (
                    "PROVEN"
                    if "RENDER_JOB_TWIN_MISMATCH" in wrong_twin_result.failure_codes
                    else "FAILED"
                ),
                "result": _result_summary(wrong_twin_result),
            },
            "wrong_observed_config_digest": {
                "status": bad_config_m5,
                "m5_error": bad_config_error,
            },
            "wrong_sequence_identity": {
                "status": "NOT PROVEN",
                "reason": (
                    "no reviewed typed sequence/asset binding exists in v1; "
                    "sequence_agreement remains NOT_ESTABLISHED by design"
                ),
            },
            "ambiguous_sequence_identity": {
                "status": "NOT PROVEN",
                "reason": (
                    "no reviewed Q10 catalog-resolution binding exists in v1; "
                    "NOT_APPLICABLE is unreachable"
                ),
            },
            "caller_expectation_differential": {
                "status": "NOT PROVEN",
                "reason": (
                    "no admissible digest-bound semantic expectation source exists "
                    "in v1"
                ),
            },
            "catalog_resolution_Q10": {
                "status": "NOT PROVEN",
                "reason": "upstream reviewed resolution binding is out of scope",
            },
        },
        "render_output": {
            "output_files": list(observed_state.get("output_files", [])),
            "output_directory": record.output_directory,
            "receipt_store_used": False,
            "receipt_created_by_m12_5": False,
        },
        "non_claims": [
            "M5 verified the render evidence; M12.5 did not recreate M5 artifact verification.",
            "M12.5 did not issue or persist a render receipt.",
            "render_state VERIFIED was intentionally unreachable because sequence/request identity is NOT_ESTABLISHED.",
            "request_digest_agreement is NOT_ESTABLISHED, not a detected mismatch.",
            "Q10 catalog resolution and typed sequence binding remain upstream/out of scope.",
        ],
    }

    if receipt_existed_before:
        if not receipt_probe.exists() or receipt_probe.read_bytes() != receipt_before:
            raise AssertionError("live M12.5 render gate modified render_receipt.json")
    elif receipt_probe.exists():
        raise AssertionError("live M12.5 render gate unexpectedly created render_receipt.json")

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("non-render", "render", "all"),
        default="all",
    )
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    report: Dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "timestamp_utc": _now(),
        "phase": args.phase,
        "results": {},
    }

    if args.phase in ("non-render", "all"):
        report["results"]["non_render"] = run_non_render_gate()
    if args.phase in ("render", "all"):
        report["results"]["render"] = run_render_gate()

    Path(args.report).write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
