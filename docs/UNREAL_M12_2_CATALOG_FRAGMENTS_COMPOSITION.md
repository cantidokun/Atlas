# Atlas M12.2 — Unreal Semantic Production Catalog + Reusable Fragments + Composition

**Status:** IMPLEMENTED (M12.2). Builds on the merged M12.1 (PR #87).

## What M12.2 implements

A versioned semantic catalog + reusable fragment/composition layer ABOVE the
M12.1 contract and the existing M4-M10 Unreal machinery. No M4-M10 behavior
changed; no second runtime/authority introduced.

### Catalog — `planning/m12/catalog.py`
- `UnrealCatalogEntrySpec` — models the Blender `SoccerProductionWorkflowSpec`
  shape (name, objective, task-class, required parameters + kinds, version), but
  resolves to Unreal semantic tasks. Reuses the conceptual shape; does not copy
  Blender-specific semantics.
- `UnrealSoccerProductionCatalog` — a versioned cursor (default catalog version
  1) that:
  - `available_task_names()` / `get_entry()` / `validate_parameters()`: canonical
    tasks (unreal.scene-prepare, unreal.environment-configure,
    unreal.camera-configure, unreal.lighting-configure, unreal.sequence-configure,
    unreal.render-execute, unreal.artifact-validate);
  - `resolve()` — deterministic: validates parameters (string/int/json kinds),
    composes canonical fragments, and normalizes through the M12.1 contract into
    a validated `UnrealProductionTaskDefinition`;
  - fail-closed on unknown task, unsupported version, missing/unexpected/bad
    parameter, or ambiguous intent — no implicit semantic substitution;
  - stable `canonical_json()` serialization.

### Reusable fragments — `planning/m12/fragments.py` + `fragments_registry.py`
- `UnrealProductionFragment` — immutable, reusable *semantic production
  capability* (canonical_id, version, label, inputs, produces, requires,
  contributes_invariants, idempotent, expandable, detail). Explicitly NOT a
  low-level Unreal command.
- Canonical registry — scene_setup, environment_setup, camera_setup,
  lighting_setup, sequence_setup, render_setup. Render_setup is non-idempotent,
  non-expandable (render execution stays constrained by M12.1).

### Composition — `planning/m12/composition.py`
- `compose_fragments(fragments, *, requested_invariants, description)` —
  deterministic:
  - dependency-ordering (Kahn topological sort over `requires` vs `produces`);
  - deterministic order for independent fragments;
  - duplicate fragment canonical_id → fail-closed;
  - conflicting requirement / incompatible non-idempotent invariant
    re-contribution → fail-closed;
  - missing dependency or cycle → fail-closed;
  - target-state merge (requested + contributed invariants) with conflict
    detection; preserves the requested-vs-verified-state distinction (no second
    evidence system);
  - no hidden mutation of requested intent.
- `UnrealComposedTaskPlan` — immutable ordered plan (fragments, fragment_ids,
  merged target state), language-neutral serialization.

## Catalog schema (canonical)

```json
{
  "catalog_version": 1,
  "entries": [
    {
      "name": "unreal.camera-configure",
      "objective": "Configure camera placement/framing for production shots.",
      "task_class": "camera-configure",
      "fragment_ids": ["scene_setup", "camera_setup"],
      "required_parameters": ["twin_id", "camera_slots"],
      "parameter_kinds": {"twin_id": "string", "camera_slots": "json"},
      "version": 1
    }
  ]
}
```

## Composition rules

- Semantic dependency = a fragment's `requires` must be among the accumulated
  `produces` of already-ordered fragments.
- Execution/verification dependency distinction: composition only reasons about
  *planning* ordering; it does not schedule, authorize, or verify execution.
- Disruptive cases fail closed, never silently reorder or substitute.
- Deterministic serialization is stable across independent runs.

## Provenance

Resolution preserves (in `UnrealProductionTaskDefinition.metadata` and
`to_json_compatible()`):
- canonical digital-twin id (`digital_twin_id` / `canonical_digital_twin_id`);
- source semantic task id (`unreal_semantic_task_id`),
- catalog version + catalog entry snapshot,
- fragment identities/versions,
- proposal provenance (from request `provenance`).

No authorization, receipt, artifact-manifest, or recovery record is generated.

## Compilation (M12.2→M12.1)

Composed non-render tasks (scene-prepare, environment/camera/lighting/sequence-
configure) compile through the EXISTING M12.1 `compile_unreal_semantic_task`
onto `AtlasTaskDefinition`. Render-bearing tasks (render-execute,
artifact-validate) resolve through the catalog but REJECT compilation with
`UnsupportedCompileMappingError`, exactly as M12.1 defined. Render execution is
not solved in this milestone.

## Blender relationship

- Shared/conceptual: the `SoccerProductionWorkflowSpec` shape (name/objective/
  required_parameters/parameter_kinds/version) and the fail-closed resolution +
  proposal-only surface.
- Unreal-specific: fragment composition, Unreal task-class taxonomy, Unreal
  target-state contributions, resolution into `UnrealProductionTaskDefinition`.
- Not modified: Blender implementation is untouched.

## C++ interoperability

Catalog entries and fragments serialize to stable, language‑neutral JSON
(`to_json_compatible` / `canonical_json`). No C++ implemented in M12.2.

## Deterministic validation

- `pytest tests/m12/` → 71 passed (34 new in M12.2)
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/ tests/m11/ tests/m12/` → 418 passed
- `pytest -m "not integration"` → **1522 passed** (was 1488)

No live Unreal, no workflow/action-runner tests, no Blender, no M11.

## M12.3 / M12.4 relationship

- **M12.3** — composition/ordering refinements + any idempotence/catalog
  extension needed for real-world workflows (this milestone already covers
  composition core).
- **M12.4** — `UnrealSemanticTaskAdapter` mapping a resolved composed plan onto
  the existing `UnrealTaskPlanner`/submission path (no new authority; render
  execution remains deferred).