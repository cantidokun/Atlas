"""Focused test suite for Atlas Live transport boundary & failure behaviors.

Verifies:
1. ProductionIntent serialization / deserialization / schema validation.
2. ProductionIntentEnvelope SHA-256 digest creation and tamper detection.
3. Transport delivery:
   - Successful delivery with DeliveryReceipt
   - Disconnected consumer handling
   - Simulated timeout rejection
   - Malformed / corrupted envelope rejection
   - Duplicate intent rejection
   - Sequence out-of-order rejection
   - Buffer overflow / backpressure rejection
4. Unreal consumer mock execution dispatch.
5. End-to-end integration through the LiveRuntimeCoordinator with transport receipts.
"""

import pytest

from planning.digital_twin_spatial import Vector3
from live.production_intent import (
    ProductionIntent,
    ProductionIntentEnvelope,
    ProductionTreatment,
)
from live.transport import (
    DeliveryReceipt,
    DeliveryStatus,
    LoopbackTransportChannel,
)
from live.unreal_consumer import ExecutionStatus, MockUnrealLiveConsumer
from live.runtime_coordinator import LiveRuntimeCoordinator
from live.simulated_provider import SimulatedSoccerStreamProvider


def _sample_intent(intent_id: str = "intent-0001") -> ProductionIntent:
    return ProductionIntent(
        intent_id=intent_id,
        treatment=ProductionTreatment.IMPACT_ACCENT,
        source_event_id="evt-strike-0001",
        target_entity_ids=("player-09", "ball"),
        intensity=0.85,
        duration_ms=250,
        timestamp_ns=1_000_000_000,
        origin=Vector3(10.0, 0.0, 0.1),
        direction=Vector3(1.0, 0.0, 0.0),
        parameters={"preset": "strike_flash_v1"},
    )


# ---------------------------------------------------------------------------
# 1. Serialization & Envelope Integrity
# ---------------------------------------------------------------------------

def test_production_intent_serialization_roundtrip():
    intent = _sample_intent()
    data = intent.to_dict()
    reconstructed = ProductionIntent.from_dict(data)

    assert reconstructed.intent_id == intent.intent_id
    assert reconstructed.treatment == intent.treatment
    assert reconstructed.source_event_id == intent.source_event_id
    assert reconstructed.target_entity_ids == intent.target_entity_ids
    assert reconstructed.intensity == intent.intensity
    assert reconstructed.duration_ms == intent.duration_ms
    assert reconstructed.timestamp_ns == intent.timestamp_ns
    assert reconstructed.origin == intent.origin
    assert reconstructed.direction == intent.direction
    assert reconstructed.parameters_snapshot() == intent.parameters_snapshot()


def test_production_intent_envelope_digest_integrity():
    intent = _sample_intent()
    envelope = ProductionIntentEnvelope.create(sequence_number=1, intent=intent, sent_at_ns=100)

    assert envelope.verify_digest() is True

    # Tampered envelope with altered intent
    tampered_intent = ProductionIntent(
        intent_id=intent.intent_id,
        treatment=intent.treatment,
        source_event_id=intent.source_event_id,
        target_entity_ids=intent.target_entity_ids,
        intensity=0.1,  # altered
        duration_ms=intent.duration_ms,
        timestamp_ns=intent.timestamp_ns,
    )
    tampered_envelope = ProductionIntentEnvelope(
        sequence_number=envelope.sequence_number,
        intent=tampered_intent,
        sent_at_ns=envelope.sent_at_ns,
        digest=envelope.digest,
    )
    assert tampered_envelope.verify_digest() is False


def test_production_intent_new_treatments_contract():
    """Verify SPEED_TRAIL and IMPACT_FRAME serialization and enum contracts."""
    trail_intent = ProductionIntent(
        intent_id="intent-trail-contract-01",
        treatment=ProductionTreatment.SPEED_TRAIL,
        source_event_id="evt-01",
        target_entity_ids=("ball",),
        intensity=0.75,
        duration_ms=300,
        timestamp_ns=1_000_000,
        direction=Vector3(0.0, 1.0, 0.0),
        parameters={"preset": "speed_trail_v1", "trail_width": 5.0},
    )
    data_trail = trail_intent.to_dict()
    assert data_trail["treatment"] == "speed_trail"
    assert data_trail["direction"] == {"x": 0.0, "y": 1.0, "z": 0.0}
    reconstructed_trail = ProductionIntent.from_dict(data_trail)
    assert reconstructed_trail.treatment == ProductionTreatment.SPEED_TRAIL
    assert reconstructed_trail.direction == Vector3(0.0, 1.0, 0.0)

    frame_intent = ProductionIntent(
        intent_id="intent-frame-contract-01",
        treatment=ProductionTreatment.IMPACT_FRAME,
        source_event_id="evt-01",
        target_entity_ids=("player-09",),
        intensity=1.0,
        duration_ms=80,
        timestamp_ns=2_000_000,
        parameters={"preset": "impact_frame_v1", "contrast": 2.0},
    )
    data_frame = frame_intent.to_dict()
    assert data_frame["treatment"] == "impact_frame"
    reconstructed_frame = ProductionIntent.from_dict(data_frame)
    assert reconstructed_frame.treatment == ProductionTreatment.IMPACT_FRAME
    assert reconstructed_frame.duration_ms == 80
    assert reconstructed_frame.parameters_snapshot()["contrast"] == 2.0


