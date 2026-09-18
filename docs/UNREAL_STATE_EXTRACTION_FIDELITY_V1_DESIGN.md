# Unreal State Extraction Fidelity v1 — Design Gate

**Status:** DESIGN — IMPLEMENTATION NOT AUTHORIZED  
**Design revision:** Red-team hardening 1  
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
versioned Unreal extraction value tree
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

### 3.1 Authoritative editor world selection

The v1 authority is the Unreal Editor world only.

The producer MUST:

1. require an editor build with `GEditor` available;
2. obtain the world exclusively from `GEditor->GetEditorWorldContext().World()`;
3. reject a null or invalid world;
4. reject any world whose `WorldType` is not the persistent editor-world type;
5. NOT fall back to `GEngine->GetWorldContexts()` for world selection.

The payload records the selection provenance as the literal contract value
`g_editor_editor_world_context`.

PIE, game, preview, thumbnail, inactive, or otherwise non-editor world contexts are
not eligible v1 authorities. The point is to remove selection dependence on
`GetWorldContexts()` iteration order.

World identity records:

- world object path;
- world package path;
- world name;
- world type;
- engine version;
- selection provenance.

### 3.2 Actor representation

For explicitly selected entity IDs, extract:

- entity ID;
- actor name;
- actor class;
- actor level package identity;
- parent binding state;
- editor visibility state;
- world-space transform;
- deterministic source identity needed for material extraction.

Entity lookup is explicit. v1 does not enumerate arbitrary actors for a semantic
request and does not infer identity from actor names.

#### Entity identity rule

The source binding convention remains:

`atlas_entity:<entity_id>`

For each requested entity ID, the producer scans the authoritative editor world and
collects all actors carrying the exact tag.

- zero matches => `ERR_ENTITY_NOT_FOUND`;
- one match => accepted;
- more than one match => `ERR_ENTITY_ID_AMBIGUOUS`;
- actor names never resolve identity;
- the same requested entity ID appearing twice in one extraction request is rejected;
- partial actor extraction is never returned as an authoritative success.

This changes the current first-match behavior into explicit ambiguity rejection.

#### Parent binding

Parent state is based only on the actor's direct attach-parent actor.

The canonical form is:

```text
parent:
  binding: "bound" | "unbound"
  entity_id: <string|null>
```

- no attach-parent actor => `unbound/null`;
- attach-parent actor with exactly one unambiguous Atlas entity binding =>
  `bound/<entity_id>`;
- attach-parent actor with no Atlas entity binding => `unbound/null`;
- attach-parent actor with duplicate Atlas entity binding => fail closed.

No parent identity is inferred from actor names.

#### Editor visibility

v1 records actor-level editor visibility only:

- `hidden_in_editor` from the authoritative editor-hidden state;
- `temporarily_hidden_in_editor` from the authoritative temporary editor-hidden state.

These flags are source facts. The extractor does not infer renderer visibility,
component visibility, lighting visibility, or semantic "visible to camera" state.

### 3.3 Transform representation

World-space transform is:

- translation in Unreal source units (centimeters);
- rotation as exact actor quaternion;
- scale as exact actor scale.

The canonical rotation representation is:

```text
coordinate_frame:
  handedness: "left"
  up_axis: "Z"
  positive_x: "forward"
  positive_y: "right"
  positive_z: "up"

rotation:
  representation: "quaternion"
  component_order: "x,y,z,w"
  unit: "unitless"
  source: "actor_world_quaternion"
```

No conversion to another engine's basis occurs in v1.

No quaternion normalization, shortest-path selection, interpolation, smoothing,
tolerance, or equivalence comparison occurs in the producer.

### 3.4 Material representation

Material extraction is per explicit actor and is component/slot based.

For every material-bearing primitive component of the selected actor, v1 records:

- deterministic component source identity;
- component class;
- component object path;
- slot index;
- slot state;
- resolved material asset path when the slot resolves to a valid asset.

The canonical material slot record is:

```json
{
  "component_object_path": "<Unreal object path>",
  "component_class": "<class name>",
  "slot_index": 0,
  "state": "resolved" | "missing",
  "material_asset_path": "<asset object path or null>"
}
```

A null material slot is `missing/null`.

A non-null slot whose required asset identity cannot be resolved is a hard extraction
failure, not an omission.

Material slot records are sorted by:

1. component object path, ordinal lexicographic order;
2. slot index, ascending.

Actor-level Atlas material-variant tags are not canonical material state.

No material parameter values, dynamic-instance runtime values, shader permutation
state, Nanite material internals, or render-pass state are extracted by v1.

### 3.5 Sequencer representation

A Sequencer extraction request targets an explicit entity ID whose bound actor MUST
resolve to exactly one `ALevelSequenceActor`.

The producer MUST NOT scan for the "first valid" sequence actor.

The sequence record contains:

- sequence-actor entity ID;
- sequence actor object path;
- sequence asset object path;
- playback range;
- tick resolution;
- display rate.

The playback range is stored in the sequence's MovieScene tick-resolution frame
space and preserves bound semantics:

```json
{
  "lower_frame": -100,
  "lower_bound": "inclusive",
  "upper_frame": 2400,
  "upper_bound": "exclusive"
}
```

Open bounds are not accepted for v1 playback-range extraction.

The rate representation is exact rational form:

```json
{
  "numerator": 24000,
  "denominator": 1
}
```

Both `tick_resolution` and `display_rate` are retained because MovieScene frame
numbers are stored in tick-resolution space while display rate is the user-facing
sequence rate.

Multiple candidate LevelSequenceActors for the requested entity, an unresolved
sequence asset, or malformed range/rate state fails closed.

The extractor does not infer sequence identity from sequence display names, actor
names, or "first valid" iteration order.

## 4. Exact numeric policy

The contract MUST distinguish:

- raw Unreal source representation;
- canonical extraction representation;
- any future semantic derived view.

All Unreal transform scalar values in v1 originate as `float32` source facts.
To make those facts byte-stable across Python/C++ implementations, canonical
transform scalar values are represented as lowercase eight-hex-digit IEEE-754
binary32 bit patterns encoded as JSON strings.

Example:

```json
"x": "3f800000"
```

This is an exact source-fidelity representation, not a rounded comparison value.

Consequences:

- no decimal reformatting can change the digest;
- no float32-to-float64 promotion changes the canonical value;
- non-finite float values fail closed before encoding;
- future semantic consumers may decode the bit pattern to numeric values;
- the extractor never performs tolerance-based comparison.

Frame numbers, schema versions, slot indices, and frame-rate numerators/denominators
are exact JSON integers within their declared source bounds.

Strings remain value strings and are not normalized, trimmed, case-folded, or Unicode
normalized by the extraction layer.

## 5. Versioned payload shape

The v1 value tree is operation-scoped and has this top-level shape:

```json
{
  "schema_version": 1,
  "extraction_kind": "actor_state" | "sequencer_state",
  "world": { ... },
  "actors": [ ... ],
  "sequences": [ ... ]
}
```

Exactly one extraction kind is present for each request:

- `actor_state` uses `actors` and MAY include material records nested under each
  actor;
- `sequencer_state` uses exactly one sequence target in `sequences`.

Unused top-level collections are empty arrays, not omitted.

World facts are always bound into the extraction payload so the same actor state
cannot silently be interpreted as belonging to a different editor world.

Actor output is ordered by canonical `entity_id`, not request order.

The complete actor record is:

```text
entity_id
actor_name
actor_class
level_package_path
parent
editor_visibility
transform
materials
source_identity
```

The exact field spelling, nullability, and enum values defined above are normative;
implementation MUST NOT invent alternate representations without a design revision.

## 6. Identity and ordering

Determinism requirements:

- entity output is ordered by canonical entity ID;
- no pointer addresses, memory addresses, object iteration order, or transient
  hash-map order may participate in payload identity;
- duplicate Atlas entity bindings are rejected;
- repeated references to the same source object are deduplicated by source identity;
- all collections with meaningful source order preserve explicitly defined source
  order;
- all unordered collections are sorted under a documented canonical key;
- request-order differences MUST produce the same canonical payload for the same
  target set;
- different actor construction order MUST NOT alter canonical ordering.

The `atlas_entity:<id>` tag is an explicit source identity binding only.

## 7. Payload and digest

The payload is versioned and language-neutral.

Canonicalization is performed over the validated value tree, not over Unreal's
native JSON serializer output.

v1 canonical bytes use JSON Canonicalization Scheme (RFC 8785), UTF-8 encoded.

Because all Unreal source floats are represented as exact binary32 hex strings,
the canonical payload contains no implementation-dependent floating-point JSON
lexemes.

