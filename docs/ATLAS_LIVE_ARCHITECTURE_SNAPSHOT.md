# Atlas Live — Architecture Snapshot

**Prepared For:** External Senior Architectural Review  
**Date:** September 4, 2026  
**Status:** Phase 4 Complete — State-to-Event Ingestion & Real Unreal Live Delivery Verified  

---

## 1. Executive Summary

Atlas Live is the real-time soccer production subsystem of Atlas. It continuously ingests physical observation streams (from cameras, computer vision, optical tracking, or simulators), maintains an authoritative canonical World-State, recognizes physical interactions as deterministic events, selects engine-agnostic production intents, and delivers them across a low-latency localhost TCP transport to Unreal Engine for real-time visual execution.

This document snapshots the subsystem map, core contracts, data flow, temporal model, deterministic boundaries, language replacement boundaries, and known architectural risks prior to real hardware sensor ingestion.

---

## 2. Subsystem Map & End-to-End Pipeline

```text
Physical Soccer Reality (Sensors, Tracking SDKs, Simulators)
                   │
                   ▼  [RawPerceptionFrame]
┌─────────────────────────────────────────────────────────────┐
│ 1. Perception Adapter Boundary (live/perception_adapter.py) │
│    - Provider-neutral raw sensor ingestion                  │
│    - Bounded jitter filtering & monotonic ordering          │
│    - Staleness & timestamp discontinuity gates              │
│    - Confidence floor & kinematic sanity filtering          │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [LiveObservationFrame]
┌─────────────────────────────────────────────────────────────┐
│ 2. Live Identity Continuity (live/identity_resolver.py)     │
│    - Astra Option C conservative identity semantics        │
│    - Ephemeral provider tracks -> stable Atlas entity IDs   │
│    - Explicit states: UNBOUND, BOUND, TEMPORARILY_UNOBSERVED│
│    - Positive evidence required; ambiguity stays unresolved │
│    - Protects both tick_raw() and tick() entry paths        │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [Resolved LiveObservationFrame]
┌─────────────────────────────────────────────────────────────┐
│ 3. Canonical World-State (live/world_state.py)              │
│    - Sole authoritative Live World-State implementation    │
│    - Explicit freshness tracking (OBSERVED/STALE/UNOBSERVED)│
│    - Kinematic derivative gap reset safety                  │
│    - Bounded historical snapshot window                     │
│    - Strict separation of observed state from predictions   │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [LiveWorldState]
┌─────────────────────────────────────────────────────────────┐
│ 4. Event Recognition Engine (live/event_engine.py)          │
│    - High-frequency rule-based kinematic event recognition  │
│    - Excludes stale/unobserved entities from kinematic math │
│    - Detects BALL_STRIKE, POSSESSION_CHANGE, etc.           │
│    - Preserves physical interaction timestamp               │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [LiveEvent]
┌─────────────────────────────────────────────────────────────┐
│ 4. Production Decision Layer (live/production_intent.py)    │
│    - Deterministic mapping from Event -> ProductionIntent   │
│    - Selects treatment category, preset, intensity, duration│
│    - Engine-agnostic; zero Unreal UObject dependencies      │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [ProductionIntentEnvelope (SHA-256 Digest)]
┌─────────────────────────────────────────────────────────────┐
│ 5. Localhost TCP Transport (live/tcp_transport.py)          │
│    - 127.0.0.1 with TCP_NODELAY                             │
│    - Protocol v1 length-prefixed framing (Big-Endian)       │
│    - Persistent streaming; non-blocking delivery receipts   │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  (Network boundary / TCP Port 7778)
┌─────────────────────────────────────────────────────────────┐
│ 6. Unreal Live Ingress Queue (AtlasLiveTcpListener & Queue) │
│    - Async background receiver thread (FRunnable)           │
│    - Partial-read frame assembly & BCrypt SHA-256 validation│
│    - Bounded MPSC ring buffer with Head Eviction overflow   │
│    - Monotonic sequence enforcement & sliding window dedup  │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  (Thread boundary: Ingress Queue -> GameThread)
┌─────────────────────────────────────────────────────────────┐
│ 7. Deterministic GameThread Pump (AtlasLiveGameThreadPump)  │
│    - Ticks on GameThread via FTSTicker once per frame       │
│    - Bounded batch dequeue (MaxIntentsPerTick)              │
│    - Zero network waits; protects frame budget              │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼  [FAtlasLiveProductionIntent]
┌─────────────────────────────────────────────────────────────┐
│ 8. Visual Effect Registry & Handlers (AtlasLiveEffectRegistry)│
│    - Maps Treatment + Preset -> IAtlasLiveEffectHandler     │
│    - Finds target actor via atlas_entity:<ID> tags          │
│    - Authoritative visual deadline enforcement              │
│    - Deterministic transient component attachment & cleanup │
│    - Supported: IMPACT_ACCENT, SPEED_TRAIL, IMPACT_FRAME   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Core Contracts & Data Flow

### A. Raw Perception & Ingestion
- **`RawPerceptionFrame`**: Raw container carrying `sensor_timestamp_ns` and a tuple of `RawEntityMeasurement` structs (`entity_id`, Cartesian coordinates `x, y, z`, velocities, `confidence`, `attributes`).
- **`PerceptionIngestionPolicy`**: Configurable boundary parameters:
  - `min_confidence`: Rejects measurements below threshold (default 0.3).
  - `max_staleness_ns`: Optional staleness drop relative to arrival clock.
  - `max_timestamp_jump_ns`: Detects clock discontinuities (default 5.0s).
  - `max_implausible_speed_m_s`: Sanity ceiling on inter-frame displacement $\frac{|\Delta \vec{p}|}{\Delta t}$ (default 60 m/s / 216 km/h).
  - `allow_out_of_order`: Rejects backward-timestamp frames by default.
- **`LiveObservationFrame`**: Normalized, validated observation frame indexed by physical `timestamp_ns` and arrival `ingested_at_ns`.

### B. World-State & Event
- **`LiveWorldState`**: Canonical snapshot containing reconciled `LiveWorldEntity` instances, coordinate references, and `reconciled_at_ns`. Owns historical temporal history for derivative calculations.
- **`LiveEvent`**: Immutable record of a recognized physical interaction (`event_id`, `event_type`, physical `timestamp_ns`, `entity_ids`, `intensity`, `location`, `direction`, `detected_at_ns`).

### C. Production Intent
- **`ProductionIntent`**: Engine-agnostic visual request:
  - `intent_id`: Unique tracking identity.
  - `treatment`: Category enum (`IMPACT_ACCENT`, `SPEED_TRAIL`, `IMPACT_FRAME`, `BALL_HIGHLIGHT`, `PLAYER_CARD`, `CINEMATIC_PUNCH`).
  - `target_entity_ids`: Logical entities (e.g. `("ball",)`, `("player-09",)`).
  - `intensity`: Normalized $[0.0, 1.0]$.
  - `duration_ms`: Duration of the visual effect.
  - `timestamp_ns`: Physical occurrence time inherited from the event.
  - `origin` / `direction`: Optional 3D vectors for spatial anchoring.
  - `parameters`: High-level creative preset keys (e.g. `{"preset": "strike_flash_v1"}`).
  - `created_at_ns`: Monotonic host generation timestamp.
- **`ProductionIntentEnvelope`**: Cryptographic wire framing carrying monotonic `sequence_number`, `sent_at_ns`, and a SHA-256 digest of `Header + CanonicalIntentJSON`.

### D. Wire Protocol (v1)
- Binary framing over localhost TCP (`127.0.0.1`):
  `[uint32 BigEndian payload_len] [uint8 protocol_version (1)] [canonical UTF-8 JSON payload]`
  - Maximum payload ceiling: 64 KB.
  - Reconnects establish a new transport `SessionId`, cleanly resetting sequence domains.

---

## 4. Temporal Model & Clock Separation

Physical world time and host/engine processing time are strictly distinguished. At no point are cross-process clocks subtracted directly.

```text
[ Physical Sensor Clock ]           [ Host Python Clock (perf_counter_ns) ]          [ Unreal Platform Clock (Cycles64) ]
   sensor_timestamp_ns  ───────────► ingested_at_ns (adapter)
            │                        reconciled_at_ns (state)
            │                        detected_at_ns (event)
            ▼                        created_at_ns (intent)
      timestamp_ns  ───────────────► sent_at_ns (transport) ─────────────────────────► ReceiverCycles (TCP read)
                                                                                        ValidatedCycles (SHA-256 ok)
                                                                                        EnqueuedCycles (queue push)
                                                                                        DequeuedCycles (GameThread pop)
                                                                                        DispatchedCycles (VFX start)
