"""Focused tests for TelemetryStreamProvider, Session Reset, Domain Checking, and Coordinate Semantics."""

from pathlib import Path
import pytest

from live.identity_resolver import IdentityState, LiveIdentityResolver
from live.perception_adapter import PerceptionAdapter, PerceptionIngestionPolicy, TimestampDomain
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.telemetry_provider import TelemetryStreamConfig, TelemetryStreamProvider
from planning.digital_twin_spatial import Vector3
from live.production_intent import ProductionIntent, ProductionTreatment


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tracking_telemetry_fixture.jsonl"


def test_telemetry_stream_provider_file_replay():
    provider = TelemetryStreamProvider()
    frames = list(provider.replay_file(FIXTURE_PATH))
    assert len(frames) == 5
    assert frames[0].source_id == "cam-field-01"
    assert frames[0].metadata["session_id"] == "session-live-01"
    assert frames[0].metadata["timestamp_domain"] == "monotonic_source"
    assert len(frames[0].measurements) == 2
    # Verify entity measurement field parsing
    ball_m = next(m for m in frames[0].measurements if m.entity_id == "trk_ball_01")
    assert ball_m.x == 0.0
    assert ball_m.y == 0.0
    assert ball_m.z == 0.1
    assert ball_m.confidence == 0.98
    assert ("track_status", "detected") in ball_m.attributes


def test_provider_session_reset_behavior():
    policy = PerceptionIngestionPolicy(
        expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE,
        max_timestamp_jump_ns=1_000_000_000,
    )
    adapter = PerceptionAdapter(source_id="cam-field-01", policy=policy)

    # Frame 1 from session-A at t=10_000_000_000
    raw1 = provider_frame(session_id="session-A", seq=1, timestamp_ns=10_000_000_000)
    obs1 = adapter.process_raw_frame(raw1)
    assert obs1 is not None

    # Frame 2 with lower timestamp from session-A is rejected (out-of-order)
    raw_stale = provider_frame(session_id="session-A", seq=2, timestamp_ns=5_000_000_000)
    obs_stale = adapter.process_raw_frame(raw_stale)
    assert obs_stale is None

    # Frame 3 from session-B with reset sequence and timestamp (t=1_000_000) is ACCEPTED
    raw_reset = provider_frame(session_id="session-B", seq=1, timestamp_ns=1_000_000)
    obs_reset = adapter.process_raw_frame(raw_reset)
    assert obs_reset is not None
    assert obs_reset.sequence_number == 1
    assert obs_reset.timestamp_ns == 1_000_000


def test_timestamp_domain_mismatch_rejection():
    # Adapter expects MONOTONIC_HOST
    policy = PerceptionIngestionPolicy(
        expected_timestamp_domain=TimestampDomain.MONOTONIC_HOST,
    )
    adapter = PerceptionAdapter(source_id="cam-field-01", policy=policy)

    # Ingest frame declaring UTC_UNIX domain
    raw_utc = provider_frame(
        session_id="session-utc",
        seq=1,
        timestamp_ns=1725500000000000000,
        domain="utc_unix",
    )
    obs = adapter.process_raw_frame(raw_utc)
    assert obs is None  # Rejection due to domain mismatch!
    assert adapter.telemetry.rejection_counts["timestamp_domain_mismatch"] == 1


def test_session_isolation_in_identity_resolver():
    resolver = LiveIdentityResolver(
        default_session="session-A",
        trusted_bindings={"trk_ball_01": "ball"},
    )
    policy = PerceptionIngestionPolicy(expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE)
    adapter = PerceptionAdapter(source_id="cam-01", policy=policy)

    # Session A: trk_ball_01 binds to ball
    frame_a = TelemetryStreamProvider().parse_telemetry_dict({
        "source_id": "cam-01",
        "session_id": "session-A",
        "sequence_number": 1,
        "timestamp_ns": 1_000_000_000,
        "timestamp_domain": "monotonic_source",
        "entities": [{"track_id": "trk_ball_01", "x": 0.0, "y": 0.0, "z": 0.0}],
    })
    obs_a = adapter.process_raw_frame(frame_a)
    assert obs_a is not None
    resolved_a = resolver.resolve_frame(obs_a)
    assert len(resolved_a.entities) == 1
    assert resolved_a.entities[0].entity_id == "ball"
    assert resolver.get_track_state("cam-01", "trk_ball_01", "session-A") == IdentityState.BOUND

    # Session B: another track claiming to be trk_ball_01 in a new session without trusted mapping
    # Resolver must NOT assume session-B track continues session-A
    frame_b = TelemetryStreamProvider().parse_telemetry_dict({
        "source_id": "cam-01",
        "session_id": "session-B",
        "sequence_number": 1,
        "timestamp_ns": 2_000_000_000,
        "timestamp_domain": "monotonic_source",
        "entities": [{"track_id": "trk_other_99", "x": 1.0, "y": 1.0, "z": 0.0}],
    })
    obs_b = adapter.process_raw_frame(frame_b)
    assert obs_b is not None
    resolved_b = resolver.resolve_frame(obs_b)
    assert len(resolved_b.entities) == 0  # Unbound track in session-B rejected


