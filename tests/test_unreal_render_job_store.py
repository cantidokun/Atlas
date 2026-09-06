"""Deterministic unit and integration tests for AtlasRenderJobRecord and AtlasRenderJobStore (Milestone 2).

Coverage targets:
1. Valid record creation
2. Schema-version rejection
3. Authoritative digest stability
4. Serialization round-trip (to_dict / from_dict)
5. Corrupted record detection & non-destructive quarantine
6. Digest mismatch detection & quarantine
7. Atomic replacement behavior
8. Duplicate create rejection
9. Stale-writer rejection via revision tracking
10. Exclusive store coordinator ownership
11. Exclusive per-job execution claim
12. Path traversal / invalid atlas_job_id rejection
13. Authoritative vs observed field separation
14. Lifecycle & recovery-state validation
15. Reload after process-style reconstruction
16. Disallowing synthetic success without attributable worker job identity
"""

import json
from pathlib import Path
import pytest

from planning.unreal_render_job_record import (
    AtlasRenderJobRecord,
    AtlasRenderJobRecordError,
    compute_authoritative_digest,
    validate_canonical_atlas_job_id,
)
from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)
from planning.unreal_render_job_store import (
    AtlasRenderJobStore,
    AtlasRenderJobStoreCorruptionError,
    AtlasRenderJobStoreError,
    AtlasRenderJobStoreLockError,
    AtlasRenderJobStoreStaleWriterError,
)


def _sample_intent_kwargs(atlas_job_id: str = "atlas-render-job-11111111-2222-3333-4444-555555555555"):
    return {
        "atlas_job_id": atlas_job_id,
        "attempt_ordinal": 1,
        "authorization_id": "auth-live-proof-001",
        "canonical_digital_twin_id": "digital-twin-soccer-pitch-01",
        "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence.AtlasSequencerFixtureSequence",
        "request_digest": "req-sha256-abcdef1234567890",
        "config_digest": "cfg-sha256-0987654321fedcba",
        "output_parent_directory": "C:/AtlasRenders",
        "output_directory": f"C:/AtlasRenders/{atlas_job_id}",
        "expected_output_spec": {"format": "png", "width": 1920, "height": 1080},
        "created_at": "2026-09-06T00:00:00Z",
        "submission_deadline": "2026-09-06T01:00:00Z",
        "execution_deadline": "2026-09-06T02:00:00Z",
    }


# ── Record Tests ─────────────────────────────────────────────────────────────

def test_valid_record_creation():
    kwargs = _sample_intent_kwargs()
    rec = AtlasRenderJobRecord.create_intent(**kwargs)

    assert rec.schema_version == 1
    assert rec.atlas_job_id == kwargs["atlas_job_id"]
    assert rec.attempt_ordinal == 1
    assert rec.lifecycle_state == RenderJobLifecycleState.PENDING_SUBMISSION
    assert rec.recovery_status == RenderJobRecoveryStatus.NONE
    assert rec.unreal_job_id is None
    assert rec.last_observed_revision == 0
    assert len(rec.authoritative_digest) == 64


def test_schema_version_rejection():
    kwargs = _sample_intent_kwargs()
    rec = AtlasRenderJobRecord.create_intent(**kwargs)
    d = rec.to_dict()
    d["schema_version"] = 2
    with pytest.raises(AtlasRenderJobRecordError, match="unsupported schema_version"):
        AtlasRenderJobRecord.from_dict(d)


def test_authoritative_digest_stability():
    kwargs = _sample_intent_kwargs()
    d1 = compute_authoritative_digest(
        schema_version=1,
        atlas_job_id=kwargs["atlas_job_id"],
        attempt_ordinal=kwargs["attempt_ordinal"],
        authorization_id=kwargs["authorization_id"],
        canonical_digital_twin_id=kwargs["canonical_digital_twin_id"],
        sequence_asset_path=kwargs["sequence_asset_path"],
        request_digest=kwargs["request_digest"],
        config_digest=kwargs["config_digest"],
        output_parent_directory=kwargs["output_parent_directory"],
        output_directory=kwargs["output_directory"],
        expected_output_spec=kwargs["expected_output_spec"],
    )
    d2 = compute_authoritative_digest(
        schema_version=1,
        atlas_job_id=kwargs["atlas_job_id"],
        attempt_ordinal=kwargs["attempt_ordinal"],
        authorization_id=kwargs["authorization_id"],
        canonical_digital_twin_id=kwargs["canonical_digital_twin_id"],
        sequence_asset_path=kwargs["sequence_asset_path"],
        request_digest=kwargs["request_digest"],
        config_digest=kwargs["config_digest"],
        output_parent_directory=kwargs["output_parent_directory"],
        output_directory=kwargs["output_directory"],
        expected_output_spec=kwargs["expected_output_spec"],
    )
    assert d1 == d2


def test_serialization_round_trip():
    kwargs = _sample_intent_kwargs()
    original = AtlasRenderJobRecord.create_intent(**kwargs)
    as_dict = original.to_dict()
    restored = AtlasRenderJobRecord.from_dict(as_dict)

    assert restored == original
    assert restored.authoritative_digest == original.authoritative_digest


def test_path_traversal_rejection():
    with pytest.raises(AtlasRenderJobRecordError, match="illegal path characters"):
        validate_canonical_atlas_job_id("../../../secret")
    with pytest.raises(AtlasRenderJobRecordError, match="illegal path characters"):
        validate_canonical_atlas_job_id("job/with/slashes")
    with pytest.raises(AtlasRenderJobRecordError, match="canonical identifier format"):
        validate_canonical_atlas_job_id("not-a-uuid")


