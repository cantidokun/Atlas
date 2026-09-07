# Atlas M12 — Unreal Semantic Soccer Production Layer (Design & Implementation Plan)

**Status:** DESIGN / INVESTIGATION ONLY. No M12 production code is implemented.
**Scope:** Design a semantic soccer-production task layer that sits ABOVE the
proven M4–M10 Unreal execution/recovery/evidence architecture, WITHOUT bypassing
or replacing any existing authority, recovery, evidence, or artifact-lineage
boundary.
**Boundary (non-negotiable):** Model proposes. Atlas validates, authorizes,
executes, tracks, verifies, and recovers. Unreal executes. Independent
verification establishes truth. M12 introduces NO second authorization authority,
scheduler, retry controller, recovery authority, or persistence authority.

---

## 1. Problem statement

Atlas already owns a mature semantic production-task abstraction on the Blender
side: `ProductionTaskDefinition` (semantic intent) compiles onto the generic
`AtlasTaskDefinition` runtime contract; `TargetStateEvaluator` verifies requested
target state from authoritative evidence; and the versioned
`soccer-production` catalog (`SoccerProductionWorkflowSpec`) provides canonical,
reusable, proposable workflows. Unreal, by contrast, is driven through the lower
level `UnrealTaskPlanner` + `UnrealAutonomousExecutor` + `UnrealAdapterProduction`
machinery — strong on execution/recovery but without an equivalent *semantic*
production-task layer.

M12 closes that asymmetry: it gives Unreal a semantic soccer-production task layer
(describe intent → normalize → validate → authorize → expand onto the existing
runtime → execute → verify → lineage), reusing the Blender-side semantic concepts
where they are engine-neutral and keeping Unreal-specific behavior in an adapter,
never duplicating concepts unnecessarily.

---

## 2. Current-state analysis

### 2.1 What Unreal already has (M4–M10, all live-validated)

| Component | Responsibility |
|---|---|
| `UnrealAdapterProduction` | transport adapter; WRITE ops via `apply_authorized`, READ via `inspect` |
| `UnrealRenderSubmissionService` | durable render-job submission (Atlas-authoritative intent + authorization) |
| `UnrealRenderJobStore` / `UnrealRenderJobRecord` | durable per-job identity, lifecycle, attempt_ordinal, nonce |
| `UnrealRenderRecoveryCoordinator` | recovery classification (Case A–K / J / G / H), receipt gating |
| `UnrealEvidenceContract` verifier | independent artifact/evidence verification, strict frame counts |
| `UnrealRenderReceipt` / `UnrealRenderReceiptStore` | receipts from verified evidence only |
| `UnrealProductionArtifactManifest` (Stage 17) | downstream provenance/lineage |
| `UnrealTransportServer.cpp` + witness journal | UE-5.6 witness, append-only, HMAC attestation, CONFLICT detection |
| M9 scenario harness + M10 S1–S8 | all live PASSED (S1–S8) |

### 2.2 What Blender-side semantics already exist (candidates to reuse)

- `ProductionTaskDefinition` — semantic production goal compiling to one
  `AtlasTaskDefinition` (semantic organization only; runtime/auth/verification
  owned by the generic task runtime).
- `TargetStateEvaluator` / `StateInvariant` — target state required to be
  satisfied by authoritative evidence (fail-closed on any failed/unevaluable
  invariant).
- `SoccerProductionWorkflowSpec` + `soccer_production_catalog` + templates —
  canonical, versioned, proposable soccer workflows; proposal-resolution only.
- `TaskPlanAuthorization` / `task_plan_authorization.py` — planning bridge that
  validates structured tools before execution trusts a plan.

### 2.3 The asymmetry and the gap

Unreal leans on low-level render-job operations; there is no Unreal equivalent of
*"prepare the soccer-field scene / configure camera / set lighting / configure
sequence / render"* expressed as a semantic, canonical, versioned, proposable
production task. M12 fills that gap without touching M4–M10 internals.

---

## 3. Architecture (overview)

