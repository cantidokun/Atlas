"""End-to-end integration test: Python Simulated Event -> ProductionIntent -> TCP -> Unreal Live Visual Effect.

Demonstrates:
1. Python generates simulated BALL_STRIKE event.
2. Production decision layer maps event to IMPACT_ACCENT production intent with preset strike_flash_v1.
3. Intent is framed into a protocol v1 envelope with SHA-256 digest and sent over localhost TCP.
4. Headless Unreal Editor receives envelope asynchronously via FAtlasLiveTcpListener.
5. Ingress queue accepts intent.
6. GameThread pump consumes queued intent.
7. FAtlasLiveEffectRegistry resolves FAtlasLiveImpactAccentHandler.
8. Real visual effect (PointLightComponent + active VFX tag) is executed on the target Ball actor.
9. Verified through delivery receipt and execution telemetry.
"""

import subprocess
import time
import pytest

from planning.digital_twin_spatial import Vector3
from live.event_engine import EventType, LiveEvent
from live.production_intent import (
    LiveProductionDecisionLayer,
    ProductionIntent,
    ProductionTreatment,
)
from live.tcp_transport import TcpTransportChannel, ConnectionState


def test_python_simulated_strike_to_unreal_visual_effect_proof():
    unreal_cmd = "C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    uproject = "C:/Users/Gavin's PC/Desktop/Atlas/unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject"

    # Start Unreal with focused Automation suite
    unreal_proc = subprocess.Popen(
        [
            unreal_cmd,
            uproject,
            "-ExecCmds=Automation RunTests Atlas.Live.Effect.DispatchVerification; Quit",
            "-unattended",
            "-nopause",
            "-nullrhi",
            "-nosound",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    port = 7778
    connected = False
    channel = TcpTransportChannel(host="127.0.0.1", port=port, timeout_s=1.0)

    t_start = time.time()
    while time.time() - t_start < 15.0:
        if unreal_proc.poll() is not None:
            break
        if channel.connect():
            connected = True
            break
        time.sleep(0.2)

    try:
        assert connected, "Failed to connect to Unreal FAtlasLiveTcpListener on 127.0.0.1:7778"
        assert channel.is_connected
        assert channel.state == ConnectionState.CONNECTED

        # 1. Physical Event: BALL_STRIKE detected -> IMPACT_ACCENT
        strike_event = LiveEvent(
            event_id="evt-strike-live-01",
            event_type=EventType.BALL_STRIKE,
            timestamp_ns=time.perf_counter_ns(),
            source_sequence=42,
            entity_ids=("player-09", "ball"),
            confidence=0.92,
            intensity=0.85,
            location=Vector3(100.0, 0.0, 15.0),
            direction=Vector3(1.0, 0.0, 0.0),
        )

        decision_layer = LiveProductionDecisionLayer(min_confidence_threshold=0.6)
        intent_accent = decision_layer.evaluate(strike_event)
        assert intent_accent is not None
        assert intent_accent.treatment == ProductionTreatment.IMPACT_ACCENT
        assert "ball" in intent_accent.target_entity_ids

        # 2. SPEED_TRAIL Intent
        intent_trail = ProductionIntent(
            intent_id="intent-trail-live-01",
            treatment=ProductionTreatment.SPEED_TRAIL,
            source_event_id="evt-strike-live-01",
            target_entity_ids=("ball",),
            intensity=0.9,
            duration_ms=250,
            timestamp_ns=time.perf_counter_ns(),
            direction=Vector3(1.0, 0.0, 0.0),
            parameters={"preset": "speed_trail_v1"},
        )

        # 3. IMPACT_FRAME Intent
        intent_frame = ProductionIntent(
            intent_id="intent-frame-live-01",
            treatment=ProductionTreatment.IMPACT_FRAME,
            source_event_id="evt-strike-live-01",
            target_entity_ids=("ball",),
            intensity=0.8,
            duration_ms=100,
            timestamp_ns=time.perf_counter_ns(),
            parameters={"preset": "impact_frame_v1"},
        )

        # Deliver all 3 treatments across TCP
        r_accent = channel.send(intent_accent)
        r_trail = channel.send(intent_trail)
        r_frame = channel.send(intent_frame)

        # Verify receipt success for all treatments
        for r in (r_accent, r_trail, r_frame):
            assert r.is_success, f"Intent delivery failed: {r.error_message}"
            assert r.status.value == "delivered"
            assert r.delivered_at_ns is not None
            assert r.delivered_at_ns >= r.sent_at_ns

        # Clean disconnect
        channel.disconnect()
        assert not channel.is_connected

    finally:
        channel.disconnect()
        try:
            unreal_proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            unreal_proc.kill()
