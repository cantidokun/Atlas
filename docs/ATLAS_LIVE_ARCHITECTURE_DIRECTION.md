# Atlas Live — Architecture Direction

## Status

Exploratory architecture direction. This document deliberately avoids freezing implementation choices before prototypes and measurements exist.

## 1. Target system

Atlas Live is intended to become a real-time soccer production subsystem capable of maintaining a continuously updated understanding of the physical production world and using that state to drive controlled digital production.

The target conceptual pipeline is:

```text
Physical world
    |
    v
Capture / external sensors
    |
    v
Perception adapters
    |
    v
Atlas World-State
    |
    +--> temporal state / prediction
    |
    +--> event recognition
    |
    v
Production decision layer
    |
    v
Atlas production interface
    |
    v
Unreal runtime
    |
    v
Live composite / output
```

The system must be capable of operating with simulated inputs before it is expected to operate with real tracking hardware.

## 2. Core abstraction: observation vs state

Do not treat an external detector's output as Atlas truth.

External systems produce **observations**. Atlas combines observations, timing, provenance, confidence, and prior state into its **World-State**.

Conceptually:

```text
Observation
  source
  timestamp
  entity
  measurement
  confidence
  coordinate frame
        |
        v
State reconciliation
        |
        v
Atlas World-State
```

This distinction is important because multiple providers may disagree, observations may arrive late, and the same provider may change over time.

## 3. World-State responsibilities

World-State should own the canonical runtime representation of relevant live reality. It should not become a dumping ground for every piece of metadata available to Atlas.

Potential state domains:

- field/world coordinate frame;
- calibration state;
- players/entities;
- ball;
- camera state;
- pose/body state;
- derived velocity/acceleration;
- spatial relationships;
- environment information relevant to production;
- event state;
- confidence and provenance;
- temporal validity/freshness.

The exact schema should emerge from concrete use cases.

## 4. Temporal model

Live Atlas is fundamentally temporal.

State should preserve enough timing information to answer questions such as:

- When was this observation captured?
- When did Atlas receive it?
- What state was believed at that time?
- Is this observation late or stale?
- What event sequence led to the current interpretation?
- How much latency exists between physical occurrence and production response?

Avoid relying on a single implicit process-clock timestamp when multiple clocks or transport boundaries exist.

A future implementation may require capture timestamps, source timestamps, receive timestamps, monotonic runtime time, and synchronization metadata. Do not add all of these until the actual integration requires them.

## 5. Event model

Events should be derived from state and temporal relationships rather than being arbitrary commands emitted by individual perception modules.

Examples include:

```text
player possession
pass
shot preparation
foot-ball contact
shot
jump
tackle
collision
save
goal
```

The initial event vocabulary should remain small and demonstrable.

An event should carry enough information for downstream production logic to understand what happened, when, where, confidence, and which entities are involved.

## 6. Prediction

Prediction is a potential latency-reduction mechanism, not a source of authoritative truth.

For example, a system may predict likely ball contact shortly before contact occurs and prepare a production effect. The eventual observed event should still determine whether the predicted action actually occurred.

Prediction should therefore be represented as prediction/intent/forecast rather than silently overwriting observed state.

## 7. Critical-loop design

Do not put heavyweight general reasoning in the per-frame critical path.

Prefer a separation such as:

```text
High-frequency runtime
  capture
  state update
  tracking integration
  temporal filtering
  event primitives
        |
        +----> bounded production decision

Lower-frequency intelligence
  semantic reasoning
  creative planning
  effect authoring
  configuration
  analysis
```

The exact frequencies should be measured rather than assumed.

## 8. Production decision layer

The decision layer should eventually be able to map events/state to production intents, for example:

```text
Event: SHOT
Intensity: 0.82
Origin: right-foot contact
Direction: ball travel vector
Treatment: IMPACT_07
Duration: 80ms
```

This is illustrative only. The actual contract should be designed from the first useful effect integration.

The live system should generally select and parameterize prepared capabilities rather than generate complex assets synchronously at event time.

## 9. Unreal boundary

Unreal should remain the production execution environment. Live should not depend on internal Unreal implementation details.

A production intent should cross an explicit boundary into an Unreal-facing adapter/runtime.

Possible transports include in-process APIs, IPC, sockets, shared memory, engine plugins, or other mechanisms. The choice should be benchmark-driven.

Important measurements:

- serialization cost;
- transport latency;
- synchronization cost;
- back-pressure behavior;
- failure detection time;
- recovery behavior.

## 10. C++ boundary

The architecture should permit a progression such as:

```text
Python prototype
      |
      v
stable language-neutral contract
      |
      v
native C++ implementation when justified
```

Likely C++ candidates include high-throughput state handling, spatial computation, concurrency, temporal processing, native integrations, and GPU-facing runtime paths.

