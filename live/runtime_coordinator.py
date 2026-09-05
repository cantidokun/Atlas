"""Coordinator runtime for the Atlas Live vertical slice.

Wires together:
1. Perception input (ObservationFrame)
2. State reconciliation (LiveWorldState)
3. Event recognition (LiveEvent)
4. Production intent mapping (ProductionIntent)
5. Transport channel delivery (LiveTransportChannel -> DeliveryReceipt)

Measures cycle times and latency across the slice without blocking critical loops.
"""

from dataclasses import dataclass, field
import time
from typing import List, Optional, Sequence, Tuple

from live.event_engine import LiveEvent, LiveEventEngine
from live.identity_resolver import LiveIdentityResolver
from live.observation import LiveObservationFrame
from live.perception_adapter import PerceptionAdapter, RawPerceptionFrame
from live.production_intent import (
    LiveProductionDecisionLayer,
    ProductionIntent,
)
from live.transport import DeliveryReceipt, LiveProductionConsumer, LiveTransportChannel, LoopbackTransportChannel
from live.world_state import LiveWorldState, LiveWorldStateReconciler


@dataclass(frozen=True)
class CycleTelemetry:
    """Detailed timing and processing metrics for a single Live runtime cycle."""

    cycle_sequence: int
    observation_timestamp_ns: int
    reconciliation_duration_ns: int
    event_engine_duration_ns: int
    decision_duration_ns: int
    dispatch_duration_ns: int
    total_cycle_duration_ns: int
    events_produced: int
    intents_produced: int
    receipts_delivered: int


class LiveRuntimeCoordinator:
    """Executes the high-frequency tick of the Atlas Live pipeline."""

    def __init__(
        self,
        twin_id: str,
        transport: Optional[LiveTransportChannel] = None,
        event_engine: Optional[LiveEventEngine] = None,
        decision_layer: Optional[LiveProductionDecisionLayer] = None,
        perception_adapter: Optional[PerceptionAdapter] = None,
        identity_resolver: Optional[LiveIdentityResolver] = None,
        max_history: int = 100,
    ) -> None:
        self.reconciler = LiveWorldStateReconciler(twin_id=twin_id, max_history=max_history)
        self.identity_resolver = identity_resolver or LiveIdentityResolver()
        self.event_engine = event_engine or LiveEventEngine()
        self.decision_layer = decision_layer or LiveProductionDecisionLayer()
        self.perception_adapter = perception_adapter
        self.transport = transport
        self._telemetry_log: List[CycleTelemetry] = []

    def tick_raw(
        self, raw_frame: RawPerceptionFrame
    ) -> Tuple[Optional[LiveWorldState], Sequence[LiveEvent], Sequence[ProductionIntent], Sequence[DeliveryReceipt]]:
        """Process raw perception frame through adapter boundary then through live pipeline."""
        if self.perception_adapter is None:
            raise ValueError("perception_adapter must be provided to process raw frames")
        obs_frame = self.perception_adapter.process_raw_frame(raw_frame)
        if obs_frame is None:
            return None, (), (), ()
        return self.tick(obs_frame)

    @property
    def telemetry_log(self) -> Sequence[CycleTelemetry]:
        return tuple(self._telemetry_log)

    def tick(
        self, frame: LiveObservationFrame
    ) -> Tuple[Optional[LiveWorldState], Sequence[LiveEvent], Sequence[ProductionIntent], Sequence[DeliveryReceipt]]:
        """Process one incoming observation frame through the vertical slice."""
        t_start = time.perf_counter_ns()

        # Step 0: Pre-admission check against reconciler timestamp
        # Atomicity: A frame rejected for staleness / out-of-order must NOT mutate identity state
        if frame.timestamp_ns <= self.reconciler._last_observation_timestamp_ns:
            return None, (), (), ()

        # Step 1: Live Identity Continuity Resolution
        resolved_frame = self.identity_resolver.resolve_frame(frame)

        # Step 2: Ingest & Reconcile World State
        prior_state = self.reconciler.current_state
        current_state = self.reconciler.ingest(resolved_frame)
        t_after_reconcile = time.perf_counter_ns()
        reconcile_ns = t_after_reconcile - t_start

        if current_state is None:
            # Frame was rejected
            return None, (), (), ()

        # Step 3: Event Detection
        events = self.event_engine.evaluate(current_state, prior_state)
        t_after_events = time.perf_counter_ns()
        events_ns = t_after_events - t_after_reconcile

        # Step 3: Production Intent Mapping
        intents: List[ProductionIntent] = []
        for evt in events:
            intent = self.decision_layer.evaluate(evt)
            if intent is not None:
                intents.append(intent)
        t_after_decision = time.perf_counter_ns()
        decision_ns = t_after_decision - t_after_events

        # Step 4: Transport Channel Delivery
        receipts: List[DeliveryReceipt] = []
        if self.transport is not None:
            for intent in intents:
                receipt = self.transport.send(intent)
                receipts.append(receipt)
        t_after_dispatch = time.perf_counter_ns()
        dispatch_ns = t_after_dispatch - t_after_decision

        total_ns = t_after_dispatch - t_start
        delivered_count = sum(1 for r in receipts if r.is_success)

        telemetry = CycleTelemetry(
            cycle_sequence=current_state.sequence_number,
            observation_timestamp_ns=frame.timestamp_ns,
            reconciliation_duration_ns=reconcile_ns,
            event_engine_duration_ns=events_ns,
            decision_duration_ns=decision_ns,
            dispatch_duration_ns=dispatch_ns,
            total_cycle_duration_ns=total_ns,
            events_produced=len(events),
            intents_produced=len(intents),
            receipts_delivered=delivered_count,
        )
        self._telemetry_log.append(telemetry)

        return current_state, tuple(events), tuple(intents), tuple(receipts)
