# ATLAS M12.6 — AUTHORITATIVE SEMANTIC EXPECTATION RESOLUTION
## R1 — NORMATIVE ARCHITECTURE FREEZE — **Revision 6**

**Revision:** R6 of the R1 artifact. Supersedes Revision 5 (preserved at
`ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV5_superseded.md`), Revision 4
(`ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV4_superseded.md`), Revision 3
(`ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV3_superseded.md`) and Revision 2
(`ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV2_superseded.md`). This document is the complete,
standalone contract: it replaces the defective Revision-2 language **at its normative
locations** and does not require the reader to reconstruct Revision 2 plus an errata list.
**Target artifact path (to be landed by the human):**
`docs/UNREAL_M12_6_SEMANTIC_EXPECTATION_RESOLUTION_DESIGN.md`
**Source material / change agenda:** Revision 5 (all still-valid material preserved) · the **third
independent review**, whose four blockers are the sole change agenda for this revision and are closed in
Part 0.1 · the second review's five findings (closed in Revision 5, restated in Part 0.2) · the earlier
five-decision adjudication (`ATLAS_M12_6_R1_REV3_ADJUDICATION.md`, still authoritative for the five R2-A
ambiguities) · current repository main.
**Status vocabulary:** `MUST` / `MUST NOT` are normative. `DECIDED` · `DEFERRED` (normative refusal
until a named upstream artifact exists) · `OPEN` (named for the reviewer) · `NOT CLAIMED` · `OUT OF SCOPE`.

**Independence limitation (stated up front).** This artifact is authored by the same agent family as the
prior M12.5/M12.6 rounds. It is **not** a gate. The next step is an independent review of *this* artifact by a
different model in a separate process.

---

# PART 0 — CHANGE RECORD

## 0.1 Revision 5 → Revision 6 — the four blockers of the third independent review, closed

| # | Blocker | Revision-6 closure | Locations |
|---|---|---|---|
| **1** | The contract defined **first-failing-stage** precedence but not what happens when **several rows apply inside one stage**; Revision 5 even asserted that no tie-resolution logic exists. | New normative subsection **XIV.3.1**: one deterministic within-stage rule — the **lowest-numbered applicable Part XV row wins** and supplies the primary token, the stage's reason class is **provably homogeneous** (census-checked per stage), `failure_codes` is the **sorted, deduplicated union of every applicable row's token in the deciding stage**, the outcome MUST be invariant under any permutation of in-stage checks, and no other tie-break may exist. Demonstrated deterministically for the R2-A state (all definitions `DEFERRED`, empty target table) ⇒ single outcome: primary `EXPECTED_VALUE_UNAVAILABLE`, stage S4, class `AUTHORITY_ABSENT`, `failure_codes = ["EXPECTED_VALUE_UNAVAILABLE", "PRODUCTION_TARGET_NOT_ESTABLISHED"]`, every required invariant `UNKNOWN`, `semantic_state = NOT_ESTABLISHED`, `overall_state = NOT_ESTABLISHED`. Per-entry refusal states are pinned by a total precedence rule in XIV.4.2. | XIV.3.1 (new), XIV.3, XIV.4.2, XV |
| **2** | Six typed members of the whole-result canonical input had no derivation, and the nested identity members (`session_identity` keys, `engine_identity`, `extractor_identity`) were not enumerated — an independent implementation would have had to invent values. | New subsection **XIV.4.6** (with **XIV.4.6.1**): exact derivation, type, nullability and coherence for `render_job_identity`, `render_attempt_identity`, `render_evidence_identity`, `evidence_trust_basis.semantic_observation`, `evidence_trust_basis.render_evidence`, `observation_digests`; the **six** `session_identity` keys enumerated with types and validity rules; exact derivation for `engine_identity` (engine-reported `engine_version`, cross-checked against `world.engine_version`) and `extractor_identity` (`extraction_kind`, verbatim); the render triple's simultaneous-population coherence rule; and the three constants bound to their module constants. The measured M12.5 defect (unconditional `semantic_observation = "TRANSPORT_CORRELATED"` on results with no bound observation) is named and superseded. | XIV.4.5, XIV.4.6 (new) |
| **3** | Part XXII left `FROZEN_CONTRACT_DERIVATION` as an OPEN reviewer decision ("recommendation: admitted by the architecture, empty at R2") while V.1 called it admissible. | **DECIDED: NOT ADMITTED IN R2.** The class is a declared *reserved* future class, never a legal value of any R2 definition: the R2 `authority_class` domain is exactly `{CODE_CONSTANT}`; a definition carrying the reserved value is a **registry-integrity failure** at **S2 / `AUTHORITY_ABSENT`** (`REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED`, new Part XV row 33, with a load-and-validate startup test and the reviewed-constant digest as the independent second line of defence). Admission requires an explicit design-gate revision stating the restricted form, the reviewed digest and the witnesses. V.1, VIII.2, VIII.4, XVIII, XXII, XXIII and XXIV now agree; the OPEN/recommendation wording is removed. | V.1, VIII.2, VIII.4, XVIII.1, XXII, XXIII, XXIV, XV |
| **4** | XIV.3 called the state expansion an "R2-B contract requirement" while XXIII/XXIV require the same expansion in R2-A. | The contradiction is removed and replaced by the normative final rule: **R2-A lands the full four enums and the classifier**; **only the specified reachable subset is reachable in R2-A**; `SATISFIED`, `NOT_SATISFIED` and the other R2-B-only states remain **unreachable** in R2-A; **R2-B later supplies the authority and witness conditions** that make those paths reachable. Stated once in XIV.3 and mirrored in XXIII and XXIV.1. | XIV.3, XXIII, XXIV.1 |

## 0.2 Carried forward (compliance record, so this artifact stands alone)

**Revision 5** closed the second review's five findings at their normative locations: the digest-comparison-side
rule with the re-verified stage/class matrix (XIV.3, XV) · the fully enumerated `evidence_identity` recipe with
the `value_state` anti-collision rule (XIV.4.3) · R2-A ownership of the target lookup machinery against an empty
table (V.4.9, V.5.1) · the enumerated whole-result `result_digest` recipe with the `invariant_result_digest`
rename (XIV.4.4, XIV.4.5) · and the R2-A/R2-B state boundary (XXIV.1).

**Revision 4** closed the first review's eight blockers: `catalog_version` non-consumption with the permitted,
declared transitive identity effect through M12.3 (III.2/III.3, X.2) · bounded preflight traversal with F1–F9,
cycle handling, exception attribution and the pinned node budget (VII.4/VII.5) · `PLAN_CONTENT_UNSUPPORTED` as a
single-condition token with the retired expectation-side synonym (X.3, X.4, XI.2, XI.3, XIV.5) ·
`EXPECTATION_DEFINITION_DUPLICATE` at S2 / `AUTHORITY_ABSENT` (VIII.4, XIV.3) · "single-valued partial lookup
over the closed reviewed target table" (V.4) · the two Domain-A digest recipes · and custom-catalog substitution
as a non-detection / invariance control (III.4, XX).

The five-decision adjudication decisions (D1–D5) remain in force as restated at their normative locations.
Revision 3's withdrawn Revision-2 claim ("caller selection is eliminated") remains withdrawn and appears **only**
as a withdrawal record.

# PART I — AUTHORITY MODEL

## I.1 Component table

| # | Component | Owns | May read | May write | Must not influence | Authority? | Commits |
|---|---|---|---|---|---|---|---|
| 1 | `planning/m12/semantic_task.py` (M12.1) | declared semantic intent (names, class, version, twin id, dependencies) | nothing at runtime | nothing | expectation values | **No** (declaration only) | source content (digest computed by M12.3) |
| 2 | `planning/m12/catalog.py` (M12.2) | code-level entry constants | nothing | nothing | expectation values | **Content yes, act no** | nothing at runtime |
| 3 | `planning/m12/fragments_registry.py` (M12.2) | the 6 canonical invariant names | nothing | nothing | expectation values | **Content yes, live state no** | nothing |
| 4 | `planning/m12/execution_plan.py` (M12.3) | ordered steps, per-step `verification_requirements`, `render_plan` | task | nothing | expectation values | **No** | `source_content_digest`; `plan_id` is **not** a commitment (provenance only) |
| 5 | `planning/m12/runtime_adapter.py` (M12.4) | reconciled runtime representation | task, plan | nothing | expectations (forbidden, Part VI) | **No** | `runtime_task_digest` (disclosure only) |
| 6 | **NEW** `planning/m12/expectation.py` — **production-target table** | the reviewed, code-level, closed target definitions | code only | nothing | the verdict | **YES — production-target authority** | `production_target_id`, `target_revision`, `target_digest`, `TARGET_TABLE_DIGEST` |
| 7 | **NEW** same module — **definition registry** | meaning: invariant → observable path + subject scope + operator + authority class + value derivation + witnesses | code only | nothing | the required set; the verdict | **YES — semantic-expectation authority** | `REGISTRY_REVISION`, `REGISTRY_SOURCE_DIGEST`, per-definition digests |
| 8 | **NEW** same module — **resolver** | deterministic derivation of the expectation | task, plan, code constants | nothing | the verdict | **No** — no verdict, no state | `expectation_digest` |
| 9 | Expectation value object | — | — | — | the verdict (it is an **untrusted input** to it) | **No** | the expectation identity tuple |
| 10 | `planning/m12/verification.py` (M12.5) | **the semantic verdict** | task, plan, expectation, observation pairs, optional mapping (provenance only) | nothing | — | **YES — SOLE semantic-verdict owner** | the result + `canonical_digest` |
| 11 | `planning/unreal_state_extraction/*` | the observation: schema, reconstruction, canonical bytes, digest | transport response | nothing | the verdict | **YES for observation identity only** | the state digest |
| 12 | `planning/unreal_evidence_contract.py` (M5) | render evidence verification | durable record + observed state | nothing | the semantic domain | **YES, unchanged** | `UnrealEvidence` |
| 13 | `planning/unreal_transport_contract.py` | correlation | — | — | the verdict | Contract, not authority | correlation only |

