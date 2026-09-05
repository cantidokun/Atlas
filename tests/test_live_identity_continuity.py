"""Focused tests for Atlas Live Identity Continuity Resolver, WorldState Freshness, and Kinematics."""

import pytest
from planning.digital_twin_spatial import SpatialPose, Vector3
from live.identity_resolver import (
    IdentityMatchStatus,
    IdentityResolverTelemetry,
    IdentityState,
    LiveIdentityResolver,
)
from live.observation import EntityObservation, LiveObservationFrame
from live.world_state import EntityFreshness, LiveWorldEntity, LiveWorldState, LiveWorldStateReconciler
from live.event_engine import LiveEventEngine
from live.runtime_coordinator import LiveRuntimeCoordinator


def _make_obs_frame(
    sequence: int,
    timestamp_ns: int,
    entities: tuple,
    source_id: str = "cam-01",
) -> LiveObservationFrame:
    return LiveObservationFrame(
        source_id=source_id,
        sequence_number=sequence,
        timestamp_ns=timestamp_ns,
        entities=entities,
    )


def test_identity_binding_explicit_trusted():
    resolver = LiveIdentityResolver(trusted_bindings={"track-01": "player-09"})
    frame = _make_obs_frame(
        1,
        1_000_000_000,
        (
            EntityObservation(
                entity_id="track-01",
                pose=SpatialPose("atlas-field", Vector3(10.0, 5.0, 0.0)),
            ),
        ),
    )
    resolved = resolver.resolve_frame(frame)
    assert len(resolved.entities) == 1
    assert resolved.entities[0].entity_id == "player-09"
    assert resolver.get_track_state("cam-01", "track-01") == IdentityState.BOUND
    assert resolver.telemetry.identity_binding_established_count >= 1


def test_unresolved_tracks_remain_unbound():
    resolver = LiveIdentityResolver(trusted_bindings={})  # Empty trusted bindings
    frame = _make_obs_frame(
        1,
        1_000_000_000,
        (
            EntityObservation(
                entity_id="unknown-track-99",
                pose=SpatialPose("atlas-field", Vector3(1.0, 2.0, 0.0)),
            ),
        ),
    )
    resolved = resolver.resolve_frame(frame)
    # Ambiguous/unbound track is NOT admitted
    assert len(resolved.entities) == 0
    assert resolver.get_track_state("cam-01", "unknown-track-99") == IdentityState.UNBOUND
    assert resolver.telemetry.track_unresolved_count == 1


def test_conflicting_candidate_tracks_trigger_dispute():
    resolver = LiveIdentityResolver(trusted_bindings={})
    # Two different provider tracks both claim to be player-09
    frame = _make_obs_frame(
        1,
        1_000_000_000,
        (
            EntityObservation(
                entity_id="track-A",
                attributes=(("atlas_entity_id", "player-09"),),
                pose=SpatialPose("atlas-field", Vector3(10.0, 5.0, 0.0)),
            ),
            EntityObservation(
                entity_id="track-B",
                attributes=(("atlas_entity_id", "player-09"),),
                pose=SpatialPose("atlas-field", Vector3(12.0, 6.0, 0.0)),
            ),
        ),
    )
    resolved = resolver.resolve_frame(frame)
    # Disputed entity is suppressed: neither track admitted to world state
    assert len(resolved.entities) == 0
    assert resolver.telemetry.identity_disputed_count == 1
    assert resolver.get_track_state("cam-01", "track-A") == IdentityState.DISPUTED


