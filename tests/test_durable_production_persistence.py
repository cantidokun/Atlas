from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_operation_sequence import DurableProductionSequenceCheckpoint
from planning.durable_production_persistence import DurableProductionPersistenceBundle
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from tests.test_durable_production_sequence_restart import _operation


def _state(twin_id="persist-twin", anchor_value="persist"):
    identity = DigitalTwinIdentity(
        twin_id, "reconstruction", (IdentityAnchor("source", "capture", anchor_value),)
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        identity.twin_id,
        "r1",
        1,
        RevisionKind.RECONSTRUCTION,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    checkpoint = DurableProductionSequenceCheckpoint.create((), 0)
    return registry, revision, checkpoint


def test_persistence_bundle_round_trips_valid_registry_and_checkpoint():
    registry, _, checkpoint = _state()
    bundle = DurableProductionPersistenceBundle.create(registry, checkpoint)
    restored = DurableProductionPersistenceBundle.from_snapshot(bundle.snapshot())
    assert restored.snapshot() == bundle.snapshot()


def test_persistence_bundle_rejects_tampered_registry_snapshot():
    registry, _, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    snapshot["registry_snapshot"] = dict(snapshot["registry_snapshot"])
    snapshot["registry_snapshot"]["snapshot_digest"] = "tampered"
    with pytest.raises(ValueError, match="registry snapshot digest"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)


def test_persistence_bundle_rejects_tampered_checkpoint():
    registry, _, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    snapshot["checkpoint_snapshot"] = dict(snapshot["checkpoint_snapshot"])
    snapshot["checkpoint_snapshot"]["sequence_digest"] = "tampered"
    with pytest.raises(ValueError, match="integrity failure"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)


def test_valid_component_pair_still_requires_rehydration_registry_binding():
    registry, revision, _ = _state()
    writes = []
    operation = _operation("task-1", revision, writes, converged=True)
    completed = DurableProductionOperationSequence((operation,)).run()
    bundle = DurableProductionPersistenceBundle.create(registry, completed.checkpoint)

    other_registry, other_revision, _ = _state("other-persist-twin", "other")
    mismatched = {
        "registry_snapshot": other_registry.snapshot(),
        "checkpoint_snapshot": bundle.checkpoint_snapshot,
    }
    restored = DurableProductionPersistenceBundle.from_snapshot(mismatched)
    resumed_writes = []
    other_operation = _operation("task-1", other_revision, resumed_writes, converged=True)
    with pytest.raises(ValueError):
        DurableProductionSequenceRehydrator(other_registry).rehydrate(
            (other_operation,), restored.registry_snapshot, restored.checkpoint_snapshot
        )
    assert resumed_writes == []


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("registry_snapshot"),
        lambda value: value.__setitem__("extra", True),
    ],
)
def test_persistence_bundle_rejects_invalid_top_level_shape(mutation):
    registry, _, checkpoint = _state()
    snapshot = DurableProductionPersistenceBundle.create(registry, checkpoint).snapshot()
    mutation(snapshot)
    with pytest.raises(ValueError, match="invalid durable production persistence bundle"):
        DurableProductionPersistenceBundle.from_snapshot(snapshot)
