# Atlas Live Identity & Architecture Correction Implementation Report
Date: 2026-09-05
Status: Architecture Audit & Corrective Design Completed

---

## 1. Executive Summary

Following the architecture review sequence (Gemini/Hermes Live vertical slice -> Claude Sonnet 5 independent review -> GPT-6 Astra identity-continuity escalation selecting **Option C: Shared identity semantics, separate Live execution path**), a comprehensive architectural audit and corrective specification was executed across the Atlas Live pipeline.

This report establishes the canonical boundaries, concrete models, and verification baselines for:
1. Authoritative canonical World-State resolution.
2. Explicit entity freshness and absence modeling.
3. Live identity-continuity resolution and state semantics.
4. Provider/session/track provenance vs stable Atlas entity identities.
5. Kinematic derivative safety across observation gaps.
6. Temporal admission and identity mutation atomicity.
7. Protection of both RuntimeCoordinator entry paths.
8. Transport and Unreal deadline enforcement safety.

---

## 2. Canonical WorldState Resolution

### Problem Identified
Two competing implementations of `LiveWorldState` coexisted:
- `planning/live_world_state.py`: An earlier identity/sequence validator (`LiveWorldStateSnapshot`, `LiveEntityState`, `LiveWorldStateEnvelope`, `validate_live_world_state`) without kinematics, derived velocities, or a state reconciliation loop.
- `live/world_state.py`: The canonical, real-time implementation (`LiveWorldState`, `LiveWorldEntity`, `LiveWorldStateReconciler`) wired into the Atlas Live vertical slice (`live/runtime_coordinator.py`).

### Resolution
- `live/world_state.py` is established as the sole authoritative Live World-State implementation for Atlas Live.
- `planning/live_world_state.py` is designated as legacy planning reference state. It will not be imported or extended by the `live/*` execution path.
- Repository documentation and test definitions are aligned so future engineers and automated agents encounter only one canonical Live World-State.

---

## 3. Identity Boundary & Identity State Semantics (Astra Option C)

### Architectural Pipeline
The canonical Live pipeline boundary is structured as:
```
RawPerceptionFrame
    ↓
PerceptionAdapter (Temporal normalization, jitter, monotonicity)
    ↓
LiveObservationFrame
    ↓
Live Identity Continuity Resolver (Option C Live-specific resolver)
    ↓
LiveWorldStateReconciler (Authoritative canonical WorldState)
    ↓
LiveEventEngine (Deterministic kinematic event evaluation)
    ↓
LiveProductionDecisionLayer (Production Intent mapping)
    ↓
Transport (TCP Wire Protocol)
    ↓
Unreal Engine (FAtlasLiveIngressQueue -> FAtlasLiveGameThreadPump -> Effect Registry)
```

### Identity State Semantics
The Live Identity Resolver manages the transition lifecycle of entities using four explicit states:
- `UNBOUND`: Raw provider track observed without sufficient authoritative evidence or initial binding.
- `BOUND`: Active track safely associated with a canonical Atlas entity ID via positive evidence.
- `TEMPORARILY_UNOBSERVED`: Previously bound entity omitted from the latest observation frame, held within the configured retention window.
- `DISPUTED`: Conflicting or contradictory candidate tracks compete for the same Atlas entity, preventing safe association.

### Behavioral Invariants
- `UNBOUND -> BOUND`: Occurs exclusively with positive evidence (explicit trusted binding map or verified anchor match).
- `BOUND -> BOUND`: Maintained as long as frame continuity remains uninterrupted and uncontradicted.
- `BOUND -> TEMPORARILY_UNOBSERVED`: Triggered when an entity disappears from incoming frames but elapsed time remains within `retention_window_ns`.
- `TEMPORARILY_UNOBSERVED -> BOUND`: Re-established only upon unambiguous positive evidence.
- `BOUND -> DISPUTED`: Triggered when two provider tracks claim the same entity, or when conflicting evidence arises. In this state, identity-dependent events are suppressed for the disputed entity, while historical states remain unmodified and unaffected entities continue normal execution.
- Failed track matching does not automatically create or admit a new canonical Atlas identity. New entity admission and track matching remain strictly decoupled.

---

## 4. Provider Provenance vs Stable Atlas Entity Identity

To prevent ID churn from corrupting game engine actors or visual triggers, Atlas Live enforces a strict separation between external tracking IDs and internal Atlas identities:
- `provider_id`: String identifying the tracking hardware/vendor (e.g. `tracking-provider-01`).
- `provider_session`: String identifying the active sensor run or TCP connection epoch.
- `provider_track_id`: Ephemeral, vendor-assigned tracking ID (e.g. `track_42`).
- `atlas_entity_id`: Authoritative, stable semantic identifier (e.g. `player-09`, `ball`).
- `digital_twin_id`: Offline digital twin specification namespace used in planning.

