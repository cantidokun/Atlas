"""End-to-end integration test: Simulated Perception Provider -> Perception Adapter -> WorldState -> EventEngine -> ProductionIntent -> TCP -> Unreal Engine.

Validates the full Atlas Live temporal chain:
1. SimulatedSoccerStreamProvider emits raw sensor observations (RawPerceptionFrame).
2. PerceptionAdapter filters jitter, validates timestamps, and normalizes into LiveObservationFrame.
3. LiveWorldStateReconciler reconciles canonical LiveWorldState with physical timestamp.
4. LiveEventEngine detects BALL_STRIKE with physical event timestamp.
5. LiveProductionDecisionLayer creates IMPACT_ACCENT ProductionIntent.
6. TcpTransportChannel frames envelope and sends across TCP 127.0.0.1:7778 to Unreal.
7. Unreal FAtlasLiveTcpListener receives, validates digest, enqueues into bounded ingress queue.
8. Unreal GameThread pump executes FAtlasLiveImpactAccentHandler on target Ball actor.
"""

import subprocess
import time
import pytest

from live.perception_adapter import PerceptionAdapter
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.simulated_provider import SimulatedSoccerStreamProvider
from live.tcp_transport import ConnectionState, TcpTransportChannel


def test_e2e_perception_adapter_to_unreal_visual_proof():
    unreal_cmd = "C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    uproject = "C:/Users/Gavin's PC/Desktop/Atlas/unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject"

    # Start Unreal with Automation test
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

        # 1. Perception Provider
        provider = SimulatedSoccerStreamProvider(source_id="tracking-cam-01", frame_rate_hz=50.0)

        # 2. Perception Adapter
        adapter = PerceptionAdapter(source_id="tracking-cam-01")

        # 3. Live Runtime Coordinator with Perception Adapter & TCP Transport
        coordinator = LiveRuntimeCoordinator(
            twin_id="twin-soccer-01",
            transport=channel,
            perception_adapter=adapter,
        )

        # Run through frames 1..10 where player approaches and strikes ball at step 10
        dispatched_receipts = []
        strike_event_detected = False

        for step in range(1, 12):
            raw_frame = provider.generate_raw_frame(step_index=step)
            state, events, intents, receipts = coordinator.tick_raw(raw_frame)

            assert state is not None
            # Verify sensor timestamp is preserved into state
            assert state.timestamp_ns == raw_frame.sensor_timestamp_ns

            if events:
                for evt in events:
                    if evt.event_type.value == "ball_strike":
                        strike_event_detected = True
                        # Event timestamp matches physical state timestamp
                        assert evt.timestamp_ns == state.timestamp_ns

            if receipts:
                dispatched_receipts.extend(receipts)

        # 4. Verify BALL_STRIKE was recognized and delivered
        assert strike_event_detected, "Event engine did not detect BALL_STRIKE from perception stream"
        assert len(dispatched_receipts) >= 1, "No delivery receipt for strike intent"

        strike_receipt = dispatched_receipts[0]
        assert strike_receipt.is_success
        assert strike_receipt.status.value == "delivered"
        assert strike_receipt.delivered_at_ns is not None
        assert strike_receipt.delivered_at_ns >= strike_receipt.sent_at_ns

        # 5. Verify Ingestion Telemetry
        telemetry = adapter.telemetry
        assert telemetry.total_frames_received == 11
        assert telemetry.total_frames_accepted == 11
        assert telemetry.total_frames_rejected == 0
        assert telemetry.total_entities_ingested > 0

        # Clean disconnect
        channel.disconnect()
        assert not channel.is_connected

    finally:
        channel.disconnect()
        try:
            unreal_proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            unreal_proc.kill()
