from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator


def _registry():
    identity = DigitalTwinIdentity(
        "artifact-binding-twin", "reconstruction", ("anchor-a",)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id, "r1", 1, RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    registry.promote_revision(revision)
    return registry, revision


def test_registry_snapshot_round_trip_is_stable_for_rehydration():
    registry, _ = _registry()
    snapshot = registry.snapshot()
    restored = DigitalTwinRegistry.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot


def test_registry_snapshot_tampering_fails_closed_before_sequence_rehydration():
    registry, _ = _registry()
    snapshot = registry.snapshot()
    snapshot["revisions"][0]["revision_id"] = "tampered"
    with pytest.raises(ValueError, match="snapshot digest"):
        DurableProductionSequenceRehydrator(registry).rehydrate((), snapshot, {
            "completed_receipts": (),
            "next_operation_index": 0,
        })
