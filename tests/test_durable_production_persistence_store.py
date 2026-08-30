"""Verify durable production restart state survives a process boundary."""

import json

import pytest

from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_persistence_store import JsonDurableProductionPersistenceStore


def test_json_store_round_trips_validated_restart_bundle(tmp_path):
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    # The registry snapshot is supplied by the production registry tests; this
    # test isolates the persistence transport and its integrity contract.
    registry_snapshot = {
        "revisions": {},
        "canonical": {},
    }
    bundle = DurableProductionPersistenceBundle(
        registry_snapshot=registry_snapshot,
        checkpoint_snapshot=checkpoint.snapshot(),
        resume_identity={
            "sequence_id": "sequence-1",
            "plan_id": "plan-1",
            "digital_twin_revision": "revision-1",
        },
        resume_identity_digest=None,
    )
    # Construct through the public snapshot contract after supplying the
    # identity digest via create-like normalization.
    from planning.durable_production_persistence import _identity_digest
    bundle = DurableProductionPersistenceBundle(
        registry_snapshot=registry_snapshot,
        checkpoint_snapshot=checkpoint.snapshot(),
        resume_identity={
            "digital_twin_revision": "revision-1",
            "plan_id": "plan-1",
            "sequence_id": "sequence-1",
        },
        resume_identity_digest=_identity_digest({
            "digital_twin_revision": "revision-1",
            "plan_id": "plan-1",
            "sequence_id": "sequence-1",
        }),
    )

    path = tmp_path / "production-state.json"
    JsonDurableProductionPersistenceStore(path).save(bundle)
    fresh_store = JsonDurableProductionPersistenceStore(path)
    restored = fresh_store.load()

    assert restored.snapshot() == bundle.snapshot()


def test_json_store_rejects_tampered_persisted_state(tmp_path):
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    path = tmp_path / "production-state.json"
    path.write_text(
        json.dumps(
            {
                "registry_snapshot": {"revisions": {}, "canonical": {}},
                "checkpoint_snapshot": checkpoint.snapshot(),
            }
        ),
        encoding="utf-8",
    )

    # Corrupt the checkpoint after it has been serialized, simulating a damaged
    # persisted restart state rather than an in-memory mutation.
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot["checkpoint_snapshot"]["next_operation_index"] = 1
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ValueError, match="integrity"):
        JsonDurableProductionPersistenceStore(path).load()
