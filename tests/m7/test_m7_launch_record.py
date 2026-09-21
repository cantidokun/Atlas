"""MF-3 — containment launch record + attempt-nonce custody (Contract V1 §10).

The launch record is the attempt's durable, authenticated identity claim for its Job
Object. These tests cover its format, its authentication, its attempt binding, and the
nonce custody rules: per attempt, supplied to the keeper only in-process, never persisted
in plaintext, never reused, never replaceable, and fail closed when custody is broken.
"""
from __future__ import annotations

import json
import pathlib

import pytest

import tests.m6.fault_fixtures as ff
from planning.unreal_containment_launch_record import (
    CONTAINMENT_DIRECTORY_NAME,
    LAUNCH_RECORD_SCHEMA_VERSION,
    SIGNED_LAUNCH_FIELDS,
    ContainmentLaunchRecord,
    ContainmentLaunchRecordError,
    ContainmentNonceCustodyError,
    assert_nonce_belongs_to_record,
    build_launch_record,
    containment_dir_for_store,
    launch_record_path,
    load_launch_record,
    require_attempt_nonce,
    verify_launch_record_for_job,
    write_launch_record,
)

NONCE = "m7-keeper-nonce-0123456789abcdef0123456789abcdef"


def _record(tmp_path, **overrides):
    store = ff.make_store(tmp_path)
    record = ff.make_submitted_record(tmp_path, attempt_nonce=NONCE, **overrides)
    store.create(record)
    return store, record


def _build(record, *, nonce=NONCE, **overrides):
    kwargs = dict(
        atlas_job_id=record.atlas_job_id,
        attempt_ordinal=record.attempt_ordinal,
        attempt_nonce=nonce,
        engine_pid=4242,
        process_creation_time_utc="2026-09-21T12:00:00+00:00",
        launch_composition_processes=1,
        project_identity=r"C:\AtlasProject",
        uproject_digest=ff.TEST_UPROJECT_DIGEST,
        keeper_identity="scripts/run_unreal_containment_keeper.py#instance-1",
        job_identity_descriptor="AtlasContainment-job",
    )
    kwargs.update(overrides)
    return build_launch_record(**kwargs)


# ── format & durability ──────────────────────────────────────────────────
def test_launch_record_round_trips_through_the_durable_store(tmp_path):
    store, record = _record(tmp_path)
    launch = _build(record)
    path = write_launch_record(containment_dir_for_store(store.root), launch, attempt_nonce=NONCE)

    assert path.parent.name == CONTAINMENT_DIRECTORY_NAME
    assert path.name == f"{record.atlas_job_id}__{record.attempt_ordinal}.json"
    loaded = load_launch_record(containment_dir_for_store(store.root), record.atlas_job_id,
                                record.attempt_ordinal)
    assert loaded == launch
    assert loaded.record_schema_version == LAUNCH_RECORD_SCHEMA_VERSION
    assert loaded.verify_digest(NONCE) is True
    assert set(loaded.to_dict()) == set(SIGNED_LAUNCH_FIELDS) | {"launch_record_digest"}


def test_launch_record_lives_outside_the_witness_journal_directory(tmp_path):
    store, record = _record(tmp_path)
    journal_root = tmp_path / "AtlasWitnessJournal"
    containment = containment_dir_for_store(store.root)
    assert journal_root.name != containment.name
    assert not str(containment).startswith(str(journal_root))


def test_launch_record_write_never_overwrites_an_attempt_identity(tmp_path):
    store, record = _record(tmp_path)
    directory = containment_dir_for_store(store.root)
    launch = _build(record)
    path = write_launch_record(directory, launch, attempt_nonce=NONCE)
    original = path.read_bytes()

    with pytest.raises(ContainmentLaunchRecordError) as excinfo:
        write_launch_record(directory, _build(record, keeper_identity="second-keeper"), attempt_nonce=NONCE)
    assert "already exists" in str(excinfo.value)
    assert path.read_bytes() == original  # the first attempt's provenance is intact


def test_unknown_and_missing_fields_are_rejected(tmp_path):
    store, record = _record(tmp_path)
    launch = _build(record)
    payload = launch.to_dict()

    with pytest.raises(ContainmentLaunchRecordError):
        ContainmentLaunchRecord.from_dict({**payload, "surprise": 1})
    missing = {k: v for k, v in payload.items() if k != "engine_pid"}
    with pytest.raises(ContainmentLaunchRecordError):
        ContainmentLaunchRecord.from_dict(missing)


def test_invalid_record_shapes_fail_closed(tmp_path):
    store, record = _record(tmp_path)
    with pytest.raises(ContainmentLaunchRecordError):
        _build(record, launch_composition_processes=0)  # a containment that contained nothing
    with pytest.raises(ContainmentLaunchRecordError):
        _build(record, deployment_mode="UNCONTAINED_ATTACHED")
    with pytest.raises(ContainmentLaunchRecordError):
        _build(record, uproject_digest="not-a-digest")


# ── authentication & attempt binding ─────────────────────────────────────
def test_digest_is_bound_to_the_durable_records_attempt_nonce(tmp_path):
    store, record = _record(tmp_path)
    launch = _build(record)
    assert launch.verify_against_job_record(record) == (True, "")
    assert launch.verify_digest(NONCE) is True
    assert launch.verify_digest(NONCE + "x") is False