def test_temporary_disappearance_and_reacquisition():
    resolver = LiveIdentityResolver(
        retention_window_ns=1_000_000_000,  # 1.0s retention
        trusted_bindings={"track-01": "player-09"},
    )
    # Frame 1: track-01 is observed
    f1 = _make_obs_frame(
        1,
        1_000_000_000,
        (EntityObservation(entity_id="track-01", pose=SpatialPose("atlas-field", Vector3(1.0, 1.0, 0.0))),),
    )
    resolver.resolve_frame(f1)
    assert resolver.get_binding("player-09").state == IdentityState.BOUND

    # Frame 2: track-01 omitted (200ms later)
    f2 = _make_obs_frame(2, 1_200_000_000, ())
    resolver.resolve_frame(f2)
    assert resolver.get_binding("player-09").state == IdentityState.TEMPORARILY_UNOBSERVED
    assert resolver.telemetry.temporary_absence_count == 1

    # Frame 3: track-01 reappears (within retention)
    f3 = _make_obs_frame(
        3,
        1_400_000_000,
        (EntityObservation(entity_id="track-01", pose=SpatialPose("atlas-field", Vector3(1.5, 1.5, 0.0))),),
    )
    resolver.resolve_frame(f3)
    assert resolver.get_binding("player-09").state == IdentityState.BOUND
    assert resolver.telemetry.reacquisition_count == 1


def test_provider_provenance_preserved_separately():
    resolver = LiveIdentityResolver(trusted_bindings={"raw-track-42": "player-09"})
    frame = _make_obs_frame(
        1,
        1_000_000_000,
        (
            EntityObservation(
                entity_id="raw-track-42",
                pose=SpatialPose("atlas-field", Vector3(0.0, 0.0, 0.0)),
                attributes=(("custom_key", "custom_val"),),
            ),
        ),
        source_id="optitrack-system",
    )
    resolved = resolver.resolve_frame(frame)
    resolved_entity = resolved.entities[0]
    assert resolved_entity.entity_id == "player-09"
    attrs = dict(resolved_entity.attributes)
    assert attrs["provider_id"] == "optitrack-system"
    assert attrs["provider_track_id"] == "raw-track-42"
    assert attrs["custom_key"] == "custom_val"


def test_reconciler_marks_omitted_entity_stale():
    reconciler = LiveWorldStateReconciler(twin_id="twin-01", freshness_window_ns=100_000_000)
    # Frame 1: player-09 present
    f1 = _make_obs_frame(
        1,
        1_000_000_000,
        (EntityObservation(entity_id="player-09", pose=SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.0))),),
    )
    s1 = reconciler.ingest(f1)
    assert s1.entity("player-09").freshness == EntityFreshness.OBSERVED
    assert s1.entity("player-09").is_observed is True

    # Frame 2: player-09 omitted after 50ms (within freshness window -> STALE)
    f2 = _make_obs_frame(2, 1_050_000_000, ())
    s2 = reconciler.ingest(f2)
    assert s2.has_entity("player-09")
    assert s2.entity("player-09").freshness == EntityFreshness.STALE
    assert s2.entity("player-09").is_observed is False
    assert s2.has_entity("player-09", only_fresh=True) is False

    # Frame 3: player-09 omitted after 200ms (> freshness window -> UNOBSERVED)
    f3 = _make_obs_frame(3, 1_200_000_000, ())
    s3 = reconciler.ingest(f3)
    assert s3.entity("player-09").freshness == EntityFreshness.UNOBSERVED


def test_stale_entity_excluded_from_event_detection():
    engine = LiveEventEngine(ball_entity_id="ball")
    # State 1: Ball and player fresh
    s1 = LiveWorldState(
        twin_id="twin-01",
        sequence_number=1,
        timestamp_ns=1_000_000_000,
        entities=(
            LiveWorldEntity("ball", pose=SpatialPose("f", Vector3(0.0, 0.0, 0.0)), velocity=Vector3(1.0, 0.0, 0.0), freshness=EntityFreshness.OBSERVED),
            LiveWorldEntity("player-09", pose=SpatialPose("f", Vector3(0.5, 0.0, 0.0)), freshness=EntityFreshness.OBSERVED),
        ),
    )
    # State 2: Ball accelerates, but player is STALE (unobserved)
    s2 = LiveWorldState(
        twin_id="twin-01",
        sequence_number=2,
        timestamp_ns=1_020_000_000,
        entities=(
            LiveWorldEntity("ball", pose=SpatialPose("f", Vector3(0.5, 0.0, 0.0)), velocity=Vector3(25.0, 0.0, 0.0), freshness=EntityFreshness.OBSERVED),
            LiveWorldEntity("player-09", pose=SpatialPose("f", Vector3(0.5, 0.0, 0.0)), freshness=EntityFreshness.STALE),
        ),
    )
    events = engine.evaluate(s2, s1)
    # Kinematic event must NOT fire against a stale entity
    assert len(events) == 0


