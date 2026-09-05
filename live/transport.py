"""Transport-neutral delivery contracts and loopback transport for Atlas Live.

Establishes a clean, observable boundary between Atlas Live ProductionIntent generation
and external execution environments (e.g. Unreal Engine).

Separates:
- What Atlas wants produced (ProductionIntent)
- How delivery is framed, sequenced, verified, and tracked (LiveTransportChannel)
- Downstream execution consumer (LiveProductionConsumer)
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
import time
from typing import Deque, Dict, List, Optional, Protocol, Sequence, Set, Tuple

from live.production_intent import ProductionIntent, ProductionIntentEnvelope


class DeliveryStatus(str, Enum):
    DELIVERED = "delivered"
    REJECTED_DISCONNECTED = "rejected_disconnected"
    REJECTED_TIMEOUT = "rejected_timeout"
    REJECTED_CORRUPTED = "rejected_corrupted"
    REJECTED_DUPLICATE = "rejected_duplicate"
    REJECTED_OUT_OF_ORDER = "rejected_out_of_order"
    REJECTED_BUFFER_FULL = "rejected_buffer_full"


@dataclass(frozen=True)
class DeliveryReceipt:
    """Observable receipt returned by a transport channel for every intent dispatch."""

    intent_id: str
    sequence_number: int
    status: DeliveryStatus
    sent_at_ns: int
    delivered_at_ns: Optional[int]
    digest: str
    error_message: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == DeliveryStatus.DELIVERED


class LiveProductionConsumer(Protocol):
    """Protocol for downstream consumers (Unreal adapter, broadcast renderer, telemetry logger)."""

    def consume(self, intent: ProductionIntent) -> bool:
        """Receive and execute/schedule a production intent. Returns True if accepted."""
        ...


class LiveTransportChannel(Protocol):
    """Protocol for transport channels delivering intents to external consumers."""

    def send(self, intent: ProductionIntent) -> DeliveryReceipt:
        """Send an intent across the transport boundary with bounded latency and return a receipt."""
        ...

    @property
    def is_connected(self) -> bool:
        ...


class LoopbackTransportChannel:
    """Deterministic, observable in-memory loopback transport channel for testing and local pipelines.

    Enforces:
    - Strictly monotonic sequence numbering
    - SHA-256 integrity verification via ProductionIntentEnvelope
    - Rejection of disconnected consumer
    - Detection and rejection of duplicate intent IDs
    - Detection and rejection of out-of-order delivery
    - Simulation of timeout / simulated failure latency
    - Bounded delivery queue (backpressure / buffer full)
    """

    def __init__(
        self,
        consumer: Optional[LiveProductionConsumer] = None,
        max_buffer_size: int = 100,
        timeout_budget_ns: int = 5_000_000,  # 5ms default budget
    ) -> None:
        self.consumer = consumer
        self.max_buffer_size = max_buffer_size
        self.timeout_budget_ns = timeout_budget_ns
        self.is_connected = True
        self.simulate_timeout: bool = False
        self.simulate_corruption: bool = False

        self._next_sequence: int = 1
        self._last_received_sequence: int = 0
        self._seen_intent_ids: Set[str] = set()
        self._in_flight: Deque[ProductionIntentEnvelope] = deque()
        self._receipts: List[DeliveryReceipt] = []

    @property
    def receipts(self) -> Sequence[DeliveryReceipt]:
        return tuple(self._receipts)

    def send(self, intent: ProductionIntent) -> DeliveryReceipt:
        now_ns = time.perf_counter_ns()
        seq = self._next_sequence
        self._next_sequence += 1

        # Check duplicate intent id
        if intent.intent_id in self._seen_intent_ids:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_DUPLICATE,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest="",
                error_message=f"Duplicate intent_id '{intent.intent_id}' rejected",
            )
            self._receipts.append(receipt)
            return receipt

        # Create envelope
        envelope = ProductionIntentEnvelope.create(sequence_number=seq, intent=intent, sent_at_ns=now_ns)

        # Check connection status
        if not self.is_connected or self.consumer is None:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_DISCONNECTED,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message="Consumer is disconnected or unavailable",
            )
            self._receipts.append(receipt)
            return receipt

        # Check buffer capacity (backpressure)
        if len(self._in_flight) >= self.max_buffer_size:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_BUFFER_FULL,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message=f"Transport buffer capacity ({self.max_buffer_size}) exceeded",
            )
            self._receipts.append(receipt)
            return receipt

        # Simulate timeout if configured
        if self.simulate_timeout:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_TIMEOUT,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message=f"Delivery exceeded timeout budget of {self.timeout_budget_ns} ns",
            )
            self._receipts.append(receipt)
            return receipt

        # Simulate corruption if configured
        if self.simulate_corruption or not envelope.verify_digest():
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_CORRUPTED,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message="Envelope digest verification failed",
            )
            self._receipts.append(receipt)
            return receipt

        # Sequence ordering check at receiving side
        if envelope.sequence_number <= self._last_received_sequence:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_OUT_OF_ORDER,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message=f"Sequence {envelope.sequence_number} <= last seen {self._last_received_sequence}",
            )
            self._receipts.append(receipt)
            return receipt

        # Deliver to consumer
        t_delivered_ns = time.perf_counter_ns()
        accepted = self.consumer.consume(envelope.intent)

        if accepted:
            self._seen_intent_ids.add(intent.intent_id)
            self._last_received_sequence = envelope.sequence_number
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.DELIVERED,
                sent_at_ns=now_ns,
                delivered_at_ns=t_delivered_ns,
                digest=envelope.digest,
            )
        else:
            receipt = DeliveryReceipt(
                intent_id=intent.intent_id,
                sequence_number=seq,
                status=DeliveryStatus.REJECTED_DISCONNECTED,
                sent_at_ns=now_ns,
                delivered_at_ns=None,
                digest=envelope.digest,
                error_message="Consumer rejected intent",
            )

        self._receipts.append(receipt)
        return receipt
