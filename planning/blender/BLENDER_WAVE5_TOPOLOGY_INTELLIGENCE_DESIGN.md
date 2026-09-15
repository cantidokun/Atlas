# Atlas Blender Wave 5 — Topology Intelligence Design Gate

**Status:** DESIGN / NOT IMPLEMENTED
**Branch:** `feat/blender-wave5-topology-intelligence`
**Baseline:** Wave 4 parent-reference completion

## 1. Objective

Wave 5 establishes deterministic, engine-independent topology intelligence for Atlas Blender meshes. It is an **analysis-only** capability: Wave 5 does not mutate meshes, authorize repairs, remove geometry, remesh, decimate, fill holes, or alter topology.

The purpose is to give Atlas a trustworthy structural description of mesh topology before later correction/optimization capabilities are introduced.

## 2. Authority boundary

```text
Blender / upstream asset
        |
        v
thin extraction adapter
        |
        v
canonical MeshModel
        |
        v
Wave 5 topology analyzer
        |
        v
canonical topology report
        |
        +--> Atlas planning / model reasoning (advisory)
        |
        +--> future correction planners (proposal only)
```

The topology analyzer is never an execution or authorization authority. It must not call `bpy`, invoke operators, save files, or modify a `MeshModel`.

## 3. Relationship to existing health checks

Existing checks remain authoritative for their existing meanings:

- `MESH_INVALID_INDEX`
- `MESH_DUPLICATE_VERTEX`
- `MESH_DUPLICATE_FACE`
- `MESH_DEGENERATE_FACE`
- `MESH_NON_MANIFOLD_EDGE`
- `MESH_WINDING_INCONSISTENT`
- `MESH_NORMAL_INCONSISTENT`
- `MESH_SCALE_OUT_OF_RANGE`

Wave 5 must not silently redefine these findings.

In particular, the current core deliberately treats an edge with incidence 1 as a boundary/open-mesh property rather than automatically calling it non-manifold. Wave 5 therefore reports boundary topology as a **structural metric**, not as an error.

## 4. Topology model

For a canonical `MeshModel`, Wave 5 derives an indexed topology graph from face vertex indices.

### Vertex metrics

- `vertex_count`
- `referenced_vertex_count`
- `isolated_vertex_count`
- `duplicate_index_reference_count` where applicable to the existing canonical face grammar

### Edge metrics

For each undirected edge `(min(vertex_a, vertex_b), max(vertex_a, vertex_b))`:

- incident face count / valence
- boundary edge when incidence is exactly 1
- manifold edge when incidence is exactly 2
- non-manifold edge when incidence is greater than 2

Aggregate metrics:

- `edge_count`
- `boundary_edge_count`
- `manifold_edge_count`
- `non_manifold_edge_count`
- maximum edge valence
- deterministic valence histogram

### Face metrics

- `face_count`
- triangle count
- quad count
- n-gon count (`vertex_count >= 5`)
- minimum face cardinality
- maximum face cardinality
- deterministic face-cardinality histogram

Existing degenerate/invalid-face checks remain separate. Wave 5 does not infer a new defect merely from a large n-gon or mixed polygon cardinality.

### Connectivity metrics

Using the face-edge adjacency graph:

- connected component count
- deterministic component membership
- per-component vertex count
- per-component edge count
- per-component face count
- per-component boundary-edge count
- per-component non-manifold-edge count

A component is connected when its faces share at least one undirected edge. Vertices touching only at a point do not merge two face components.

### Loose geometry

Wave 5 identifies:

- isolated vertices: vertices not referenced by any face
- loose edges: not directly representable by the current canonical `MeshModel` because `MeshModel` stores faces rather than independent edge primitives

Therefore **loose-edge detection is explicitly deferred** until the canonical model can represent or truthfully extract standalone Blender edges. Wave 5 must not fabricate edges from insufficient source information.

## 5. Determinism

The topology report must be deterministic for identical canonical input.

Requirements:

- undirected edges are canonicalized as `(min(a,b), max(a,b))`;
- component traversal starts from the lowest vertex/face index available;
- component identifiers are deterministic and derived from canonical minimum indices, not process/object identity;
- histogram keys are sorted numerically in serialized output;
- collections are emitted in stable index/order form;
- no hash-randomized iteration order may affect output;
- no floating-point tolerance is used for purely indexed topology metrics.

## 6. Invalid-input behavior

Wave 5 consumes the already validated canonical `MeshModel` contract. It must still fail closed if a caller bypasses normal construction and supplies an invalid object.

It must never:

- silently clamp an invalid vertex index;
- invent missing vertices;
- skip malformed faces and continue with a partial topology graph;
- reinterpret invalid indices as negative Python indexes;
- coerce arbitrary objects into topology primitives.

Invalid canonical input should raise the existing declared contract error rather than producing a misleading topology report.

## 7. Complexity target

