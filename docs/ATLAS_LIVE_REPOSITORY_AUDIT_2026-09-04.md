# Atlas Live — Repository Audit

**Audit date:** September 4, 2026
**Repository:** `cantidokun/Atlas`
**Reviewed GitHub base:** `main` at `91e9efc3e9f4c9d6f37b651da95f2e3b363a540d`

## Executive finding

Atlas is ready to begin an **architectural/prototyping track for Live**, but the repository should not yet be treated as if it contains a real-time live-soccer runtime.

The existing codebase has strong control-plane architecture and a proven Unreal render boundary. It does not, from the reviewed documentation/tree evidence, establish a complete live perception → World-State → event → production → Unreal loop.

That is a favorable starting point: the Live system can be added as a bounded subsystem while reusing mature Atlas contracts where appropriate, rather than retrofitting real-time behavior into the existing offline task engine.

## 1. Existing strengths relevant to Live

### 1.1 Explicit authority boundaries

The repository's generic architecture contract establishes proposal → validation → evidence → authorization → execution → receipt → fresh verification. Qwen is explicitly not granted direct production authority.

This is valuable for Live because it gives Atlas a mature control philosophy. The implementation should adapt that philosophy to streaming runtime semantics rather than copy its transaction structure into every frame.

### 1.2 Independent verification and evidence

The existing system treats executor success as insufficient proof and requires authoritative evidence. This should influence Live health/state verification, but Live may need continuous verification rather than one post-action verification step.

### 1.3 Unreal production boundary

The current Unreal path has been locally exercised through UE 5.6 with deterministic render configuration, MRQ submission, dynamic job IDs, asynchronous inspection, output artifact discovery, artifact validation, evidence-bound receipts, and durable receipt persistence.

This gives Live a meaningful downstream production foundation. It does **not** prove that Unreal is ready for real-time state-driven cinematic augmentation.

### 1.4 Language-neutral evolution remains possible

The repository's development direction already recognizes Python-first/hybrid development and future C++ replacement of performance-sensitive components. Live should use that principle explicitly.

## 2. Existing limitations relevant to Live

### 2.1 No demonstrated canonical live World-State runtime

The current documented architecture is centered on task intent, plans, controlled actions, evidence, and verification. A continuously updated, temporal, multi-entity World-State is not established as a production runtime capability.

This should be built deliberately rather than inferred from existing task state.

### 2.2 Existing `live_*` files are not evidence of Live soccer runtime

The repository contains multiple files named `live_*`, including Qwen/Blender proof and continuation harnesses. Search results show these are focused on live proof of Blender operations such as parenting, object deletion, marker creation, renaming, rotation, evidence loops, and conditional action loops.

Do not place new real-time soccer runtime semantics into these historical proof scripts simply because they contain the word `live`.

### 2.3 Unreal job persistence is not runtime persistence

The current handoff explicitly states that the Unreal runtime render-job registry remains in-memory and that durable receipt persistence does not provide cross-process render-job recovery.

Live must preserve this distinction and should not build assumptions on a nonexistent persistent Unreal runtime registry.

### 2.4 No demonstrated live perception boundary

There is no established canonical interface in the reviewed documentation for ingesting real camera/tracking/pose/ball observations into Atlas World-State.

This is an opportunity for Live to establish a clean observation boundary without committing to a vendor prematurely.

### 2.5 No demonstrated end-to-end live latency budget

The current render proof establishes functional production transport, not a bounded end-to-end live latency budget. Live will need instrumentation across capture, perception, state, event, decision, transport, Unreal scheduling, rendering, and output.

## 3. Existing repository structure implications

The repository contains a substantial top-level Python implementation and controller architecture, documentation, Unreal integration, tests, and multiple live proof scripts. The exact current working-tree state on the development PC must be inspected before modification because the September 1 handoff records a local Unreal checkpoint that diverged from GitHub `main`.

Do not use GitHub's current tree as proof that the local development machine contains exactly the same code.

## 4. Recommended Live boundary

Prefer a dedicated subsystem such as:

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

This is a direction, not a mandatory directory layout. Hermes should adapt it to the actual repository after inspection.

The critical dependency direction should be approximately:

```text
external observations
        ↓
perception adapters
        ↓
Atlas World-State
        ↓
events / prediction
        ↓
production intent
        ↓
Unreal adapter
        ↓
Unreal
```

Avoid reverse dependencies from provider-specific code into the canonical state model.

## 5. Architectural opportunity

The most valuable new Atlas abstraction may be the separation between:

**Observation:** what an external source measured.

**World-State:** Atlas's reconciled representation of current reality.

**Event:** a derived temporal interpretation.

**Production Intent:** what Atlas wants the production environment to do.

**Execution:** how Unreal actually performs it.

This gives Atlas a stable architecture even as tracking technologies, ML models, transports, and Unreal implementations change.

## 6. Recommended first proof

Do not begin with a full computer-vision system.

First prove:

```text
simulated observations
      ↓
World-State
      ↓
deterministic event
      ↓
production intent
      ↓
downstream consumer
```

Measure it.

Then replace one simulated boundary at a time with real infrastructure.

## 7. Important non-goals for the first Live increment

Do not initially attempt to:

- build a complete soccer tracking platform;
- select a permanent commercial tracking vendor;
- make an LLM responsible for frame-by-frame decisions;
- rewrite the entire Atlas runtime in C++;
- replace the proven Unreal render path without a capability gap;
- redesign Blender architecture for Live;
- create a universal plugin ecosystem;
- claim production readiness.

## 8. Current recommendation to Hermes

Hermes should treat this repository as a mature control-plane foundation with an incomplete Live data-plane/runtime layer.

Build the missing runtime incrementally.

Reuse established contracts where they fit.

Do not confuse conceptual consistency with identical implementation mechanics.

The best architecture is the one that allows the Live subsystem to grow from simulation to real inputs and eventually real-time production without forcing a wholesale rewrite of Atlas or turning every subsystem into a real-time component.