def test_output_directory_must_contain_job_id():
    kwargs = _sample_intent_kwargs()
    kwargs["output_directory"] = "C:/AtlasRenders/unisolated_dir"
    with pytest.raises(AtlasRenderJobRecordError, match="must contain atlas_job_id"):
        AtlasRenderJobRecord.create_intent(**kwargs)


def test_terminal_state_cannot_regress():
    kwargs = _sample_intent_kwargs()
    rec = AtlasRenderJobRecord.create_intent(**kwargs)
    # Transition to failed
    terminal = rec.transition(lifecycle_state=RenderJobLifecycleState.FAILED)
    assert terminal.lifecycle_state == RenderJobLifecycleState.FAILED

    # Attempt to regress back to RENDERING
    with pytest.raises(AtlasRenderJobRecordError, match="illegal terminal state regression"):
        terminal.transition(lifecycle_state=RenderJobLifecycleState.RENDERING)


def test_disallow_synthetic_success_without_engine_job():
    kwargs = _sample_intent_kwargs()
    rec = AtlasRenderJobRecord.create_intent(**kwargs)
    # Attempting to verify or finalize without an attributable unreal_job_id must be rejected
    with pytest.raises(AtlasRenderJobRecordError, match="attributable engine job identity"):
        rec.transition(lifecycle_state=RenderJobLifecycleState.VERIFIED)

    with pytest.raises(AtlasRenderJobRecordError, match="attributable engine job identity"):
        rec.transition(lifecycle_state=RenderJobLifecycleState.FINALIZED)


# ── Store Persistence & Concurrency Tests ────────────────────────────────────

def test_store_create_and_load(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    kwargs = _sample_intent_kwargs()
    record = AtlasRenderJobRecord.create_intent(**kwargs)

    saved = store.create(record)
    assert saved == record
    assert store.exists(record.atlas_job_id)

    loaded = store.load(record.atlas_job_id)
    assert loaded == record
    assert loaded.authoritative_digest == record.authoritative_digest


def test_store_duplicate_create_rejected(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    kwargs = _sample_intent_kwargs()
    record = AtlasRenderJobRecord.create_intent(**kwargs)

    store.create(record)
    with pytest.raises(AtlasRenderJobStoreError, match="Cannot create existing job"):
        store.create(record)


def test_store_update_with_stale_writer_rejection(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    kwargs = _sample_intent_kwargs()
    record = AtlasRenderJobRecord.create_intent(**kwargs)
    store.create(record)

    # Transition revision 0 -> 1
    updated_1 = record.transition(
        lifecycle_state=RenderJobLifecycleState.SUBMITTED,
        atlas_submitted_at="2026-09-06T00:01:00Z",
    )
    store.update(updated_1, expected_revision=0)

    # Stale writer trying to update using old revision 0
    stale_update = record.transition(
        lifecycle_state=RenderJobLifecycleState.FAILED,
    )
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="Stale writer"):
        store.update(stale_update, expected_revision=0)

    # Implicit non-monotonic update rejection
    stale_implicit = AtlasRenderJobRecord.from_dict({
        **updated_1.to_dict(),
        "last_observed_revision": 1,  # Not strictly greater than current (1)
    })
    with pytest.raises(AtlasRenderJobStoreStaleWriterError, match="Monotonic revision violation"):
        store.update(stale_implicit)


def test_store_detects_corrupt_file_and_quarantines(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    kwargs = _sample_intent_kwargs()
    record = AtlasRenderJobRecord.create_intent(**kwargs)
    store.create(record)

    # Tamper with the raw file to make it unparseable JSON
    file_path = store._job_file_path(record.atlas_job_id)
    file_path.write_text("CORRUPTED_NON_JSON_DATA", encoding="utf-8")

    with pytest.raises(AtlasRenderJobStoreCorruptionError, match="quarantined"):
        store.load(record.atlas_job_id)

    # Original file should be gone, moved to quarantine
    assert not file_path.exists()
    quarantined_files = list(store.quarantine_dir.glob("*.corrupt.*"))
    assert len(quarantined_files) >= 1


def test_store_detects_digest_mismatch_and_quarantines(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    kwargs = _sample_intent_kwargs()
    record = AtlasRenderJobRecord.create_intent(**kwargs)
    store.create(record)

    # Tamper with an authoritative field inside JSON
    file_path = store._job_file_path(record.atlas_job_id)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    payload["record"]["sequence_asset_path"] = "/Game/Malicious/ChangedSequence"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AtlasRenderJobStoreCorruptionError, match="authoritative_digest mismatch"):
        store.load(record.atlas_job_id)

    assert not file_path.exists()
    quarantined_files = list(store.quarantine_dir.glob("*.corrupt.*"))
    assert len(quarantined_files) >= 1


def test_coordinator_exclusive_lock(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")

    with store.acquire_coordinator("coord-A"):
        # Second coordinator must be rejected
        with pytest.raises(AtlasRenderJobStoreLockError, match="Another Atlas coordinator is currently active"):
            with store.acquire_coordinator("coord-B"):
                pass

    # After exit, coordinator-B can acquire
    with store.acquire_coordinator("coord-B"):
        pass


def test_per_job_execution_claim(tmp_path):
    store = AtlasRenderJobStore(tmp_path / "atlas_store")
    job_id = "atlas-render-job-99999999-aaaa-bbbb-cccc-dddddddddddd"

    with store.acquire_job_claim(job_id, "worker-1"):
        # Second worker attempting same job must be rejected
        with pytest.raises(AtlasRenderJobStoreLockError, match="Exclusive execution claim"):
            with store.acquire_job_claim(job_id, "worker-2"):
                pass

    # After release, worker-2 can acquire
    with store.acquire_job_claim(job_id, "worker-2"):
        pass
