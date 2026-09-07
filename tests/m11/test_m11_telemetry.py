"""M11.1 deterministic tests: append-only telemetry (design §11)."""

import json

import pytest

from planning.m11_router.telemetry import (
    AppendOnlyTelemetry,
    RouterTelemetryRecord,
    TelemetryValidationError,
)
from planning.m11_router.risk import RISK_DIMENSIONS


def _zero_dims():
    return {d: 0 for d in RISK_DIMENSIONS}


def _rec(task_id="task-1", attempt_id="a1", **kw):
    return RouterTelemetryRecord(
        task_id=task_id, attempt_id=attempt_id,
        risk_dimension_scores=_zero_dims(), risk_tier="L0",
        task_classes=frozenset({"docs"}),
        **kw,
    )


def test_telemetry_records_are_immutable(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    rec = _rec()
    tele.append(rec)
    with pytest.raises(AttributeError):
        rec.final_outcome = "PASS"  # frozen


def test_append_only_no_overwrite(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    tele.append(_rec(task_id="t", attempt_id="a1", final_outcome="ESCALATED"))
    tele.append(_rec(task_id="t", attempt_id="a2", final_outcome="PASS",
                     record_type="escalation", escalation_id="e1"))
    records = tele.read_task("t")
    assert len(records) == 2
    assert records[0].attempt_id == "a1"
    assert records[0].final_outcome == "ESCALATED"   # not overwritten
    assert records[1].attempt_id == "a2"
    assert records[1].final_outcome == "PASS"


def test_escalation_creates_new_record(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    tele.append(_rec(task_id="t", attempt_id="a1"))
    tele.append(_rec(task_id="t", attempt_id="a2", record_type="escalation", escalation_id="e1"))
    assert len(tele.read_task("t")) == 2


def test_sensitive_attempt_nonce_rejected(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    with pytest.raises(TelemetryValidationError):
        _rec(attempt_id="a1", selection_reason="attempt_nonce=abc123")  # nonce leaks


def test_sensitive_api_key_rejected(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a1", selection_reason="api_key=xyz")


def test_sensitive_hmac_key_rejected(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a1",
                              selection_reason="witness HMAC key deadbeef")


def test_sensitive_string_in_task_classes_rejected(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a1",
                              task_classes=frozenset({"secret-token"}))


def test_clean_record_is_allowed(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    rec = _rec(task_id="t", attempt_id="a1", final_outcome="PASS",
               selection_reason="max_dim=0; profile=m0")
    tele.append(rec)
    assert len(tele.read_all()) == 1


def test_telemetry_write_failure_fails_closed(tmp_path):
    # A non-writable target path should raise -> caller treats as UNKNOWN.
    tele = AppendOnlyTelemetry(tmp_path / "sub" / "tele.jsonl")
    # Attempt write to a path whose parent is a file -> should fail.
    blocker = tmp_path / "blocker"
    blocker.write_text("z")
    tele2 = AppendOnlyTelemetry(tmp_path / "blocker" / "tele.jsonl")
    with pytest.raises((TelemetryValidationError, OSError)):
        tele2.append(_rec())


def test_sensitive_value_dropped_not_persisted(tmp_path):
    # Fail-closed: a record containing a credential is never written.
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a1", 
                              selection_reason="Bearer abcdefghijklmnopqrstuvwxyz")
    assert tele.count() == 0
    assert not (tmp_path / "tele.jsonl").exists()