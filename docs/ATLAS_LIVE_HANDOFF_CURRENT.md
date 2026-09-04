# Atlas Live — Hermes Development Handoff

**Prepared:** September 4, 2026
**Purpose:** Establish the architectural starting point and development mandate for Hermes-led development of Atlas Live.
**Repository:** `cantidokun/Atlas`
**Base reviewed:** GitHub `main` at `91e9efc3e9f4c9d6f37b651da95f2e3b363a540d`
**Important:** This document is a development handoff, not a claim that Atlas Live is already implemented or production-ready.

## 1. Mission

Atlas Live is the future real-time operating layer of Atlas for live soccer production. It should eventually allow Atlas to ingest live observations of a real soccer environment, maintain a continuously updated representation of that world, recognize meaningful events, select or parameterize production treatments, and drive controlled real-time execution in Unreal.

The Live subsystem remains part of the Atlas ecosystem. It is not a second Atlas and must not become an independent architectural universe inside the repository.

The objective is **not** to force a complete live system immediately. The objective is to establish the foundations so that Atlas can progressively move from simulated/live-like data to real sensors, tracking systems, cameras, and real-time production without requiring a rewrite.

## 2. Current repository reality

The existing Atlas repository is already a mature Python-oriented control architecture with strong validation, authorization, evidence, verification, receipts, recovery, and replanning concepts. The repository also contains substantial Blender and Unreal development work.

The current README reports a locally proven Unreal Engine 5.6 render boundary, including MRQ submission, dynamic job identity, asynchronous inspection, output artifact discovery, independent artifact validation, deterministic render receipts, and durable receipt persistence. The Unreal runtime job registry itself remains in-memory and cross-process job recovery is not implemented.

The generic architecture contract establishes the core principle that reasoning proposes, Atlas validates/authorizes/executes, production environments perform controlled work, and independent verification establishes what actually happened. A successful executor response is not itself proof of successful target state.

These existing principles are important to Live, but Live must not blindly copy an offline task/action architecture into a high-frequency real-time loop. Live has a different timing model and should determine which existing concepts remain synchronous, which become streaming state, and which require new runtime primitives.

## 3. Existing authoritative documents

Read these before making architectural changes:

- `README.md`
- `ATLAS_HANDOFF_CURRENT.md`
- `UNREAL_AGENT_HANDOFF_CURRENT.md`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
- `docs/OPENHANDS_TRANSITION_GUIDE.md`

Also inspect the actual current source tree and tests. Do not infer implementation from filenames alone.

## 4. Relationship to existing Atlas

Conceptually:

```text
                     ATLAS
                       |
        +--------------+--------------+
        |              |              |
     Blender         Unreal         Core
        |              |              |
        +--------------+--------------+
                       |
                shared contracts
                       |
                canonical Digital Twin
                       |
                 +-----+------+
                 |            |
              Offline       Live
             production    runtime
```

Live should reuse shared concepts where they genuinely fit, while introducing specialized real-time primitives where the offline architecture would create unnecessary latency or coupling.

Do not create duplicate definitions of fundamental Atlas concepts merely because Live has different runtime needs. Conversely, do not force a low-frequency transactional abstraction into a high-frequency streaming problem simply for conceptual uniformity.

## 5. World-State Model

The World-State Model is an Atlas-owned architectural layer.

External systems may provide observations, detections, tracks, poses, camera transforms, calibration, timing, or other sensor information. Those systems are providers/adapters. They do not define Atlas's canonical internal representation.

The World-State Model should eventually be capable of representing, as appropriate:

- field/world coordinate system and calibration;
- players and stable identities where available;
- body/pose state;
- ball state;
- cameras and camera transforms;
- relevant environment state;
- confidence/provenance for observations;
- timestamps and temporal relationships;
- derived kinematics or spatial relationships;
- recognized events and event confidence;
- source/version information sufficient to understand how state was derived.

This is a direction, not a frozen schema. Hermes should design the model based on actual repository needs and evidence from prototypes.

## 6. External perception philosophy

Atlas should remain vendor-agnostic.

