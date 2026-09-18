# Unreal State Extraction Fidelity v1 — Design Gate

**Status:** DESIGN — IMPLEMENTATION NOT AUTHORIZED  
**Branch:** `feat/unreal-state-extraction-fidelity-v1-design`  
**Parent:** Atlas `main` at the September 18, 2026 checkpoint  
**Relationship to M12.5:** independent and intentionally does not modify M12.5

## 1. Purpose

Atlas already has a useful Unreal read surface, including world, actor, material,
Niagara, Blueprint, Sequencer, and render-state inspection. Those probes are
execution-boundary operations, not yet a canonical extraction contract.

This milestone establishes a bounded, deterministic, read-only Unreal state
producer that can become the authoritative source for future target-state
verification and cross-engine digital-twin reasoning.

The milestone is analogous in architectural role to Blender Extraction Fidelity
v1, but it is Unreal-specific and does not attempt cross-engine equivalence.

## 2. Authority model

The authority chain is:

```text
Real Unreal editor state
    ↓
C++ read-only extraction producer
    ↓
versioned Unreal extraction payload
    ↓
Python contract validation / canonicalization
    ↓
deterministic digest
    ↓
future consumers
```

The extractor MUST NOT:

- authorize a task;
- execute writes;
- submit or retry a render;
- issue receipts;
- alter recovery state;
- save packages/assets;
- mark packages dirty;
- mutate Actors, Sequences, Materials, Niagara systems, Blueprints, or world state.

M12.5 is not changed by this milestone.

## 3. v1 extraction scope

### World

Extract:

- authoritative selected editor-world identity;
- world name/path;
- world type;
- deterministic world-selection provenance;
- declared engine/version metadata required for interpretation.

The current "first world context" behavior is insufficient. v1 must define a
deterministic editor-world selection rule and fail closed when multiple eligible
worlds remain ambiguous.

### Actor representation

For explicitly selected entity IDs, extract:

- entity ID;
- actor name;
- class;
- level/package identity where available;
- parent identity when unambiguous;
- visibility state;
- world-space location;
- world-space rotation;
- world-space scale;
- deterministic component/source identity where required by the contract.

Entity lookup remains explicit. v1 does not enumerate arbitrary actors for a semantic
request and does not infer identity from actor names.

### Material representation

Move beyond the current tagged "variant name" probe.

v1 should extract, at minimum:

- ordered material-slot identity;
- resolved material asset identity/path where available;
- explicit representation of missing/unresolved material references;
- deterministic omission/failure semantics.

Temporary Atlas variant tags are not sufficient canonical material state.

### Sequencer representation

For an explicitly identified sequence target, extract:

- sequence asset identity/path;
- deterministic owning actor identity;
- playback range;
- frame-rate representation required to interpret frame numbers;
- deterministic handling of multiple candidate sequence actors.

The current "first valid LevelSequenceActor" behavior is not sufficient and must
be replaced by explicit target binding or deterministic ambiguity rejection.

### Render state

Render-job recovery/evidence remains outside this milestone. Existing M4–M10
render configuration and evidence contracts are frozen. v1 may expose only the
minimal render/config facts needed to preserve architectural consistency, but it
must not duplicate `verify_render_job_evidence`.

## 4. Numeric and representation policy

The contract must distinguish:

- raw Unreal source representation;
- canonical extraction representation;
- any future semantic derived view.

For transforms, v1 must use an explicit canonical rotation representation rather
than relying on human-readable FRotator strings. The contract must specify axis
order, handedness/coordinate-frame declaration, units, and numeric precision.

Unreal world-space translation remains in Unreal's declared source units; no
meters conversion is performed in this milestone.

No normalization, interpolation, smoothing, tolerance-based comparison, or
quaternion-equivalence inference is performed by the producer.

## 5. Identity and ordering

Determinism requirements:

- entity output is ordered by canonical entity ID;
- no pointer addresses, memory addresses, object iteration order, or transient
  hash-map order may participate in payload identity;
- repeated references to the same source object are deduplicated by source
  identity;