```

- **In-Process Latency Metrics**:
  - $\Delta t_{\text{reconcile}} = \text{reconciled\_at\_ns} - \text{ingested\_at\_ns}$
  - $\Delta t_{\text{event}} = \text{detected\_at\_ns} - \text{reconciled\_at\_ns}$
  - $\Delta t_{\text{queue}} = \text{CyclesToMs}(\text{DequeuedCycles} - \text{EnqueuedCycles})$
  - $\Delta t_{\text{dispatch}} = \text{CyclesToMs}(\text{DispatchedCycles} - \text{DequeuedCycles})$
- **Cross-Process Measurement**: Evaluated via transport round-trip echo benchmarking rather than raw clock subtraction.

---

## 5. Unreal Engine Ingress & Visual Execution Boundary

- **`FAtlasLiveTcpListener`**:
  - Background `FRunnable` thread binding non-blocking TCP socket to `127.0.0.1:7778`.
  - Reassembles partial TCP frames, checks version and bounds, validates SHA-256 via Windows `BCrypt`, and pushes to the queue.
  - **Zero GameThread blocking**.
- **`FAtlasLiveIngressQueue`**:
  - Bounded thread-safe MPSC queue (default capacity 128).
  - **Overflow Policy**: Drop Oldest (Head Eviction) to guarantee that fresh real-time visual intents are never blocked by stale queued items.
  - Sliding-window `IntentId` deduplication and session-reset sequence monotonicity.
  - Atomic utilization telemetry (`UtilizationRatio`, `bWarningThresholdExceeded`).
- **`FAtlasLiveGameThreadPump`**:
  - Bounded batch pump (`MaxIntentsPerTick = 16`) running on `FTSTicker` on the GameThread.
  - Prevents burst intent arrivals from blowing the frame budget.
- **`FAtlasLiveEffectRegistry` & Concrete Handlers**:
  - Resolves target actors via actor tags: `atlas_entity:<ENTITY_ID>`.
  - Enforces authoritative visual deadlines (`DeadlineMs`, default 500ms): stale intents are dropped before touching actors.
  - **`FAtlasLiveImpactAccentHandler`**: Attaches transient `UPointLightComponent` with intensity and attenuation scaled by intent.
  - **`FAtlasLiveSpeedTrailHandler`**: Attaches transient `ULineBatchComponent` drawing directional velocity lines.
  - **`FAtlasLiveImpactFrameHandler`**: Attaches transient unbound `UPostProcessComponent` overriding viewport contrast and saturation.
  - Automatic deterministic cleanup upon duration expiration or preemption.

---

## 6. Language & Migration Strategy (Python vs. C++)

Atlas Live maintains a hybrid language boundary designed for progressive native migration:

| Subsystem Component | Current Implementation | Migration Readiness / Plan |
| :--- | :--- | :--- |
| **Perception Ingestion & Jitter** | Python (`PerceptionAdapter`) | High-frequency candidate. Interface is designed around plain structs (`RawPerceptionFrame`), making C++ conversion straightforward. |
| **World-State Reconciliation** | Python (`LiveWorldStateReconciler`) | Candidate for native implementation when fusing multi-camera 120 Hz feeds or running spatial kinematic filters. |
| **Event Engine** | Python (`LiveEventEngine`) | Rule-based vector arithmetic; clean candidate for C++ when state reconciler moves to native. |
| **Production Decision Layer** | Python (`LiveProductionDecisionLayer`) | Kept in Python for AI orchestration, creative configuration, and template compilation. |
| **Transport Wire Protocol** | Python / C++ | Protocol v1 binary framing is completely language-agnostic and standard TCP. |
| **Unreal Ingress & VFX Dispatch**| Unreal C++ (`AtlasUnrealTransport`) | Fully native C++ in engine module. Zero Python runtime dependency inside Unreal. |

---

## 7. Current Known Architectural Risks & Tradeoffs

1. **Multi-Camera Asynchronous Arrival Jitter**:
   - Current `PerceptionAdapter` enforces strict monotonic sensor ordering per provider (`allow_out_of_order=False`). When multi-camera feeds with varying capture/encoding latencies arrive concurrently, a sliding-window temporal reassembly buffer will be needed upstream of reconciliation.
2. **GameThread Hitch Eviction**:
   - Under severe rendering load, GameThread frame hitches (>500ms) will cause incoming intents to evict older queued intents or expire their visual deadlines. This is the intended behavior (visual freshness over historical replay), but demands backpressure telemetry alerting.
3. **Target Actor Identity Continuity**:
   - Target actors must exist in the Unreal scene with `atlas_entity:<ID>` tags. If an external tracker drops or swaps tracking IDs (e.g. tracker assigns a new player ID mid-play), the effect registry will report `MissingTarget` until target reconciliation stabilizes.

---

## 8. Multi-Provider Seam, Parameter Fidelity, & Delivery Semantics

### 8.1 Multi-Provider Reserved Seam (Documented Boundary)
Future multi-provider fan-in will enter via a dedicated temporal merge / reassembly seam:
```text
Per-provider perception adapters
    ↓