## I.2 The two new authorities and their constraints

The **production-target table** fixes what the production is supposed to be; the **definition registry** fixes
which observable fact decides which invariant. Both are admissible **only** as stateless, code-level, closed,
revisioned, digest-revalidated constant tables with no caller-reachable runtime write path and no ability to
produce a verdict. Neither is a verifier. **M12.5 remains the sole semantic-verdict owner**: the resolver
returns expectations or refusals and never a verdict state. (Relationship to M12.5 stated normatively in XXV.)

## I.3 Validated diagram

```text
digest-bound resolved source task        (NOT "canonical task origin" — Part II)
        | requested invariant set (names only)
        v
closed code-level vocabulary + definition registry
        | meaning + observable path + operator + subject scope
        v
production-target table  (target derived from the closed triple; never caller-authored)
        | authoritative expected value
        v
expectation resolver  (total over the closed typed AND structurally valid domain)
        | deterministic expected value
        v
immutable expectation
        |
        +---- observed State Extraction tree
        v
M12.5 verifier  (sole verdict owner)
        v
SATISFIED / NOT_SATISFIED / UNKNOWN / NOT_ESTABLISHED
```

---

# PART II — TASK-ORIGIN AUTHORITY

## II.1 Measured finding

Rebuilding a raw semantic request from a genuinely resolved task's own fields (`snapshot()` /
`to_json_compatible()`) and re-normalizing yields **identical** `canonical_json`, `source_content_digest`,
`plan_id` and plan `canonical_json`. No content-level check can distinguish:

- **Case A** — a task produced on the canonical path (`UnrealSoccerProductionCatalog.resolve(...)` /
  `normalize_unreal_semantic_request(...)`);
- **Case B** — an arbitrary caller-created task whose fields merely match the canonical schema.

## II.2 Ruling: explicit `NOT_ESTABLISHED` boundary

| Option | Verdict |
|---|---|
| existing authority-binding mechanism | **None exists for a semantic task.** The only authority-bearing records bind render jobs / receipts / engine journals, and M12.1–M12.4 reject authority material (`_FORBIDDEN_AUTHORITY_KEYS`, `UnauthorizedSemanticFieldError`). |
| minimal reuse of an existing mechanism | **Rejected** — render/job-scoped; wiring it in would be a general task authority in disguise and would import M4–M10 authority modules into the M12 line. |
| new narrowly-scoped authority binding | **Rejected for R2** — it is the correct *eventual* answer and belongs to the Q10 design gate. M12.6 MUST NOT invent it. |
| explicit `NOT_ESTABLISHED` boundary | **DECIDED — ADOPTED.** |

## II.3 Claims

M12.6 **MAY** claim: (1) content consistency of the supplied task/plan pair (tamper-evidence only);
(2) canonical-vocabulary conformance; (3) expectation identity agreement.
M12.6 **MUST NOT** claim: canonical task origin; genuine catalog resolution; any authorization, dispatch or
execution; digital-twin verification (Part XIII).
**Structural MUSTs:** no `canonical_origin` / `resolved` / `catalog_verified` / `attested` field may exist on the
expectation, a definition, or the result. Any carried status MUST be the fixed value `NOT_ESTABLISHED`, MUST NOT
vary in any digest, and **no rule may branch on it toward acceptance** (test-asserted).

---

# PART III — CATALOG AUTHORITY

## III.1 Measured facts

| Question | Answer |
|---|---|
| Entries authoritative? | **As content only** — frozen `UnrealCatalogEntrySpec` module constants. |
| Catalog object authoritative? | **No** — `DEFAULT_UNREAL_CATALOG.version = 99` and `._entries = <extended>` both succeed (plain attributes). |
| Runtime instances substitutable? | **Yes** — `UnrealSoccerProductionCatalog(entries=(...), version=7)` resolved `unreal.sequence-configure` into a task whose invariant set was `('scene_initialized',)`. |
| Custom catalogs admissible? | **By construction, yes** — therefore M12.6 MUST NOT read any catalog object. |
| Is `catalog_version` provenance? | **It is not even a checked input** — `plan.catalog_version = 999` produces no refusal and leaves `plan_id` and `source_content_digest` unchanged. M12.3's own domain check accepts `1`, `999` and — because `bool` is an `int` subclass — `True`, while refusing `False`, `0`, `-1`, `"x"`, `None`, `1.0` (measured). |
| Full canonical catalog digest required? | **No, and it MUST NOT be added** — it authenticates content only, and not uniquely (hand-reproduction is byte-identical). |

## III.2 `catalog_version` — M12.6 does not consume it semantically (D2 / R4 blocker 1)

**MUST NOT semantically consume `catalog_version`.** M12.6 does not read the field by name from the plan, the
task, or task metadata; it does not interpret the field's meaning; it does not validate it; it does not compare
it; it does not use it for target selection; it does not use it as an input to any semantic decision; and no
refusal code or reason class may be **triggered by its value**. M12.6 MUST NOT independently interpret the field
in any way.

**The transitive identity effect through M12.3 is explicitly PERMITTED and declared.** M12.3 places
`catalog_version` inside the plan's canonical document, and the catalog resolver writes
`metadata["catalog_version"]`, which M12.3's `compute_source_content_digest` covers. M12.6 MUST NOT modify,
filter, re-derive, strip or bypass those upstream commitments — **M12.3 is PRESERVED UNCHANGED**. Therefore:

- a plan document whose `catalog_version` differs has a different `plan_content_digest`, because the field is a
  member of the canonical document M12.6 is given (X.2);
- two task documents that differ only in `metadata.catalog_version` have different `source_content_digest`s, and
  therefore different expectation identities;
- both are **content-commitment effects on supplied documents**. They are permitted, and they are declared here
  rather than hidden.

**M12.6 MUST NOT claim** that changing `catalog_version` leaves all M12.6 expectation identity or digests
unchanged; that the field is "forbidden in every respect"; or that its presence can never alter an identity
tuple. Those Revision-3 statements are **withdrawn** (Part 0.1, item 1).

**M12.6 MUST guarantee:**

1. **no distinguished refusal path** — a difference confined to `catalog_version` produces exactly the same code
   and the same reason class as any other supplied-document content difference (an identity/digest comparison at
   stage S3 ⇒ `EXPECTATION_IDENTITY_MISMATCH` / `EXPECTATION_DIGEST_MISMATCH`, `BINDING_ABSENT`), never a token
   of its own and never a semantic evaluation outcome;
2. **no semantic dependence** — no expected value, selected target, invariant state, requirement set or scope
   depends on the field;
3. **structural traversal only** — the preflight traverses the field as opaque structure under the uniform
   content-wide predicate (VII.3, VII.4), with no key lookup, no value comparison and no derivation.

## III.3 The transitive channel, exactly

| Document | Where the field sits | M12.6 treatment |
|---|---|---|
| plan | `UnrealExecutionPlan.to_json_compatible()["catalog_version"]` | traversed as opaque structure during preflight; **committed** by `plan_content_digest` over the full canonical document (X.2); **never consumed semantically** |
| task (catalog-resolved) | `metadata["catalog_version"]`, written by the catalog resolver | traversed as opaque structure; **committed** by M12.3's unmodified `source_content_digest`; **never consumed semantically** |
| task (hand-built) | the same key, if present | identical treatment |

Consequences, declared: two supplied task documents differing only in that key are **different inputs**, and
M12.6 MUST NOT claim that they produce identical expectation identities. For a **fixed** supplied document pair,
the field's value still changes no semantic outcome (III.2.1–III.2.3). Closing the channel entirely would require
modifying M12.3's recipe, which is **out of scope** and forbidden: **M12.3 is PRESERVED UNCHANGED**.

## III.4 Minimum safe contract

M12.6 owns a code-level vocabulary keyed by `(entry_name, entry_version)`; it MUST NOT import or read
`DEFAULT_UNREAL_CATALOG`, `UnrealSoccerProductionCatalog`, or any catalog instance; it MUST NOT read
`catalog_version` anywhere (plan, task, metadata); an unknown `(name, version)` ⇒
`EXPECTATION_VOCABULARY_MISMATCH`. M12.2 remains a *declaration* layer and is not turned into a security
boundary.

---

# PART IV — REQUIRED INVARIANT SET

## IV.1 Authority chain (frozen)

```text
digest-bound resolved source task  (target_state.invariant_names — NAMES ONLY)
        v
exact-set reconciliation  (EQUALITY with the plan union, both directions, non-empty)
        v
closed code-level vocabulary check  (M12.6: declared (entry_name, entry_version) pair -> fragment ids -> names)
        v
plan-step canonicality check  (every step.semantic_operation is a canonical fragment id)
        v
definition registry
```

Required names **MUST NOT** be sourced from the observation, the runtime mapping, caller-added metadata,
expected-value fields, render records, environment variables, or arbitrary configuration. Measured basis: a
caller-authored name outside the canon is refused by `INCOMPLETE_REQUIRED_INVARIANT_SET`, but the *boundary*
today is the live-mutable fragment registry — after in-memory mutation of a fragment's
`contributes_invariants`, a hand-built task declaring the injected name became plan-consistent with a
byte-identical `plan_id`. The vocabulary check MUST therefore use M12.6's own constant table, never live
registry state.

## IV.2 Closed vocabulary (v1 — the entire admissible set)