def test_end_to_end_recorded_telemetry_replay_through_live_pipeline():
    # Setup Live pipeline with explicit trusted bindings for fixture
    resolver = LiveIdentityResolver(
        trusted_bindings={
            "trk_ball_01": "ball",
            "trk_p09_01": "player-09",
        }
    )
    policy = PerceptionIngestionPolicy(
        expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE,
    )
    adapter = PerceptionAdapter(source_id="cam-field-01", policy=policy)
    coordinator = LiveRuntimeCoordinator(
        twin_id="twin-soccer-01",
        perception_adapter=adapter,
        identity_resolver=resolver,
    )

    provider = TelemetryStreamProvider()
    processed_states = []

    for raw_frame in provider.replay_file(FIXTURE_PATH):
        state, events, intents, receipts = coordinator.tick_raw(raw_frame)
        assert state is not None
        processed_states.append(state)

    assert len(processed_states) == 5
    # Verify entity resolution and presence in final frame
    final_state = processed_states[-1]
    assert final_state.has_entity("ball")
    assert final_state.has_entity("player-09")
    ball = final_state.entity("ball")
    assert ball.pose.position.x == 1.0
    assert ball.pose.position.y == 0.0
    assert ball.pose.position.z == 0.15


def test_production_intent_retains_canonical_meters():
    # Verify that ProductionIntent retains canonical meters (does not convert to cm)
    intent = ProductionIntent(
        intent_id="intent-01",
        treatment=ProductionTreatment.IMPACT_ACCENT,
        source_event_id="evt-01",
        target_entity_ids=("ball",),
        intensity=0.8,
        duration_ms=200,
        timestamp_ns=1_000_000,
        origin=Vector3(1.25, 0.5, 0.15),  # Meters!
    )
    # The origin in Python must be exactly 1.25, 0.5, 0.15
    assert intent.origin.x == 1.25
    assert intent.origin.y == 0.5
    assert intent.origin.z == 0.15

    # Serialized wire dictionary also retains canonical meters
    wire_dict = intent.to_dict()
    assert wire_dict["origin"]["x"] == 1.25
    assert wire_dict["origin"]["y"] == 0.5
    assert wire_dict["origin"]["z"] == 0.15


def test_replay_file_pacing_and_determinism():
    provider = TelemetryStreamProvider()
    # Paced replay with speed_factor=10.0 (accelerated cadence)
    frames_paced = list(provider.replay_file(FIXTURE_PATH, realtime=True, speed_factor=50.0))
    assert len(frames_paced) == 5
    # Non-paced replay
    frames_instant = list(provider.replay_file(FIXTURE_PATH, realtime=False))
    assert len(frames_instant) == 5

    # Determinism: sequences and coordinates must be identical
    for f_p, f_i in zip(frames_paced, frames_instant):
        assert f_p.sequence_number == f_i.sequence_number
        assert f_p.sensor_timestamp_ns == f_i.sensor_timestamp_ns
        assert len(f_p.measurements) == len(f_i.measurements)
        for m_p, m_i in zip(f_p.measurements, f_i.measurements):
            assert m_p.entity_id == m_i.entity_id
            assert m_p.x == m_i.x
            assert m_p.y == m_i.y
            assert m_p.z == m_i.z


# Helper
def provider_frame(session_id: str, seq: int, timestamp_ns: int, domain: str = "monotonic_source"):
    data = {
        "source_id": "cam-field-01",
        "session_id": session_id,
        "sequence_number": seq,
        "timestamp_ns": timestamp_ns,
        "timestamp_domain": domain,
        "entities": [{"track_id": "trk_ball_01", "x": 1.0, "y": 2.0, "z": 0.1}],
    }
    return TelemetryStreamProvider().parse_telemetry_dict(data)