Temporal reassembly / multi-provider merge
    ↓
Live identity continuity resolver
    ↓
Canonical WorldState
```
- Current single-stream reconciler assumes global monotonic ordering.
- Multi-provider fan-in will enter through this reserved temporal merge seam rather than relying on `allow_out_of_order` on individual adapters.

### 8.2 ProductionIntent Parameter Fidelity Across Wire
- Python `ProductionIntent.parameters` supports general JSON-compatible values.
- The Unreal TCP wire parser flattens parameter values to strings (`TMap<FString, FString>`).
- Structured numeric fidelity across the network boundary is string-encoded; schema validation remains deliberately deferred.

### 8.3 Delivery Semantics Clarification
- Python `DeliveryStatus.DELIVERED` indicates that the network transport send completed successfully (`sendall`).
- It does **NOT** indicate that Unreal has processed the intent or that GameThread has dispatched the effect. Python<->Unreal ACK/backpressure remains deferred.

### 8.4 Visual Deadline Safety
- In `FAtlasLiveEffectRegistry::DispatchIntent`, `ReceiverCycles == 0` is treated as missing receiver timing and rejected conservatively for deadline safety. Missing receiver timing never silently disables deadline enforcement.

### 8.5 Engineering Review Workflow
The model review workflow for Atlas Live:
- **Gemini / Hermes:** Primary implementation and verification.
- **Claude Sonnet 5:** Independent architectural reviewer.
- **GPT-6 Astra:** Escalation authority for architecture forks (chose Option C).
- **DeepSeek V4 Flash:** Optional secondary engineering/review model, not currently replacing Gemini.


---

## 9. Deliberately Deferred Capabilities

The following features were investigated and deliberately deferred to keep the live pipeline lean:
- **No Heavyweight Perception SDK Integrations**: Hawk-Eye, Chyron, or OpenCV tracking SDKs were not bound yet; synthetic providers proved the adapter interface first.
- **No Generalized ECS or Message Bus**: Avoided complex middleware in favor of deterministic function pipelines and bounded ring buffers.
- **No Speculative Complex VFX Assets**: Avoided importing bulky external Niagara systems until gameplay and cinematic requirements demand them; transient components (`PointLight`, `LineBatch`, `PostProcess`) proved the dispatcher contract cleanly.
- **No Camera Spatial Manipulation**: Camera motion was excluded from `IMPACT_FRAME` to preserve camera authority and avoid nausea-inducing jitter during live sports viewing.

---

## 10. Current Verification Evidence

- **Focused Python Live Test Suite**:
  - `tests/test_live_perception_adapter.py` (9/9 passed)
  - `tests/test_live_perception_e2e_proof.py` (1/1 passed)
  - `tests/test_live_vfx_pipeline_proof.py` (1/1 passed)
  - `tests/test_live_tcp_e2e_proof.py` (1/1 passed)
  - `tests/test_live_tcp_transport.py` (4/4 passed)
  - `tests/test_live_transport.py` (10/10 passed)
  - `tests/test_live_transport_benchmark.py` (4/4 passed)
  - `tests/test_live_world_state.py` (10/10 passed)
  - `tests/test_live_vertical_slice.py` (8/8 passed)
- `tests/test_live_perception_adapter.py` (9/9 passed)
- `tests/test_live_perception_e2e_proof.py` (1/1 passed)
- `tests/test_live_vfx_pipeline_proof.py` (1/1 passed)
- `tests/test_live_tcp_e2e_proof.py` (1/1 passed)
- `tests/test_live_tcp_transport.py` (4/4 passed)
- `tests/test_live_transport.py` (10/10 passed)
- `tests/test_live_transport_benchmark.py` (4/4 passed)
- `tests/test_live_world_state.py` (10/10 passed)
- `tests/test_live_vertical_slice.py` (8/8 passed)
- `tests/test_live_unreal_production_artifact_proof.py` (3/3 passed)
- `tests/test_live_identity_continuity.py` (9/9 passed)
- `tests/test_live_telemetry_provider.py` (7/7 passed)
- `tests/test_live_telemetry_socket_provider.py` (5/5 passed)
- `tests/test_live_skillcorner_adapter.py` (5/5 passed)
- **Total: 77/77 tests passing in ~42 seconds**.
- **Unreal Automation Tests (UE 5.6 Headless)**:
  - `Atlas.Live.IngressQueue.BoundaryVerification`: **Passed**
  - `Atlas.Live.Transport.TcpIntegration`: **Passed**
  - `Atlas.Live.Effect.DispatchVerification`: **Passed**
  - `Atlas.Live.Integration.EndToEndVisualEffectProof`: **Passed**
  - **Total: 4/4 automation tests passing, Exit Code: 0**.
- **Unreal Build Verification**:
  - `AtlasUnrealHarnessEditor Win64 Development` compiles and links cleanly with MSVC 14.44 / VS2022.
