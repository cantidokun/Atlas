"""Focused test suite for Atlas Live vertical slice:
Observation -> World-State -> Event -> Production Intent -> Downstream Consumer
"""

import pytest

from planning.digital_twin_spatial import SpatialPose, Vector3
from live.event_engine import EventType, LiveEvent, LiveEventEngine
from live.observation import EntityObservation, LiveObservationFrame
from live.production_intent import (
    LiveProductionDecisionLayer,
    ProductionIntent,
    ProductionTreatment,
)
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.simulated_provider import SimulatedSoccerStreamProvider
from live.transport import LoopbackTransportChannel
from live.unreal_consumer import MockUnrealLiveConsumer
from live.world_state import LiveWorldEntity, LiveWorldState, LiveWorldStateReconciler


# ---------------------------------------------------------------------------
# Unit Tests: Observation Schema & Ingestion
# ---------------------------------------------------------------------------

def test_observation_frame_creation_and_immutability():
    pose = SpatialPose("atlas-field", Vector3(10.0, 5.0, 0.0))
    entity_obs = EntityObservation(
        entity_id="player-10",
        pose=pose,
        velocity=Vector3(1.0, 0.0, 0.0),
        confidence=0.95,
        attributes=(("team", "home"),),
    )
    frame = LiveObservationFrame(
        source_id="provider-camera-01",
        sequence_number=1,
        timestamp_ns=1000000,
        entities=(entity_obs,),
        frame_attributes=(("phase", "first_half"),),
        metadata={"camera_count": 4},
    )

    assert frame.source_id == "provider-camera-01"
    assert frame.sequence_number == 1
    assert frame.timestamp_ns == 1000000
    assert frame.entity("player-10").confidence == 0.95
    assert frame.metadata_snapshot()["camera_count"] == 4

    with pytest.raises(TypeError):
        frame.metadata["camera_count"] = 5


def test_observation_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="entity_id"):
        EntityObservation(entity_id=" ")

    with pytest.raises(ValueError, match="confidence"):
        EntityObservation(entity_id="p1", confidence=1.5)

    with pytest.raises(ValueError, match="sequence_number"):
        LiveObservationFrame(
            source_id="s1",
            sequence_number=0,
            timestamp_ns=1000,
        )

    with pytest.raises(ValueError, match="unique ids"):
        e1 = EntityObservation(entity_id="p1")
        LiveObservationFrame(
            source_id="s1",
            sequence_number=1,
            timestamp_ns=1000,
            entities=(e1, e1),
        )


# ---------------------------------------------------------------------------
# Unit Tests: World-State Reconciliation & Derivation
# ---------------------------------------------------------------------------

def test_world_state_reconciler_derives_velocity_when_missing():
    reconciler = LiveWorldStateReconciler(twin_id="twin-001")

    # Frame 1 at t = 0s, pos = (0, 0, 0)
    f1 = LiveObservationFrame(
        source_id="s1",
        sequence_number=1,
        timestamp_ns=0,
        entities=(
            EntityObservation(
                entity_id="ball",
                pose=SpatialPose("atlas-field", Vector3(0.0, 0.0, 0.0)),
            ),
        ),
    )
    s1 = reconciler.ingest(f1)
    assert s1 is not None
    assert s1.entity("ball").velocity is None

    # Frame 2 at t = 0.1s (100_000_000 ns), pos = (1.0, 0.0, 0.0)
    f2 = LiveObservationFrame(
        source_id="s1",
        sequence_number=2,
        timestamp_ns=100_000_000,
        entities=(
            EntityObservation(
                entity_id="ball",
                pose=SpatialPose("atlas-field", Vector3(1.0, 0.0, 0.0)),
            ),
        ),
    )
    s2 = reconciler.ingest(f2)
    assert s2 is not None
    v = s2.entity("ball").velocity
    assert v is not None
    assert pytest.approx(v.x, 0.001) == 10.0  # 1.0m / 0.1s = 10 m/s
    assert pytest.approx(v.y, 0.001) == 0.0
    assert pytest.approx(v.z, 0.001) == 0.0


def test_world_state_reconciler_rejects_stale_or_out_of_order_frames():
    reconciler = LiveWorldStateReconciler(twin_id="twin-001")
    f1 = LiveObservationFrame(source_id="s1", sequence_number=1, timestamp_ns=100)
    assert reconciler.ingest(f1) is not None

    # Stale frame (timestamp <= 100)
    f_stale = LiveObservationFrame(source_id="s1", sequence_number=2, timestamp_ns=50)
    assert reconciler.ingest(f_stale) is None

    # Identical timestamp
    f_dup = LiveObservationFrame(source_id="s1", sequence_number=3, timestamp_ns=100)
    assert reconciler.ingest(f_dup) is None

    # Newer frame succeeds
    f_next = LiveObservationFrame(source_id="s1", sequence_number=4, timestamp_ns=200)
    assert reconciler.ingest(f_next) is not None


# ---------------------------------------------------------------------------
# Unit Tests: Event Engine
# ---------------------------------------------------------------------------