def test_launch_record_of_another_attempt_never_binds(tmp_path):
    store, record = _record(tmp_path)
    other = _build(record, attempt_ordinal=record.attempt_ordinal + 1)
    ok, reason = other.verify_against_job_record(record)
    assert ok is False
    assert "attempt_ordinal" in reason


def test_tampered_launch_record_file_fails_closed(tmp_path):
    store, record = _record(tmp_path)
    directory = containment_dir_for_store(store.root)
    path = write_launch_record(directory, _build(record), attempt_nonce=NONCE)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["engine_pid"] = payload["engine_pid"] + 1  # a signed field, digest untouched
    path.write_text(json.dumps(payload), encoding="utf-8")

    resolved, reason = verify_launch_record_for_job(directory, record)
    assert resolved is None
    assert "HMAC authentication failed" in reason


def test_replayed_launch_record_from_another_attempt_is_refused(tmp_path):
    """An attempt-1 record copied onto attempt 2's identity path cannot authenticate."""
    store, record = _record(tmp_path)
    directory = containment_dir_for_store(store.root)
    first = write_launch_record(directory, _build(record), attempt_nonce=NONCE)

    second_identity_path = launch_record_path(directory, record.atlas_job_id, 2)
    second_identity_path.write_bytes(first.read_bytes())

    ordinal_two_record = ff.make_submitted_record(tmp_path / "second", attempt_ordinal=2,
                                                  attempt_nonce=NONCE)
    resolved, reason = verify_launch_record_for_job(directory, ordinal_two_record)
    assert resolved is None
    assert "attempt_ordinal" in reason or "HMAC" in reason


def test_absent_launch_record_is_unprovable_not_absent(tmp_path):
    store, record = _record(tmp_path)
    directory = containment_dir_for_store(store.root)
    assert load_launch_record(directory, record.atlas_job_id, record.attempt_ordinal) is None
    resolved, reason = verify_launch_record_for_job(directory, record)
    assert resolved is None
    assert "no containment launch record exists" in reason


def test_malformed_launch_record_file_fails_closed(tmp_path):
    store, record = _record(tmp_path)
    directory = containment_dir_for_store(store.root)
    path = launch_record_path(directory, record.atlas_job_id, record.attempt_ordinal)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    resolved, reason = verify_launch_record_for_job(directory, record)
    assert resolved is None
    assert "not parseable JSON" in reason


# ── MF-3 nonce custody ───────────────────────────────────────────────────
def test_nonce_is_generated_by_the_submitter_not_the_keeper(tmp_path):
    """The record's nonce must be the durable record's own value; a keeper cannot mint one."""
    store, record = _record(tmp_path)
    with pytest.raises(ContainmentNonceCustodyError):
        assert_nonce_belongs_to_record("keeper-invented-nonce", record)
    # A record the keeper authenticated with its own invented secret can be built but can
    # never bind to the durable record: the HMAC is recomputed from the record's own nonce.
    invented = _build(record, nonce="keeper-invented-nonce")
    forged_ok, forged_reason = invented.verify_against_job_record(record)
    assert forged_ok is False
    assert "HMAC authentication failed" in forged_reason
    # The honest path is the record's own nonce, and that one verifies.
    assert_nonce_belongs_to_record(record.attempt_nonce, record)
    assert _build(record).verify_against_job_record(record) == (True, "")


def test_missing_or_empty_nonce_produces_no_authenticated_record(tmp_path):
    store, record = _record(tmp_path)
    for bad in (None, "", "   ", 123, b"bytes"):
        with pytest.raises(ContainmentNonceCustodyError):
            require_attempt_nonce(bad)
        with pytest.raises(ContainmentNonceCustodyError):
            _build(record, nonce=bad)


def test_nonce_is_never_persisted_in_plaintext(tmp_path):
    store, record = _record(tmp_path)
    launch = _build(record)
    directory = containment_dir_for_store(store.root)
    path = write_launch_record(directory, launch, attempt_nonce=NONCE)

    raw = path.read_bytes()
    assert NONCE.encode() not in raw
    text = raw.decode("utf-8")
    assert NONCE not in text
    assert NONCE not in repr(launch)
    assert NONCE not in json.dumps(launch.to_dict())
    assert "attempt_nonce" not in launch.to_dict()


def test_writer_refuses_to_persist_a_record_carrying_the_nonce(tmp_path):
    """Defence in depth: if a field ever contained the secret, the write is refused."""
    store, record = _record(tmp_path)
    leaky = _build(record, keeper_identity=f"keeper-that-leaks-{NONCE}")
    with pytest.raises(ContainmentNonceCustodyError):
        write_launch_record(containment_dir_for_store(store.root), leaky, attempt_nonce=NONCE)


def test_nonce_is_never_reused_across_attempts(tmp_path):
    """Two attempts with different nonces cannot share one launch record."""
    store, record_one = _record(tmp_path)
    record_two = ff.make_submitted_record(tmp_path / "attempt2", attempt_ordinal=2,
                                          attempt_nonce="second-attempt-nonce-aaaaaaaa")
    directory = containment_dir_for_store(store.root)
    write_launch_record(directory, _build(record_one), attempt_nonce=NONCE)
    write_launch_record(directory, _build(record_two, nonce=record_two.attempt_nonce),
                        attempt_nonce=record_two.attempt_nonce)

    ok_one, _ = verify_launch_record_for_job(directory, record_one)
    ok_two, _ = verify_launch_record_for_job(directory, record_two)
    assert ok_one is not None and ok_two is not None
    assert ok_one.launch_record_digest != ok_two.launch_record_digest
