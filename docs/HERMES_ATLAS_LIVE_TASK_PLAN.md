# Hermes — Atlas Live Task Plan

## Purpose

This is the initial work queue for Hermes-led development of Atlas Live. It is intentionally staged so that Hermes can make implementation decisions from evidence rather than being forced into a large predetermined architecture.

The task sequence is a recommended dependency order, not a requirement to complete every item exactly as written. Hermes may split, merge, reorder, or replace tasks when repository inspection or measurements justify doing so. Significant deviations should be documented.

---

# Phase 0 — Repository reconnaissance

## Task 0.1 — Inspect the actual checkout

Before modifying code:

- inspect branch and working-tree state;
- inspect recent history;
- inspect existing Atlas architecture and tests;
- identify existing shared contracts that Live should reuse;
- identify existing files whose names contain `live` and determine whether they are live-runtime work or historical Blender test/harness work;
- inspect Unreal integration points;
- inspect current Python/C++ infrastructure and build configuration;
- identify the actual local state versus GitHub history.

Do not assume every file named `live_*` belongs to the future live runtime. The current repository contains several "live" Blender proof/harness scripts; these are not evidence that a real-time soccer runtime already exists.

Deliverable: a short architecture/audit note committed under `docs/` if one does not already exist.

## Task 0.2 — Establish the Live boundary

Determine the smallest clean repository boundary for Live. Prefer a dedicated Live namespace/directory over scattering new runtime files across the repository.

Do not reorganize existing Blender or Unreal code merely to make the new directory aesthetically consistent.

Deliverable: proposed module map and dependency direction.

---

# Phase 1 — World-State foundation

## Task 1.1 — Define observations

Design a minimal observation representation capable of accepting deterministic simulated input.

At minimum investigate:

- entity/source identity;
- timestamp;
- coordinate frame/reference;
- measurement/state payload;
- confidence where meaningful;
- provenance.

Keep the first representation small.

## Task 1.2 — Define the first World-State

Create an Atlas-owned World-State representation for the minimum useful scenario.

Start with only the entities required to demonstrate the pipeline, likely:

- field/world reference;
- one or more players;
- ball;
- timestamps;
- derived event/state information.

Do not attempt to model every conceivable soccer or broadcast entity in version one.

## Task 1.3 — State update semantics

Prove deterministic handling of:

- ordered observations;
- late observations;
- stale observations;
- duplicate observations;
- missing observations;
- confidence changes.

The correct behavior should be explicit and testable.

## Task 1.4 — Contract boundary

Ensure downstream modules consume Atlas World-State rather than provider-specific payloads.

A provider adapter may know about vendor-specific formats. The event engine and production layer should not.

---

# Phase 2 — Temporal/event engine

## Task 2.1 — Temporal state

Add only the temporal history needed to derive meaningful state transitions.

Avoid building an unbounded event store or generalized time-series database before a concrete requirement exists.

## Task 2.2 — First event

Implement one deterministic event from simulated state. A good candidate is a simple player/ball interaction or shot-related state transition.

The event should include sufficient context for downstream use:

- event type;
- event time;
- involved entity IDs;
- location where meaningful;
- confidence/quality;
- provenance/derivation information.

## Task 2.3 — Prediction prototype

Prototype prediction separately from observed truth.

A prediction must be identifiable as a prediction and must never silently become authoritative state.

Measure whether prediction actually provides useful lead time before expanding the system.

---

# Phase 3 — Performance and runtime architecture

## Task 3.1 — Build a deterministic stream benchmark

Create a repeatable simulated stream and measure:

- observation ingestion rate;
- World-State update time;
- event calculation time;
- queue depth/backlog;
- end-to-end state latency;
- latency variance;
- memory behavior.

Use realistic stream rates rather than arbitrary microbenchmarks where possible.

## Task 3.2 — Identify native bottlenecks

Only after measurements, determine which components genuinely need C++ or GPU acceleration.

Candidates may include:

- high-frequency state processing;
- spatial calculations;
- temporal filtering;
- concurrency;
- perception integrations;
- GPU-facing paths.

Do not convert the entire Live subsystem to C++ simply because the target is real-time.

## Task 3.3 — Stable boundary

Where native code is introduced, establish a clean language-neutral boundary so Python and C++ implementations can coexist.

The boundary should be designed around data/contracts rather than Python object internals.

---

# Phase 4 — Perception adapter

## Task 4.1 — Simulated provider adapter

Create a provider adapter that behaves like an external tracking system and emits observations into Atlas.

The goal is to prove the integration boundary before selecting a real vendor.

## Task 4.2 — Provider failure behavior

Simulate:

- disconnect;
- delayed messages;
- malformed messages;
- stale data;
- confidence collapse;
- dropped data.

Verify that the World-State remains explicit about uncertainty and does not silently fabricate authoritative observations.

## Task 4.3 — Evaluate real provider categories

Only after the adapter contract is useful, investigate actual tracking/perception technologies and select candidates based on:

