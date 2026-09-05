"""Runner script to generate the transport comparison measurements."""

import json
from live.transport_benchmark import (
    benchmark_serialization,
    benchmark_shared_memory_ring,
    benchmark_tcp_transport,
)


def run_all_benchmarks():
    print("=== ATLAS LIVE TRANSPORT BENCHMARK SUITE ===")

    # 1. Serialization Benchmark
    print("1. Benchmarking Serialization / Deserialization / Digest (1000 iterations)...")
    ser_res = benchmark_serialization(iterations=1000)
    print(f"   Payload size: {ser_res.payload_size_bytes} bytes")
    print(f"   Serialization: avg={ser_res.avg_serialize_us:.1f}us, p99={ser_res.p99_serialize_us:.1f}us")
    print(f"   SHA-256 Digest: avg={ser_res.avg_digest_us:.1f}us, p99={ser_res.p99_digest_us:.1f}us")
    print(f"   Deserialization: avg={ser_res.avg_deserialize_us:.1f}us, p99={ser_res.p99_deserialize_us:.1f}us")
    print(f"   Total ser+deser+digest budget: {ser_res.avg_serialize_us + ser_res.avg_digest_us + ser_res.avg_deserialize_us:.1f}us")

    # 2. Localhost TCP Benchmark (Stream)
    print("\n2. Benchmarking Localhost TCP (TCP_NODELAY, 500 packets)...")
    tcp_res = benchmark_tcp_transport(iterations=500)
    print(f"   Delivered: {tcp_res.delivered_count}/500")
    print(f"   One-way Latency: avg={tcp_res.avg_latency_us:.1f}us, p50={tcp_res.p50_latency_us:.1f}us, p99={tcp_res.p99_latency_us:.1f}us")
    print(f"   Jitter: {tcp_res.jitter_us:.1f}us")
    print(f"   Round-trip Latency (ack): avg={tcp_res.avg_round_trip_us:.1f}us")

    # 3. Localhost TCP Benchmark (Burst of 10)
    print("\n3. Benchmarking Localhost TCP (Burst of 10)...")
    tcp_burst_res = benchmark_tcp_transport(iterations=500, burst_size=10)
    print(f"   Delivered: {tcp_burst_res.delivered_count}/500")
    print(f"   One-way Latency: avg={tcp_burst_res.avg_latency_us:.1f}us, p99={tcp_burst_res.p99_latency_us:.1f}us")

    # 4. Shared Memory Ring Buffer Benchmark
    print("\n4. Benchmarking Shared-Memory Ring Buffer (500 packets)...")
    shm_res = benchmark_shared_memory_ring(iterations=500)
    print(f"   Delivered: {shm_res.delivered_count}/500")
    print(f"   One-way Latency: avg={shm_res.avg_latency_us:.1f}us, p50={shm_res.p50_latency_us:.1f}us, p99={shm_res.p99_latency_us:.1f}us")
    print(f"   Jitter: {shm_res.jitter_us:.1f}us")

    summary = {
        "payload_bytes": ser_res.payload_size_bytes,
        "serialization_us": {
            "serialize_avg": ser_res.avg_serialize_us,
            "digest_avg": ser_res.avg_digest_us,
            "deserialize_avg": ser_res.avg_deserialize_us,
            "total_codec_avg": ser_res.avg_serialize_us + ser_res.avg_digest_us + ser_res.avg_deserialize_us,
        },
        "tcp": {
            "delivered": tcp_res.delivered_count,
            "one_way_avg_us": tcp_res.avg_latency_us,
            "p50_us": tcp_res.p50_latency_us,
            "p99_us": tcp_res.p99_latency_us,
            "jitter_us": tcp_res.jitter_us,
            "round_trip_avg_us": tcp_res.avg_round_trip_us,
        },
        "shm": {
            "delivered": shm_res.delivered_count,
            "one_way_avg_us": shm_res.avg_latency_us,
            "p50_us": shm_res.p50_latency_us,
            "p99_us": shm_res.p99_latency_us,
            "jitter_us": shm_res.jitter_us,
        },
    }
    with open("transport_benchmark_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nBenchmark summary saved to transport_benchmark_summary.json")


if __name__ == "__main__":
    run_all_benchmarks()
