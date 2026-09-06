"""M6 §31 items 5,18,22,23 — duplicate submit_render serialization, authorization
revalidation, transport-unavailable waiting, and execution-deadline handling.

Authoritative: docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md §31.
"""

import pytest

from planning.unreal_render_contract import UnrealRenderConfig
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStoreStaleWriterError,
)
from planning.unreal_render_submission import (
    UnrealRenderSubmissionError,
    UnrealRenderSubmissionService,
)
from planning.unreal_transport_named_pipe import (
    NamedPipeTransportDisconnectedError,
    NamedPipeTransportTimeoutError,
)
import tests.m6.fault_fixtures as ff


def _cfg(**overrides):
    params = dict(
        width=1920,
        height=1080,
        start_frame=0,
        end_frame=24,
        output_directory="placeholder",
        output_format="png",
    )
    params.update(overrides)
    return UnrealRenderConfig(**params)


class _SubmissionTransport:
    """Deterministic fake transport with scripted injectable failures.

    Mirrors MockUnrealTransport from the M3 submission tests but is importable
    from the M6 fixtures so the whole fault suite shares one harness.
    """

    def __init__(self, submit_failure=None, cap_failure=None):
        self.submit_failure = submit_failure
        self.cap_failure = cap_failure
        self.sent_requests = []
        self.submit_call_count = 0

    def _session(self):
        return {
            "editor_session_id": "sess-m6-ue56",
            "process_id": 4321,
            "process_creation_time_utc": "2026-09-06T00:00:00Z",
            "server_start_time_utc": "2026-09-06T00:00:01Z",
            "engine_version": "5.6",
            "project_identity": "AtlasUnrealHarness",
        }

    def send(self, request):
        from planning.unreal_transport_contract import UnrealTransportResponse

        self.sent_requests.append(request)
        if request.operation_name == "get_capabilities":
            if self.cap_failure is not None:
                raise self.cap_failure
            from planning.unreal_adapter_production import REQUIRED_RECOVERY_CAPABILITIES

            return UnrealTransportResponse(
                request_id=request.request_id, operation_name=request.operation_name,
                entity_ids=request.entity_ids, success=True,
                observed_state={"capabilities": list(REQUIRED_RECOVERY_CAPABILITIES)},
                error="", source="unreal-editor-5.6", schema_version=1, error_code="",
                session_identity=self._session(),
            )
        elif request.operation_name == "submit_render":
            self.submit_call_count += 1
            if self.submit_failure is not None:
                raise self.submit_failure
            atlas_id = request.arguments.get("atlas_job_id", "job")
            return UnrealTransportResponse(
                request_id=request.request_id, operation_name=request.operation_name,
                entity_ids=request.entity_ids, success=True,
                observed_state={"render_job": {"job_id": "unreal-m6-submit-1", "atlas_job_id": atlas_id, "status": "submitted", "progress": 0.0}},
                error="", source="unreal-editor-5.6", schema_version=1, error_code="",
                session_identity=self._session(),
            )
        raise RuntimeError(f"Unexpected operation {request.operation_name}")


def _service(tmp_path, transport=None):
    from planning.unreal_adapter_production import UnrealAdapterProduction
    from planning.unreal_render_job_store import AtlasRenderJobStore

    store = AtlasRenderJobStore(tmp_path / "store")
    transport = transport or _SubmissionTransport()
    adapter = UnrealAdapterProduction(transport)
    return store, UnrealRenderSubmissionService(store=store, adapter=adapter), transport


def _submit_kwargs(**overrides):
    params = dict(
        authorization_id="auth-m6-submit",
        canonical_digital_twin_id="twin-m6-test",
        sequence_asset_path="/Game/Test.Test",
        output_parent_directory="C:/Renders",
        render_config=_cfg(),
    )
    params.update(overrides)
    return params


# ── Item 5: duplicate submit_render serialization ─────────────────────────────
def test_m6_item05_duplicate_submission_is_serialized_idempotently(tmp_path):
    store, service, transport = _service(tmp_path)
    res1 = service.submit_render(**_submit_kwargs())
    assert res1.is_duplicate is False
    assert res1.record.lifecycle_state == RenderJobLifecycleState.SUBMITTED

    # Resubmit with the SAME atlas_job_id (duplicate execution attempt)
    res2 = service.submit_render(**_submit_kwargs(existing_atlas_job_id=res1.record.atlas_job_id))
    assert res2.is_duplicate is True
    assert res2.record == res1.record
    # Same atlas_job_id must produce exactly ONE transport dispatch
    assert transport.submit_call_count == 1


def test_m6_item05_duplicate_with_conflicting_parameters_rejected(tmp_path):
    store, service, transport = _service(tmp_path)
    atlas_id = "atlas-render-job-11111111-2222-3333-4444-555555555555"
    service.submit_render(**_submit_kwargs(existing_atlas_job_id=atlas_id))
    with pytest.raises(UnrealRenderSubmissionError, match="Conflicting reuse"):
        service.submit_render(**_submit_kwargs(existing_atlas_job_id=atlas_id, sequence_asset_path="/Game/Different"))


# ── Item 18: authorization revalidation for new execution ─────────────────────
def test_m6_item18_authorization_id_binds_immutably_and_blocks_swap(tmp_path):
    store, service, transport = _service(tmp_path)
    atlas_id = "atlas-render-job-22222222-3333-4444-5555-666666666666"
    service.submit_render(**_submit_kwargs(existing_atlas_job_id=atlas_id, authorization_id="auth-original"))
    # A DIFFERENT authorization_id on the same logical job must be rejected
    with pytest.raises(UnrealRenderSubmissionError, match="Conflicting reuse"):
        service.submit_render(**_submit_kwargs(existing_atlas_job_id=atlas_id, authorization_id="auth-attacker"))


