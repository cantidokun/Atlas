"""Unit and mock tests for Python-side TCP transport channel."""

import socket
import struct
import threading
import time
import pytest

from planning.digital_twin_spatial import Vector3
from live.production_intent import ProductionIntent, ProductionTreatment
from live.transport import DeliveryStatus
from live.tcp_transport import ConnectionState, TcpTransportChannel


def _create_intent(intent_id: str = "intent-tcp-001", seq: int = 1) -> ProductionIntent:
    return ProductionIntent(
        intent_id=intent_id,
        treatment=ProductionTreatment.IMPACT_ACCENT,
        source_event_id=f"evt-{intent_id}",
        target_entity_ids=("player-09", "ball"),
        intensity=0.85,
        duration_ms=200,
        timestamp_ns=time.perf_counter_ns(),
        origin=Vector3(10.0, 0.0, 0.1),
        direction=Vector3(1.0, 0.0, 0.0),
        parameters={"preset": "strike_flash_v1"},
    )


def test_tcp_frame_encoding():
    intent = _create_intent("intent-001", 1)
    frame = TcpTransportChannel.encode_frame(1, intent, 100000)

    # Frame header: 4 bytes length + 1 byte version
    assert len(frame) > 5
    payload_len, version = struct.unpack("!IB", frame[:5])
    assert version == 1
    assert payload_len == len(frame) - 5


def test_tcp_frame_oversized_rejection():
    intent = _create_intent("intent-large", 1)
    # Patch parameters to exceed 64KB
    huge_params = {f"k_{i}": "x" * 1000 for i in range(70)}
    object.__setattr__(intent, "parameters", huge_params)

    with pytest.raises(ValueError, match="exceeds maximum"):
        TcpTransportChannel.encode_frame(1, intent, 100000)


def test_tcp_transport_disconnected_send():
    channel = TcpTransportChannel(host="127.0.0.1", port=9999)
    assert not channel.is_connected

    intent = _create_intent("intent-disc", 1)
    receipt = channel.send(intent)

    assert receipt.status == DeliveryStatus.REJECTED_DISCONNECTED
    assert not receipt.is_success
    assert "not connected" in str(receipt.error_message)


def test_tcp_transport_mock_server_delivery_and_framing():
    # Setup mock TCP server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.listen(1)

    received_frames = []
    stop_event = threading.Event()

    def server_worker():
        conn, _ = server_sock.accept()
        try:
            while not stop_event.is_set():
                header = conn.recv(5)
                if not header or len(header) < 5:
                    break
                plen, ver = struct.unpack("!IB", header)
                payload = bytearray()
                while len(payload) < plen:
                    chunk = conn.recv(plen - len(payload))
                    if not chunk:
                        break
                    payload.extend(chunk)
                received_frames.append((ver, bytes(payload)))
        finally:
            conn.close()

    t = threading.Thread(target=server_worker, daemon=True)
    t.start()

    channel = TcpTransportChannel(host="127.0.0.1", port=port)
    assert channel.connect()
    assert channel.is_connected
    assert channel.state == ConnectionState.CONNECTED

    intent1 = _create_intent("intent-1", 1)
    intent2 = _create_intent("intent-2", 2)

    r1 = channel.send(intent1)
    r2 = channel.send(intent2)

    assert r1.is_success
    assert r2.is_success
    assert channel.total_frames_sent == 2
    assert channel.total_bytes_sent > 0

    time.sleep(0.05)
    channel.disconnect()
    assert not channel.is_connected
    assert channel.state == ConnectionState.DISCONNECTED

    stop_event.set()
    server_sock.close()
    t.join(timeout=1.0)

    assert len(received_frames) == 2
    assert received_frames[0][0] == 1  # version 1
    assert received_frames[1][0] == 1
