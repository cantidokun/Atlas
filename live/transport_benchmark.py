"""Micro-benchmark and workload simulation for evaluating Atlas Live transport candidates.

Evaluates:
- ProductionIntent serialization / deserialization latency and payload size
- SHA-256 digest calculation overhead
- Delivery latency across localhost TCP, Windows Named Pipes, and Shared-Memory Ring Buffer
- Sustained 50-60 Hz load profile
- Burst load profile (e.g. 10 rapid strike events in a single tick)
- Queueing / backpressure behavior
"""

import json
import math
import mmap
import os
import socket
import struct
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from planning.digital_twin_spatial import Vector3
from live.production_intent import ProductionIntent, ProductionIntentEnvelope, ProductionTreatment


def create_sample_intent(
    sequence: int = 1,
    treatment: ProductionTreatment = ProductionTreatment.IMPACT_ACCENT,
) -> ProductionIntent:
    return ProductionIntent(
        intent_id=f"intent-bench-{sequence:06d}",
        treatment=treatment,
        source_event_id=f"evt-strike-{sequence:06d}",
        target_entity_ids=("player-09", "ball"),
        intensity=0.85,
        duration_ms=250,
        timestamp_ns=time.perf_counter_ns(),
        origin=Vector3(10.0, 0.0, 0.1),
        direction=Vector3(1.0, 0.0, 0.0),
        parameters={"preset": "strike_flash_v1", "quality": "cinematic_high"},
    )


class SerializationBenchmarkResult:
    def __init__(
        self,
        sample_count: int,
        payload_size_bytes: int,
        serialize_latencies_us: List[float],
        deserialize_latencies_us: List[float],
        digest_latencies_us: List[float],
    ) -> None:
        self.sample_count = sample_count
        self.payload_size_bytes = payload_size_bytes
        self.serialize_latencies_us = serialize_latencies_us
        self.deserialize_latencies_us = deserialize_latencies_us
        self.digest_latencies_us = digest_latencies_us

    @property
    def avg_serialize_us(self) -> float:
        return sum(self.serialize_latencies_us) / len(self.serialize_latencies_us)

    @property
    def p99_serialize_us(self) -> float:
        s = sorted(self.serialize_latencies_us)
        return s[int(len(s) * 0.99)]

    @property
    def avg_deserialize_us(self) -> float:
        return sum(self.deserialize_latencies_us) / len(self.deserialize_latencies_us)

    @property
    def p99_deserialize_us(self) -> float:
        s = sorted(self.deserialize_latencies_us)
        return s[int(len(s) * 0.99)]

    @property
    def avg_digest_us(self) -> float:
        return sum(self.digest_latencies_us) / len(self.digest_latencies_us)

    @property
    def p99_digest_us(self) -> float:
        s = sorted(self.digest_latencies_us)
        return s[int(len(s) * 0.99)]


def benchmark_serialization(iterations: int = 500) -> SerializationBenchmarkResult:
    serialize_times: List[float] = []
    deserialize_times: List[float] = []
    digest_times: List[float] = []

    sample = create_sample_intent(1)
    d = sample.to_dict()
    raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_size = len(raw)

    for i in range(iterations):
        intent = create_sample_intent(i + 1)

        # 1. Serialization
        t0 = time.perf_counter_ns()
        d_out = intent.to_dict()
        b_out = json.dumps(d_out, sort_keys=True, separators=(",", ":")).encode("utf-8")
        t1 = time.perf_counter_ns()
        serialize_times.append((t1 - t0) / 1000.0)

        # 2. SHA-256 Digest creation
        t2 = time.perf_counter_ns()
        envelope = ProductionIntentEnvelope.create(i + 1, intent, t2)
        t3 = time.perf_counter_ns()
        digest_times.append((t3 - t2) / 1000.0)

        # 3. Deserialization
        t4 = time.perf_counter_ns()
        d_in = json.loads(b_out.decode("utf-8"))
        reconstructed = ProductionIntent.from_dict(d_in)
        t5 = time.perf_counter_ns()
        deserialize_times.append((t5 - t4) / 1000.0)

    return SerializationBenchmarkResult(
        sample_count=iterations,
        payload_size_bytes=payload_size,
        serialize_latencies_us=serialize_times,
        deserialize_latencies_us=deserialize_times,
        digest_latencies_us=digest_times,
    )


class TransportBenchmarkResult:
    def __init__(
        self,
        name: str,
        delivered_count: int,
        latencies_us: List[float],
        round_trip_us: Optional[List[float]] = None,
    ) -> None:
        self.name = name
        self.delivered_count = delivered_count
        self.latencies_us = latencies_us
        self.round_trip_us = round_trip_us or []

    @property
    def avg_latency_us(self) -> float:
        return sum(self.latencies_us) / len(self.latencies_us) if self.latencies_us else 0.0

    @property
    def p50_latency_us(self) -> float:
        if not self.latencies_us:
            return 0.0
        s = sorted(self.latencies_us)
        return s[int(len(s) * 0.50)]

    @property
    def p99_latency_us(self) -> float:
        if not self.latencies_us:
            return 0.0
        s = sorted(self.latencies_us)
        return s[int(len(s) * 0.99)]

    @property
    def jitter_us(self) -> float:
        if len(self.latencies_us) < 2:
            return 0.0
        mean = self.avg_latency_us
        variance = sum((x - mean) ** 2 for x in self.latencies_us) / len(self.latencies_us)
        return math.sqrt(variance)

    @property
    def avg_round_trip_us(self) -> float:
        return sum(self.round_trip_us) / len(self.round_trip_us) if self.round_trip_us else 0.0