```text
Qwen / AI model (development or production proposal)
        ↓  propose structured production intent (semantic, no execution grants)
UnrealSemanticProductionIntent (proposal)
        ↓  M12: semantic task normalization + catalog resolution
UnrealProductionTaskDefinition (M12, semantic)         [NEW — mirrors ProductionTaskDefinition]
        ↓  M12: target-state model + fragment composition
UnrealSemanticTaskPlan (M12, ordered, dependency-checked)
        ↓  existing Atlas authorization boundary (TaskPlanAuthorization / dispatch)
atlas-authorized execution proposal
        ↓  EXPAND onto existing Unreal runtime (NO new scheduler/authority)
UnrealTaskPlanner (existing) → UnrealAutonomousExecutor (existing)
        ↓  existing Unreal transport + render-job store + recovery
UnrealAdapterProduction → NamedPipe → UE 5.6 harness → durable render-job record
        ↓  existing recovery coordinator (Case A–K etc.)
UnrealRenderRecoveryCoordinator (existing)
        ↓  existing independent verification
UnrealEvidenceContract verifier (strict) → verified UnrealEvidence
        ↓  existing receipt + artifact lineage
UnrealRenderReceipt → ProductionArtifactManifest (Stage 17)
```

Key invariant: **M12 adds a semantic *coordination/description* layer; it does not
add a scheduler or a second runtime.** The existing `UnrealTaskPlanner` +
`UnrealAutonomousExecutor` + `UnrealAdapterProduction` + recovery coordinator
remain the single execution/authority path.

---

## 4. Semantic task contract (M12)

`UnrealProductionTaskDefinition` (frozen dataclass) expresses, in semantic terms:

| Field | Meaning | Who sets it |
|---|---|---|
| `name` | canonical stable task name | catalog |
| `objective` | human-readable semantic goal | proposal → normalized |
| `domain` | always `soccer-production` | fixed |
| `task_class` | one of the M12 Unreal taxonomy (below) | catalog |
| `parameters` | typed, validated parameters (scene id, twin id, camera slot, etc.) | proposal/catalog |
| `required_evidence` | tuple of `EvidenceRequest` (inspection tools) | catalog |
| `intended_actions` | tuple of semantic action descriptors (NO raw exec grants) | catalog |
| `target_state` | `UnrealTargetStateSpec` (see §6) | catalog |
| `fragments` | ordered list of reusable fragment names (§7) | catalog |
| `allowed_tools` | constrained tool set | catalog |
| `expects_render` | whether it culminates in a render job (bool) | catalog |
| `provenance` | twin id, source-asset refs, workflow/task provenance | Atlas |
| `version` | semantic task version | catalog |
| `metadata` | opaque, validated | proposer+Atlas |

**Contract rule:** like Blender's `ProductionTaskDefinition`, the semantic task is
a **proposal-resolution surface only** — it does NOT authorize, schedule, or run.
`compile()` produces an `AtlasTaskDefinition`-shaped contract and/or expands to
existing `UnrealTaskPlanner` operations; it can never mint receipts, authorization
IDs, protected flags, recovery authority, or final verification. (These are
enforced by construction and by tests that mirror the existing
`production_task.py` invariant.)

---

## 5. Unreal soccer-production task taxonomy (constrained)

Design a **constrained Unreal vocabulary** for Atlas's soccer-field digital-twin
domain. Evaluate which are full tasks; some are just parameters/fragments, not
tasks.

| Candidate | Task? | Rationale |
|---|---|---|
| `scene-prepare` | Task | prepare/initialize the soccer digital-twin scene (existence checks, imports, baselines) |
| `environment-configure` | Task | field/environment configuration (surface, markings, surroundings) — stateful, verifiable |
| `camera-configure` | Task | camera placement/framing for production shots — represents target camera state |
| `lighting-configure` | Task | lighting configuration — stateful, verifiable |
| `sequence-configure` | Task | cinematic/ULevelSequence configuration (playback range etc.) |
| `render-configure` | Task | render job configuration (already largely in `UnrealRenderContract`); wrapper task |
| `render-execute` | Task | run the authorized render (→ existing render-job machinery) |
| `effect-pass-prepare` | Draft/extension | future cinematic/VFX pass preparation (not a task yet) |
| `artifact-validate` | Task | artifact preparation/validation wrapper over existing verifier |
| `inspect-*` (camera/lighting/scene) | Fragment/evidence | inspection operations as reusable fragments, not standalone tasks |