- ambiguous identity resolution fails closed;
- all collections with meaningful order preserve explicitly defined source order;
- all unordered collections are canonically sorted under a documented key.

The entity tag convention `atlas_entity:<id>` may remain the current lookup
mechanism for v1, but the design must treat it as an explicit source identity
binding rather than silently promoting actor names to identity.

## 6. Payload and digest

The payload is versioned and language-neutral.

Normative canonical serialization is:

```text
JSON
  sort_keys = true
  separators = (",", ":")
  ensure_ascii = true
  allow_nan = false
  UTF-8 bytes
  SHA-256
```

No engine serializer output is itself authoritative canonical bytes.

The extraction digest commits to the bounded extraction payload only. Execution,
authorization, receipt, recovery, transport request IDs, timestamps, and transient
engine-session metadata are excluded unless explicitly declared extraction facts.

## 7. Failure semantics

The producer fails closed for:

- no eligible world;
- ambiguous world selection;
- missing requested entity;
- duplicate/conflicting entity identity;
- ambiguous sequence target;
- unresolved required asset identity;
- non-finite numeric values;
- unsupported source representation;
- malformed material/sequence state;
- any attempt to obtain data through a write/mutation path.

Partial payloads MUST NOT be presented as complete authoritative extraction.

## 8. Python/C++ interoperability

The C++ producer is responsible for obtaining source facts from Unreal's authoritative
runtime/editor APIs.

Python remains responsible for:

- payload schema validation;
- canonicalization checks;
- digest calculation;
- fixture/audit orchestration;
- deterministic and hostile-input tests where practical.

The contract is deliberately JSON/value based so a future native C++ implementation
or alternate producer can replace Python-side interpretation without redesigning
the higher semantic layers.

## 9. Live evidence

The milestone requires a disposable Unreal 5.6 live fixture, not a persistent
project mutation.

The live gate must prove:

- world-selection determinism;
- explicit entity identity binding;
- actor transform fidelity;
- actor visibility/parent identity;
- material-slot fidelity;
- sequencer identity/range fidelity;
- repeated extraction stability;
- no package dirtying;
- no asset/world mutation;
- digest stability.

The frozen existing M4–M10 render/recovery fixtures are not mutated by this gate.

## 10. Non-goals

This milestone does NOT implement:

- M12.5 semantic verification;
- semantic event abstraction;
- temporal observation/state delta;
- cross-engine equivalence;
- render-job recovery;
- artifact/receipt issuance;
- generic Unreal scene reconstruction;
- geometry extraction for arbitrary meshes;
- Nanite/Lumen internals;
- VFX simulation state;
- camera/lens physical calibration beyond data already exposed by explicit target
  inspection;
- persistence or a second durable state authority.

## 11. Acceptance gates

Before implementation can merge:

1. design review is independently CLEAR;
2. C++ extraction producer is read-only by code inspection;
3. Python contract tests prove exact schema/failure semantics;
4. deterministic A/B/C construction-order and process-run checks pass;
5. Python 3.9/3.11 parity passes where applicable;
6. Unreal 5.6 live gate passes against a disposable fixture;
7. repeated extraction yields byte-identical payload and digest;
8. no M4–M10 behavior changes;
9. no M12.5 changes;
10. no workflow/action-runner tests are required unless separately authorized.

## 12. Next implementation shape

The likely implementation split is:

```text
Unreal C++
  └─ bounded read-only extractor / typed payload

Python
  ├─ extraction contract + schema validation
  ├─ canonicalization + SHA-256
  ├─ hostile/determinism tests
  └─ live fixture gate
```

Existing `inspect_target_actors`, `inspect_material_state`, and
`inspect_sequencer_state` should be treated as source probes to reuse or refine,
not as the final extraction contract.

## 13. Architectural intent

The major objective is to make Unreal state **factual, bounded, deterministic, and
portable across Python/C++ boundaries** before semantic layers begin interpreting it.

This work is deliberately independent of M12.5. It improves the substrate that a
future verifier can consume without changing the existing verification authority.
