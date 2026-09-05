"""Focused tests for LiveTelemetryUdpReceiver: socket lifecycle, framing, backpressure, and pipeline integration."""

import json
import socket
import time
import pytest

from live.identity_resolver import LiveIdentityResolver
from live.perception_adapter import PerceptionAdapter, PerceptionIngestionPolicy, TimestampDomain
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.telemetry_socket_provider import LiveTelemetryUdpReceiver


@pytest.fixture
def udp_receiver():
    receiver = LiveTelemetryUdpReceiver(host="127.0.0.1", port=0, max_queue_size=4)
    assert receiver.start() is True
    assert receiver.bound_port > 0
    yield receiver
    receiver.stop()


def _send_udp(port: int, payload: bytes) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(payload, ("127.0.0.1", port))
    finally:
        sock.close()


def test_udp_receiver_valid_packet_and_poll(udp_receiver):
    packet = {
        "source_id": "cam-01",
        "session_id": "session-1",
        "sequence_number": 1,
        "timestamp_ns": 1_000_000_000,
        "timestamp_domain": "monotonic_source",
        "entities": [{"track_id": "trk-1", "x": 1.0, "y": 2.0, "z": 0.0, "confidence": 0.95}],
    }
    _send_udp(udp_receiver.bound_port, json.dumps(packet).encode("utf-8"))

    # Poll with short wait
    frame = None
    t0 = time.time()
    while time.time() - t0 < 1.0:
        frame = udp_receiver.poll_raw_frame()
        if frame is not None:
            break
        time.sleep(0.01)

    assert frame is not None
    assert frame.source_id == "cam-01"
    assert frame.sequence_number == 1
    assert frame.metadata["session_id"] == "session-1"
    assert len(frame.measurements) == 1
    assert frame.measurements[0].entity_id == "trk-1"
    assert frame.measurements[0].x == 1.0

    telemetry = udp_receiver.telemetry
    assert telemetry.packets_received >= 1
    assert telemetry.packets_accepted >= 1
    assert telemetry.packets_rejected_malformed == 0


def test_udp_receiver_malformed_json_rejected(udp_receiver):
    # Send malformed bytes
    _send_udp(udp_receiver.bound_port, b"{invalid-json: none,")
    time.sleep(0.05)

    frame = udp_receiver.poll_raw_frame()
    assert frame is None
    telemetry = udp_receiver.telemetry
    assert telemetry.packets_received == 1
    assert telemetry.packets_rejected_malformed == 1
    assert telemetry.packets_accepted == 0


def test_udp_receiver_oversized_datagram_rejected(udp_receiver):
    # Default max_datagram_bytes is 1472. Send datagram exceeding 1472 bytes
    oversized_entities = [
        {"track_id": f"trk_{i}", "x": float(i), "y": 0.0, "z": 0.0, "notes": "x" * 100}
        for i in range(25)
    ]
    packet = {
        "source_id": "cam-01",
        "session_id": "session-1",
        "sequence_number": 1,
        "timestamp_ns": 1_000_000_000,
        "entities": oversized_entities,
    }
    payload = json.dumps(packet).encode("utf-8")
    assert len(payload) > 1472  # Exceeds Ethernet MTU limit

    _send_udp(udp_receiver.bound_port, payload)
    time.sleep(0.05)

    frame = udp_receiver.poll_raw_frame()
    assert frame is None
    telemetry = udp_receiver.telemetry
    assert telemetry.packets_received == 1
    assert telemetry.packets_rejected_oversized == 1
    assert telemetry.packets_accepted == 0


def test_udp_receiver_drop_oldest_overflow(udp_receiver):
    # Max queue size is 4; send 6 packets
    for i in range(1, 7):
        packet = {
            "source_id": "cam-01",
            "session_id": "session-1",
            "sequence_number": i,
            "timestamp_ns": 1_000_000_000 + i * 20_000_000,
            "entities": [{"track_id": "trk-1", "x": float(i), "y": 0.0, "z": 0.0}],
        }
        _send_udp(udp_receiver.bound_port, json.dumps(packet).encode("utf-8"))
        time.sleep(0.005)

    time.sleep(0.05)
    telemetry = udp_receiver.telemetry
    assert telemetry.packets_received == 6
    assert telemetry.packets_dropped_overflow >= 2

    # Queue should contain the latest items (packets 3, 4, 5, 6)
    drained = []
    while True:
        f = udp_receiver.poll_raw_frame()
        if f is None:
            break
        drained.append(f.sequence_number)

    assert len(drained) == 4
    assert drained == [3, 4, 5, 6]  # Oldest (1, 2) evicted


def test_udp_to_pipeline_end_to_end_integration():
    receiver = LiveTelemetryUdpReceiver(host="127.0.0.1", port=0, max_queue_size=16)
    assert receiver.start() is True

    try:
        # Setup coordinator
        policy = PerceptionIngestionPolicy(expected_timestamp_domain=TimestampDomain.MONOTONIC_SOURCE)
        adapter = PerceptionAdapter(source_id="cam-01", policy=policy)
        resolver = LiveIdentityResolver(trusted_bindings={"trk_ball_99": "ball"})
        coordinator = LiveRuntimeCoordinator(
            twin_id="twin-test-01",
            perception_adapter=adapter,
            identity_resolver=resolver,
        )

        # Transmit 3 consecutive packets
        for seq in range(1, 4):
            packet = {
                "source_id": "cam-01",
                "session_id": "session-udp-e2e",
                "sequence_number": seq,
                "timestamp_ns": 1_000_000_000 + (seq - 1) * 20_000_000,
                "timestamp_domain": "monotonic_source",
                "entities": [{"track_id": "trk_ball_99", "x": float(seq), "y": 0.0, "z": 0.1}],
            }
            _send_udp(receiver.bound_port, json.dumps(packet).encode("utf-8"))
            time.sleep(0.01)

        time.sleep(0.05)

        # Poll and tick pipeline
        processed = 0
        while True:
            raw = receiver.poll_raw_frame()
            if raw is None:
                break
            state, events, intents, receipts = coordinator.tick_raw(raw)
            assert state is not None
            assert state.has_entity("ball")
            processed += 1

        assert processed == 3
        current = coordinator.reconciler.current_state
        assert current is not None
        assert current.entity("ball").pose.position.x == 3.0
    finally:
        receiver.stop()
