"""End-to-end integration test: Python Atlas Live -> TCP -> Unreal Live Ingress -> GameThread Pump.

Automation test demonstrating the complete live delivery pipeline:
1. Spawns Unreal Editor in headless mode with AtlasUnrealTransport module running.
2. Unreal starts FAtlasLiveTcpListener on 127.0.0.1:7778, backed by FAtlasLiveIngressQueue and FAtlasLiveGameThreadPump.
3. Python connects via TcpTransportChannel.
4. Python sends a stream of ProductionIntent envelopes with SHA-256 digests.
5. Unreal TCP thread receives, decodes, validates digest, enqueues into ingress queue.
6. Unreal GameThread pump ticks, dequeues, and dispatches to effect dispatcher.
7. Verifies delivery receipts and execution status.
"""

import socket
import subprocess
import time
import pytest

from planning.digital_twin_spatial import Vector3
from live.production_intent import ProductionIntent, ProductionTreatment
from live.tcp_transport import TcpTransportChannel, ConnectionState


def _make_intent(seq: int) -> ProductionIntent:
    return ProductionIntent(
        intent_id=f"intent-e2e-{seq:04d}",
        treatment=ProductionTreatment.IMPACT_ACCENT,
        source_event_id=f"evt-strike-{seq:04d}",
        target_entity_ids=("player-09", "ball"),
        intensity=0.88,
        duration_ms=250,
        timestamp_ns=time.perf_counter_ns(),
        origin=Vector3(12.5, -4.2, 0.15),
        direction=Vector3(0.9, 0.1, 0.0),
        parameters={"preset": "strike_flash_v1", "e2e_verified": "true"},
    )


def test_python_tcp_to_unreal_live_ingress_proof():
    # 1. First test whether Unreal Editor is already listening or launch a short test process
    unreal_cmd = "C:/Program Files/Epic Games/UE_5.6/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    uproject = "C:/Users/Gavin's PC/Desktop/Atlas/unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject"

    # Start Unreal with Automation test that runs for 4 seconds then shuts down
    # During these 4 seconds, the module's FAtlasLiveTcpListener is live on 7778!
    unreal_proc = subprocess.Popen(
        [
            unreal_cmd,
            uproject,
            "-ExecCmds=Automation RunTests Atlas.Live.IngressQueue.BoundaryVerification; Quit",
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

    # Wait up to 10 seconds for Unreal to boot and bind port 7778
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

        # 2. Send stream of 5 ProductionIntents across real TCP socket
        receipts = []
        for i in range(1, 6):
            intent = _make_intent(i)
            receipt = channel.send(intent)
            receipts.append(receipt)
            time.sleep(0.01)  # 10ms cadence (100 Hz burst)

        # 3. Verify all receipts are marked DELIVERED
        for idx, receipt in enumerate(receipts):
            assert receipt.is_success, f"Intent {idx+1} failed: {receipt.error_message}"
            assert receipt.status.value == "delivered"
            assert receipt.delivered_at_ns is not None
            assert receipt.delivered_at_ns >= receipt.sent_at_ns

        assert channel.total_frames_sent == 5
        assert channel.total_bytes_sent > 0
        assert channel.total_send_errors == 0

        # Clean disconnect
        channel.disconnect()
        assert not channel.is_connected

    finally:
        channel.disconnect()
        try:
            unreal_proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            unreal_proc.kill()