**Decision:** The six concrete canonical tasks for M12.0 are `scene-prepare`,
`environment-configure`, `camera-configure`, `lighting-configure`,
`sequence-configure`, and `render-execute`; plus `artifact-validate` as a
verification wrapper. `effect-pass-prepare` is reserved for the extension point
(§14). Each is a **task only if it has an independently-inspectable target state**
(§6) — pure transforms with no durable target state are fragments, not tasks.

---

## 6. Target-state model

`UnrealTargetStateSpec` is the semantic expression of the requested result. It
must be **independently inspectable** (the verifier can re-derive it without
trusting the model).

| Aspect | Expression |
|---|---|
| requested intent | `objective` + per-task-class semantic goal |
| canonical identifiers | `canonical_digital_twin_id`, `sequence_asset_path`, `unreal_job_id` (never collapsed) |
| expected state | named `StateInvariant` predicates over authoritative evidence (mirror `TargetStateEvaluator`) |
| allowed mutations | an allow-list of permitted tool/operation names (never a wildcard write grant) |
| dependencies | fragment/action dependency graph (reuse `validate_action_dependencies`) |
| engine-specific config | opaque `engine_config` dict passed to the Unreal adapter, schema-validated |
| verification requirements | which evidence must be green for success (tests/build/static/contract analog for Unreal inspect state) |
| provenance | `digital_twin_id`, source assets, workflow/task provenance, expected artifact manifest identity |

`UnrealTargetStateEvaluator` reuses the existing `TargetStateEvaluator` semantics:
evaluate all invariants every time; target satisfied only when all pass; any
failed/unevaluable invariant fails closed.

---

## 7. Task fragments / composition

Reusable, composable Unreal production fragments (engine-specific adaptations of
the Blender fragment idea):

- `scene_setup`
- `camera_setup`
- `lighting_setup`
- `sequence_setup`
- `render_setup`
- `effect_setup` (reserved)
- `artifact_validation`

Each fragment declares:
- **contract:** input parameters + expected evidence tools + semantic pre/post
  state predicates;
- **dependencies:** e.g. `camera_setup` depends on `scene_setup`;
- **ordering:** a DAG over the fragment set (validated);
- **idempotence:** a fragment is idempotent iff its target-state invariants are
  already satisfied → skip (proposal only; never writes "already there" without
  verification);
- **failure behavior:** a fragment that cannot reach target state fails the
  enclosing task through the existing runtime (no blind retry; bounded);
- **state verification:** each fragment maps to an inspection/verification step
  (through the existing evidence verifier);
- **cross-process implications:** a fragment may produce a checkpoint; recovery
  is handled by the existing render-job record, not a new mechanism.

Composition is validated by `validate_action_dependencies`-style logic and by the
existing `TaskPlanAuthorization` bridge (an unauthorized/malformed fragment is
rejected before execution).

---

## 8. Versioned catalog + canonicalization

Reuse the catalog pattern already proven by `soccer_production_catalog`:

- `UnrealSoccerProductionCatalog` — versioned registry of
  `UnrealProductionTaskDefinition` spec entries (`name`, `objective`,
  `template_name`, `required_parameters`, `parameter_kinds`, `version`), each
  resolving to the canonical (compile → runtime contract).
- Canonicalization: proposals reference canonical names + version; unknown/
  unversioned references are rejected (no guessing).
- Composition: a workflow resolves to an ordered set of fragments and produces
  `UnrealSemanticTaskPlan`.
- Validation: schemas validated before use; malformed entries fail closed.
- Persistence: the catalog is declarative data (like the Blender catalog); it is
  **proposal-resolution only** — no job/receipt/persistence authority.
- Migration: versioned; old versions remain resolvable for provenance; new
  versions are additive with explicit migration notes for parameter changes.

**Recommendation:** the catalog *shape* is shared cross-engine (same
`SoccerProductionWorkflowSpec`-like spec); the *content* (task definitions and
fragments) is Unreal-specific. Do not create a second incompatible catalog system.

---

## 9. Authorization boundary (critical)