| entry `(name, version)` | task_class | fragments | invariant names |
|---|---|---|---|
| `unreal.scene-prepare` 1 | scene-prepare | scene_setup | scene_initialized |
| `unreal.environment-configure` 1 | environment-configure | environment_setup | environment_configured |
| `unreal.camera-configure` 1 | camera-configure | scene_setup, camera_setup | scene_initialized, cameras_configured |
| `unreal.lighting-configure` 1 | lighting-configure | scene_setup, lighting_setup | scene_initialized, lighting_configured |
| `unreal.sequence-configure` 1 | sequence-configure | scene_setup, camera_setup, sequence_setup | scene_initialized, cameras_configured, sequence_configured |
| `unreal.render-execute` 1 | render-execute | scene_setup, camera_setup, sequence_setup, render_setup | scene_initialized, cameras_configured, sequence_configured, render_configured |
| `unreal.artifact-validate` 1 | artifact-validate | scene_setup | scene_initialized |

Six distinct names. `(entry_name, entry_version)` MUST be a **declared pair** in this table; each field being
individually valid is not sufficient.

## IV.3 Reconciliation behaviour (each condition has exactly one token)

| Condition | Behaviour | Token |
|---|---|---|
| missing invariant (task set ⊋ plan union) | refuse before evaluation | `INCOMPLETE_REQUIRED_INVARIANT_SET` |
| extra invariant (plan union ⊋ task set) | refuse before evaluation | `EXTRA_PLAN_VERIFICATION_REQUIREMENT` |
| unknown invariant (outside the closed vocabulary of the declared pair) | refuse before evaluation | `EXPECTATION_VOCABULARY_MISMATCH` |
| duplicate — task side | impossible by construction (`frozenset`; `_check_tokens` refuses duplicates) | construction error (M12.1/M12.3) |
| duplicate — registry side (two definitions for one name) | registry-integrity refusal at load-and-validate + startup test | `EXPECTATION_DEFINITION_DUPLICATE` |
| reordered invariant | semantically irrelevant: canonical sets and all digests use the sorted tuple | none — property-tested |
| unsupported invariant (canonical name, no `REGISTERED` definition) | refuse; all required invariants `UNKNOWN` | `EXPECTED_VALUE_UNAVAILABLE` |
| plan step not a canonical fragment id | refuse before evaluation | `PLAN_STEP_NOT_CANONICAL` |
| required set empty | refuse | `EMPTY_REQUIRED_INVARIANT_SET` |

**No third synonym may be introduced** for any row above. Measured basis for `PLAN_STEP_NOT_CANONICAL`: a task
with `dependencies = ["scene_setup", "totally_unregistered_fragment"]` normalizes, generates a plan carrying
that step (with empty requirements), and passes the verifier with no refusal; `plan_id` carries the unknown id.

---

# PART V — EXPECTATION AUTHORITY

## V.1 Authority classes (R2 scope)

| Class | Safe? | Admissible? | Conditions |
|---|---|---|---|
| `CODE_CONSTANT` | SAFE | **ADMISSIBLE but empty** (no reviewed production constant exists — V.6/XVIII) | reviewed literal in code; reviewed constant digest; Domain-A value |
| `FROZEN_CONTRACT_DERIVATION` | SAFE only in the restricted form | **NOT ADMITTED IN R2 — reserved** (decision; no longer a reviewer question). It is *not* a legal `authority_class` value for any R2 definition (the R2 domain is exactly `{CODE_CONSTANT}`, VIII.2), because every derivable candidate today is schema-forced or payload-fidelity (V.3). A definition carrying it is a registry-integrity failure at **S2 / `AUTHORITY_ABSENT`** (`REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED`, XV row 33). Admission requires an explicit design-gate revision that states the restricted form, the reviewed digest and the minimal-difference witnesses | beyond R2: pure, total, code-authored rule over the reconstructed frozen tree; no caller input; `definition_id` + reviewed digest + witnesses |
| `M5_RECORD_FIELD` | — | **DEFERRED — removed from R2 scope** | render evidence is owned by the M12.5 render path; it is **not** an M12.6 expectation source |
| `CALLER_FIELD` (task/plan/request/metadata/parameters/catalog snapshot/mapping) | UNSAFE | **REMOVED — never registrable** | — |

## V.2 Which task/catalog fields may supply an expected value

**None, with one bounded set of typed target-specification inputs**: `task_class` and
`target_state.expects_render` (render limb only). Identity/lookup keys (`canonical_task_id`, `task_version`,
`catalog_entry_name`, `catalog_entry_version`, fragment ids, `source_content_digest`, `plan_content_digest`) are
identity, never values. `digital_twin_id` is neither a value nor a selector. Everything else
(`target_state.description`, `metadata.*` incl. `parameters`/`catalog_entry`/`fragments`/`catalog_version`,
`provenance.*`, `task_name`, `intent`, `allowed_mutations`, evidence/action arguments, plan and step
provenance) is **forbidden**, enforced by an AST/data-flow allowlist test.

## V.3 Derivation cannot rescue the empty set

Measured: schema-forced facts are vacuous (`world_type`, `selection_provenance`, `is_partitioned_world`, level
`loaded`/`visible`, exactly one persistent level, `slot_count == len(slots)`, mesh/parent shape rules,
ordering/uniqueness, material-class dedup, `omitted.count ≥ len(classes)`, derived `extraction_kind`, non-empty
`actors` for the actor kind); the four non-schema-forced cross-references (actor level containment, world vs
persistent-level path, bound-parent entity presence, unbound-parent path presence) are discriminating but
**payload-fidelity**, and MUST NOT be registered under a production invariant name: the vocabulary is
name-pinned, so doing so would make `semantic_state = SATISFIED` readable as production verification — a
deceptive positive.

Because no derivable candidate is registrable, the **class itself is not admitted in R2** (V.1, VIII.2): the
R2 `authority_class` domain is the single value `CODE_CONSTANT`, and carrying the reserved value is refused at
**S2 / `AUTHORITY_ABSENT`** (`REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED`). This closes the Part XXII question
without leaving an OPEN recommendation.

## V.4 Production-target selection (D1) — normative rule

**MUST.** The production target is selected by a code-level, reviewed, closed mapping — a **single-valued
partial lookup over the closed reviewed target table** — from the task's closed selector triple:

```text
entry_name    := task.canonical_task_id     MUST be a name in the Part IV.2 vocabulary
entry_version := task.task_version          MUST form a DECLARED PAIR with entry_name in Part IV.2
task_class    := task.task_class            MUST be in the closed task-class vocabulary

PRODUCTION_TARGET_BY_TASK[ (entry_name, entry_version, task_class) ] -> production_target_id
```

1. **Caller value authorship is eliminated.** The caller MUST NOT provide `production_target_id`, any target
   field, or any expected value. No parameter, field, or channel for them exists.
2. **Caller selection among code-approved targets remains** — and is bounded exactly as the caller's selection
   of the required invariant set already is (both are closed-vocabulary selection among code-reviewed
   options). The Revision-2 claim that caller selection is "eliminated" is **withdrawn**.
3. **Single-valued partial lookup (not a total function).** The table is a **partial lookup over the closed
   reviewed key space**: at most one row per `(entry_name, entry_version, task_class)` triple, and **not every
   admitted triple need have a row**. A **duplicate row** MUST deterministically refuse at load-and-validate:
   `PRODUCTION_TARGET_MAPPING_DUPLICATE` (stage S2, `AUTHORITY_ABSENT`, with a startup test). A **missing row**
   MUST deterministically refuse at resolution: `PRODUCTION_TARGET_NOT_ESTABLISHED` (stage S4,
   `AUTHORITY_ABSENT`). Ambiguity is structurally impossible; partiality is explicit and is resolved by refusal,
   never by a default, a fallback, a nearest match, or a caller-supplied substitute.
4. **The normative semantic claim (MUST be stated in the landed artifact and in every definition's
   `non_claim`):**
   > `SATISFIED` means: the evaluated observation satisfies the production target specification selected by the
   > supplied task content and approved by the reviewed code target table.
5. **Prohibited interpretations (each MUST be stated):** M12.6 does **not** establish that the selected target
   was **appropriate**, **intended**, **authorized**, or **requested by an authorized actor**. Those remain
   `NOT_ESTABLISHED`.
6. **Digital-twin identity is never the missing authority.** `digital_twin_id` MUST NOT be used as the
   selector, as the substitution for a task↔target binding, or as any part of the claim (Part XIII).
7. **Target identity is bound (MUST).** `production_target_id`, `target_revision`, `target_digest` and
   `target_table_digest` participate in the expectation identity tuple, in the expectation digest and in the
   result; a `SATISFIED` result lacking them is a validation error (XIV.2).
8. **Future strengthening (recorded, not implemented).** If a reviewed task↔target binding or a Q10-class
   resolution binding later exists, the claim MUST be narrowed further ("… and authorized by the binding").
   M12.6 MUST NOT pre-empt it.

### V.4.9 Rung ownership of the target-selection machinery (MUST — decision, not a choice)

- **R2-A implements the lookup machinery**: the closed key derivation, the
  `PRODUCTION_TARGET_BY_TASK` **single-valued partial lookup**, the duplicate-row integrity check
  (`PRODUCTION_TARGET_MAPPING_DUPLICATE`), the reviewed-digest revalidation
  (`PRODUCTION_TARGET_NOT_CANONICAL`, `TARGET_TABLE_DIGEST`), and the deterministic
  **`PRODUCTION_TARGET_NOT_ESTABLISHED`** refusal for a missing row — **against an empty reviewed target table
  (zero entries)**. With zero entries every lookup deterministically refuses, so R2-A can never resolve a target
  and never reaches evaluation.
- **R2-B owns authority population**: authoring and reviewing the target entries, their `source_reference`,
  `target_digest` and the table digest, and everything downstream of a resolved target (positive semantic
  verification, the witnesses of Part XVIII).