- latency;
- accuracy;
- coordinate output;
- synchronization;
- API/accessibility;
- hardware requirements;
- licensing;
- deployment constraints.

Do not hard-code a vendor into the architecture solely because it is the first available SDK.

---

# Phase 5 — Production decision interface

## Task 5.1 — Production intent

Define the smallest production intent needed to turn an event into a controlled Unreal-side action.

Separate:

```text
what happened
        |
        v
what Atlas wants produced
        |
        v
how Unreal implements it
```

The production intent should not expose unnecessary Unreal internals.

## Task 5.2 — Prepared effect selection

Prototype selection/parameterization of a prepared production capability.

The live runtime should not require synchronous generation of complex visual assets at event time.

## Task 5.3 — Intelligence boundary

Determine which decisions are deterministic runtime logic and which benefit from higher-level AI/LLM reasoning.

Do not place an LLM in the frame-critical path merely because it can make a sophisticated decision.

If an AI component is used, define what happens when it is slow, unavailable, or uncertain.

---

# Phase 6 — Unreal live bridge

## Task 6.1 — Transport experiment

Evaluate the smallest viable mechanism for delivering production intents/state to Unreal.

Candidates may include:

- in-process integration;
- Unreal plugin/module;
- IPC;
- local sockets;
- shared memory;
- another appropriate mechanism.

Choose from measured requirements rather than preference.

## Task 6.2 — Latency measurement

Measure:

```text
Atlas decision
 -> transport
 -> Unreal receipt
 -> Unreal scheduling
 -> effect start
```

Do not infer transport performance from a successful connection alone.

## Task 6.3 — Failure behavior

Test unavailable Unreal, delayed acknowledgments, malformed commands, and command backlog.

The live runtime must not silently accumulate stale production commands.

---

# Phase 7 — First simulated end-to-end live scenario

Build one deterministic scenario:

```text
simulated observations
      -> World-State
      -> event
      -> production intent
      -> Unreal
      -> controlled effect
```

The purpose is to prove the architecture, not visual sophistication.

Record:

- state latency;
- event latency;
- production-command latency;
- Unreal latency;
- total measured path;
- variance;
- failure behavior.

This is the first meaningful Live milestone.

---

# Phase 8 — Real input

Only after the simulated pipeline is stable, introduce one real external input source.

Prefer one variable at a time. For example:

```text
real tracking input
      +
simulated remainder of world
```

Then progressively replace simulation with real inputs.

Do not introduce every camera/tracking/pose/segmentation dependency simultaneously.

---

# Phase 9 — Real-time cinematic augmentation

Once state/event/production interfaces are stable, begin testing Atlas's cinematic repertoire in real-time.

Potential treatments include:

- impact frames;
- smear frames;
- chromatic aberration;
- cinematic bleed;
- match-cut transformations;
- spatial overlays;
- digital-twin interaction;
- environment-driven effects;
- liquid/fluid-like environment behavior;
- other prepared VFX treatments justified by production goals.

The visual repertoire should remain modular. A visual effect should not redefine the underlying World-State architecture.

---

# Architectural review gates

Before progressing materially, verify:

### Gate A — State

- World-State is Atlas-owned.
- Provider payloads do not leak into downstream contracts.
- Timestamps and freshness semantics are explicit.

### Gate B — Runtime

- Critical processing is measurable.
- Slow intelligence does not block the core runtime.
- Backlog behavior is bounded and observable.

### Gate C — Production

- Production intent is separated from Unreal implementation.
- Prepared capabilities can be selected/parameterized.
- Unreal remains a controlled execution environment.

### Gate D — Failure

- Provider failures are explicit.
- Stale state is not silently treated as current.
- Optional intelligence can degrade safely.
- Unreal communication failures are observable.

### Gate E — Evidence

- Live claims are backed by reproducible tests or real measurements.
- Simulated success is not described as real-world readiness.
- Performance claims include test conditions.

---

# Definition of done for the initial Hermes assignment

The initial assignment is complete when Hermes has:

1. inspected the actual repository;
2. established the Live module boundary;
3. documented the architecture decision;
4. implemented a minimal deterministic simulated observation stream;
5. created an Atlas-owned World-State;
6. derived at least one deterministic event;
7. exposed a downstream production interface without direct provider coupling;
8. added focused tests;
9. measured the basic runtime path;
10. documented what remains unknown.

Do not proceed directly from this assignment to a large real-time framework unless the repository inspection demonstrates that the framework already exists and should be extended.

---

# Hermes operating instruction

Use this plan as a map, not a cage.

When an implementation choice is uncertain:

1. inspect existing code;
2. identify the actual constraint;
3. prototype the smallest useful solution;
4. measure it;
5. choose the simplest architecture that preserves future extensibility;
6. document important tradeoffs;
7. continue.

If the repository already contains a suitable abstraction, reuse it. If an existing abstraction is fundamentally mismatched to Live's timing model, do not force it into the critical path merely for consistency; document the divergence and preserve a clean interface between the systems.