Model proposal ends → M12 semantic-task validation begins → Atlas authorization
→ Unreal execution. The M12 layer and the semantic task definition MUST NEVER:

- mint authorization IDs;
- mint receipts;
- set protected production flags;
- grant recovery authority;
- perform final verification;
- select/schedule the execution worker.

These remain owned by the existing boundaries:
- `TaskPlanAuthorization` authorizes a plan;
- `UnrealRenderSubmissionService` + `UnrealRenderRecoveryCoordinator` own
  render-job authorization/recovery;
- `UnrealEvidenceContract` verifier owns final verification;
- `UnrealRenderReceipt` issues receipts from verified evidence only.

A semantic task is an **expression of intent + a validated plan**, never an
authorization device.

---

## 10. Unreal adapter boundary

Unreal-specific behavior lives in a thin `UnrealSemanticTaskAdapter` that knows
how to interpret a validated `UnrealSemanticTaskPlan` in terms of the EXISTING
lower-level operations:

- maps each authorized task/fragment onto `UnrealTaskPlanner` inspection/
  material/sequence operations and, for `render-execute`, onto
  `UnrealRenderSubmissionService` (already the authority path).
- never talks to the transport/recovery/verifier directly except through their
  existing public entry points.
- is the only component that understands engine-specific config
  (`engine_config` in the target-state spec).

Provider/task-specific naming (camera slots, lighting channels, sequence asset
paths) is configuration-driven, not hard-coded.

---

## 11. Recovery interaction

M12 sits ABOVE M4–M10 recovery; it does not replace it.

```text
semantic task → normalization → existing authorized task runtime
  → existing UnrealTaskPlanner / UnrealAutonomousExecutor (authorized)
  → existing UnrealAdapterProduction → transport
  → existing durable render-job record (UnrealRenderJobRecord)
  → existing UnrealRenderRecoveryCoordinator (Case A–K / J / G / H)
  → existing evidence verifier → receipt → artifact lineage
```

Semantic tasks do NOT require a second durable store. Cross-process scenarios
(Unreal restart, Atlas restart, partial progress, torn witness, missing artifact,
duplicate identity) are already handled by the render-job record + recovery
coordinator + verifier. A semantic task that does not reach a render job either
(1) completes via verified target-state inspection, or (2) leaves only the
Atlas task record (if any) as durable evidence — never a second recovery
authority. "Partial progress" for a pre-render fragment is expressed as
target-state invariants (what is verified) + an explicit "not reached" outcome,
not as a fake render.

---

## 12. Verification

Semantic-task completion is verified **target state**, not command success.

- **Observed:** inspection evidence from the Unreal harness (scene/camera/
  lighting/sequence/render inspected state).
- **Independently verified:** via the existing `UnrealEvidenceContract` verifier,
  plus `UnrealTargetStateEvaluator` over the target-state invariants.
- **Success:** all required invariants satisfied AND (for render tasks) the
  render-job FINISHED + strict frame-count + artifact hashes verified.
- **Partial progress:** some invariants satisfied, some not → NOT success;
  reported as partial, non-terminal (no receipt).
- **Uncertainty:** unknown/unevaluable invariant → fail closed (no success
  claim).
- **Recoverable:** a render-bearing task is recoverable via the existing
  coordinator; a pure target-state task has no render job and is re-runnable
  idempotently (fragments that are already at target skip) — never a second
  recovery system.

---

## 13. Provenance / artifact lineage

M12 semantic tasks connect to the existing provenance graph WITHOUT collapsing
identities:

- **canonical Digital Twin identity** (source of truth, `canonical_digital_twin_id`)
  and **production artifact identity** (per-render manifest/receipt, Stage 17)
  remain distinct and are never collapsed.
- Each semantic task records: `digital_twin_id`, source asset references,
  workflow/task provenance (catalog name+version, fragment set), the execution
  receipt (if render), the verified `UnrealEvidence`, and the
  `ProductionArtifactManifest` (downstream lineage only).
- The manifest is downstream provenance; it does not re-authorize.

---

## 14. Future extensibility (cinematic / VFX scope)

Account for the existing future Atlas cinematic/VFX repertoire WITHOUT
implementing it (M12 non-goal):