Potential external providers may include camera tracking, player tracking, ball tracking, pose estimation, segmentation, depth, timecode/genlock, video I/O, and other specialized systems. Atlas should consume them through explicit adapters.

A future provider replacement should not require rewriting the downstream event engine, cinematic system, or Unreal integration.

However, do not invent a generalized adapter framework before at least one real integration/prototype establishes the need. Start with the smallest abstraction that preserves the architectural boundary and evolve it from evidence.

## 7. Runtime language strategy

Atlas remains hybrid rather than becoming a wholesale C++ rewrite.

Python remains appropriate for AI/LLM interaction, higher-level reasoning, orchestration, authoring, experimentation, data preparation, Blender automation, and other areas where Python is effective.

C++ should be considered strongly for latency-sensitive or high-throughput runtime components such as high-frequency state processing, tracking integration, temporal buffering, spatial computation, concurrency, GPU-facing paths, and Unreal-facing runtime code where profiling demonstrates a need.

The key requirement is **replaceability**: a Python prototype should be able to evolve into a native implementation without changing the surrounding conceptual contract.

Do not write C++ merely because Live is intended to be real-time. Profile first where practical.

## 8. Real-time design principles

Live should be designed around bounded latency and predictable behavior rather than average speed alone.

Important principles:

- avoid placing an LLM or heavyweight general reasoning loop in the per-frame critical path;
- separate high-frequency state/tracking from lower-frequency semantic reasoning;
- use prediction where it can safely reduce perceived latency;
- precompute/cache expensive production resources where appropriate;
- keep live execution deterministic enough to degrade gracefully;
- isolate slow or unavailable subsystems;
- prefer a simpler valid production treatment over stalling the live pipeline;
- measure latency at subsystem boundaries rather than relying on end-to-end guesses;
- preserve timestamps so latency and temporal alignment can be diagnosed;
- distinguish processing latency from capture, transport, buffering, rendering, and output latency.

These are architectural goals, not arbitrary numerical requirements. Establish real budgets from prototype measurements.

## 9. Creative intelligence vs live execution

Atlas should eventually support a distinction between:

**Creative/intelligent layer:** can reason about effects, sequences, style, production strategy, and preparation without being in the frame-critical loop.

**Live runtime:** consumes current state/events and executes bounded-latency decisions using prepared capabilities.

An LLM may help author rules, propose treatments, classify or reason about non-critical events, or prepare production plans. It should not be required to make every frame's decision for the live system.

## 10. Unreal relationship

Unreal remains the controlled production execution environment.

Live should communicate through an explicit interface rather than directly coupling perception code to Unreal implementation details.

The eventual flow may resemble:

```text
Live observations
      -> Atlas World State
      -> event/decision layer
      -> production command/intent
      -> Unreal adapter/runtime
      -> rendered/composited result
```

The exact transport is intentionally open. Evaluate the actual latency, reliability, and deployment requirements before choosing between in-process, IPC, sockets, shared memory, engine plugin interfaces, or another mechanism.

Do not introduce a transport abstraction with many unused implementations prematurely.

## 11. Safety and authority

The existing Atlas authority model remains applicable to high-level production decisions:

```text
AI/reasoning
    -> proposes
Atlas runtime
    -> validates / controls
Production environment
    -> executes
Independent observation/verification
    -> establishes result
```

Live may require different mechanics from transactional offline actions, but it must not use real-time performance as a reason to bypass validation, authorization, provenance, or safety boundaries.

For live systems, the equivalent of verification may be continuous state observation, health monitoring, output validation, or event confirmation rather than a single post-action check.

Hermes should design this carefully rather than force an offline receipt pattern onto every frame.

## 12. Failure philosophy

A live production system must continue operating when optional intelligence or external providers fail.

Plan for:

- missing/late observations;
- stale state;
- confidence degradation;
- tracking loss;
- provider disconnects;
- model inference overload;
- Unreal communication failure;
- dropped frames/messages;
- clock/timecode problems;
- malformed external data;
- resource exhaustion.