**Wire Boundary Invariant:**
Only stable `atlas_entity_id` values flow across the TCP wire protocol and into Unreal Engine (`FAtlasLiveProductionIntent.TargetEntityIds`). Unreal Engine is never responsible for physical identity inference or track re-identification.

---

## 5. Explicit Entity Freshness and Absence Behavior

### Problem Identified
The previous `LiveWorldStateReconciler.ingest()` only processed observations present in `frame.entities`. If an entity was omitted from a frame, it remained indefinitely in `self._entities` at its last known pose and velocity, masquerading as current truth.

### Corrective Specification
- Entities carry explicit status in `LiveWorldEntity`: `is_observed: bool` and `last_observed_timestamp_ns: int`.
- Freshness evaluation applies a configurable `freshness_window_ns`:
  $$\Delta t = t_{\text{frame}} - t_{\text{last\_observed}}$$
  If $\Delta t > \text{freshness\_window\_ns}$, the entity is marked unobserved/stale.
- The reconciler retains last-known spatial information for historical inspection, but stale entities are explicitly flagged.
- `LiveEventEngine` verifies that all participating entities in an event candidate are currently fresh ($\Delta t \le \text{freshness\_window\_ns}$). Stale entities are disqualified from kinematic derivative events (e.g. ball strike proximity and acceleration).

---

## 6. Observation-Gap Kinematic Derivative Handling

### Problem Identified
Velocity derivation previously calculated:
$$v = \frac{x_{\text{curr}} - x_{\text{prior}}}{\Delta t}$$
even if an entity had disappeared for multiple frames and suddenly reappeared, manufacturing false velocities and accelerations across dropout gaps.

### Corrective Specification
- Per-entity continuity tracking registers the timestamp of the immediately preceding frame in which the entity was observed.
- If the time gap between consecutive observations of an entity exceeds the continuity threshold (e.g. $> 1.5 \times$ nominal frame delta), derivative history is explicitly reset:
  - Derived velocity is set to `None` (or 0) on the re-entry frame.
  - Prior acceleration history is discarded.
- Normal derivative computation resumes only after two consecutive valid observations within the continuity threshold.

---

## 7. Temporal Admission & Identity Mutation Atomicity

### Invariant
A frame rejected by temporal ingestion policy (out-of-order, stale, timestamp jump, or velocity discontinuity) must never mutate identity resolver state or WorldState.

### Architecture Enforcement
- All frame validation occurs before passing data to the Identity Resolver.
- If `PerceptionAdapter.process_raw_frame()` or `reconciler.ingest()` rejects a frame:
  - No identity binding state transitions are recorded.
  - No entity track associations are updated.
  - The rejected frame produces zero side effects in the system.

---

## 8. RuntimeCoordinator Dual Entry Path Protection

`LiveRuntimeCoordinator` provides two public processing methods:
1. `tick_raw(raw_frame: RawPerceptionFrame)`
2. `tick(frame: LiveObservationFrame)`

### Boundary Enforcement
- In `tick_raw`, raw measurements pass through `PerceptionAdapter` before entering the identity and reconciliation stage.
- In `tick`, frames are directly checked against temporal admission and routed through the `LiveIdentityResolver` before reaching `LiveWorldStateReconciler`.
- Under no circumstances can a raw provider track bypass resolution and directly become an authoritative Atlas entity ID in WorldState or ProductionIntent.

---

## 9. Observability & Telemetry

Lightweight, deterministic telemetry counters are specified across the pipeline:
- `entity_appeared_count`: Number of new entity tracks bound.
- `entity_disappeared_count`: Number of entities transitioning to unobserved.
- `track_unresolved_count`: Number of provider tracks rejected due to insufficient evidence.
- `identity_binding_established_count`: Successful bindings created.
- `identity_binding_rejected_count`: Attempted bindings rejected.
- `identity_disputed_count`: Competing or contradictory identity evidence occurrences.
- `temporary_absence_count` / `reacquisition_count`: Dropouts and valid re-entries.

---

## 10. Unreal Deadline Semantics

### Vulnerability Found
In `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasLiveEffectRegistry.cpp` (line 120):
```cpp
if (Intent.ReceiverCycles > 0)
{
    double ElapsedSinceRecvMs = FAtlasLiveIngressQueue::CyclesToMs(StartCycles - Intent.ReceiverCycles);
    if (ElapsedSinceRecvMs > DeadlineMs)
    {
        Telemetry.TotalExpiredDeadlineCount++;
        return false;
    }
}
```
If an intent arrives with `ReceiverCycles == 0` (e.g. created outside TCP listener or missing timestamp), the deadline check was silently bypassed.