- `effect_setup` fragment is the reserved extension slot.
- Impact frames, smear frames, cinematic bleed, match-cut transformations,
  liquid/fluid effects, and chromatic aberration as impact accent: these are
  future **effect-pass** tasks/parameters that M12 will support via the
  `effect-pass-prepare` reserve class + `effect_setup` fragment once defined.
- They are NOT implemented in M12 and NOT added to the constrained task class
  list yet (the taxonomy is deliberately narrow: soccer-field production
  representation only).

---

## 15. Photogrammetry relationship

The established pipeline is preserved:

```text
photogrammetry software → initial 3D reconstruction
    → Blender analysis/cleanup/preparation
    → Unreal production/digital-twin representation
```

M12 does NOT move photogrammetry responsibility into Unreal. Unreal consumes the
prepared digital-twin representation and produces authorized, verified
production artifacts. Photogrammetry/reconstruction stays upstream (Blender).

---

## 16. Qwen / model integration

- Do NOT redesign Qwen (or any model) as an authority.
- A model may **propose** `UnrealSemanticProductionIntent` (task class,
  parameters, objective). All proposals are normalized + validated by M12 and
  then authorized by the existing Atlas boundary.
- The semantic layer must remain useful regardless of which reasoning model
  produced the proposal — the proposal is schema-validated; the model's identity
  never grants execution.
- No model self-confidence is used for verification.

---

## 17. C++ interoperability

Preserve the Atlas requirement that future performance-sensitive components can
move to C++ without redesigning higher-level Python contracts:

- The Python `UnrealSemanticTaskPlan`/`UnrealTargetStateSpec` are pure data
  contracts with a stable wire/JSON schema.
- The existing `AtlasUnrealTransportServer.cpp` already owns transport +
  witness journal; a future C++ target-state **inspector** (e.g. fast
  camera/lighting/sequence state reads) can be added behind the existing
  `ProviderAdapter`/transport boundary without changing the Python semantic
  layer.
- The semantic layer stays Python; only leaf inspection/execution primitives are
  candidates for C++.

---

## 18. Non-goals (explicit)

M12 does NOT:

- replace M4–M10 recovery;
- weaken evidence verification;
- create model authority (model proposes only);
- create a second scheduler;
- create a second retry controller;
- create a second persistence authority;
- replace the existing render-job record;
- redesign M11 (frozen);
- implement VFX/cinematic features (reserved slot only);
- build a general-purpose Unreal automation framework;
- move photogrammetry into Unreal.

---

## 19. Migration strategy

1. Introduce M12 semantic modules alongside existing code (no existing-file churn
   beyond additive new modules under `planning/m12/`).
2. Wire the semantic layer to the EXISTING `UnrealTaskPlanner` +
   `UnrealAutonomousExecutor` + submission + recovery (no changes to those
   authorities).
3. Ship the catalog + fragments + target-state + verification as the semantic
   surface; verify against deterministic tests first, then a live render task
   through the existing path.
4. No data migration (render-job store/receipts unchanged).

---

## 20. Risks

| Risk | Mitigation |
|---|---|
| Semantic layer accidentally authorizes | construction-invariant tests mirror production_task.py (must not mint receipts/auth/flags/recovery); authority-isolation tests |
| Duplicate of Blender catalog | reuse the catalog *shape*; only content is Unreal-specific |
| Second recovery/persistence authority | no new durable store; render-bearing tasks use existing render-job record; target-state tasks leave only Atlas task record (if any) |
| Off-by-one/exclusive-range regression (as in Defect D) | strict verifier + reuse start/end-inclusive contract; live-tested render path |
| Taxonomy creep beyond soccer field | constrained task-class set enforced by catalog validation |
| Model-generated task data overrides authority | proposal normalized + validated; never sets protected flags |

---

## 21. Acceptance criteria (M12)

- A semantic `UnrealProductionTaskDefinition` compiles to the existing runtime
  contract and NEVER to a second authority.
- Target-state evaluation is deterministic, independent, fail-closed.
- Catalog is versioned, canonical, proposal-resolution only.
- Each fragment is dependency-validated + idempotence-aware.
- Render-bearing tasks flow through the existing submission + recovery +
  verifier + receipt + lineage unchanged.
