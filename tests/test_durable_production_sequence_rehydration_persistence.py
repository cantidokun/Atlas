from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator


def _registry():
    identity = DigitalTwinIdentity(
        "twin-1",
        "soccer-field",
        (IdentityAnchor("capture", "source", "capture-1"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        "twin-1", "r1", 1, RevisionKind.RECONSTRUCTION,
        None, identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def test_rehydrator_requires_mapping_registry_snapshot():
    registry, _ = _registry()
    rehydrator = DurableProductionSequenceRehydrator(registry)
    with pytest.raises(TypeError, match="registry snapshot"):
        rehydrator.rehydrate((), [], {})


def test_registry_snapshot_round_trip_is_integrity_checked():
    registry, _ = _registry()
    snapshot = registry.snapshot()
    restored = DigitalTwinRegistry.from_snapshot(snapshot)
    assert restored.snapshot() == snapshot


def test_tampered_registry_snapshot_is_rejected_before_checkpoint_rehydration():
    registry, _ = _registry()
    snapshot = registry.snapshot()
    snapshot["identities"]["twin-1"]["entity_type"] = "tampered"
    checkpoint_snapshot = DurableProductionSequenceCheckpoint.create((), 0).snapshot()
    rehydrator = DurableProductionSequenceRehydrator(registry)
    with pytest.raises(ValueError, match="snapshot digest"):
        rehydrator.rehydrate((), snapshot, checkpoint_snapshot)