def test_derivative_reset_after_observation_gap():
    reconciler = LiveWorldStateReconciler(twin_id="twin-01", max_derivative_gap_ns=100_000_000)  # 100ms
    # Frame 1: ball at (0, 0, 0)
    f1 = _make_obs_frame(1, 1_000_000_000, (EntityObservation("ball", pose=SpatialPose("f", Vector3(0.0, 0.0, 0.0))),))
    reconciler.ingest(f1)

    # Frame 2: consecutive observation 20ms later -> velocity derived
    f2 = _make_obs_frame(2, 1_020_000_000, (EntityObservation("ball", pose=SpatialPose("f", Vector3(0.2, 0.0, 0.0))),))
    s2 = reconciler.ingest(f2)
    assert s2.entity("ball").velocity is not None
    assert pytest.approx(s2.entity("ball").velocity.x, rel=1e-3) == 10.0

    # Frame 3: observation gap of 500ms (> 100ms max_derivative_gap_ns)
    f3 = _make_obs_frame(3, 1_520_000_000, (EntityObservation("ball", pose=SpatialPose("f", Vector3(5.0, 0.0, 0.0))),))
    s3 = reconciler.ingest(f3)
    # Derivative history MUST reset: no velocity manufactured across gap
    assert s3.entity("ball").velocity is None

    # Frame 4: next consecutive observation 20ms later resumes normal derivatives
    f4 = _make_obs_frame(4, 1_540_000_000, (EntityObservation("ball", pose=SpatialPose("f", Vector3(5.4, 0.0, 0.0))),))
    s4 = reconciler.ingest(f4)
    assert s4.entity("ball").velocity is not None
    assert pytest.approx(s4.entity("ball").velocity.x, rel=1e-3) == 20.0


def test_temporal_rejection_does_not_mutate_identity():
    resolver = LiveIdentityResolver(trusted_bindings={"track-01": "player-09"})
    coordinator = LiveRuntimeCoordinator(twin_id="twin-01", identity_resolver=resolver)

    # Ingest valid frame at t=1000
    f1 = _make_obs_frame(1, 1_000_000_000, (EntityObservation("track-01", pose=SpatialPose("f", Vector3(0.0, 0.0, 0.0))),))
    s1, _, _, _ = coordinator.tick(f1)
    assert s1 is not None

    est_count_before = resolver.telemetry.identity_binding_established_count
    disputed_before = resolver.telemetry.identity_disputed_count

    # Out-of-order frame at t=500 with conflicting track claiming player-09
    f_stale = _make_obs_frame(
        2,
        500_000_000,
        (
            EntityObservation(
                "track-CONFLICT",
                attributes=(("atlas_entity_id", "player-09"),),
                pose=SpatialPose("f", Vector3(99.0, 99.0, 0.0)),
            ),
        ),
    )
    s_rejected, _, _, _ = coordinator.tick(f_stale)
    assert s_rejected is None  # Rejected!

    # Identity state must NOT have mutated
    assert resolver.telemetry.identity_disputed_count == disputed_before
    assert resolver.telemetry.identity_binding_established_count == est_count_before
    assert resolver.get_binding("player-09").state == IdentityState.BOUND
