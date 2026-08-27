from __future__ import annotations

import pytest

from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator


def test_rehydrator_rejects_non_mapping_checkpoint():
    with pytest.raises(TypeError, match="checkpoint"):
        DurableProductionSequenceRehydrator.__new__(DurableProductionSequenceRehydrator).rehydrate(
            (), {}, []
        )


def test_rehydrator_rejects_registry_snapshot_without_valid_digest():
    with pytest.raises(ValueError, match="snapshot"):
        DurableProductionSequenceRehydrator.__new__(DurableProductionSequenceRehydrator).rehydrate(
            (), {"identities": {}, "revisions": {}, "snapshot_digest": "bad"},
            {"completed_receipts": (), "next_operation_index": 0},
        )
