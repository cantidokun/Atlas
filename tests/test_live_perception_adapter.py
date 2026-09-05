"""Focused test suite for perception adapter and temporal ingestion boundary."""

import time
import pytest

from live.perception_adapter import (
    IngestionRejectionReason,
    PerceptionAdapter,
    PerceptionIngestionPolicy,
    RawEntityMeasurement,
    RawPerceptionFrame,
)
from live.simulated_provider import SimulatedSoccerStreamProvider
from live.world_state import LiveWorldStateReconciler
from live.event_engine import EventType, LiveEventEngine


def test_valid_raw_frame_ingestion_and_temporal_separation():
    adapter = PerceptionAdapter(source_id="test-cam-01")
    raw = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=1_000_000,
        measurements=(
            RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1, vx=5.0, vy=0.0, vz=0.0, confidence=0.9),
        ),
    )

    t_ingest = 1_005_000
    frame = adapter.process_raw_frame(raw, ingested_at_ns=t_ingest)

    assert frame is not None
    assert frame.source_id == "test-cam-01"
    assert frame.sequence_number == 1
    # Physical sensor timestamp preserved
    assert frame.timestamp_ns == 1_000_000
    # Ingestion arrival timestamp preserved separately
    assert frame.ingested_at_ns == 1_005_000
    assert len(frame.entities) == 1
    assert frame.entity("ball").confidence == 0.9
    assert adapter.telemetry.total_frames_accepted == 1


def test_out_of_order_and_duplicate_timestamp_rejection():
    adapter = PerceptionAdapter(source_id="test-cam-01")

    # Frame 1 at t = 100ms
    f1 = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=100_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1),),
    )
    assert adapter.process_raw_frame(f1, ingested_at_ns=105_000_000) is not None

    # Frame 2 arriving with older timestamp t = 80ms (out of order)
    f_old = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=2,
        sensor_timestamp_ns=80_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=9.0, y=0.0, z=0.1),),
    )
    assert adapter.process_raw_frame(f_old, ingested_at_ns=106_000_000) is None
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.OUT_OF_ORDER.value] == 1

    # Frame 3 arriving with duplicate timestamp t = 100ms
    f_dup = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=3,
        sensor_timestamp_ns=100_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1),),
    )
    assert adapter.process_raw_frame(f_dup, ingested_at_ns=107_000_000) is None
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.OUT_OF_ORDER.value] == 2


def test_stale_observation_rejection_against_arrival_clock():
    policy = PerceptionIngestionPolicy(max_staleness_ns=200_000_000)  # 200ms
    adapter = PerceptionAdapter(source_id="test-cam-01", policy=policy)

    # Frame with sensor time t = 0, but arriving at t = 300ms (staleness = 300ms > 200ms)
    raw = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=0,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1),),
    )
    frame = adapter.process_raw_frame(raw, ingested_at_ns=300_000_000)
    assert frame is None
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.STALE.value] == 1


def test_timestamp_discontinuity_rejection():
    policy = PerceptionIngestionPolicy(max_timestamp_jump_ns=1_000_000_000)  # 1s max jump
    adapter = PerceptionAdapter(source_id="test-cam-01", policy=policy)

    f1 = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=1_000_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1),),
    )
    assert adapter.process_raw_frame(f1, ingested_at_ns=1_000_000_000) is not None

    # Frame 2 with 5 second jump (discontinuity)
    f2 = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=2,
        sensor_timestamp_ns=6_000_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1),),
    )
    assert adapter.process_raw_frame(f2, ingested_at_ns=6_000_000_000) is None
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.TIMESTAMP_DISCONTINUITY.value] == 1


def test_confidence_degradation_and_filtering():
    policy = PerceptionIngestionPolicy(min_confidence=0.5)
    adapter = PerceptionAdapter(source_id="test-cam-01", policy=policy)

    raw = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=1_000_000,
        measurements=(
            RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1, confidence=0.8),
            RawEntityMeasurement(entity_id="player-09", x=5.0, y=0.0, z=0.0, confidence=0.2),  # < 0.5
        ),
    )
    frame = adapter.process_raw_frame(raw, ingested_at_ns=1_000_000)
    assert frame is not None
    assert len(frame.entities) == 1
    assert frame.entities[0].entity_id == "ball"
    assert adapter.telemetry.total_entities_filtered == 1
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.CONFIDENCE_TOO_LOW.value] == 1


def test_implausible_velocity_jump_rejection():
    policy = PerceptionIngestionPolicy(max_implausible_speed_m_s=60.0)  # max 60 m/s
    adapter = PerceptionAdapter(source_id="test-cam-01", policy=policy)

    # Frame 1: ball at (10, 0, 0) at t = 0
    f1 = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=1,
        sensor_timestamp_ns=0,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.0),),
    )
    assert adapter.process_raw_frame(f1, ingested_at_ns=0) is not None

    # Frame 2: 10ms later (t = 10_000_000 ns), ball jumps to (50, 0, 0)
    # displacement = 40m / 0.01s = 4000 m/s > 60 m/s
    f2 = RawPerceptionFrame(
        source_id="test-cam-01",
        sequence_number=2,
        sensor_timestamp_ns=10_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=50.0, y=0.0, z=0.0),),
    )
    frame2 = adapter.process_raw_frame(f2, ingested_at_ns=10_000_000)
    # Ball filtered out due to velocity implausibility -> empty frame rejected
    assert frame2 is None
    assert adapter.telemetry.rejection_counts[IngestionRejectionReason.VELOCITY_IMPLAUSIBLE.value] == 1


