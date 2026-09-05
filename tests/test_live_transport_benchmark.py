"""Focused unit tests for the Live transport benchmark harness."""

import pytest

from live.transport_benchmark import (
    benchmark_serialization,
    benchmark_shared_memory_ring,
    benchmark_tcp_transport,
    create_sample_intent,
)


def test_sample_intent_creation_and_payload_size():
    intent = create_sample_intent(sequence=1)
    d = intent.to_dict()
    assert d["intent_id"] == "intent-bench-000001"
    assert "player-09" in d["target_entity_ids"]
    assert "ball" in d["target_entity_ids"]
    assert intent.intensity == 0.85


def test_serialization_benchmark_execution():
    res = benchmark_serialization(iterations=20)
    assert res.sample_count == 20
    assert 200 <= res.payload_size_bytes <= 1000  # typical intent is ~300-400 bytes
    assert res.avg_serialize_us > 0.0
    assert res.avg_deserialize_us > 0.0
    assert res.avg_digest_us > 0.0


def test_tcp_transport_benchmark_execution():
    res = benchmark_tcp_transport(iterations=30)
    assert res.delivered_count >= 25
    assert res.avg_latency_us > 0.0
    assert res.avg_round_trip_us > 0.0
    assert res.p99_latency_us > 0.0


def test_shared_memory_ring_benchmark_execution():
    res = benchmark_shared_memory_ring(iterations=30)
    assert res.delivered_count >= 25
    assert res.avg_latency_us > 0.0
    assert res.p99_latency_us > 0.0