- **MUST NOT** be deferred to R2-B: the lookup algorithm, the key derivation, the integrity and digest checks,
  and the refusal token. **MUST NOT** be attempted in R2-A: any target value, any `source_reference`, any
  inference of a target from the harness fixture, `digital_twin_id`, a task class, or a test constant.

## V.5 Production-target table — structure and trust boundary

```text
ProductionTargetSpec (frozen, sealed, closed)
  production_target_id           : str    # code constant; never caller-supplied
  target_revision                : int    # >= 1
  world_package_path             : str    # reviewed constant (Domain A string)
  persistent_level_package_path   : str    # reviewed constant
  required_entity_ids            : tuple[str, ...]        # canonical entity grammar, sorted, non-empty
  required_entity_classes        : tuple[tuple[str, str], ...]  # (entity_id, actor_class) reviewed constants
  planned_sequence_asset_path    : str | None   # design intent ONLY — never compared to any render record
  source_reference               : str    # the reviewed human artifact that fixes these values
  target_digest                  : str    # reviewed constant over this entry's canonical form minus itself
  non_claim                      : str
TARGET_TABLE_DIGEST : str   # reviewed constant over the ordered entries with per-item digests
```

| Question (adjudication A1) | Ruling |
|---|---|
| Who reviews target definitions? | The human repo/design review process, with a gate of its own: the table decides semantic truth and MUST NOT arrive inside an implementation PR. |
| Where do they live? | **Code-level constants** in `planning/m12/expectation.py` (a closed module-level `tuple` of frozen, sealed dataclasses). **Not** configuration, **not** environment, **not** a runtime-loadable data file. |
| How is content committed? | Per-entry `target_digest` and table-level `TARGET_TABLE_DIGEST`, both reviewed constants, both recomputed from the code objects. |
| How is substitution detected? | In-call digest recomputation plus identity equality of `production_target_id` and `target_revision`; a different derived id ⇒ `EXPECTATION_IDENTITY_MISMATCH`. |
| Is runtime mutation in scope? | **As detection, yes; as prevention, no.** Python cannot prevent in-process mutation (VIII.4). |
| Does the resolver revalidate? | **Yes, on every call**, from the same objects it is about to use; it MUST NOT cache a validated copy. |
| Is detection sufficient? | Sufficient against accidental/defective mutation, a benign caller, and any actor without in-process code execution. **Not** sufficient against an adversary with arbitrary in-process execution — `OUT OF SCOPE` as a prevention goal. |
| Prevention vs detection vs trusted process | The stated property is **"revalidated against a reviewed constant digest"** plus **"no caller-reachable runtime write path"**. The word **"immutable" MUST NOT be used** for the target table or the registry. The trusted-process assumption (the M12 line runs inside the Atlas process beside its own authority modules) MUST be recorded. |

### V.5.1 Rung ownership of the table itself (MUST)

The table **structure** (V.5) plus the lookup machinery (V.4.9) land in **R2-A**; the table **content**
(reviewed entries with values and `source_reference`) lands in **R2-B** and only after its own review gate.
R2-A therefore ships a **fully implemented, empty** `PRODUCTION_TARGETS` / `PRODUCTION_TARGET_BY_TASK`, whose
digests still recompute (`TARGET_TABLE_DIGEST` over an empty ordered tuple) and whose every lookup refuses with
`PRODUCTION_TARGET_NOT_ESTABLISHED` (stage S4, `AUTHORITY_ABSENT`).

## V.6 Production-target status (MUST be recorded)

**No authoritative reviewed production-target artifact exists in the repository.** Therefore:
the table **structure** may be specified (V.5) and implemented; **target values MUST remain absent/deferred**;
no invariant may become `REGISTERED`; and expectation resolution **MUST refuse** wherever target authority is
unavailable (`PRODUCTION_TARGET_NOT_ESTABLISHED`) or wherever a required invariant lacks a `REGISTERED`
definition (`EXPECTED_VALUE_UNAVAILABLE`). **No target value may be fabricated** — not by inference from the
harness fixture, not from `digital_twin_id`, and not from any test constant.

---

# PART VI — M12.4 RUNTIME MAPPING

**DECIDED: the `UnrealRuntimeMapping` MUST NOT become a semantic expectation authority.** Six source-grounded
reasons: it is a caller-facing producer; `semantic_fidelity = "aggregate"` with `runtime_task_snapshot = None`
for render-bearing plans; it is optional on the consumed path (its guards dissolve when it is optional); it is a
second reconciliation point for the required set; it carries `declared=True` (verbatim caller) content; and it
closes the forbidden cycle `task → plan → mapping → expectation → task`.
**Permitted role:** `runtime_mapping_digest` as a carried disclosure only; no rule may read it; the resolver
MUST receive no mapping. A test MUST assert that supplying, omitting, or mutating a mapping changes no
expectation field, no digest, and no verdict.

---

# PART VII — EXPECTATION RESOLVER (D2 + D3)

## VII.1 Contract

```text
planning/m12/expectation.py
  resolve_semantic_expectation(
      *, source_task: UnrealProductionTaskDefinition, plan: UnrealExecutionPlan
  ) -> UnrealSemanticExpectation | SemanticExpectationRefusal

  compute_plan_content_digest(plan: UnrealExecutionPlan) -> str   # the ONLY plan-digest entry point
  compute_source_content_digest(...)                              # M12.3's, called unmodified
```

Exactly one object is returned. Semantic conditions are **values, not exceptions**. No fallback, no default, no
partial object, no `None`.

## VII.2 Accepted types and fields (exhaustive)

- `source_task` MUST be an **exact** `UnrealProductionTaskDefinition`; `plan` MUST be an **exact**
  `UnrealExecutionPlan` (`type(x) is ...`; no duck typing, no proxies, no subclasses).
