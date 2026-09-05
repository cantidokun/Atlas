"""Focused tests for SkillCorner Open Data tracking adapter, real dropout handling, and end-to-end Atlas Live pipeline."""

from pathlib import Path
import pytest

from live.event_engine import LiveEventEngine
from live.identity_resolver import IdentityState, LiveIdentityResolver
from live.perception_adapter import PerceptionAdapter, PerceptionIngestionPolicy, TimestampDomain
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.skillcorner_adapter import SkillCornerAdapterConfig, SkillCornerTrackingAdapter
from live.world_state import EntityFreshness, LiveWorldStateReconciler


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "skillcorner_2017461_raw_slice.jsonl"


def test_skillcorner_adapter_source_frame_and_timing_preservation():
    config = SkillCornerAdapterConfig(session_id="test-sc-session")
    adapter = SkillCornerTrackingAdapter(config)

    frames = list(adapter.replay_raw_file(FIXTURE_PATH))
    assert len(frames) == 500

    # First frame in slice is frame 2510
    f0 = frames[0]
    assert f0.sequence_number == 2510
    assert f0.sensor_timestamp_ns == 2510 * 100_000_000
    assert f0.source_id == "skillcorner-broadcast-cam"
    assert f0.metadata["source_frame"] == "2510"
    assert f0.metadata["session_id"] == "test-sc-session"
    assert f0.metadata["timestamp_domain"] == "monotonic_source"

    # Verify Ball and player measurements
    ball_m = next((m for m in f0.measurements if m.entity_id == "trk_ball"), None)
    assert ball_m is not None
    assert ball_m.confidence == 1.0  # is_detected=True
    assert ("track_status", "detected") in ball_m.attributes
    assert ball_m.frame_id == "atlas-field"
    assert ball_m.z == 0.14


def test_skillcorner_adapter_extrapolated_detection_degradation():
    config = SkillCornerAdapterConfig(
        detected_player_confidence=0.95,
        extrapolated_player_confidence=0.4,
    )
    adapter = SkillCornerTrackingAdapter(config)

    frames = list(adapter.replay_raw_file(FIXTURE_PATH))
    f0 = frames[0]

    # Find detected vs extrapolated players in frame 2510
    det_players = [m for m in f0.measurements if m.confidence == 0.95]
    extrap_players = [m for m in f0.measurements if m.confidence == 0.4]

    assert len(det_players) > 0
    assert len(extrap_players) > 0
    assert ("track_status", "detected") in det_players[0].attributes
    assert ("track_status", "extrapolated") in extrap_players[0].attributes


def test_skillcorner_adapter_replay_determinism():
    adapter = SkillCornerTrackingAdapter()
    run1 = list(adapter.replay_raw_file(FIXTURE_PATH))
    run2 = list(adapter.replay_raw_file(FIXTURE_PATH))

    assert len(run1) == len(run2) == 500
    for f1, f2 in zip(run1, run2):
        assert f1.sequence_number == f2.sequence_number
        assert f1.sensor_timestamp_ns == f2.sensor_timestamp_ns
        assert len(f1.measurements) == len(f2.measurements)


def test_skillcorner_real_dropouts_and_unobserved_transition():
    # In frame 2540, ball is present; in later frames near 2700, broadcast zooms in and ball drops out
    config = SkillCornerAdapterConfig(filter_extrapolated_ball=True)  # True dropouts
    adapter = SkillCornerTrackingAdapter(config)

    trusted = {"trk_ball": "ball", "trk_p582974": "player-582974"}
    resolver = LiveIdentityResolver(trusted_bindings=trusted)
    policy = PerceptionIngestionPolicy(
        expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE,
        max_timestamp_jump_ns=1_000_000_000,
    )
    perception_adapter = PerceptionAdapter(source_id="skillcorner-broadcast-cam", policy=policy)
    reconciler = LiveWorldStateReconciler(
        twin_id="twin-sc-01",
        freshness_window_ns=250_000_000,
        max_derivative_gap_ns=150_000_000,
    )
    coordinator = LiveRuntimeCoordinator(
        twin_id="twin-sc-01",
        perception_adapter=perception_adapter,
        identity_resolver=resolver,
    )
    coordinator.reconciler = reconciler

    observed_dropout = False
    for raw_frame in adapter.replay_raw_file(FIXTURE_PATH):
        state, _, _, _ = coordinator.tick_raw(raw_frame)
        if state is not None and state.has_entity("ball"):
            ball_ent = state.entity("ball")
            if ball_ent.freshness in (EntityFreshness.STALE, EntityFreshness.UNOBSERVED):
                observed_dropout = True
                break

    assert observed_dropout is True, "Expected to observe genuine real-world ball dropout in broadcast tracking"


def test_skillcorner_full_pipeline_ball_strike_event_detection():
    # Real strike event occurs at frame 2871-2872 with player M. Francois (582974)
    config = SkillCornerAdapterConfig(session_id="skillcorner-match-2017461-p1")
    adapter = SkillCornerTrackingAdapter(config)

    policy = PerceptionIngestionPolicy(
        min_confidence=0.3,
        expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE,
        max_timestamp_jump_ns=1_000_000_000,
        max_implausible_speed_m_s=80.0,
    )
    perception_adapter = PerceptionAdapter(source_id="skillcorner-broadcast-cam", policy=policy)
    trusted = {"trk_ball": "ball", "trk_p582974": "player-582974"}
    resolver = LiveIdentityResolver(default_session="skillcorner-match-2017461-p1", trusted_bindings=trusted)
    reconciler = LiveWorldStateReconciler(
        twin_id="twin-sc-01",
        freshness_window_ns=300_000_000,
        max_derivative_gap_ns=150_000_000,
    )
    event_engine = LiveEventEngine(ball_entity_id="ball", proximity_threshold_m=2.0, acceleration_threshold_m_s2=15.0)

    coordinator = LiveRuntimeCoordinator(
        twin_id="twin-sc-01",
        perception_adapter=perception_adapter,
        identity_resolver=resolver,
        event_engine=event_engine,
    )
    coordinator.reconciler = reconciler

    strike_events = []
    strike_intents = []

    for raw_frame in adapter.replay_raw_file(FIXTURE_PATH):
        state, events, intents, _ = coordinator.tick_raw(raw_frame)
        if events:
            for evt in events:
                strike_events.append((raw_frame.sequence_number, evt))
        if intents:
            for intent in intents:
                strike_intents.append((raw_frame.sequence_number, intent))

    # Assert real-data BALL_STRIKE event detected deterministically
    assert len(strike_events) >= 1
    f_num, evt = strike_events[0]
    assert 2870 <= f_num <= 2875
    assert "player-582974" in evt.entity_ids
    assert "ball" in evt.entity_ids
    assert evt.intensity > 0.0

    # Assert ProductionIntent was generated with canonical meters
    assert len(strike_intents) >= 1
    intent = strike_intents[0][1]
    assert intent.target_entity_ids == ("player-582974", "ball")
    assert intent.origin is not None
    # Ball location in canonical meters on pitch: x=37.28, y=16.43, z=0.14
    assert 30.0 <= intent.origin.x <= 45.0
    assert 10.0 <= intent.origin.y <= 25.0
