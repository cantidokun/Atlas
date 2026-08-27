from __future__ import annotations

import pytest

from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator


def _registry_snapshot():
    identity = DigitalTwinIdentity(
        "rehydration-integrity-twin",
        "reconstruction",
        (IdentityAnchor("source", "capture", "integrity"),),
    )
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    return registry.snapshot()


def test_rehydrator_rejects_non_mapping_checkpoint():
    snapshot = _registry_snapshot()
    with pytest.raises(TypeError, match="sequence snapshot must be a mapping"):
        DurableProductionSequenceRehydrator.__new__(DurableProductionSequenceRehydrator).rehydrate(
            (), snapshot, []
        )


def test_rehydrator_rejects_registry_snapshot_without_valid_digest():
    with pytest.raises(ValueError, match="snapshot"):
        DurableProductionSequenceRehydrator.__new__(DurableProductionSequenceRehydrator).rehydrate(
            (), {"identities": {}, "revisions": {}, "snapshot_digest": "bad"},
            {"completed_receipts": (), "next_operation_index": 0},
        )