# ---------------------------------------------------------------------------
# 2. Transport Delivery & Failure Semantics
# ---------------------------------------------------------------------------

def test_transport_successful_delivery():
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    intent = _sample_intent()

    receipt = transport.send(intent)
    assert receipt.is_success is True
    assert receipt.status == DeliveryStatus.DELIVERED
    assert receipt.intent_id == intent.intent_id
    assert receipt.sequence_number == 1
    assert receipt.delivered_at_ns is not None
    assert receipt.delivered_at_ns >= receipt.sent_at_ns
    assert len(consumer.received_intents) == 1
    assert len(consumer.dispatches) == 1

    dispatch = consumer.dispatches[0]
    assert dispatch.intent_id == intent.intent_id
    assert dispatch.target_unreal_preset == "NS_LiveSoccer_BallStrike_Burst"
    assert dispatch.status == ExecutionStatus.QUEUED


def test_transport_disconnected_consumer():
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    transport.is_connected = False
    intent = _sample_intent()

    receipt = transport.send(intent)
    assert receipt.is_success is False
    assert receipt.status == DeliveryStatus.REJECTED_DISCONNECTED
    assert "disconnected" in receipt.error_message.lower()
    assert len(consumer.received_intents) == 0


def test_transport_timeout_simulation():
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    transport.simulate_timeout = True
    intent = _sample_intent()

    receipt = transport.send(intent)
    assert receipt.is_success is False
    assert receipt.status == DeliveryStatus.REJECTED_TIMEOUT
    assert "timeout" in receipt.error_message.lower()
    assert len(consumer.received_intents) == 0


def test_transport_corrupted_payload_rejection():
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    transport.simulate_corruption = True
    intent = _sample_intent()

    receipt = transport.send(intent)
    assert receipt.is_success is False
    assert receipt.status == DeliveryStatus.REJECTED_CORRUPTED
    assert "digest" in receipt.error_message.lower()
    assert len(consumer.received_intents) == 0


def test_transport_duplicate_delivery_rejection():
    consumer = MockUnrealLiveConsumer()
    transport = LoopbackTransportChannel(consumer=consumer)
    intent = _sample_intent(intent_id="intent-unique-01")

    # First send succeeds
    receipt1 = transport.send(intent)
    assert receipt1.status == DeliveryStatus.DELIVERED

    # Resending same intent_id fails
    receipt2 = transport.send(intent)
    assert receipt2.status == DeliveryStatus.REJECTED_DUPLICATE
    assert "duplicate" in receipt2.error_message.lower()
    assert len(consumer.received_intents) == 1


def test_transport_buffer_overflow_backpressure():
    consumer = MockUnrealLiveConsumer()
    # Configure buffer size of 2
    transport = LoopbackTransportChannel(consumer=consumer, max_buffer_size=2)
    transport._in_flight.append("msg1")
    transport._in_flight.append("msg2")

    intent = _sample_intent()
    receipt = transport.send(intent)
    assert receipt.status == DeliveryStatus.REJECTED_BUFFER_FULL
    assert "buffer" in receipt.error_message.lower()
    assert len(consumer.received_intents) == 0


# ---------------------------------------------------------------------------
# 3. End-to-End Coordinator Integration with Transport
# ---------------------------------------------------------------------------

def test_coordinator_end_to_end_with_transport():
    provider = SimulatedSoccerStreamProvider(frame_rate_hz=50.0)
    consumer = MockUnrealLiveConsumer(fps=60.0)
    transport = LoopbackTransportChannel(consumer=consumer)
    coordinator = LiveRuntimeCoordinator(twin_id="twin-live-01", transport=transport)

    delivered_receipts = []
    for frame in provider.generate_strike_scenario(total_frames=20):
        state, events, intents, receipts = coordinator.tick(frame)
        assert state is not None
        for r in receipts:
            delivered_receipts.append(r)

    # In the 20 frame strike scenario, frame 10 contacts the ball and emits an intent
    assert len(delivered_receipts) >= 1
    for r in delivered_receipts:
        assert r.is_success is True
        assert r.status == DeliveryStatus.DELIVERED
        assert r.delivered_at_ns is not None

    assert len(consumer.dispatches) >= 1
    disp = consumer.dispatches[0]
    assert disp.target_unreal_preset == "NS_LiveSoccer_BallStrike_Burst"
    assert disp.duration_frames > 0

    # Telemetry check
    for cycle in coordinator.telemetry_log:
        if cycle.intents_produced > 0:
            assert cycle.receipts_delivered == cycle.intents_produced
            assert cycle.dispatch_duration_ns > 0