Let `V` be vertex count, `F` face count, and `E` the number of unique undirected edges.

Target complexity:

- edge construction: `O(sum(face cardinality))`, effectively `O(E + face-corners)`;
- referenced/isolated vertices: `O(V + face-corners)`;
- connectivity: `O(F + E)` using adjacency traversal;
- aggregate histograms: `O(V + E + F)`;
- memory: `O(V + E + F)`.

No quadratic all-pairs vertex/face/component comparison is permitted.

## 8. Report shape

Wave 5 should expose an immutable, canonical report rather than returning an unstructured dictionary from the core.

Conceptual shape:

```text
TopologyReport
  schema_version
  mesh_id
  vertex_count
  referenced_vertex_count
  isolated_vertex_count
  edge_count
  boundary_edge_count
  manifold_edge_count
  non_manifold_edge_count
  max_edge_valence
  edge_valence_histogram
  face_count
  triangle_count
  quad_count
  ngon_count
  face_cardinality_histogram
  connected_component_count
  components[]
```

Each component is immutable and contains deterministic counts and its canonical member indices.

The exact serialized grammar must be finalized before implementation and tested as a closed schema. Unknown fields must fail closed on parsing.

## 9. Finding policy

Wave 5 is primarily a **measurement/reporting layer**.

It must not automatically introduce readiness-blocking findings for:

- boundary edges;
- n-gons;
- multiple connected components;
- isolated vertices;
- mixed triangle/quad/n-gon topology.

Those are structural facts whose production acceptability depends on the asset/profile.

The existing `MESH_NON_MANIFOLD_EDGE` finding remains the current blocking/non-blocking policy signal for edges with incidence greater than 2. Wave 5 may expose the same topology with richer aggregate metrics, but must not duplicate or alter finding semantics merely to populate the report.

## 10. C++ seam

The canonical topology report is the intended language-neutral seam.

Python is the first implementation, but all externally meaningful values must be representable as canonical JSON primitives with stable enum/string identifiers and deterministic ordering. A future C++ implementation must be able to reproduce the same report from the same canonical `MeshModel` input.

No Blender-specific types cross this seam.

## 11. Live Blender boundary

Wave 5 live validation must prove **extraction fidelity**, not invent unsupported topology semantics.

The live gate should construct a disposable in-memory Blender scene containing known topology cases, extract through the existing Blender adapter, and independently inspect the source mesh through Blender's API.

At minimum the fixture should exercise:

1. a closed manifold component;
2. an open/boundary component;
3. two disconnected face components;
4. an isolated vertex if the current Blender extraction preserves unused mesh vertices;
5. a non-manifold edge with incidence greater than two.

The gate must verify that canonical topology metrics agree with independently observed Blender source topology, and that the source file is never saved or mutated.

If the current extraction boundary cannot preserve a fixture property faithfully, that limitation must be recorded rather than widening the adapter as an incidental part of Wave 5.

## 12. Test plan

Before implementation can be considered complete:

### Deterministic tests

- single triangle
- closed tetrahedral component
- open plane/grid
- two disconnected components
- isolated vertex
- non-manifold edge with valence 3+
- mixed triangle/quad/n-gon mesh
- empty/invalid input rejection
- invalid index rejection
- deterministic repeatability
- canonical serialization round-trip
- component ordering stability
- histogram ordering stability
- large synthetic mesh linear-scaling sanity case

### Adversarial tests

Hostile cases must prove the analyzer cannot:

- mutate the source mesh/model;
- reorder canonical faces/vertices;
- invent edges;
- convert boundary edges into non-manifold findings;
- treat point-contact faces as one component;
- accept out-of-range indices;
- depend on Python hash iteration order;
- emit unstable component IDs;
- leak mutable references through the report;
- accept unknown serialized fields.

### Live tests

The live gate is separate from deterministic tests and must use the actual Blender executable. It must prove source preservation, extraction fidelity, deterministic metrics, and no save/mutation side effects.

## 13. Explicit non-goals for Wave 5

Wave 5 does **not** implement:

- automatic hole filling;
- bridge/edge stitching;
- vertex welding;
- remeshing;
- decimation;
- triangulation;
- quadification;
- normal repair;
- UV repair;
- material changes;
- object transforms;
- collection/hierarchy changes;
- Blender operators;
- persistence or recovery.

Those require separate design gates.

## 14. Exit criteria

Wave 5 is complete only when all of the following are independently true:

1. the canonical report schema is frozen;
2. deterministic analyzer implementation exists with no `bpy` dependency;
3. deterministic tests pass;
4. adversarial tests pass with zero unauthorized mutation;
5. canonical serialization is deterministic and round-trippable;
6. live Blender validation passes against the supported extraction boundary;
7. an independent red-team review finds no blocker;
8. documentation records any extraction limitations discovered during live validation.

No Wave 5 mutation capability may be merged under the name of topology intelligence. Mutation begins only in a later, separately gated wave.