def test_configurable_policy_disables_bounds_when_configured():
    """Verify that sanity boundaries are configurable policy rather than immutable constants."""
    permissive_policy = PerceptionIngestionPolicy(
        min_confidence=0.1,
        max_implausible_speed_m_s=None,  # Disabled
        max_timestamp_jump_ns=None,  # Disabled
        allow_out_of_order=True,
    )
    adapter = PerceptionAdapter(source_id="test-permissive", policy=permissive_policy)

    # Frame 1: ball at (0, 0, 0) at t = 1s
    f1 = RawPerceptionFrame(
        source_id="test-permissive",
        sequence_number=1,
        sensor_timestamp_ns=1_000_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=0.0, y=0.0, z=0.0, confidence=0.15),),
    )
    assert adapter.process_raw_frame(f1) is not None

    # Frame 2: 10s jump with 1000 m/s displacement (accepted because jump and speed checks disabled)
    f2 = RawPerceptionFrame(
        source_id="test-permissive",
        sequence_number=2,
        sensor_timestamp_ns=11_000_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10_000.0, y=0.0, z=0.0, confidence=0.15),),
    )
    assert adapter.process_raw_frame(f2) is not None

    # Frame 3: Out-of-order timestamp accepted when allow_out_of_order is True
    f3 = RawPerceptionFrame(
        source_id="test-permissive",
        sequence_number=3,
        sensor_timestamp_ns=5_000_000_000,
        measurements=(RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.0),),
    )
    assert adapter.process_raw_frame(f3) is not None


def test_policy_validates_argument_ranges():
    with pytest.raises(ValueError, match="min_confidence"):
        PerceptionIngestionPolicy(min_confidence=-0.1)

    with pytest.raises(ValueError, match="min_confidence"):
        PerceptionIngestionPolicy(min_confidence=1.1)

    with pytest.raises(ValueError, match="max_staleness_ns"):
        PerceptionIngestionPolicy(max_staleness_ns=0)

    with pytest.raises(ValueError, match="max_timestamp_jump_ns"):
        PerceptionIngestionPolicy(max_timestamp_jump_ns=-10)

    with pytest.raises(ValueError, match="max_implausible_speed_m_s"):
        PerceptionIngestionPolicy(max_implausible_speed_m_s=0.0)


def test_temporal_chain_preserves_physical_event_time_through_world_state_and_events():
    """Verify that physical sensor occurrence timestamp is strictly preserved from Raw frame -> WorldState -> Event."""
    adapter = PerceptionAdapter(source_id="cam-01")
    reconciler = LiveWorldStateReconciler(twin_id="twin-01")
    event_engine = LiveEventEngine(acceleration_threshold_m_s2=15.0)

    # Physical sensor timestamp: 1_234_567_000 ns
    # Processing arrival timestamp: 1_234_570_000 ns (3us arrival latency)
    t_sensor_1 = 1_000_000
    t_ingest_1 = time.perf_counter_ns()

    raw1 = RawPerceptionFrame(
        source_id="cam-01",
        sequence_number=1,
        sensor_timestamp_ns=t_sensor_1,
        measurements=(
            RawEntityMeasurement(entity_id="player-09", x=9.0, y=0.0, z=0.0, vx=5.0, vy=0.0, vz=0.0),
            RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1, vx=0.0, vy=0.0, vz=0.0),
        ),
    )

    frame1 = adapter.process_raw_frame(raw1, ingested_at_ns=t_ingest_1)
    assert frame1 is not None
    assert frame1.timestamp_ns == t_sensor_1
    assert frame1.ingested_at_ns == t_ingest_1

    s1 = reconciler.ingest(frame1)
    assert s1 is not None
    assert s1.timestamp_ns == t_sensor_1
    assert s1.reconciled_at_ns is not None
    assert s1.reconciled_at_ns >= t_ingest_1

    # 20ms later in physical reality: strike occurs
    t_sensor_2 = t_sensor_1 + 20_000_000
    t_ingest_2 = time.perf_counter_ns()

    raw2 = RawPerceptionFrame(
        source_id="cam-01",
        sequence_number=2,
        sensor_timestamp_ns=t_sensor_2,
        measurements=(
            RawEntityMeasurement(entity_id="player-09", x=10.0, y=0.0, z=0.0, vx=5.0, vy=0.0, vz=0.0),
            RawEntityMeasurement(entity_id="ball", x=10.0, y=0.0, z=0.1, vx=25.0, vy=5.0, vz=2.0),
        ),
    )

    frame2 = adapter.process_raw_frame(raw2, ingested_at_ns=t_ingest_2)
    s2 = reconciler.ingest(frame2)
    assert s2 is not None
    assert s2.timestamp_ns == t_sensor_2

    events = event_engine.evaluate(s2, s1)
    assert len(events) == 1
    strike_event = events[0]

    assert strike_event.event_type == EventType.BALL_STRIKE
    # Event timestamp reflects physical sensor time, NOT detection time
    assert strike_event.timestamp_ns == t_sensor_2
    assert strike_event.detected_at_ns is not None
    assert strike_event.detected_at_ns >= t_ingest_2