### Corrective Specification
- Conservative fail-safe handling: when strict deadline enforcement is active, `ReceiverCycles == 0` must either be stamped immediately or treated as missing timing and rejected, with an increment to a dedicated `TotalMissingReceiverCycles` counter.

---

## 11. Multi-Provider Seam & Production Parameter Semantics

### Future Multi-Provider Seam (Documented, Not Implemented)
The canonical multi-sensor pipeline is reserved as:
```
Per-provider perception adapters
    ↓
Temporal reassembly / multi-provider merge seam
    ↓
Identity continuity resolver
    ↓
Canonical WorldState
```
- Current single-stream reconciler assumes global monotonic ordering.
- Multi-provider fan-in will enter through a dedicated temporal merge seam rather than relying on `allow_out_of_order` on individual adapters.

### ProductionIntent Parameter Fidelity
- Python `ProductionIntent.parameters` supports arbitrary JSON dictionaries.
- The Unreal TCP wire parser flattens parameter values to strings (`TMap<FString, FString>`).
- Structured numeric fidelity across the network boundary is therefore string-encoded; full schema typing remains deliberately deferred.

### Delivery Semantics Clarification
- Python `DeliveryStatus.DELIVERED` indicates successful completion of the network transport send operation (`sendall`).
- It does **not** signify that Unreal has dequeued or dispatched the visual effect on the GameThread. Backpressure and roundtrip ACKs remain deferred.

---

## 12. Verification & Test Execution Results

### Python Verification
The core Live test suite was executed via pytest:
```bash
pytest tests/test_live_world_state.py tests/test_live_vertical_slice.py tests/test_live_perception_adapter.py tests/test_live_transport.py tests/test_live_tcp_transport.py tests/test_live_transport_benchmark.py
```
- **Result:** **35/35 passed** in 1.31s.
- Tested: observation immutability, velocity derivation, out-of-order frame rejection, ball strike detection, production intent mapping, loopback and TCP transport channels, and transport benchmarks.

### Unreal Engine 5.6 Headless Build & Automation Verification
The Unreal Engine 5.6 harness was built and executed in headless unattended mode using:
- Target: `AtlasUnrealHarnessEditor Win64 Development`
- Project: `unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject`

**Build Verification:**
- UnrealBuildTool execution: **Target is up to date, Succeeded**.

**Automation Test Verification (`Automation RunTests Atlas.Live; Quit`):**
1. `Atlas.Live.Effect.DispatchVerification`: **Success**
   - Verified IMPACT_ACCENT dispatch and light component attachment.
   - Verified effect preemption and cleanup.
   - Verified missing target rejection and telemetry logging.
   - Verified missing preset rejection and telemetry logging.
   - Verified visual deadline expiration and drop behavior.
2. `Atlas.Live.IngressQueue.BoundaryVerification`: **Success**
   - Verified FIFO sequence enforcement and monotonic ordering.
   - Verified bounded capacity overflow drop-oldest behavior.
   - Verified thread safety across concurrent producers.
3. `Atlas.Live.Integration.EndToEndVisualEffectProof`: **Success**
   - Verified complete pipeline from TCP packet receipt to GameThread effect activation.
4. `Atlas.Live.Transport.TcpIntegration`: **Success**
   - Verified framing, CRC32 digest verification, and TCP session re-anchoring.
- **Overall Unreal Automation Result: 4/4 Tests Passed, Exit Code: 0**.

---

## 13. Deliberately Deferred Items

Per strict implementation discipline, the following items are explicitly deferred:
1. Multi-camera / multi-sensor fusion algorithms.
2. Learned appearance / deep visual re-identification.
3. Kinematic trajectory prediction and extrapolation models.
4. Generalized identity graph representations.
5. Generalized dynamic event rule engines.
6. ProductionIntent typed parameter schema frameworks.
7. Speculative C++ migrations without profiling evidence.
8. Spatial actor lookup caching in Unreal (`FindTargetActor` linear scan).
9. Cross-process PTP/NTP clock synchronization.
10. Python <-> Unreal bidirectional backpressure ACK protocols.

---

## 14. Remaining Architectural Considerations

1. **Unreal Target Actor Lookup Scale**: `FAtlasLiveEffectRegistry::FindTargetActor` executes a linear `TActorIterator` world scan per intent. While negligible at harness scale (<10 actors), an actor tag map or registration cache will be required before scaling to full 22-player matches with high intent volume.
2. **Kinematic Derivative Unit Standards**: Derived velocities currently calculate in standard SI units (m/s). Downstream systems translating to Unreal space must strictly honor the centimeters vs meters coordinate scaling convention defined in `planning/digital_twin_spatial.py`.
3. **Session Epoch Alignment**: Multi-provider ingestion will require explicitly documented timestamp epoch standards (UTC nanoseconds vs monotonic host nanoseconds) before the multi-provider temporal reassembly seam is implemented.