Failure handling should be explicit and observable. A subsystem should not silently invent authoritative state to conceal a failure.

Graceful degradation is preferred to pipeline-wide failure when safe.

## 13. Development methodology

Hermes should proceed incrementally:

1. inspect current repository and establish exact integration points;
2. document architectural findings;
3. build a minimal simulated World-State pipeline;
4. prove event/state update semantics;
5. measure performance and timing;
6. add one real external input where useful;
7. establish a controlled Unreal bridge;
8. integrate increasingly realistic event and production behavior;
9. profile and move genuine bottlenecks to C++/GPU/native implementations;
10. expand toward live soccer use cases only as each prerequisite is demonstrated.

Do not jump directly to camera hardware, full player tracking, or a large C++ framework without proving the preceding contracts.

## 14. Repository hygiene

Keep Live isolated from existing Blender and Unreal code except where an explicit interface is required.

Prefer a future structure along these lines, but adapt it to the repository after inspection rather than forcing it:

```text
live/
  runtime/
  world_state/
  perception/
  events/
  production/
  adapters/
  tests/

research/live/
  prototypes/
  benchmarks/
  experiments/
```

The exact module names are intentionally not mandatory.

Experimental work should be distinguishable from runtime code. Do not pollute production modules with one-off experiments.

## 15. Git and change discipline

Before modification:

```bash
git status
git branch --show-current
git log -5 --oneline
```

Do not reset, discard, overwrite, or clean unrelated local work.

The September 1 handoff records a local Unreal checkpoint `f658e16` and divergence from GitHub `main`. That local checkpoint must be preserved when the actual development machine is inspected. GitHub's current `main` history is not a substitute for the user's local working tree.

Prefer focused commits. Update documentation when an architectural or verified milestone changes.

## 16. Testing rules

Tests should demonstrate behavior, not merely code coverage.

For Live, eventually include:

- state schema/contract tests;
- timestamp/ordering tests;
- stale-data behavior;
- malformed-input rejection;
- provider adapter tests;
- event recognition tests;
- prediction tests;
- bounded-latency/benchmark tests;
- failure/degradation tests;
- Unreal bridge tests;
- integration tests using deterministic simulated streams.

Do not weaken existing Atlas tests to accommodate Live. Do not claim live readiness from simulated tests alone.

## 17. What Hermes is empowered to decide

Hermes should have substantial freedom over implementation details, including:

- module decomposition;
- concrete C++/Python boundaries;
- data structures;
- concurrency model;
- transport technology;
- provider adapter details;
- model/runtime choices;
- benchmark methodology;
- simulation strategy;
- test organization;
- optimization techniques.

The constraints in this document are architectural principles and integration boundaries, not a demand to implement a predetermined design.

If evidence shows that a proposed boundary is wrong, Hermes should document the finding and improve the design rather than preserve a bad abstraction for consistency.

## 18. What requires deliberate human/architectural review

Pause for review before:

- changing shared Atlas contracts in a breaking way;
- restructuring existing Blender/Unreal architecture solely for Live;
- introducing a major dependency with broad system implications;
- granting external software broader production authority;
- changing security/authorization semantics;
- making destructive Git operations;
- claiming production/live readiness;
- replacing an established proven path without a demonstrated capability gap.

## 19. First objective

The first objective is **not** "build live soccer."

The first objective is:

> Establish a minimal, testable, measurable Atlas Live runtime in which a deterministic stream of simulated observations becomes an Atlas-owned World-State, produces derived events, and can be consumed by a downstream production interface without coupling the model to any particular tracking vendor or requiring an LLM in the critical loop.

Once that foundation is sound, the next bottleneck should be selected from evidence.

## 20. Definition of progress

Progress should be reported in terms of demonstrated capability, not architectural ambition.

For each increment record:

- what capability was added;
- what existing contract it uses;
- what remains simulated;
- measured latency/throughput where applicable;
- tests executed;
- known limitations;
- whether the capability is experimental, implemented, locally proven, or production-ready.

Never label a subsystem "live-ready" simply because it works in a local simulation.
