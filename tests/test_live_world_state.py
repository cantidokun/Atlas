import copy

import pytest

from planning.digital_twin_spatial import SpatialPose, Vector3
from planning.live_world_state import (
    LiveEntityState,
    LiveWorldStateEnvelope,
    LiveWorldStateSnapshot,
    validate_live_world_state,
)


def _snapshot(sequence=1):
    return LiveWorldStateSnapshot(
        twin_id="soccer-twin-001",
        revision_id="revision-004",
        state_sequence=sequence,
        observed_at="2026-09-04T00:00:00Z",
        source_id="tracking-provider-01",
        entities=(
            LiveEntityState(
                entity_id="player-07",
                pose=SpatialPose(
                    frame_id="atlas-field",
                    position=Vector3(12.0, 8.0, 0.0),
                ),
                attributes=(("team", "home"), ("role", "attacker")),
            ),
        ),
        world_attributes=(("match_phase", "open_play"),),
        metadata={"feed": {"type": "tracking"}},
    )


def test_live_snapshot_is_provider_neutral_and_queryable():
    snapshot = _snapshot()
    assert snapshot.entity("player-07").attributes[0] == ("team", "home")
    assert snapshot.attribute("MATCH_PHASE") == "open_play"


def test_live_snapshot_rejects_duplicate_entities():
    entity = LiveEntityState(entity_id="player-07")
    with pytest.raises(ValueError, match="unique ids"):
        LiveWorldStateSnapshot(
            twin_id="soccer-twin-001",
            revision_id="revision-004",
            state_sequence=1,
            observed_at="2026-09-04T00:00:00Z",
            source_id="tracking-provider-01",
            entities=(entity, entity),
        )


def test_live_snapshot_rejects_duplicate_attributes():
    with pytest.raises(ValueError, match="unique keys"):
        LiveEntityState(entity_id="player-07", attributes=(("team", "home"), ("TEAM", "away")))


def test_live_snapshot_metadata_is_deeply_immutable_and_detached():
    source = {"feed": {"type": "tracking"}}
    snapshot = LiveWorldStateSnapshot(
        twin_id="soccer-twin-001",
        revision_id="revision-004",
        state_sequence=1,
        observed_at="2026-09-04T00:00:00Z",
        source_id="tracking-provider-01",
        metadata=source,
    )
    source["feed"]["type"] = "tampered"
    assert snapshot.metadata_snapshot()["feed"]["type"] == "tracking"
    with pytest.raises(TypeError):
        snapshot.metadata["feed"]["type"] = "tampered"


def test_live_snapshot_metadata_snapshot_is_defensively_copied():
    snapshot = _snapshot()
    detached = snapshot.metadata_snapshot()
    detached["feed"]["type"] = "tampered"
    assert snapshot.metadata_snapshot()["feed"]["type"] == "tracking"


def test_live_state_validation_accepts_matching_identity_and_monotonic_sequence():
    validate_live_world_state(
        _snapshot(sequence=7),
        expected_twin_id="soccer-twin-001",
        expected_revision_id="revision-004",
        previous_sequence=6,
    )


def test_live_state_validation_rejects_twin_mismatch():
    with pytest.raises(ValueError, match="twin_id"):
        validate_live_world_state(_snapshot(), expected_twin_id="different-twin")


def test_live_state_validation_rejects_revision_mismatch():
    with pytest.raises(ValueError, match="revision_id"):
        validate_live_world_state(_snapshot(), expected_revision_id="revision-005")


def test_live_state_validation_rejects_stale_sequence():
    with pytest.raises(ValueError, match="monotonically"):
        validate_live_world_state(_snapshot(sequence=7), previous_sequence=7)


def test_live_envelope_keeps_provider_metadata_outside_canonical_state():
    snapshot = _snapshot()
    envelope = LiveWorldStateEnvelope(
        snapshot=snapshot,
        provider_type="tracking-service",
        provider_version="2.1",
    )
    assert envelope.snapshot is snapshot
    assert envelope.provider_type == "tracking-service"
    assert envelope.provider_version == "2.1"
