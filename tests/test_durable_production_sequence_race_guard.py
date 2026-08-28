from __future__ import annotations

import pytest

from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.durable_production_sequence_rehydration import DurableProductionSequenceRehydrator
from planning.durable_production_operation_sequence import DurableProductionOperationSequence
from tests.test_durable_production_sequence_restart import _operation, _registry


def test_rehydration_does_not_begin_writes_when_canonical_revision_drifts():
    registry, revision = _registry()
    persisted_registry = registry.snapshot()
    writes = []

    first = _operation("task-1", revision, writes, converged=True)
    second = _operation("task-2", revision, writes, converged=False)
    interrupted = DurableProductionOperationSequence((first, second)).run()
    persisted_checkpoint = interrupted.checkpoint.snapshot()

    newer = DigitalTwinRevision(
        revision.twin_id,
        "r2",
        2,
        RevisionKind.CLEANUP,
        source_revision_id=revision.revision_id,
        source_fingerprint=revision.source_fingerprint,
    )
    registry.register_revision(newer)

    resumed_writes = []
    resumed_first = _operation("task-1", revision, resumed_writes, converged=True)
    resumed_second = _operation("task-2", revision, resumed_writes, converged=True)

    with pytest.raises(ValueError, match="stale Digital Twin revision"):
        DurableProductionSequenceRehydrator(registry).rehydrate(
            (resumed_first, resumed_second),
            persisted_registry,
            persisted_checkpoint,
        )

    assert resumed_writes == []
