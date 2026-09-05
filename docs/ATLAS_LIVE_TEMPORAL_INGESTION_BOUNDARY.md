# Atlas Live — State-to-Event Temporal Ingestion Boundary (Phase 4)

## 1. Architectural Role

The Temporal Ingestion Boundary sits between external observation providers (optical cameras, computer vision, tracking vendors, simulators) and the Atlas World-State reconciliation engine.

Its primary obligation is **temporal normalization and sensor anomaly filtering without deciding semantic events**.

```text
External Tracking / Sensor / Simulator
            │
            ▼ (RawPerceptionFrame)
┌───────────────────────────────────────────────┐
│              PerceptionAdapter                │
│  - Jitter & Out-of-Order Packet Filtering    │
│  - Staleness & Epoch Validation               │
│  - Timestamp Discontinuity Rejection          │
│  - Confidence Floor Enforcement               │
│  - Implausible Kinematic Discontinuity Check │
│  - Ingestion Latency Telemetry                │
└───────────────────────────────────────────────┘
            │
            ▼ (LiveObservationFrame: sensor_t + ingested_t)
┌───────────────────────────────────────────────┐
│           LiveWorldStateReconciler            │
│  - Entity State & Derived Velocity            │
│  - Reconciled At Timestamp                    │
└───────────────────────────────────────────────┘
            │
            ▼ (LiveWorldState: sensor_t + reconciled_t)
┌───────────────────────────────────────────────┐
│               LiveEventEngine                 │
│  - Physical Interaction Detection             │
│  - Preserves Physical Occurrence Timestamp    │
│  - Detected At Timestamp                      │
└───────────────────────────────────────────────┘
            │
            ▼ (LiveEvent: sensor_t + detected_t)
┌───────────────────────────────────────────────┐
│          ProductionDecisionLayer              │
│  - Maps Event to ProductionIntent             │
│  - Created At Timestamp                       │
└───────────────────────────────────────────────┘
            │
            ▼ (ProductionIntent: sensor_t + created_t)
         TCP Transport -> Unreal Live Ingress -> Visual Dispatch
```

---

## 2. Temporal Semantics: The 6 Discrete Clock Points

At no point does Atlas Live conflate arrival/processing time with the physical time of occurrence.

1. **`sensor_timestamp_ns` / `timestamp_ns`**:
   - The physical capture or observation timecode from the sensor clock.
   - Preserved end-to-end across `RawPerceptionFrame` $\to$ `LiveObservationFrame` $\to$ `LiveWorldState` $\to$ `LiveEvent` $\to$ `ProductionIntent`.
2. **`ingested_at_ns`**:
   - Monotonic host time (`time.perf_counter_ns()`) when `PerceptionAdapter` accepts the raw observation frame.
3. **`reconciled_at_ns`**:
   - Monotonic host time when `LiveWorldStateReconciler` integrates observations into a new `LiveWorldState` snapshot.
4. **`detected_at_ns`**:
   - Monotonic host time when `LiveEventEngine` determines that a semantic event occurred.
5. **`created_at_ns`**:
   - Monotonic host time when `LiveProductionDecisionLayer` evaluates the event and generates a `ProductionIntent`.
6. **`transport_sent_at_ns` / `ReceiverCycles` / `DispatchedCycles`**:
   - Transport and Unreal GameThread timestamps tracking network transmission and visual execution latency.

---

## 3. Jitter, Staleness, and Kinematic Boundary Policy

`PerceptionIngestionPolicy` defines explicit, testable, and configurable bounds:

1. **Monotonic Ordering & Bounded Reordering**:
   - `allow_out_of_order` (default `False`): Strict monotonic sensor timestamp enforcement ($t_{\text{sensor}} > t_{\text{last\_seen\_sensor}}$). Stale or out-of-order packets are rejected immediately with `OUT_OF_ORDER` telemetry.
   - When set to `True`, the adapter permits out-of-order delivery across asynchronous channels, reserving sliding jitter-buffer reassembly for future multi-sensor tracking adapters without architectural rewrites.
   - Backward jitter $\Delta t_{\text{jitter}} = t_{\text{last\_seen\_sensor}} - t_{\text{sensor}}$ is continuously recorded for telemetry.
2. **Staleness**:
   - `max_staleness_ns` (optional): Rejects packets arriving older than this threshold relative to arrival time in the same epoch as `STALE`. Can be disabled (`None`) for offline/simulation replay.
3. **Timestamp Discontinuities**:
   - `max_timestamp_jump_ns` (default `5.0s`, optional): Rejects forward time gaps exceeding this bound to prevent clock step errors or sensor desynchronization. Can be disabled (`None`).
4. **Confidence Floor**:
   - `min_confidence` (default `0.3`, range `[0.0, 1.0]`): Filters individual entity observations falling below this floor without rejecting valid co-observed entities in the frame.
5. **Kinematic Sanity Bounds**:
   - `max_implausible_speed_m_s` (default `60.0 m/s` / `216 km/h`, optional): Configurable sanity ceiling on implied inter-frame velocity $\frac{|\vec{p}_t - \vec{p}_{t-1}|}{\Delta t}$. Can be tuned or disabled (`None`) depending on camera resolution, frame rate, or simulation scale.
6. **Separation of Concerns & Identity Continuity**:
   - Ingestion filters noisy observations; it **never** declares that a ball strike or pass occurred.
   - Normalization outputs clean `LiveObservationFrame` batches which feed directly into `LiveIdentityResolver`.
   - Identity Continuity (Option C) resolves vendor tracking IDs to stable Atlas entity IDs before admission to the canonical `LiveWorldStateReconciler`.
   - Future multi-sensor fan-in will enter through a dedicated temporal merge / reassembly seam before reaching identity continuity.