Python remains appropriate for higher-level intelligence, experimentation, orchestration, data/model workflows, and other non-critical components.

Do not create a C++ framework simply to satisfy an architectural preference. Let profiling and integration requirements drive native migration.

## 11. External providers

Potential provider categories:

- camera tracking;
- player tracking;
- ball tracking;
- pose estimation;
- segmentation/matting;
- depth;
- calibration;
- timecode/genlock;
- video I/O;
- other specialized real-time production systems.

Providers should be integrated through adapters into Atlas's observation/state boundary.

The provider abstraction should remain as small as possible until an actual provider proves the need for additional features.

## 12. Latency decomposition

Measure the whole path, not just model inference:

```text
capture
 + acquisition
 + buffering
 + transport
 + inference
 + tracking
 + state reconciliation
 + event recognition
 + decision
 + transport to Unreal
 + Unreal scheduling
 + rendering
 + compositing
 + output transport
```

The system should record enough telemetry to identify which segment dominates latency and which segment introduces variance.

Latency variance is a first-class engineering concern.

## 13. Graceful degradation

The live system should degrade by capability rather than collapse globally where safe.

Examples:

```text
tracking confidence drops
    -> reduce effect complexity / suppress effect

provider disconnects
    -> mark affected state unavailable

intelligence unavailable
    -> continue with deterministic rules / prepared behavior

Unreal transport unavailable
    -> production path remains explicit about degraded state
```

Do not fabricate authoritative state to keep the pipeline appearing healthy.

## 14. Verification philosophy for live

Offline Atlas often verifies a mutation after execution. Live Atlas may instead need continuous verification.

Potential verification signals include:

- state freshness;
- source health;
- timestamp coherence;
- confidence thresholds;
- event confirmation;
- command acknowledgment;
- Unreal runtime health;
- output health.

A live verification framework should not be built as a giant generalized system before a concrete end-to-end prototype identifies the required signals.

## 15. Digital Twin and Identity Relationship

Atlas owns the canonical Digital Twin.

Photogrammetry remains an upstream reconstruction process. Blender analyzes, cleans, corrects, optimizes, and prepares reconstructed assets. Unreal is a downstream production execution environment.

Live state should reference the canonical world/digital coordinate system rather than making a tracking vendor's coordinate system the permanent Atlas identity.

Explicit identity distinction:
- **Provider Tracking Identity**: Ephemeral, vendor-assigned IDs emitted by perception hardware/trackers (e.g., `track_42`).
- **Stable Atlas Entity Identity**: Authoritative runtime entities recognized across Atlas Live (`player-09`, `ball`).
- **Digital Twin Identity**: Canonical offline asset identities and anchor models defined in `planning/digital_twin_identity.py`.

Live execution reuses the conservative identity semantics (MATCH, NO_MATCH, INSUFFICIENT_EVIDENCE) via `live/identity_resolver.py` without depending on planning/Blender offline workflows.

## 16. Engineering and Architecture Review Workflow

To prevent architectural drift and maintain rigorous implementation discipline, Atlas Live uses a multi-model engineering and review chain:
- **Gemini / Hermes:** Primary implementation and verification agent.
- **Claude Sonnet 5:** Independent architectural reviewer identifying structural risks.
- **GPT-6 Astra:** Escalation authority for architectural forks (selected Option C: shared identity semantics, separate Live execution path).
- **DeepSeek V4 Flash:** Optional secondary engineering/review model, not currently replacing Gemini.

## 17. Next Development Phase: Direct Camera Perception V1

**Target Architecture:**
```text
Real Fixed Camera
    →
External Perception Worker (isolated process)
    →
Video Capture + Player/Ball Detection + Short-Term Tracking
    →
Fixed-Camera Pitch Registration / Homography
    →
Canonical Field Coordinates in Meters (atlas-field)
    →
Atlas UDP Telemetry (< 1472 bytes MTU)
    →
Existing Verified Atlas Live Pipeline
    →
Unreal Engine
```

The camera capture and neural detection stack must remain decoupled from Atlas Core. Physical camera selection will precede locking sensor parameters.



## 18. Architectural anti-patterns to avoid

- LLM-per-frame decision loops;
- provider-specific state becoming Atlas's canonical schema;
- direct perception-to-Unreal coupling;
- synchronous blocking on optional intelligence;
- unbounded queues that hide latency until the system fails;
- giant generalized plugin frameworks before a second integration exists;
- speculative C++ rewrites;
- experimental prototypes mixed into production runtime modules;
- silently treating predictions as observations;
- declaring live readiness from a simulation alone.

## 19. Evolution rule

This document is a direction, not a rigid implementation specification.

When implementation evidence contradicts an architectural assumption:

1. measure the contradiction;
2. document it;
3. propose the smallest architectural correction;
4. preserve existing contracts where possible;
5. update this document if the direction materially changes.