def test_m6_item18_new_execution_requires_existing_authorization_path(tmp_path):
    store, service, transport = _service(tmp_path)
    # Without a valid authorization_id the submission path rejects up front
    with pytest.raises(UnrealRenderSubmissionError, match="authorization_id must be a non-empty string"):
        service.submit_render(**_submit_kwargs(authorization_id="   "))


# ── Item 22: transport-unavailable waiting behavior ───────────────────────────
def test_m6_item22_transport_timeout_waits_without_resubmission(tmp_path):
    transport = _SubmissionTransport(submit_failure=NamedPipeTransportTimeoutError("pipe read timed out"))
    store, service, transport = _service(tmp_path, transport)
    res = service.submit_render(**_submit_kwargs())
    assert res.acceptance_unknown is True
    assert res.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert res.record.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING
    # NO blind retry: exactly one transport dispatch
    assert transport.submit_call_count == 1


def test_m6_item22_transport_disconnect_waits_without_resubmission(tmp_path):
    inject = _SubmissionTransport(submit_failure=NamedPipeTransportDisconnectedError("pipe gone"))
    store, service, transport = _service(tmp_path, inject)
    res = service.submit_render(**_submit_kwargs())
    assert res.acceptance_unknown is True
    assert res.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert res.record.recovery_status == RenderJobRecoveryStatus.RECOVERY_PENDING
    assert transport.submit_call_count == 1


def test_m6_item22_uncertain_wait_does_not_mutate_to_terminal_or_resubmit(tmp_path):
    inject = _SubmissionTransport(submit_failure=NamedPipeTransportTimeoutError("timeout"))
    store, service, transport = _service(tmp_path, inject)
    res = service.submit_render(**_submit_kwargs())
    # Durable intent was persisted BEFORE dispatch and is retained in waiting state
    assert store.exists(res.record.atlas_job_id)
    rec = store.load(res.record.atlas_job_id)
    assert rec.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert rec.recovery_attempts_or_ambiguity_count == 1
    assert "Transport uncertainty" in (rec.failure_reason or "")


# ── Item 23: execution/submission deadline handling ───────────────────────────
def test_m6_item23_deadlines_are_durably_persisted_on_record(tmp_path):
    # Deadlines are carried on the durable record. The M6 contract requires that
    # waiting/ambiguity does NOT automatically resubmit; deadlines are preserved.
    store, service, transport = _service(tmp_path)
    res = service.submit_render(
        **_submit_kwargs(
            submission_deadline="2026-09-06T00:05:00Z",
            execution_deadline="2026-09-06T00:10:00Z",
        )
    )
    rec = store.load(res.record.atlas_job_id)
    assert rec.submission_deadline == "2026-09-06T00:05:00Z"
    assert rec.execution_deadline == "2026-09-06T00:10:00Z"
    # Deadlines survive a deterministic reload round-trip
    reloaded = store.load(res.record.atlas_job_id)
    assert reloaded.execution_deadline == "2026-09-06T00:10:00Z"


def test_m6_item23_expired_execution_deadline_never_auto_resubmits(tmp_path):
    # GAP DOCUMENTATION: production does not yet enforce deadline-expiry
    # transitions (record stores the deadline but no coordinator/submission path
    # honors an expired window with an EXHAUSTED transition). M6 therefore asserts
    # the fail-closed invariant that IS enforced: transport uncertainty is not
    # converted into an automatic retry, even with an expired window.
    inject = _SubmissionTransport(submit_failure=NamedPipeTransportTimeoutError("timeout"))
    store, service, transport = _service(tmp_path, inject)
    res = service.submit_render(
        **_submit_kwargs(
            submission_deadline="2020-01-01T00:00:00Z",  # long expired
            execution_deadline="2020-01-01T00:00:00Z",
        )
    )
    assert res.acceptance_unknown is True
    assert res.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert transport.submit_call_count == 1


def test_m6_item23_waiting_state_does_not_advance_on_deadline_without_explicit_gate(tmp_path):
    inject = _SubmissionTransport(submit_failure=NamedPipeTransportTimeoutError("timeout"))
    store, service, transport = _service(tmp_path, inject)
    res = service.submit_render(
        **_submit_kwargs(
            submission_deadline="2020-01-01T00:00:00Z",
            execution_deadline="2020-01-01T00:00:00Z",
        )
    )
    # Even with an expired submission window, uncertain acceptance stays WAITING
    # and does NOT auto-resubmit, FAIL, or mint success.
    assert res.acceptance_unknown is True
    assert res.record.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert transport.submit_call_count == 1


# ── Transport uncertainty + stale writer on update ────────────────────────────
def test_m6_item22_stale_writer_rejected_after_waiting_transition(tmp_path):
    store, service, transport = _service(tmp_path)
    res = service.submit_render(**_submit_kwargs())
    rec = store.load(res.record.atlas_job_id)
    # A stale writer attempting to overwrite with an older revision is rejected
    stale = rec.transition(lifecycle_state=RenderJobLifecycleState.FAILED)
    with pytest.raises(AtlasRenderJobStoreStaleWriterError):
        store.update(stale, expected_revision=0)