- No new scheduler/retry/recovery/persistence/authorization authority exists.
- Semantic layer usable regardless of proposing model.
- No M4–M10 boundary or data model changed.

---

## 22. Proposed M12 milestone breakdown

| Milestone | Scope | Outcome |
|---|---|---|
| M12.0 (this design) | design/plan only | reviewed design PR |
| M12.1 | `UnrealProductionTaskDefinition`, `UnrealTargetStateSpec/Evaluator`, authority-isolation tests | semantic contract layer |
| M12.2 | `UnrealSoccerProductionCatalog` + constrained task classes + versioning | catalog layer |
| M12.3 | fragments/composition + dependency + idempotence | composition layer |
| M12.4 | `UnrealSemanticTaskAdapter` mapping to existing planner/submission/recovery | integration layer (no new authority) |
| M12.5 | verification wiring (target-state + existing verifier) + provenance | verification/provenance |
| M12.6 | deterministic suite + live render-task validation through existing path | validated M12 |
| Future | `effect_setup` fragment + cinematic/VFX task classes (post-M12) | extension |

---

## 23. Shared vs Unreal-specific recommendation

**Shared cross-engine (reuse/extend Blender patterns):**
- `ProductionTaskDefinition`-like semantic contract shape;
- `TargetStateEvaluator`/invariant semantics;
- `SoccerProductionWorkflowSpec`-like catalog: versioned, canonical, proposable.

**Unreal-specific (new M12 modules):**
- `UnrealProductionTaskDefinition`, `UnrealTargetStateSpec`,
  `UnrealSoccerProductionCatalog`, `UnrealSemanticTaskAdapter`, Unreal fragment
  implementations.

**Explicitly separate (do not merge):**
- Unreal identity (`canonical_digital_twin_id`) vs artifact identity (manifest);
- Unreal runtime/verifier/receipt (M4–M10) vs semantic description (M12);
- Blender execution vs Unreal execution.

---

## 24. Unresolved questions

1. Which pre-render fragments (camera/lighting/sequence setup) need a durable
   checkpoint vs. being fully re-derivable from target-state inspection?
2. Should `sequence-configure` + `render-execute` be composed automatically, or
   always authorized as separate tasks?
3. For pure target-state tasks with no render job, is a lightweight
   `AtlasTaskRecord` durable record warranted, or is verified-in-memory +
   provenance sufficient (avoiding a new durable authority)?
4. Exact target-state inspection operations per fragment (which C++ inspector
   primitives come first).
5. Whether `effect-pass-prepare` is a full M12 task or strictly a post-M12
   fragment slot.

---

## 25. Implementation-plan (what the next PR must contain)

The next M12 implementation PR (M12.1) should contain, in minimal scope:
- `planning/m12/__init__.py`, `semantic_task.py`
  (`UnrealProductionTaskDefinition` + `compile`, `snapshot`),
- `planning/m12/target_state.py`
  (`UnrealTargetStateSpec` + `UnrealTargetStateEvaluator`),
- `planning/m12/task_classes.py` (constrained taxonomy constants),
- `tests/m12/test_m12_semantic_task.py`,
  `tests/m12/test_m12_authority_isolation.py`
  (authority-isolation: no auth/receipt/verifier minting; no second scheduler),
- docs update `docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md` (this doc) with an
  "implemented" status marker after review.

It must NOT touch M4–M10 modules or the render-job store, and must keep the full
deterministic suite green.

---

**Implementation status:** M12.1 (semantic task contract + normalize/compile),
M12.2 (catalog + fragments + composition), and M12.3 (semantic execution-plan
boundary) are IMPLEMENTED (`planning/m12/`; `docs/UNREAL_M12_1_SEMANTIC_TASK_CONTRACT.md`,
`docs/UNREAL_M12_2_CATALOG_FRAGMENTS_COMPOSITION.md`,
`docs/UNREAL_M12_3_EXECUTION_PLAN.md`). Delivery order: M12.1 → M12.2 → M12.3 →
adapter (M12.4) → verification (M12.5). Render-bearing execution remains deferred
until independently proven. See §25.

*Design only — no M12 production code was implemented in this task.*