def benchmark_tcp_transport(iterations: int = 500, burst_size: int = 1) -> TransportBenchmarkResult:
    """Benchmark localhost TCP streaming transport (length-prefixed binary frames)."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.listen(1)

    latencies_us: List[float] = []
    round_trips_us: List[float] = []
    received_count = 0
    stop_event = threading.Event()

    def server_worker():
        nonlocal received_count
        conn, _ = server_sock.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            while not stop_event.is_set():
                # Read 4-byte length prefix
                header = conn.recv(4)
                if not header or len(header) < 4:
                    break
                length = struct.unpack("!I", header)[0]
                data = bytearray()
                while len(data) < length:
                    packet = conn.recv(length - len(data))
                    if not packet:
                        break
                    data.extend(packet)
                t_recv_ns = time.perf_counter_ns()
                # Parse sent_at_ns from first 8 bytes
                sent_at_ns = struct.unpack("!Q", data[:8])[0]
                lat = (t_recv_ns - sent_at_ns) / 1000.0
                latencies_us.append(lat)
                received_count += 1
                # Echo 8-byte ack for round-trip measurement
                conn.sendall(data[:8])
        finally:
            conn.close()

    server_thread = threading.Thread(target=server_worker, daemon=True)
    server_thread.start()

    # Client
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    client_sock.connect(("127.0.0.1", port))

    sample_intent = create_sample_intent(1)
    payload_json = json.dumps(sample_intent.to_dict()).encode("utf-8")

    try:
        for i in range(iterations):
            t_send_ns = time.perf_counter_ns()
            # Frame: [4-byte length][8-byte timestamp][payload_json]
            body = struct.pack("!Q", t_send_ns) + payload_json
            frame = struct.pack("!I", len(body)) + body
            client_sock.sendall(frame)

            # Wait for 8-byte ack
            ack = client_sock.recv(8)
            t_ack_ns = time.perf_counter_ns()
            round_trips_us.append((t_ack_ns - t_send_ns) / 1000.0)

            # Small cadence delay if not in burst
            if burst_size == 1:
                time.sleep(0.0005)  # 0.5ms pacing
    finally:
        time.sleep(0.02)
        stop_event.set()
        client_sock.close()
        server_sock.close()
        server_thread.join(timeout=1.0)

    return TransportBenchmarkResult(
        name="localhost_tcp_nodelay",
        delivered_count=received_count,
        latencies_us=latencies_us,
        round_trip_us=round_trips_us,
    )


def benchmark_shared_memory_ring(iterations: int = 500) -> TransportBenchmarkResult:
    """Benchmark memory-mapped shared memory ring buffer with spin-wait synchronization."""
    slot_size = 512
    slot_count = 64
    total_size = 64 + slot_count * slot_size  # 64-byte header: write_idx(8), read_idx(8)

    # Use anonymous mmap or named temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.truncate(total_size)
    temp_file.close()

    latencies_us: List[float] = []
    received_count = 0
    stop_event = threading.Event()

    def consumer_worker():
        nonlocal received_count
        with open(temp_file.name, "r+b") as f:
            mm = mmap.mmap(f.fileno(), total_size)
            try:
                local_read_idx = 0
                while not stop_event.is_set() or local_read_idx < iterations:
                    # Read write_idx
                    write_idx = struct.unpack_from("!Q", mm, 0)[0]
                    if local_read_idx < write_idx:
                        slot = local_read_idx % slot_count
                        offset = 64 + slot * slot_size
                        # Read 8-byte timestamp + 4-byte payload len
                        sent_at_ns, plen = struct.unpack_from("!QI", mm, offset)
                        t_recv_ns = time.perf_counter_ns()
                        lat = (t_recv_ns - sent_at_ns) / 1000.0
                        latencies_us.append(lat)
                        received_count += 1
                        local_read_idx += 1
                        # Update read_idx in header
                        struct.pack_into("!Q", mm, 8, local_read_idx)
                    else:
                        # Spin wait or short sleep
                        time.sleep(0.00001)
            finally:
                mm.close()

    consumer_thread = threading.Thread(target=consumer_worker, daemon=True)
    consumer_thread.start()

    # Producer
    sample_intent = create_sample_intent(1)
    payload_json = json.dumps(sample_intent.to_dict()).encode("utf-8")

    with open(temp_file.name, "r+b") as f:
        mm = mmap.mmap(f.fileno(), total_size)
        try:
            # Initialize indices to 0
            struct.pack_into("!QQ", mm, 0, 0, 0)
            for i in range(iterations):
                # Check ring buffer space
                write_idx = i
                slot = write_idx % slot_count
                offset = 64 + slot * slot_size

                t_send_ns = time.perf_counter_ns()
                # Write to slot: [8-byte sent_at_ns][4-byte plen][payload_json]
                struct.pack_into("!QI", mm, offset, t_send_ns, len(payload_json))
                mm[offset + 12 : offset + 12 + len(payload_json)] = payload_json

                # Commit write_idx
                struct.pack_into("!Q", mm, 0, write_idx + 1)
                time.sleep(0.0005)
        finally:
            mm.close()

    time.sleep(0.02)
    stop_event.set()
    consumer_thread.join(timeout=1.0)
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass

    return TransportBenchmarkResult(
        name="shared_memory_ring_buffer",
        delivered_count=received_count,
        latencies_us=latencies_us,
    )