def test_event_engine_detects_ball_strike():
    engine = LiveEventEngine(
        ball_entity_id="ball",
        proximity_threshold_m=1.5,
        acceleration_threshold_m_s2=15.0,
    )

    # State 1: Ball stationary at (10, 0, 0), Player at (9.0, 0, 0)
    s1 = LiveWorldState(
        twin_id="twin-001",
        sequence_number=1,
        timestamp_ns=0,
        entities=(
            LiveWorldEntity(
                entity_id="player-10",
                pose=SpatialPose("atlas-field", Vector3(9.0, 0.0, 0.0)),
                velocity=Vector3(5.0, 0.0, 0.0),
                confidence=0.9,
            ),
            LiveWorldEntity(
                entity_id="ball",
                pose=SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.0)),
                velocity=Vector3(0.0, 0.0, 0.0),
                confidence=0.95,
            ),
        ),
    )

    # State 2: 20ms later (t = 20_000_000 ns). Ball struck: vel jumps to (20, 0, 0).
    # Player at (9.1, 0, 0), distance to ball = 0.9m <= 1.5m
    # dv = 20 m/s / 0.02s = 1000 m/s^2 > 15 m/s^2
    s2 = LiveWorldState(
        twin_id="twin-001",
        sequence_number=2,
        timestamp_ns=20_000_000,
        entities=(
            LiveWorldEntity(
                entity_id="player-10",
                pose=SpatialPose("atlas-field", Vector3(9.1, 0.0, 0.0)),
                velocity=Vector3(4.0, 0.0, 0.0),
                confidence=0.9,
            ),
            LiveWorldEntity(
                entity_id="ball",
                pose=SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.0)),
                velocity=Vector3(20.0, 0.0, 0.0),
                confidence=0.95,
            ),
        ),
    )

    events = engine.evaluate(s2, s1)
    assert len(events) == 1
    evt = events[0]
    assert evt.event_type == EventType.BALL_STRIKE
    assert "player-10" in evt.entity_ids
    assert "ball" in evt.entity_ids
    assert evt.confidence == pytest.approx(0.9 * 0.95, 0.001)
    assert evt.intensity > 0.0
    assert evt.direction is not None
    assert pytest.approx(evt.direction.x, 0.001) == 1.0


# ---------------------------------------------------------------------------
# Unit Tests: Production Decision & Consumer
# ---------------------------------------------------------------------------

def test_production_decision_layer_maps_strike_to_intent():
    decision_layer = LiveProductionDecisionLayer(min_confidence_threshold=0.6)
    event = LiveEvent(
        event_id="evt-01",
        event_type=EventType.BALL_STRIKE,
        timestamp_ns=1000,
        source_sequence=1,
        entity_ids=("player-10", "ball"),
        confidence=0.85,
        intensity=0.8,
        location=Vector3(10.0, 0.0, 0.0),
        direction=Vector3(1.0, 0.0, 0.0),
    )

    intent = decision_layer.evaluate(event)
    assert intent is not None
    assert intent.treatment == ProductionTreatment.IMPACT_ACCENT
    assert intent.target_entity_ids == ("player-10", "ball")
    assert intent.intensity == 0.8
    assert intent.duration_ms >= 100
    assert intent.parameters_snapshot()["preset"] == "strike_flash_v1"


def test_production_consumer_mock_accepts_and_disconnects():
    consumer = MockUnrealLiveConsumer()
    intent = ProductionIntent(
        intent_id="i1",
        treatment=ProductionTreatment.IMPACT_ACCENT,
        source_event_id="evt-01",
        target_entity_ids=("ball",),
        intensity=0.5,
        duration_ms=150,
        timestamp_ns=1000,
    )

    assert consumer.consume(intent) is True
    assert len(consumer.received_intents) == 1

    consumer.is_connected = False
    assert consumer.consume(intent) is False
    assert len(consumer.received_intents) == 1


# ---------------------------------------------------------------------------
# End-to-End Vertical Slice Integration Test
# ---------------------------------------------------------------------------

def test_live_vertical_slice_end_to_end_with_simulated_stream():
    """Verify complete observation -> world-state -> event -> intent -> consumer flow."""
    provider = SimulatedSoccerStreamProvider(
        source_id="sim-tracking",
        frame_rate_hz=50.0,
        player_id="player-09",
        ball_id="ball",
    )
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    coordinator = LiveRuntimeCoordinator(twin_id="atlas-soccer-twin-01", transport=transport)

    total_events_detected = 0
    total_intents_dispatched = 0

    # Feed 20 frames from the simulated strike scenario
    for frame in provider.generate_strike_scenario(total_frames=20):
        state, events, intents, receipts = coordinator.tick(frame)
        assert state is not None
        assert state.has_entity("player-09")
        assert state.has_entity("ball")
        total_events_detected += len(events)
        total_intents_dispatched += len(intents)

    # In the scenario, frame 10 contacts the ball and accelerates it, triggering a strike event
    assert total_events_detected >= 1
    assert total_intents_dispatched >= 1
    assert len(consumer.received_intents) >= 1

    received = consumer.received_intents[0]
    assert received.treatment == ProductionTreatment.IMPACT_ACCENT
    assert "player-09" in received.target_entity_ids
    assert "ball" in received.target_entity_ids
    assert received.intensity > 0.0

    # Verify telemetry records every cycle
    telemetry = coordinator.telemetry_log
    assert len(telemetry) == 20
    for cycle in telemetry:
        # Every cycle should complete in well under 5ms in pure Python
        assert cycle.total_cycle_duration_ns < 10_000_000  # < 10ms
        assert cycle.reconciliation_duration_ns >= 0
        assert cycle.event_engine_duration_ns >= 0