The SHA-256 digest commits to the bounded extraction payload only.

Execution, authorization, receipt, recovery, transport request IDs, timestamps,
and transient engine-session metadata are excluded unless explicitly declared
extraction facts.

## 8. Failure semantics

The producer fails closed for:

- no eligible editor world;
- non-editor world selection;
- missing requested entity;
- duplicate/conflicting entity identity;
- ambiguous parent identity;
- wrong actor type for explicit Sequencer target;
- ambiguous sequence target;
- unresolved required material or sequence asset identity;
- non-finite numeric values;
- unsupported source representation;
- malformed material/sequence state;
- duplicate request entity IDs;
- any attempt to obtain data through a write/mutation path.

Partial payloads MUST NOT be presented as complete authoritative extraction.

## 9. Python/C++ interoperability

The C++ producer is responsible for obtaining authoritative source facts from
Unreal APIs and constructing the typed v1 value tree.

Python remains responsible for:

- payload schema validation;
- canonicalization;
- RFC 8785 byte encoding;
- SHA-256 digest calculation;
- fixture/audit orchestration;
- deterministic and hostile-input tests where practical.

The contract is value-based and language-neutral. A future native C++ consumer or
alternate producer can replace the Python orchestration without changing the
semantic state shape.

The C++ transport serializer is never itself the digest authority.

## 10. Live evidence

The milestone requires a disposable Unreal 5.6 live fixture, not a persistent
project mutation.

The live gate must prove:

- editor-world selection is deterministic and never falls back to context iteration;
- unique entity binding succeeds;
- duplicate entity binding fails closed;
- actor transform fidelity is exact at the canonical float32-bit level;
- actor parent and editor-visibility facts are deterministic;
- material-slot records are deterministic across component construction order;
- missing and unresolved material states follow the contract;
- explicit LevelSequenceActor binding succeeds;
- ambiguous sequence binding fails closed;
- playback range bounds and tick/display rates are exact;
- repeated extraction yields identical value trees;
- repeated extraction yields identical canonical bytes and digest;
- no package dirtying occurs;
- no asset/world mutation occurs.

The frozen existing M4–M10 render/recovery fixtures are not mutated by this gate.

## 11. Non-goals

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
- persistence or a second durable state authority;
- material parameter evaluation;
- runtime shader state extraction.

## 12. Acceptance gates

Before implementation can merge:

1. design review is independently CLEAR;
2. C++ extraction producer is read-only by code inspection;
3. Python contract tests prove exact schema/failure semantics;
4. deterministic A/B/C construction-order and process-run checks pass;
5. Python 3.9/3.11 parity passes where applicable;
6. Unreal 5.6 live gate passes against a disposable fixture;
7. repeated extraction yields byte-identical payload and digest;
8. duplicate identity fixtures fail closed;
9. no M4–M10 behavior changes;
10. no M12.5 changes;
11. no workflow/action-runner tests are required unless separately authorized.

## 13. Implementation shape after design clearance

Only after an independent design review returns CLEAR:

```text
Unreal C++
  └─ bounded read-only extractor / typed v1 value tree

Python
  ├─ extraction contract + schema validation
  ├─ RFC 8785 canonicalization + SHA-256
  ├─ hostile/determinism tests
  └─ live Unreal 5.6 fixture gate
```

Existing `inspect_target_actors`, `inspect_material_state`, and
`inspect_sequencer_state` remain source probes to reuse or refine; they are not
the final extraction contract.

## 14. Independent red-team result

The original design had five material ambiguities:

1. editor-world selection still admitted iteration-order dependence;
2. canonical JSON numeric bytes were not actually cross-language deterministic;
3. duplicate entity tags could still resolve by first match;
4. material component/slot identity and unresolved-state semantics were incomplete;
5. Sequencer target identity, playback-bound semantics, and rate representation
   were underspecified.

This revision resolves those contract gaps at the design level.

Implementation remains unauthorized until an independent review confirms that these
rules are internally consistent, implementable in UE 5.6, and compatible with the
frozen M4–M10 authority boundaries.

## 15. Architectural intent

The major objective is to make Unreal state factual, bounded, deterministic, and
portable across Python/C++ boundaries before semantic layers begin interpreting it.

This work is deliberately independent of M12.5. It improves the substrate that a
future verifier can consume without changing the existing verification authority.