- Fields read from the task: `canonical_task_id`, `task_class`, `task_version`, `digital_twin_id`,
  `target_state.invariant_names`, `target_state.expects_render`, and the JSON-compatible form for
  `source_content_digest` (M12.3's recipe, called unmodified).
- Fields read from the plan: `plan_id` (**provenance only**), `source_task_id`, `source_task_version`,
  `digital_twin_id`, `source_content_digest`, `steps[*].semantic_operation`,
  `steps[*].verification_requirements`, `render_plan`, and the JSON-compatible form for
  `plan_content_digest` (X.2).
- **`catalog_version` MUST NOT be semantically consumed** (III.2). It is not read by name, not validated, not
  compared, not a selector, and not an input to any semantic decision; it is only traversed as opaque structure
  and committed transitively through M12.3's unmodified recipes (III.3, X.2).
- **`digital_twin_id` is read only for the expectation identity/provenance** — never as an expected value and
  never as a target selector (V.4.6, Part XIII).

## VII.3 Forbidden inputs and the read-for-a-purpose rule

Forbidden as parameters and as **semantic** reads: any observation, request or response;
`UnrealRuntimeMapping` or any mapping digest; any `expected*` / `expectation*` / `verified` / `semantic_state` /
`target_satisfied` value; catalog objects; `catalog_version` (semantically — III.2); `metadata.*` and
`provenance.*` (semantically); `target_state.description`; evidence/action arguments; filesystem, environment,
clock, RNG, network, model output; any `planning.unreal_*` import other than the two type imports.

**Read-for-a-purpose rule (MUST).** M12.6 **semantically consumes** a field only if that field either
(a) participates in a declared semantic comparison, or (b) participates in a declared identity or digest binding.
Every other read is prohibited as a semantic read — **including reads performed "only for structural
validation"**.

**Structural traversal is not semantic consumption (reconciliation, MUST).** The structural preflight (VII.4) and
the digest projections (X.2, XI.4) traverse supplied content as **opaque structure**. Such traversal is permitted
and does not violate this rule, because it is:

1. **content-wide** — one uniform predicate applied to every node, independent of any field's name or meaning;
2. **name-blind** — it performs no key lookup other than the declared top-level key set, and MUST NOT look up,
   detect, branch on, or compare any particular nested key;
3. **value-neutral** — it performs no value comparison and derives nothing from any value;
4. **verdict-only** — its sole outcome is structural validity, or a refusal with a category F1–F9.

Traversal MUST NOT be used to smuggle a semantic read of `metadata`, `provenance`, parameters, or
`catalog_version` (for example by detecting a specific key or value shape).

## VII.4 Structural preflight (MUST, before any canonicalization)

The resolver validates both supplied objects against a **closed structural preflight schema**. The preflight runs
**before** any canonicalization and MUST NOT call the serializer, the canonicalizer, or `deepcopy`.

**VII.4.1 Declared checks (each maps to exactly one category).**

1. exact expected type (F1);
2. closed attribute set; no missing attribute; no undeclared top-level key in the JSON-compatible projection (F2);
3. exact scalar types and domains — `bool` **excluded** from integer domains; `task_version` /
   `source_task_version` ≥ 1; `source_content_digest` a 64-character lowercase hex string (F3);
4. JSON-compatible nested content only — `str`/`bool`/`int`/`float`/`None`/mapping/sequence; **no** `set`,
   `bytes`, `bytearray`, arbitrary object, `complex`, or non-string mapping key (F4);
5. no non-finite float (`NaN`, `±Inf`) (F5);
6. bounded traversal — nesting depth ≤ 20 with the root at depth 0, **and** a total-node budget of
   **100,000** visited nodes (module constant `PREFLIGHT_NODE_BUDGET = 100_000`) (F6);
7. lone-surrogate handling and UTF-8 encodability (F7);
8. integer-to-decimal convertibility in the pinned runtime (F8);
9. non-empty / duplicate-element constraints where the closed schema requires them (F9);
10. the declared top-level key set equals the projection's top-level key set (F2).

**VII.4.2 Bounded traversal (MUST).**

- **Accepted container types.** The traversal descends into `dict` (string keys only) and into `list` and
  `tuple`; scalars (`str`, `bool`, `int`, `float`, `None`) are leaves. Any other node type is **F4**.
- **Termination.** Traversal MUST be bounded by **both** the depth bound and the total-node budget
  (`PREFLIGHT_NODE_BUDGET = 100_000` visited nodes); the bounds are what guarantee termination. **Cycles** are
  therefore handled by the bound: a cyclic structure (reachable only
  from a hand-mutated supplied object, since M12.1/M12.3 build fresh acyclic projections) MUST terminate at the
  bound and be refused as **F6**. An implementation **MAY** additionally detect a repeated container identity on
  the current path and refuse it as **F6** — the same token and category, so no new category or token exists for
  cycles.
- **No serializer calls.** The preflight MUST NOT invoke `json.dumps`, the Domain-B canonicalizer, Domain-A
  canonicalization, or `deepcopy`. Nothing is serialized until the preflight has passed.
- **Exception attribution (MUST).** Every inspection of supplied content is guarded, and any exception raised
  **while inspecting supplied content** — including hostile container behaviour such as a `dict` subclass whose
  `items()`/`__iter__`/`__getitem__`/`__len__` raises, or a malformed object that cannot be inspected — is
  **attributed to the supplied input** and MUST be classified **F4**. It MUST NOT be reported as
  `RESOLVER_INTERNAL_FAILURE`.
- **No independent key consumption.** The traversal never looks up a nested key by name and never compares a
  value (VII.3); it evaluates one uniform predicate over every node.

**VII.4.3 Failure token.** Every failure above returns **`RESOLVER_INPUT_STRUCTURE_INVALID`** carrying
`detail_category ∈ {F1, F2, F3, F4, F5, F6, F7, F8, F9}` and reason class `BINDING_ABSENT`. Categories are values
of **one** token and MUST NOT become separate refusal tokens.

| Category | Condition |
|---|---|
| **F1** | exact type — not the expected type (subclass, proxy, duck-type) |
| **F2** | undeclared or missing field / top-level key-set mismatch |
| **F3** | scalar type or value domain (incl. `bool` where `int` is required; version < 1) |
| **F4** | non-canonicalizable, unsupported, or **uninspectable** value (`set`, `bytes`, object, `complex`, non-string key, inspection raising) |
| **F5** | non-finite float (`NaN`, `±Inf`) |
| **F6** | bounded traversal exceeded — depth > 20, node budget exceeded (> 100,000 visited nodes), or a cycle caught by the bound |
| **F7** | lone surrogate or non-UTF-8-encodable string |
| **F8** | integer not convertible to decimal in the pinned runtime |
| **F9** | empty or duplicate element where a non-empty unique sequence is required |

**VII.4.4 Scope of F2 versus `EXPECTATION_INCOMPLETE` (MUST).** F2 applies to the **task/plan** projections.
For the **expectation** object, closed-schema failures (declared member set, count/name correspondence, tuple
ordering/uniqueness) are reported as `EXPECTATION_INCOMPLETE`, while its value-content structural failures are
reported as `RESOLVER_INPUT_STRUCTURE_INVALID` with the corresponding F category (XIV.5). The two tokens apply to
different objects and MUST NOT be used for each other's object; both are `BINDING_ABSENT`.

## VII.5 Attribution: structural failure vs internal failure (MUST)

- **`RESOLVER_INPUT_STRUCTURE_INVALID`** is the **only** outcome for malformed supplied content, including
  hostile container behaviour: any exception raised **while inspecting supplied content** is attributed to the
  supplied input and MUST be classified by its category (F4 for uninspectable values). It is decided **before**
  any serializer, canonicalizer or `deepcopy` call, which the preflight MUST NOT make.
- **`RESOLVER_INTERNAL_FAILURE`** (reason class `INTERNAL_FAILURE`, `overall_state = UNKNOWN`) is **reserved**
  for faults **not attributable to malformed supplied input**: an exception raised by M12.6's own code, or by a
  code-level authority source (registry or target table), after the preflight has passed. It MUST NOT be emitted
  for any preflight failure, and the two tokens MUST NOT be used interchangeably.
- The canonicalization pipeline is additionally guarded so that no failure can escape as an exception; but any
  such guard exists only as a backstop. `INTERNAL_FAILURE` is **not** a semantic classification: it satisfies no
  acceptance criterion, it is reachable only by fault injection, and **its appearance in any gate or live record
  is itself a defect** and MUST be reported as one.

## VII.6 Nested mutation — the three distinct cases (MUST NOT be conflated)

| Case | Classification | Token / class |
|---|---|---|
| malformed exact-type content (a `set` in `provenance`, non-string key, `NaN`, opaque object, depth, lone surrogate, over-long integer, empty/duplicate element) | **structural invalidity of a supplied artifact** | `RESOLVER_INPUT_STRUCTURE_INVALID` (F1–F9), `BINDING_ABSENT` |
| structurally valid content that disagrees with what was committed (e.g. `verification_requirements` edited so the plan content digest no longer recomputes) | **identity mismatch between supplied artifacts** | `IDENTITY_MISMATCH` / `EXPECTATION_IDENTITY_MISMATCH`, `BINDING_ABSENT` |
| mutation of a **code-level authority table** (registry, target table) | **authority not canonical** | `REGISTRY_SOURCE_NOT_CANONICAL` / `PRODUCTION_TARGET_NOT_CANONICAL`, `AUTHORITY_ABSENT` |

## VII.7 Totality (normative statement)

> `resolve_semantic_expectation` is **total over the closed typed AND structurally valid input domain**: for
> every `(source_task, plan)` pair that (a) satisfies the exact-type preconditions and (b) passes the structural
> preflight of VII.4, the function returns an expectation or a refusal and **never raises**. For any exact-type
> pair that fails the preflight it returns `RESOLVER_INPUT_STRUCTURE_INVALID` and **never raises**. Totality over
> arbitrary Python objects is **NOT CLAIMED**: an input that is not of the two exact types is refused
> (`RESOLVER_INPUT_STRUCTURE_INVALID`, category F1), not accepted and not raised upon.

## VII.8 Properties (each property-tested)

`PURE` · `TOTAL (as defined in VII.7)` · `DETERMINISTIC (XI)` · `OBSERVATION-BLIND` · `VALUE-CALLER-BLIND` ·
`NO-IO` · `NO-PERSISTENCE` · `NO-ENGINE` · `NO-VERDICT` · `NO-RENDER` · `NO-DYNAMIC-REGISTRY` · `FAIL-CLOSED`
(monotone: ambiguity can only move the outcome toward refusal) · `IDEMPOTENT`.

## VII.9 Stage scope (how the resolver and verifier share one pipeline)

The stage order of XIV.4 applies to the **whole pipeline**. The resolver executes S1–S4 over
`(task, plan, code constants)` and returns an expectation or a refusal. The verifier, receiving an expectation
as an **untrusted input**, re-executes S1–S4 in **revalidation mode** (structural validity of the supplied
expectation, code-level revalidation, identity/digest binding, coverage) before S5–S6. One stage order, one
discriminator, one token per condition — for both components.

---

# PART VIII — CLOSED REGISTRY / DEFINITIONS

## VIII.1 Module constants

```text
EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"
RESOLVER_REVISION             = "m12.6-resolver-v1"
REGISTRY_REVISION             = 1
TARGET_TABLE_REVISION         = 1
SEMANTIC_INVARIANT_DEFINITIONS : tuple[SemanticInvariantDefinition, ...]   # sorted by invariant_name
EXPECTATION_VOCABULARY         : tuple[EntryVocabulary, ...]               # sorted by (entry_name, entry_version)
PRODUCTION_TARGET_BY_TASK      : tuple[TaskTargetMapping, ...]             # sorted by (name, version, class)
PRODUCTION_TARGETS             : tuple[ProductionTargetSpec, ...]          # sorted by production_target_id
REGISTRY_SOURCE_DIGEST         : str   # reviewed constant
TARGET_TABLE_DIGEST            : str   # reviewed constant
```

Every table is a `tuple` of frozen, sealed dataclasses whose every field is an immutable value type
(`str`/`int`/`bool`/`None`/`tuple`), so no nested mutable container exists to mutate.
`EntryVocabulary`: `entry_name`, `entry_version`, `task_class`, `fragment_ids`, `invariant_names`,
`parameter_names`, `parameter_kinds`, `vocabulary_digest`.
`TaskTargetMapping`: `entry_name`, `entry_version`, `task_class`, `production_target_id`.

## VIII.2 Definition schema

| Field | Type | Requirement |
|---|---|---|
| `invariant_name` | `str` | exact match against IV.2; unique in the table |
| `definition_revision` | `int ≥ 1` | bumped on any semantic change |
| `definition_status` | `str` | `REGISTERED` \| `DEFERRED`; `DEFERRED` behaves exactly as unregistered |
| `authority_class` | `str` | **`CODE_CONSTANT` only in R2** (single-value domain; the reserved `FROZEN_CONTRACT_DERIVATION` is **not admitted in R2** — V.1/V.3/XV row 33 — and any definition carrying it fails load-and-validate with `REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED` at S2 / `AUTHORITY_ABSENT`) |
| `observable_paths` | `tuple[str, ...]` | exact paths in the frozen tree, sorted, non-empty |
| `subject_scope` | `tuple[str, ...]` | canonical entity ids that must be present, sorted, non-empty where entity-scoped |
| `comparison` | `str` | `EQUALS` \| `SET_EQUALS` \| `CONTAINS_ALL` \| `EXACTLY_ONE` \| `SUBSET_OF` |
| `admissible_value_type` | `str` | `STR` \| `INT` \| `BOOL` \| `STR_SET` (never floats) |
| `expected_value_source` | `str` | `TARGET_FIELD` \| `CODE_CONSTANT` |
| `expected_value` | closed union (Domain A) | reviewed literal, or `{"$target_field": "<field>"}` resolved through the derived target entry |
| `target_binding` | `str` | `PRODUCTION_TARGET` \| `NONE` |
| `missing_behavior` / `unsupported_behavior` | `str` | fixed `"UNKNOWN_EVIDENCE_INSUFFICIENT"` (defined below) |
| `definition_digest` | `str` | SHA-256 over the Domain-A canonical form minus itself |
| `witness_positive` / `witness_negative` / `witness_lossy` | `WitnessRef` | all three REQUIRED for `REGISTERED` (Part XIX) |
| `non_claim` | `str` | the sentence stating what `SATISFIED` does not mean for this invariant |

`WitnessRef`: `ref`, `expected_state` (an `invariant_state`), `expected_code` (`str | None`), `dimension`
(the single varied dimension).

**`UNKNOWN_EVIDENCE_INSUFFICIENT` (declared constant, defined here exactly once).** The fixed value of the two
behaviour fields above. It means: the invariant resolves to `invariant_state = UNKNOWN` with reason class
`EVIDENCE_INSUFFICIENT`. It is a **definition-field constant** — it is *not* a refusal token and *not* a reason
class, and it MUST NOT appear in `failure_codes`. The only reason class with a similar name is
`EVIDENCE_INSUFFICIENT`, and the two MUST NOT be used interchangeably.

## VIII.3 Table integrity and mutation (normative wording)

The stated property is: **"code-level closed constant tables whose content is revalidated against reviewed
constant digests on every resolution, and which expose no caller-reachable runtime write path."** The word
**"immutable" MUST NOT be used** for either table. Four testable conditions: (1) immutable value-type fields
only; (2) no accessor returns a live table object and no mutable re-export exists; (3) revalidation happens in
the same call, from the same objects, by recomputing and comparing digests
(`REGISTRY_SOURCE_NOT_CANONICAL` / `PRODUCTION_TARGET_NOT_CANONICAL`); (4) revisions and digests are carried
into every expectation and result, so a change invalidates prior expectations by construction. A module-level
`dict` plus an intention not to mutate it satisfies none of these (measured contrast: `REGISTERED_INVARIANTS`
is a runtime-mutable `dict` read by nothing).

## VIII.4 Registry-integrity tokens

| Condition | Token | Reason class |
|---|---|---|
| two definitions for one `invariant_name` | `EXPECTATION_DEFINITION_DUPLICATE` | `AUTHORITY_ABSENT` (code-level **authority-table integrity**, stage **S2**, at load-and-validate, with a startup test) |
| two mapping rows for one `(entry_name, entry_version, task_class)` triple | `PRODUCTION_TARGET_MAPPING_DUPLICATE` | `AUTHORITY_ABSENT` (code-level **authority-table integrity**, stage **S2**, at load-and-validate, with a startup test) |

A third registry-integrity row applies to the class domain (V.1, VIII.2):

| Condition | Token | Reason class |
|---|---|---|
| a definition carries an authority class not admitted in R2 (the reserved `FROZEN_CONTRACT_DERIVATION`) | `REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED` | `AUTHORITY_ABSENT` (code-level **authority-table integrity**, stage **S2**, at load-and-validate, with a startup test) |

All three rows are **authority-table integrity** failures and therefore `AUTHORITY_ABSENT` at stage **S2**
(XIV.3); none is a supplied-artifact failure and none may be classified `BINDING_ABSENT`. The reviewed-constant
digest revalidation (`REGISTRY_SOURCE_NOT_CANONICAL`) remains an independent second line of defence for the same
condition and neither check may be omitted. A **missing** row is not a
duplicate and is not an integrity failure: a missing target row is a **coverage** failure at stage **S4**
(`PRODUCTION_TARGET_NOT_ESTABLISHED`), and a canonical invariant name with no `REGISTERED` definition is a
coverage failure at stage **S4** (`EXPECTED_VALUE_UNAVAILABLE`).

These are distinct tokens for distinct tables (different objects), **not** synonyms; no other duplicate-rule
token may be added.

## VIII.5 Python-level mutation — explicit scope

- **Prevented: nothing, in-process.** `object.__setattr__`, attribute rebinding, `sys.modules` substitution and
  `importlib.reload` are all possible.
- **Detected (MUST):** any content change to the definitions / vocabulary / mappings / targets the resolver
  reads ⇒ digest mismatch ⇒ refusal. No validated copy may be cached.
- **`OUT OF SCOPE` as a prevention goal:** an adversary with arbitrary same-process code execution (who could
  equally patch the resolver, the verifier, or `hashlib`). The boundary is the process plus the authority
  contracts; this statement MUST appear in the landed artifact rather than implying that `frozen=True` is
  integrity.

---

# PART IX — EXPECTATION SCHEMA

Closed; **no extension bag, no undeclared field, no free-form semantic metadata**; undeclared fields are
**refused**, never ignored.

| Field | Type | Canonical form | Identity significance | Digest participation | Authority source | Mutability |
|---|---|---|---|---|---|---|
| `expectation_contract_revision` | `str` | Domain A string | identity (shape) | in | code constant | value-immutable |
| `resolver_revision` | `str` | Domain A string | identity | in | code constant | value-immutable |
| `registry_revision`, `registry_digest` | `int`, 64-hex | Domain A | identity | in | recomputed+compared | value-immutable |
| `target_table_revision`, `target_table_digest` | `int`, 64-hex | Domain A | identity | in | recomputed+compared | value-immutable |
| `production_target_id`, `target_revision`, `target_digest` | `str`, `int`, 64-hex | Domain A | identity (**selected target**) | in | **derived** (V.4) | value-immutable |
| `task_identity`, `task_version` | `str`, `int` | Domain A | identity | in | task | value-immutable |
| `digital_twin_id` | `str` | Domain A | **provenance — never a claim, never a selector** | in (as provenance) | task | value-immutable |
| `catalog_entry_name`, `catalog_entry_version` | `str`, `int` | Domain A | identity (vocabulary key; declared pair) | in | validated against IV.2 | value-immutable |
| `vocabulary_digest` | 64-hex | Domain A | identity | in | code constant | value-immutable |
| `source_content_digest` | 64-hex | lowercase hex | identity (only task content commitment) | in | M12.3's recipe, unmodified | value-immutable |
| `plan_id` | `str` | Domain A string | **PROVENANCE ONLY** (X.1) | in (as provenance) | plan | value-immutable |
| `plan_content_digest` | 64-hex | lowercase hex | identity (plan content commitment) | in | recomputed (X.2) | value-immutable |
| `render_task` | `bool` | Domain A bool | identity (comparison input) | in | derived from the task's authoritative class, compared to the plan | value-immutable |
| `required_invariant_names` | `tuple[str, ...]` | sorted, unique, non-empty | identity (the required set) | in | task target state, vocabulary-validated | value-immutable |
| `invariant_expectations` | `tuple[InvariantExpectation, ...]` | sorted by name; exactly one per required name | identity | in | resolver | value-immutable |
| `origin_status` | `str` | fixed `"NOT_ESTABLISHED"` | **none — constant; MUST NOT vary in any digest and MUST NOT be branched on** | in (as a constant) | Part II.3 | value-immutable |
| `expectation_digest` | 64-hex | lowercase hex | identity | over the object **excluding itself** | resolver | value-immutable |

**`catalog_version` is not a field** and MUST NOT be added.

`InvariantExpectation` (frozen, sealed, closed): `invariant_name`, `authority_class`, `definition_id`,
`definition_revision`, `definition_digest`, `observable_paths`, `subject_scope`, `comparison`,
`admissible_value_type`, `expected_value`, `value_digest`, `target_binding`, `target_revision` (nullable),
`non_claim`.

**Rejection rules (each with exactly one token).** Undeclared field, missing declared field, or empty/duplicate/
unsorted tuple ⇒ `EXPECTATION_INCOMPLETE`; empty required set ⇒ `EMPTY_REQUIRED_INVARIANT_SET`; count/name
mismatch between `required_invariant_names` and `invariant_expectations` ⇒ `EXPECTATION_INCOMPLETE`; two entries
for one name ⇒ `EXPECTATION_DEFINITION_DUPLICATE`; digest mismatch ⇒ `EXPECTATION_DIGEST_MISMATCH`; value type
not permitted by the definition ⇒ `EXPECTATION_CONTRADICTORY`; float, authority-shaped key, or non-Domain-A
value ⇒ `RESOLVER_INPUT_STRUCTURE_INVALID` with the corresponding F category (XIV.5); a variable
`origin_status` ⇒ `EXPECTATION_CONTRADICTORY`.
An expectation whose identity does not recompute from the supplied `(task, plan, code constants)` is refused —
a fabricated expectation is unusable **because it cannot match**: this is the load-bearing consequence of
resolver purity, and it is the reason the expectation may be treated as an untrusted input.

---

# PART X — PLAN IDENTITY AND THE SINGLE PLAN-CONTENT DIGEST RECIPE

## X.1 `plan_id` is provenance (not a commitment)

Measured: `_build_plan_id` binds source task id, source task version, the ordered fragment ids and a **48-bit
prefix** of the source-content digest; it does **not** bind step content (after an in-memory fragment mutation a
regenerated plan carried different `verification_requirements` with a byte-identical `plan_id`). `plan_id`
MUST therefore be carried as **provenance only** and MUST NOT be used as a content commitment.

## X.2 The recipe (singular, normative)

```text
canonical input : plan.to_json_compatible()        (the FULL canonical document)
canonicalizer   : planning.m12.execution_plan._canonical_bytes / _canonical_sha256   (Domain B, XI.2)
byte sequence   : the canonicalizer's output bytes — UTF-8, no BOM, no trailing newline
encoding        : UTF-8
hash            : SHA-256, lowercase hex
exact call      : plan_content_digest = execution_plan._canonical_sha256(
                      plan.to_json_compatible(), "execution_plan")
implementation  : ONE function, planning/m12/expectation.py::compute_plan_content_digest(plan) -> str
```

1. **Full-document commitment, no exclusions.** The digest input is the whole canonical document, exactly as
   M12.3 defines it. **No key is excluded**, and no subset, projection, field list or alternative form may be
   substituted. `catalog_version` is therefore inside the commitment — a **permitted transitive effect**
   (III.2/III.3), not a semantic read and not a hidden dependency.
2. **One call site.** The resolver's identity construction, the verifier's revalidation and every test MUST call
   that one function; inlining a re-derivation is a defect, and an AST test MUST assert exactly one call site.
3. **Ordering.** Mapping keys are sorted by the canonicalizer (order-irrelevant); sequence order is preserved
   (step order and provenance lists are order-**sensitive**, which is intended, because plan step order is
   semantic).
4. **Owner argument.** The canonicalizer's `owner` argument affects only error text, never the digest.
5. **Refusal paths.** A **structurally invalid** plan never reaches this recipe: it is refused earlier as
   `RESOLVER_INPUT_STRUCTURE_INVALID` with its F category (VII.4). A **structurally valid** plan containing a
   `float` is refused here with `PLAN_CONTENT_UNSUPPORTED` (X.3) — that token has exactly this one condition.
6. **Verification.** The digest is recomputed by the resolver at resolution time and by the M12.5 verifier before
   evaluation; a difference ⇒ `EXPECTATION_IDENTITY_MISMATCH`. The digest proves **content identity, not
   authority** (Part II).
7. **Property tests (MUST).** (a) *Variance*: changing `catalog_version` changes `plan_content_digest`, as does
   changing any other plan field; (b) *semantic invariance*: notwithstanding (a), the code and reason class
   produced for the change are exactly those of any other supplied-document content difference
   (`EXPECTATION_IDENTITY_MISMATCH`/`EXPECTATION_DIGEST_MISMATCH`, `BINDING_ABSENT`, S3) — no distinguished path;
   (c) *divergence detection*: the digest equals `sha256(plan.canonical_json().encode("utf-8"))` for a float-free
   plan, asserted as a **divergence detector** and never as a second recipe.

## X.3 `PLAN_CONTENT_UNSUPPORTED` — single condition (MUST)

`compute_plan_content_digest` MUST refuse with **`PLAN_CONTENT_UNSUPPORTED`** in exactly one situation: a
**structurally valid** plan document (one that has passed the preflight of VII.4) that is rejected **solely** by
the deterministic finite-float policy — i.e. the Domain-B projection contains at least one `float`.

Rationale: float serialization is interpreter-dependent (XI.2), no expectation can contain a float (Domain A
refuses floats), and the affected surface is caller-authored `task.provenance` only (measured: provenance floats
reach the plan; `metadata.parameters` floats do not). Reason class `BINDING_ABSENT`; stage S1/S3 boundary as
implemented in the pipeline (a structural refusal of supplied content).

**MUST NOT** be used for any other condition: a plan that is not structurally valid is refused earlier as
`RESOLVER_INPUT_STRUCTURE_INVALID` with its F category and MUST NOT reach this token; a surrogate (F7), an
integer digit-limit failure (F8), an unsupported value type (F4) or a depth/budget failure (F6) are all
preflight refusals and MUST NOT be reported as `PLAN_CONTENT_UNSUPPORTED`.

## X.4 Surrogate hardening (MUST, without modifying M12.3)

Domain B accepts a lone surrogate while Domain A refuses it. M12.6 MUST therefore apply the lone-surrogate
predicate to the task's and the plan's JSON-compatible documents **during the structural preflight**: a lone
surrogate in either document is **F7** ⇒ `RESOLVER_INPUT_STRUCTURE_INVALID` with category F7. It is structural
invalidation of supplied content and MUST NOT be reported as `PLAN_CONTENT_UNSUPPORTED`. M12.3's source-digest
recipe itself MUST NOT be modified (**M12.3 is PRESERVED UNCHANGED**).

# PART XI — CANONICALIZATION AND DETERMINISM (D5)

## XI.1 Domains (two, declared; no third implementation)

| Domain | Primitive | Content | Used for |
|---|---|---|---|
| **A — `EXTRACTION_JCS`** | `unreal_state_extraction.jcs.canonicalize` / `canonical_bytes` (RFC 8785 restricted: UTF-16 code-unit key order; ECMAScript escaping; non-ASCII literal; lone surrogates refused; decimals only with `|n| ≤ 2^53-1`; **floats refused**; UTF-8 no BOM) | fully caller-free, code-authored content | observed-state digest; expectation canonical form; `expectation_digest`, `value_digest`, `definition_digest`, `vocabulary_digest`, `target_digest`, `target_table_digest`, `registry_digest` |
| **B — `M12_STRUCTURAL`** | `execution_plan._canonical_bytes` (via `canonical_json`/`_canonical_sha256`): sorted keys by **code point**, compact separators, `ensure_ascii=True`, `allow_nan=False`, string keys only, depth ≤ 20, finite floats allowed | caller-influenced structural documents | `source_content_digest` (M12.3, unmodified) and `plan_content_digest` (X.2) |
| **FORBIDDEN** | `verification._canonical_digest` (a second implementation with no depth bound and no strict validation); any new helper; `json.dumps` as a canonicalization oracle | — | — |

Measured basis: the two key orders genuinely differ (on RFC 8785's own `weird` vector, JCS orders
`…\u20ac, \U0001f602, \ufb33` while `json.dumps(sort_keys=True)` orders `…\u20ac, \ufb33, \U0001f602`) and the
serializations are not equal — so `json.dumps` cannot serve as an oracle and the domains MUST NOT be compared by
bytes, only by digest. JCS refuses `1.5` and `|n| > 2^53-1`; Domain B accepts both, and caller `provenance`
floats do reach the plan — hence both domains are **required**, not convenient. Domain A MUST adopt depth ≤ 20
so that expectation canonicalization cannot recurse without bound.

## XI.2 Domain B implementation characteristics (MUST be documented; all measured)

| Property | Behaviour |
|---|---|
| key ordering | sorted by code point; insertion order irrelevant (digests equal) |
| separators | compact `(",", ":")` |
| `ensure_ascii` | `True` — non-ASCII escaped as `\uXXXX`; astral characters as surrogate pairs (`"\ud83d\ude02"`) |
| `allow_nan` | `False` — `NaN` and `±Infinity` refused |
| strict JSON validation | `_validate_strict_json`: string keys only, `str`/`bool`/`int`/`float`/`None`/mapping/sequence only, depth ≤ 20, non-finite refused; `bool` distinct from `int` |
| depth | bound 20 (root at depth 0) |
| type rejections | `set`, `bytes`, `bytearray`, arbitrary object, `complex`, non-string key ⇒ deterministic refusal (`UnrealExecutionPlanError`) |
| floats | accepted by Domain B; CPython shortest-repr (`1e-07`, `1e+21`, `1e+22`, `5e-324`, `1.7976931348623157e+308`, `-0.0`, `0.30000000000000004`) — **not** ECMAScript form; M12.6 refuses a **structurally valid, float-bearing** plan document with `PLAN_CONTENT_UNSUPPORTED` (X.3, sole condition) |
| integers | arbitrary precision, decimal, but subject to the runtime's integer-to-decimal digit limit (measured: `2**20000` raises inside `json.dumps`): a non-convertible integer is **F8** ⇒ `RESOLVER_INPUT_STRUCTURE_INVALID`, decided in the preflight and **never** reported as `PLAN_CONTENT_UNSUPPORTED` |
| platform inputs | none — no locale, timezone, filesystem or network input on the path |
| hash seed | none — no unordered container is ever iterated (sets are refused, not iterated) |
| JSON encoder | CPython `json` with the fixed flags above; number formatting delegates to `float.__repr__` / `int.__str__` |

## XI.3 Determinism contract (normative, bounded)

> Domain B determinism is guaranteed **within the pinned CPython runtime** and **across processes, across
> `PYTHONHASHSEED` values, and across supported platforms**. It is **NOT** guaranteed across different Python
> **implementations** or different Python **versions**. Cross-runtime determinism is **NOT CLAIMED**.

**Pinned runtime (MUST be recorded in the artifact and in gate evidence):** **CPython 3.11.16**,
`sys.get_int_max_str_digits() == 4300`. Because the only runtime-dependent formatting classes are floats and
over-long integers, and because both manifest as a **refusal** — the float policy at `PLAN_CONTENT_UNSUPPORTED`
(X.3) and the integer digit limit at `RESOLVER_INPUT_STRUCTURE_INVALID` category **F8** (VII.4) — or as digest
**disagreement** (`IDENTITY_MISMATCH`), a cross-runtime divergence can only fail closed and can never produce a
false accept. A change of the pinned runtime is a **re-baseline event**: plans/expectations generated
under one runtime MUST NOT be assumed valid under another, and the fail-closed manifestation is refusal. Gate
evidence MUST record the runtime version and the digit limit alongside the determinism result.

## XI.4 Per-digest canonical inputs (exact)

| Digest | Domain | Canonical input |
|---|---|---|
| observed-state digest | A | the reconstructed extraction tree (`digest.extract`) |
| `source_content_digest` | B | `task.to_json_compatible()` via M12.3's `compute_source_content_digest` (unmodified) |
| `plan_content_digest` | B | `plan.to_json_compatible()` — the **full** canonical document, no exclusions — via X.2 (single call site) |
| `vocabulary_digest` (per entry) | A | the `EntryVocabulary` minus its digest |
| `definition_digest` | A | the `SemanticInvariantDefinition` minus its digest |
| `target_digest` (per target) | A | the `ProductionTargetSpec` minus its digest |
| `target_table_digest` | A | the ordered targets with per-item digests |
| `registry_digest` | A | the ordered tuple (vocabulary, definitions, mappings, targets) with per-item digests |
| `value_digest` | A | `(definition_id, definition_revision, comparison, admissible_value_type, expected_value)` |
| `expectation_digest` | A | the expectation object minus `expectation_digest` |

---

# PART XII — OBSERVATION BINDING

| Element | Trusted? | Role |
|---|---|---|
| extraction schema revision | **yes** | MUST equal `EXTRACTION_SCHEMA_VERSION` (=1); else `EXTRACTION_CONTRACT_REVISION_MISMATCH` |
| reconstructed tree + canonical digest | **yes** | the only observation content; fresh non-aliasing reconstruction; RFC 8785 digest |
| correlation | **yes** | request↔response identity (`request_id`, `operation_name`, `entity_ids`, `schema_version`) |
| scope | trusted as caller-declared labels, with reported ids canonical | M12.6 MUST require `subject_scope ⊆ scope.entity_ids` and expected entities present in the tree |
| request identity | **yes, as an identifier** (which correlated request — not *who* asked) | carried in the observation identity |
| session identity (six keys) | transport-rooted, **NOT authenticated** | closed key set MUST hold; `engine_version` MUST equal `world.engine_version` |
| `extractor_identity` | **not a producer identity** — the field holds `tree["extraction_kind"]`, a value derived from the payload's own content; M12.6 MUST NOT treat it as extractor provenance and claims none | carried as a kind label |
| producer identity / extractor version / attestation | **`NOT_ESTABLISHED`** — none exists in the contract | — |
| execution identity | **MUST NOT BE INVENTED** | Part XVI states the non-claim |

One new binding requirement (MUST): **per-invariant subject-scope agreement** — the observation scope MUST
contain the definition's `subject_scope` (else `EXPECTATION_SCOPE_NOT_OBSERVED`), and declared expected
entities MUST be present in the reconstructed tree (a genuine `NOT_SATISFIED`, never an ambient `UNKNOWN`).
Measured basis: an observation with `entity_ids=("UNRELATED_ENTITY_XYZ",)` and a substituted actor set is
currently accepted with no refusal.

---

# PART XIII — DIGITAL TWIN

**DECISION: `NOT_ESTABLISHED`.** `digital_twin_id` is task identity/provenance only — **never** a verified
engine fact, **never** an expected value, **never** the target selector, and **never** the missing authority
substituted for a task↔target binding.

1. The result's `digital_twin_id` is not a twin-verification claim.
2. M12.6 MUST NOT create a twin authority to make a result look stronger.
3. M12.6 MUST NOT infer twin identity from `engine_version`, `project_identity`, `world_name`, or string
   similarity.
4. The only admissible future upgrade is an upstream, reviewed twin↔task binding (Q10-class). Until it exists the
   non-claim of V.4.5 stands verbatim, including: `SATISFIED` does **not** mean the observed world is the
   requested digital twin.
5. **No invariant may consume the twin id as a value**; a definition that would need it is `DEFERRED`.

---

# PART XIV — RESULT COHERENCE, RESULT STATES, RESULT SCHEMA (D3 + D4)

## XIV.1 The construction guard is not a security boundary

The module-private `_ConstructionGuard` sentinel is retained **only as an accidental-construction guard**: it
prevents a code path from accidentally building a result that never passed the verifier. It is **not**
unforgeable against code executing in the same Python process and no such claim is made. **The real invariant is
result coherence validation** (XIV.2), enforced at construction **and** at serialization.
**Trust boundary (MUST be stated):** the expectation is the only new input and is treated as an **untrusted
claim** — the verifier recomputes its identity and digests from `(task, plan, code constants)` and refuses any
mismatch; verifier and result contract live in the same trust domain (the Atlas process), so an adversary able
to execute code there can defeat any in-process contract. What the contract guarantees: (a) no *accidental*
positive; (b) no positive without a complete, attributed, digest-coherent evaluation; (c) every positive
recomputable from committed inputs by a third party.

## XIV.2 Structural `SATISFIED` requirements (all ten, conjunctively, at construction and at serialization)

| # | Condition | Violation token |
|---|---|---|
| 1 | non-empty required invariant set | `EMPTY_REQUIRED_INVARIANT_SET` |
| 2 | complete required-set reconciliation (exact set equality with the plan union) | `INCOMPLETE_REQUIRED_INVARIANT_SET` / `EXTRA_PLAN_VERIFICATION_REQUIREMENT` |
| 3 | a valid, identity-verified expectation present | `EXPECTED_VALUE_UNAVAILABLE` |
| 4 | expectation identity recomputed and equal (task, plan, registry, target table, resolver) | `EXPECTATION_IDENTITY_MISMATCH` |
| 5 | per-invariant definition identity verified (`definition_id`, `definition_revision`, `definition_digest`) | `EXPECTATION_DIGEST_MISMATCH` |
| 6 | observation identity verified (transport-rooting, schema revision, correlation, scope agreement) | `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED` / `OBSERVATION_CORRELATION_MISMATCH` / `EXPECTATION_SCOPE_NOT_OBSERVED` |
| 7 | complete evaluation — one closed result per required invariant, every state `SATISFIED` | `EXPECTED_VALUE_UNAVAILABLE` |
| 8 | complete attribution — definition identity, subject scope, expected-value identity, the observed value(s) carried by `resolved_observables` + `value_state`, evidence identity | `EXPECTATION_INCOMPLETE` |
| 9 | coherent result digest — derived at serialization from the validated inputs, recomputable | — |
| 10 | no unsupported / missing / contradictory / non-established condition anywhere in the result | the specific code |

`overall_state == "SATISFIED"` additionally requires `semantic_state == "SATISFIED"` and
`render_state ∈ {VERIFIED, NOT_REQUIRED}`. Since `render_state = VERIFIED` is unreachable in v1 (XVII), overall
`SATISFIED` is reachable **only** for non-render-bearing tasks — asserted by test, not assumed.

## XIV.3 Result-state vocabularies and the classifier (D4)

**Expansion is required — and it is an R2-A obligation (MUST — decision, not an implementation choice).** The
four closed vocabularies below are landed **in full by R2-A**, together with the classifier, the mapper and the
tests. They are **not** deferred to R2-B, and no document may call them an R2-B requirement. What R2-B later
supplies is not the *vocabulary* but the **authority and witness conditions** (a `REGISTERED` definition, a
populated reviewed target table, the two real witnesses) that make the currently unreachable members reachable
(XXIV.1). Head vocabularies of the implementation base, for contrast: `semantic_state` = {SATISFIED,
NOT_SATISFIED, UNKNOWN, INVALID_OBSERVATION}; `overall_state` = {SATISFIED, NOT_ESTABLISHED, UNKNOWN} — i.e.
`NOT_SATISFIED` is **absent** at the overall level today, and `NOT_ESTABLISHED` is absent from `semantic_state`.

```text
invariant_state      ∈ { SATISFIED, NOT_SATISFIED, UNKNOWN, MISSING }                        # closed, 4
                                                                                             # landed in R2-A; the R2-A
                                                                                             # reachable subset is in XXIV.1
semantic_state       ∈ { SATISFIED, NOT_SATISFIED, UNKNOWN, INVALID_OBSERVATION,
                         NOT_ESTABLISHED }                                                   # closed, 5
                                                                                             # landed in R2-A in full
overall_state        ∈ { SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_ESTABLISHED }                # closed, 4
                                                                                             # landed in R2-A in full
outcome_reason_class ∈ { SATISFIED, EVALUATED_MISMATCH, EVIDENCE_INSUFFICIENT,
                         BINDING_ABSENT, AUTHORITY_ABSENT, INTERNAL_FAILURE }                # closed, 6
                                                                                             # landed in R2-A in full
```

Exact semantics: **`SATISFIED`** — every required invariant was evaluated and all passed, with the conditional
render domain non-blocking. **`NOT_SATISFIED`** — at least one required invariant was **actually evaluated** and
failed, the evidence suffices to assert mismatch, no invariant is `UNKNOWN`/`MISSING`, and no
`BINDING_ABSENT`/`AUTHORITY_ABSENT` condition is present. **`UNKNOWN`** — evaluation could not be completed or
the evidence was insufficient to decide. **`NOT_ESTABLISHED`** — the semantic authority or the binding required
to make the claim does not exist **for this claim** (no registered definition, no production target,
non-canonical authority content, or a binding failure). `NOT_SATISFIED` is **never** collapsed into `UNKNOWN`;
`NOT_ESTABLISHED` is **never** collapsed into `UNKNOWN`.

**Reason classes — ONE discriminator (MUST):**

> `BINDING_ABSENT` — the failed check concerns a **supplied artifact**: the task, the plan, the expectation,
> their structural validity, or an identity/digest relationship among supplied artifacts.
> `AUTHORITY_ABSENT` — the failed check concerns a **code-level authority source**: the invariant registry, the
> production-target table, code-level coverage, or the code-level render-dimension state.
> `EVIDENCE_INSUFFICIENT` — the failed check concerns **supplied observation evidence**.
> `EVALUATED_MISMATCH` — an admissible invariant was actually evaluated and failed.
> `SATISFIED` — every required condition passed after actual evaluation.
> `INTERNAL_FAILURE` — an unexpected implementation/internal fault occurred (VII.5).

Applying it: **`REGISTRY_SOURCE_NOT_CANONICAL` → `AUTHORITY_ABSENT`**, **`PRODUCTION_TARGET_NOT_CANONICAL` →