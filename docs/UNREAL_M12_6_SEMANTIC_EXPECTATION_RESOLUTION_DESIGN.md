# ATLAS M12.6 — AUTHORITATIVE SEMANTIC EXPECTATION RESOLUTION
## R1 — NORMATIVE ARCHITECTURE FREEZE — **Revision 7**

**Revision:** R7 of the R1 artifact. Supersedes Revision 6 and preserves all R6 material except the normative correction recorded below. Supersedes Revision 5 (preserved at
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

**Revision-7 correction record.** Independent code review of R2-A identified a contradiction in R6's measured-compatibility sentence for the S4 coverage-gap case. R6 simultaneously required `semantic_state = NOT_ESTABLISHED` for the canonical R2-A outcome and said the coverage-gap semantic state was unchanged. R7 resolves this by making the canonical R2-A outcome authoritative: the coverage-gap result is `NOT_ESTABLISHED / NOT_ESTABLISHED`. Existing compatibility prose is amended accordingly; no positive state becomes reachable.

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
`AUTHORITY_ABSENT`**, **`PRODUCTION_TARGET_MAPPING_DUPLICATE` → `AUTHORITY_ABSENT`** and
**`EXPECTATION_DEFINITION_DUPLICATE` → `AUTHORITY_ABSENT`** — all four are failures of a **code-level authority
table**, with no supplied artifact involved. The Revision-3 classification of `EXPECTATION_DEFINITION_DUPLICATE`
as `BINDING_ABSENT` is **withdrawn** (Part 0.1, item 4). The corrected clause reads: *`BINDING_ABSENT` if a
**supplied-artifact** identity, digest, or structural check failed.*

**Authority-table integrity vs coverage (MUST, one split, used consistently):**

| Kind of failure | Stage | Reason class | Examples |
|---|---|---|---|
| **authority-table integrity** — the table itself is malformed, ambiguous or not the reviewed content | **S2** | `AUTHORITY_ABSENT` | two definitions for one name (`EXPECTATION_DEFINITION_DUPLICATE`); two mapping rows for one triple (`PRODUCTION_TARGET_MAPPING_DUPLICATE`); registry/target content not matching its reviewed constant digest (`REGISTRY_SOURCE_NOT_CANONICAL`, `PRODUCTION_TARGET_NOT_CANONICAL`) |
| **coverage for this input** — the table is intact but supplies nothing for this input | **S4** | `AUTHORITY_ABSENT` | canonical name with no `REGISTERED` definition (`EXPECTED_VALUE_UNAVAILABLE`); no target row for the derived triple (`PRODUCTION_TARGET_NOT_ESTABLISHED`); v1 render-dimension states |

**Digest-comparison-side rule (MUST — the single classification for every digest failure).** A digest failure
is classified by **which side of the comparison is a reviewed constant**:

1. a **carried digest inside a supplied artifact** (the expectation's `expectation_digest`, an entry's
   `value_digest`, or a `definition_digest` carried in the expectation) compared against a value recomputed from
   `(task, plan, validated authority)` ⇒ **supplied-artifact failure** ⇒ **S3 / `BINDING_ABSENT`**
   (`EXPECTATION_DIGEST_MISMATCH`);
2. a **code-level authority's own content** compared against its **reviewed constant digest**
   (`REGISTRY_SOURCE_DIGEST`, each definition's reviewed digest, `TARGET_TABLE_DIGEST`, each entry's
   `target_digest`) ⇒ **authority failure** ⇒ **S2 / `AUTHORITY_ABSENT`** (`REGISTRY_SOURCE_NOT_CANONICAL`,
   `PRODUCTION_TARGET_NOT_CANONICAL`).

Both sides are validated, **S2 before S3**, so the two can never be conflated, the first failing stage decides,
and no digest failure may be classified by any other rule. Part XV applies this rule to every row.

**Stage precedence (normative, EXCEPTION-FREE):**

```text
S1 structural preflight                     -> BINDING_ABSENT        (VII.4; incl. the float policy boundary)
S2 authority revalidation                   -> AUTHORITY_ABSENT      (table integrity: digests, duplicates)
S3 binding                                  -> BINDING_ABSENT        (task<->plan; expectation<->resolution;
                                                                      declared pair; plan content digest)
S4 coverage                                 -> AUTHORITY_ABSENT      (no REGISTERED definition; no target row;
                                                                      v1 render dims)
S5 observation binding                      -> EVIDENCE_INSUFFICIENT (correlation, rooting, revision, scope,
                                                                      contradiction, missing observable)
S6 evaluation                               -> EVALUATED_MISMATCH | SATISFIED
```

**The first failing stage determines the outcome**, and **within a stage the rule of XIV.3.1 determines the
outcome** (lowest-numbered applicable row wins; `failure_codes` is the sorted union of the stage's applicable
tokens) — therefore no evaluation order, dict/set iteration or implementation choice can influence a result.
`overall_state` follows the reason class:
`SATISFIED → SATISFIED`; `EVALUATED_MISMATCH → NOT_SATISFIED`; `EVIDENCE_INSUFFICIENT → UNKNOWN`;
`AUTHORITY_ABSENT`/`BINDING_ABSENT` → `NOT_ESTABLISHED`; `INTERNAL_FAILURE → UNKNOWN`.
Declared many-to-one token mapping inside a stage: `EXPECTED_VALUE_UNAVAILABLE` is `AUTHORITY_ABSENT` for a
coverage gap (S4) and `EVIDENCE_INSUFFICIENT` for a missing observable (S5); `EXPECTATION_VOCABULARY_MISMATCH`
is `BINDING_ABSENT` (S3) because the failed check is over the supplied task's declared set.

**R2-A / R2-B state rule (MUST — decision, not an implementation choice; four clauses, all normative).**

1. **R2-A lands the full four enums and the classifier.** `invariant_state` (4), `semantic_state` (5, including
   `NOT_ESTABLISHED`), `overall_state` (4, including `NOT_SATISFIED`) and `outcome_reason_class` (6) are
   implemented **in full** in R2-A, together with the stage classifier, the mapper, the compatibility-table
   change and the single affected assertion (`tests/m12/test_m12_5_verification.py:153`).
2. **Only the specified reachable subset is reachable in R2-A** — exactly the subset fixed in XXIV.1:
   `invariant_state ∈ {UNKNOWN, MISSING}`, `semantic_state ∈ {UNKNOWN, NOT_ESTABLISHED}`,
   `overall_state ∈ {UNKNOWN, NOT_ESTABLISHED}`, `outcome_reason_class ∈ {BINDING_ABSENT, AUTHORITY_ABSENT,
   INTERNAL_FAILURE}`, stages S1–S4.
3. **`SATISFIED`, `NOT_SATISFIED` and every other R2-B-only state remain unreachable in R2-A** (no definition is
   `REGISTERED` and the target table is empty, so the resolver refuses before evaluation). They MUST exist in the
   vocabulary, MUST be exercised by the classifier tests on refusal paths, and MUST NOT be producible by any
   path, flag, override or fixture.
4. **R2-B later supplies the authority and witness conditions that make those paths reachable** — a `REGISTERED`
   definition with positive/negative/lossy witnesses (Part XIX) and a populated reviewed target table (V.5) —
   and nothing else. Deferring the *vocabulary* to R2-B is **not permitted**, because it would make the
   classifier inconsistent with the result contract in R2-A.

**Measured compatibility (old → new; no row becomes positive).** Coverage gap: UNKNOWN/NOT_ESTABLISHED →
**NOT_ESTABLISHED/NOT_ESTABLISHED** (canonical R2-A S4 outcome; no longer described as unchanged). Task/plan binding failure, set-rule failure, render-classification mismatch, claimed-digest
assertion: INVALID_OBSERVATION/UNKNOWN → **NOT_ESTABLISHED/NOT_ESTABLISHED** (changed 2 fields,
`BINDING_ABSENT`). No-observation supplied, not-transport-rooted, correlation mismatch, contradictory
duplicate, observation-shape/future-field: unchanged INVALID_OBSERVATION/UNKNOWN. Render-bearing v1: unchanged
UNKNOWN/NOT_ESTABLISHED. **Affected existing assertions on the implementation base (exhaustive): exactly one** —
`tests/m12/test_m12_5_verification.py:153`. All other state assertions in `tests/m12`
(`test_m12_5_verification.py:87/103/121/262`, `test_m12_5_adversarial.py:95/128/129/166/167/221/222`) keep
their values; `test_m12_5_identity_binding.py` asserts codes only; the live-gate state checks exist only on the
unmerged live-promotion-gate branch.

## XIV.3.1 Within-stage precedence and deterministic aggregation (MUST — decision, not a choice)

**Rule (one rule, total, exception-free).** When more than one Part XV row applies inside the same stage, the
outcome is determined by a fixed total order over rows plus fixed aggregation:

1. **Winner (primary row).** The applicable row with the **lowest Part XV row number** wins. It supplies the
   **primary failure code** (the row's first-listed token) and, through the stage, the reason class. The order is
   the row number as printed in Part XV — never the order in which a check happens to run, never a set/dict
   iteration order, never an exception's arrival order, never a lexicographic comparison of token names.
2. **Class homogeneity (checked, not assumed).** Within every stage the applicable rows are reason-class
   homogeneous — S1: rows 1, 28, 29 → `BINDING_ABSENT`; S2: rows 9–12, 33 → `AUTHORITY_ABSENT`; S3: rows 4, 5, 7, 8,
   13, 14, 21, 26, 27, 30, 31 → `BINDING_ABSENT`; S4: rows 3, 6, 22, 32 → `AUTHORITY_ABSENT`; S5: rows 15–20,
   23–25 → `EVIDENCE_INSUFFICIENT`; S6: rows none (evaluation outcomes are not refusals) — therefore
   `outcome_reason_class` is the deciding stage's single class and can never depend on which row wins. A census
   test MUST assert this homogeneity from the Part XV table itself, so a future row added with a foreign class in
   the same stage fails the test rather than silently changing semantics.
3. **Aggregation of `failure_codes` (MUST).** `failure_codes` is the **union of the tokens of every applicable row
   in the deciding stage**, deduplicated and sorted ascending by Domain-A canonical bytes — not only the primary
   row's token — so the code set is a total function of the inputs and never of evaluation order. The primary
   code MUST be a member of that set. **No** token from a **later** stage may appear (those stages do not run) and
   no token from a row that does not apply may appear. No placeholder, no exception text, no prose (XIV.5).
4. **Order independence (MUST).** The complete result — stage, primary code, class, `failure_codes`,
   `semantic_state`, `overall_state`, every per-entry state and both digests — MUST be invariant under any
   permutation of the checks executed inside a stage. A test MUST run the same input with the in-stage checks
   executed in at least two different orders and assert **byte-identical** serialized results and digests.
5. **No other tie-break may exist.** No "first exception wins", no string comparison, no priority assigned by the
   implementation, no caller-visible selection, no randomness. An implementation MAY record the primary row
   internally for diagnostics, but **no field of the result may depend on it** beyond clauses 1–3.

**R2-A demonstration (definitions all `DEFERRED`, target table empty) — one deterministic outcome.** Take a
structurally valid task whose required set is within the Part IV.2 vocabulary and whose
`(entry_name, entry_version)` is a declared pair, and a structurally valid expectation object (the variant with
no expectation supplied is treated below). Then:

- **S1 passes** — preflight over the supplied artifacts raises no F1–F9 condition.
- **S2 passes** — both authority tables are the reviewed tables (the registry and an **empty** target table);
  their reviewed-constant digests recompute and no duplicate row exists.
- **S3 passes** — identity, task↔plan binding, the declared pair, the plan content digest and (when supplied) the
  expectation's carried digests all agree.
- **S4 applies two rows simultaneously** — row 6, because every canonical name has **no `REGISTERED`
  definition** (`DEFERRED` behaves exactly as unregistered), and row 22, because the empty target table has **no
  row** for the derived triple. **Winner = row 6** (lowest number) ⇒ primary code `EXPECTED_VALUE_UNAVAILABLE`.
  The stage's class is `AUTHORITY_ABSENT` (rows 3, 6, 22, 32 are homogeneous).
- **Aggregate:** `failure_codes = ["EXPECTED_VALUE_UNAVAILABLE", "PRODUCTION_TARGET_NOT_ESTABLISHED"]` — sorted,
  deduplicated, both from S4, no S5/S6 token.
- **Per-entry states** follow the total precedence rule of XIV.4.2: no entry reached S5, so **every required
  invariant is `UNKNOWN`** with the not-evaluated shape (`value_state = ABSENT`, `observation_bound = false`,
  `resolved_observables = ()`, `mismatch_reason = null`). `MISSING` is **not** produced here.
- **Aggregate states:** `outcome_reason_class = AUTHORITY_ABSENT`, `semantic_state = NOT_ESTABLISHED`,
  `overall_state = NOT_ESTABLISHED`, `render_state` per Part XVII, and `result_digest` recomputable by an
  independent implementation (XIV.4.5/XIV.4.6).
- **Uniqueness of the outcome.** The rule yields **exactly one** outcome for this input. In the variant with no
  expectation supplied, S1–S3 still pass and S4 still applies the same two rows (the required set cannot be
  covered either way), so the stage, primary code, class and aggregate are identical; only the
  expectation-derived members of the digest differ. `SATISFIED` and `NOT_SATISFIED` are unreachable.

## XIV.4 Invariant results, evidence identity, and the two result digests

**Naming (MUST).** The **per-entry** digest is `invariant_result_digest`; the **whole-result** digest is
`result_digest`. Revision 4 used `result_digest` for the per-entry digest; that collision is removed and the
older name MUST NOT be used for the per-entry digest anywhere.

### XIV.4.1 Closed invariant-result schema (one entry)

```text
InvariantVerificationResult
  invariant_name          : str      # exact registry vocabulary item
  definition_id           : str
  definition_revision     : int      # >= 1
  definition_digest       : str      # 64 hex — the definition's reviewed constant digest
  authority_class         : str      # CODE_CONSTANT only in R2 (VIII.2); reserved class not admitted
  subject_scope           : tuple[str, ...]        # sorted ascending
  expected_value_identity : str      # value_digest of the expectation entry
  comparison              : str      # EQUALS | SET_EQUALS | CONTAINS_ALL | EXACTLY_ONE | SUBSET_OF
  admissible_value_type   : str      # STR | INT | BOOL | STR_SET
  observed_path_patterns  : tuple[str, ...]        # the definition's declared patterns, sorted ascending
  value_state             : str      # closed: PRESENT | PRESENT_NULL | ABSENT   (XIV.4.2)
  resolved_observables    : tuple[ResolvedObservable, ...]   # empty iff value_state == ABSENT
  observation_bound       : bool
  observation_identity    : ObservationIdentity | null      # null iff observation_bound is false
  invariant_state         : str      # closed: SATISFIED | NOT_SATISFIED | UNKNOWN | MISSING
  mismatch_reason         : str | null     # closed code, non-null iff invariant_state == NOT_SATISFIED
  evidence_identity       : str      # 64 hex (XIV.4.3)
  invariant_result_digest : str      # 64 hex (XIV.4.4)

ResolvedObservable (frozen, sealed, closed)
  concrete_path : str                 # closed path grammar with explicit indices, e.g. actors[0].actor_class
  value         : <Domain A value>    # a JSON null here is a VALUE reported by the engine, never an absence
```

**MUSTs.** No arbitrary mapping may masquerade as a verified invariant result (no `dict`, no `mappingproxy`, no
open key set). Entries are in canonical order and individually digest-bound. `invariant_state == NOT_SATISFIED`
requires a non-null `mismatch_reason` from the closed vocabulary; `invariant_state == SATISFIED` requires
`observation_bound == true`, a non-empty `resolved_observables`, all identity fields non-null, and a non-empty
`evidence_identity`; `UNKNOWN`/`MISSING` require a null `mismatch_reason` and are never counted as evaluated.
`value_state == ABSENT` requires `resolved_observables == ()`; `value_state != ABSENT` requires it to be
non-empty.

### XIV.4.2 Observable resolution, disposition, and derivation (MUST — fully specified)

**Path grammar (closed).** A pattern is a sequence of segments separated by `.`; a segment is an identifier from
the frozen extraction schema's declared key set for that node, optionally followed by `[*]` (any index of an
array). A **concrete path** replaces every `[*]` with a decimal index (`[0]`, `[1]`, …). Nothing else is legal:
no other wildcard, no recursion, no JSONPath/XPath, no escaping, no case folding, no trailing separator. A
pattern with no legal concrete instance yields no instances; a pattern that is not in the grammar is a
registry-integrity failure (S2), never an evaluation outcome.

**Resolution and ordering (MUST).** For each declared pattern, the evaluator enumerates the concrete paths
present in the **reconstructed** tree (VII.4 / Part XII) and produces one `ResolvedObservable` per concrete path,
where `value` is the tree's value at that path. The resulting tuple is sorted **ascending by the Domain-A
canonical UTF-8 bytes of `concrete_path`**. No other ordering is permitted, and the evaluator MUST NOT reorder,
filter, deduplicate or select among instances ("best", "first", "newest", "largest" are all forbidden).

**Disposition `value_state` (closed, derived — MUST NOT be caller-supplied or implementation-chosen).**

| `value_state` | Derived iff |
|---|---|
| `ABSENT` | **zero** concrete paths resolve for the declared patterns |
| `PRESENT_NULL` | at least one resolves **and every** resolved `value` is JSON `null` |
| `PRESENT` | at least one resolves **and at least one** resolved `value` is not JSON `null` |

**Anti-collision rule (MUST).** `ABSENT` and `PRESENT_NULL` are distinguished **only** by `value_state`, which is
a mandatory member of both the entry and the `evidence_identity` canonical input. M12.6 MUST NOT represent
absence by a sentinel string (e.g. `"<absent>"`, `""`), by an omitted member, by an empty array standing in for a
value, by a magic index, by a nullable-field convention, or by any other encoding. `resolved_observables` MUST be
empty for `ABSENT` and non-empty otherwise, and a `ResolvedObservable` whose `value` is `null` is a **present
value that happens to be null** — it is never rewritten to an absence.

**No normalization (MUST).** Values MUST NOT be case-folded, trimmed, Unicode-normalized, numerically coerced,
re-typed, rounded, or path-canonicalized; comparison is byte-exact on the Domain-A canonical bytes of the value.
Domain A string escaping (XI.1) is the only encoding applied anywhere in this section.

**Derivation table (closed — disposition to state and result-level reason).**

| `value_state` | observation bound | value type admissible for the definition | `invariant_state` | result-level token (class, stage) |
|---|---|---|---|---|
| `ABSENT` | false | — | `MISSING` | `EXPECTED_VALUE_UNAVAILABLE` (`EVIDENCE_INSUFFICIENT`, S5) |
| `ABSENT` | true | — | `MISSING` | `EXPECTED_VALUE_UNAVAILABLE` (`EVIDENCE_INSUFFICIENT`, S5) |
| `PRESENT_NULL` | true | null admitted by the definition | evaluate | `SATISFIED` / `EVALUATED_MISMATCH` (S6) |
| `PRESENT_NULL` | true | null not admitted | `UNKNOWN` | `EXPECTATION_CONTRADICTORY` (`EVIDENCE_INSUFFICIENT`, S5) |
| `PRESENT` | true | all values admissible | evaluate | `SATISFIED` / `EVALUATED_MISMATCH` (S6) |
| `PRESENT` | true | any value inadmissible | `UNKNOWN` | `EXPECTATION_CONTRADICTORY` (`EVIDENCE_INSUFFICIENT`, S5) |

Rows with `observation_bound == false` and `value_state != ABSENT` are impossible by construction (values can only
come from a bound observation). The `SATISFIED` / `EVALUATED_MISMATCH` outcomes are **unreachable in R2-A**
(Part XXIV; XIV.3 clause 3).

**Refusal-stage per-entry precedence (MUST — total, order-independent, no implementation choice).** For a result
whose decisive stage is **S1–S4**, every required invariant is reported with `invariant_state = UNKNOWN`,
`mismatch_reason = null`, `value_state = ABSENT`, `observation_bound = false`, `resolved_observables = ()` (the
**not-evaluated shape**) — `MISSING` MUST NOT be produced, because no invariant reached observation binding. For
a result whose decisive stage is **S5**, exactly one of three cases applies to each entry, in this order:
(i) the entry has a bound observation and its declared patterns resolved to **zero** concrete paths ⇒
`invariant_state = MISSING` (row 23, and its per-entry absence is what the aggregated
`EXPECTED_VALUE_UNAVAILABLE` reports); (ii) the entry has a bound observation and a resolved value whose type is
inadmissible for the definition ⇒ `invariant_state = UNKNOWN` (row 24); (iii) otherwise (no bound observation, or
the failure is not attributable to this entry) ⇒ `invariant_state = UNKNOWN` with the not-evaluated shape. The
same rule is applied to every entry of a result, the rule is a pure function of the entry and the decisive stage,
and no entry may be reported in a state outside this table. Per-entry states are recorded individually and never
aggregated into a single value.

### XIV.4.3 `evidence_identity` — Domain A, new recipe (MUST)

**Domain:** A (`EXTRACTION_JCS`, XI.1) — a new, explicitly defined Domain A recipe (not an M12.5 recipe).

```text
canonical input — a closed object with EXACTLY these members, no others, none omitted:
  "schema"                  : "m12.6-evidence-identity-v1"
  "invariant_name"          : <str>
  "definition_id"           : <str>
  "definition_revision"     : <int>
  "definition_digest"       : <64 hex>
  "authority_class"         : <str enum>
  "comparison"              : <str enum>
  "admissible_value_type"   : <str enum>
  "subject_scope"           : [ <str>, ... ]        # sorted ascending, Domain-A order
  "observed_path_patterns"  : [ <str>, ... ]        # sorted ascending
  "value_state"             : "PRESENT" | "PRESENT_NULL" | "ABSENT"
  "resolved_observables"    : [ {"concrete_path": <str>, "value": <Domain A value>}, ... ]
                              # empty iff value_state == "ABSENT"; sorted ascending by the Domain-A canonical
                              # UTF-8 bytes of "concrete_path"
  "observation_bound"       : true | false
  "observation_request_id"  : <str> | null          # null iff observation_bound == false
  "observation_scope"       : [ <str>, ... ] | null # request-declared order preserved; null iff not bound
  "canonical_state_digest"  : <64 hex> | null       # null iff not bound
canonicalizer : planning.unreal_state_extraction.jcs.canonicalize   (Domain A)
hash         : SHA-256 over the canonical UTF-8 bytes, lowercase hex
implementation: ONE function, planning/m12/expectation.py::compute_evidence_identity(...) -> str
```

**Derivation of the observed value (MUST).** The observed value(s) of an entry are derived **only** by XIV.4.2's
resolution: the definition's declared patterns are resolved against the reconstructed tree of the bound
observation envelope, and each instance's value is taken **verbatim** from that tree. They are carried in the
canonical input by the `resolved_observables` array plus `value_state`; `observed_value` is **not** a separate
member, so a **present JSON null** is unambiguous (a `ResolvedObservable` with `value: null` and
`value_state: "PRESENT_NULL"`) and an **absent path** is unambiguous (`[]` plus `value_state: "ABSENT"`). No
value may be derived from any other source: not from the expectation, the task, the plan, the catalog, the
target table, a caller-supplied field, or a second observation that is not bound to this entry.
Every member is always present; the three observation members are `null` exactly when
`observation_bound` is false. The recipe is computed for **every** entry, including refusal entries (using
`value_state: "ABSENT"`, `observation_bound: false` and the declared definition members). Uniqueness: exactly one
implementation and exactly one call site (AST-asserted). Reproducibility: an independent implementation
recomputes it from the supplied observation envelope, the reconstructed tree, the definition, and the derived
disposition alone — with no convention left to choose, since the grammar, ordering, encoding and null rules are
all fixed above. Coherence: an entry whose `evidence_identity` does not recompute is a construction error.

### XIV.4.4 `invariant_result_digest` — Domain A, new recipe (per entry, MUST)

```text
canonical input : the entry's FULL declared member set (XIV.4.1) MINUS the "invariant_result_digest" member,
                  with "resolved_observables" rendered as its closed objects and "observation_identity"
                  rendered as the nested member set of XIV.4.5
canonicalizer   : Domain A (jcs.canonicalize)
hash            : SHA-256 over the canonical UTF-8 bytes, lowercase hex
implementation  : ONE function, planning/m12/expectation.py::compute_invariant_result_digest(entry) -> str
```

Uniqueness/coherence (MUST): one implementation, one call site; the digest commits **every** declared member,
including `value_state`, `resolved_observables`, `evidence_identity`, `invariant_state` and `mismatch_reason`;
it is recomputable from the entry alone by an independent implementation; and two entries differing in any
declared member MUST have different `invariant_result_digest`s.

### XIV.4.5 `result_digest` — the whole-result recipe (Domain A, MUST)

**Canonical input: a closed object with EXACTLY the following members — no others, none omitted.**

| Member | Type / value |
|---|---|
| `schema` | the constant `"m12.6-result-v1"` (domain separation) |
| `verifier_revision` | the constant `"m12.6-v1"` (**pinned**; bumped from M12.5's `"m12.5-v1"` as part of R2-A and validated at construction) |
| `expectation_contract_revision` | the constant `EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"` (VIII.1) |
| `resolver_revision` | the constant `RESOLVER_REVISION = "m12.6-resolver-v1"` (VIII.1) |
| `registry_revision` | int |
| `registry_digest` | 64 hex |
| `target_table_revision` | int |
| `target_table_digest` | 64 hex |
| `production_target_id` | str \| **null** (null iff no target row resolved) |
| `target_revision` | int \| **null** (null iff no target row resolved) |
| `target_digest` | 64 hex \| **null** (null iff no target row resolved) |
| `task_identity` | str |
| `task_version` | int ≥ 1 |
| `digital_twin_id` | str (provenance; never a claim — Part XIII) |
| `catalog_entry_name` | str |
| `catalog_entry_version` | int ≥ 1 |
| `vocabulary_digest` | 64 hex |
| `plan_id` | str (provenance only — X.1) |
| `source_content_digest` | 64 hex |
| `plan_content_digest` | 64 hex |
| `render_task` | bool |
| `required_invariant_names` | array of str, **sorted ascending** |
| `expectation_identity` | object — nested member set below |
| `expectation_digest` | 64 hex |
| `observation_identity` | object \| **null** (null iff no observation was bound) |
| `observation_digests` | array of 64 hex, **sorted ascending**, unique; derivation and nullability per **XIV.4.6** |
| `render_job_identity` | str \| **null**; derivation and nullability per **XIV.4.6** |
| `render_attempt_identity` | int ≥ 1 \| **null**; derivation and nullability per **XIV.4.6** |
| `render_evidence_identity` | 64 hex \| **null**; derivation and nullability per **XIV.4.6** |
| `evidence_trust_basis` | object with exactly `semantic_observation` and `render_evidence`, each a closed-enum `str` (never `null`); values per **XIV.4.6** |
| `invariant_results` | array of entry objects (XIV.4.1), **in canonical order** |
| `semantic_state` | str (closed 5-value enum) |
| `render_state` | str (closed enum) |
| `overall_state` | str (closed 4-value enum) |
| `outcome_reason_class` | str (closed 6-value enum) |
| `failure_codes` | array of str, **sorted ascending, unique** |
| `origin_status` | the constant `"NOT_ESTABLISHED"` (II.3) |

**Nested `expectation_identity` (exact member set).** `expectation_contract_revision`, `resolver_revision`,
`registry_revision`, `registry_digest`, `target_table_revision`, `target_table_digest`,
`production_target_id` (str \| null), `target_revision` (int \| null), `target_digest` (64 hex \| null),
`task_identity`, `task_version`, `digital_twin_id`, `catalog_entry_name`, `catalog_entry_version`,
`vocabulary_digest`, `source_content_digest`, `plan_id`, `plan_content_digest`, `render_task`,
`required_invariant_names` (sorted array), `invariant_expectations_digest` (64 hex), `expectation_digest` (64 hex).

**Nested `observation_identity` (exact member set, when non-null).** `contract_revision` (int),
`extractor_identity` (str), `engine_identity` (str), `session_identity` (object with **exactly** the six
declared session keys, each rendered with its own declared type), `scope_identity` (object with exactly
`operation_name` (str) and `entity_ids` (array of str **in the request's declared order**)),
`request_identity` (str), `canonical_state_digest` (64 hex).
**Every one of these seven members has exactly one derivation, one type and one nullability rule — XIV.4.6.1.
None of them may be invented, defaulted, normalized or omitted.**

**Ordering rules (MUST).** Object members are unordered — Domain A sorts them by UTF-16 code units, and no
implementation may impose another order. The **only** ordered constructs are the arrays named as sorted above
(sorted ascending by Domain-A canonical bytes) and `entity_ids` inside `scope_identity`, which **preserves the
correlated request's declared order** because that order is part of the request identity. `invariant_results` is
ordered by `invariant_name`, ascending, on the Domain-A canonical bytes of the name.

**Presence / null rules (MUST).** Every declared member is present in every result. "Not applicable" is expressed
as JSON `null` on the members listed as nullable, never by omitting the member, never by an empty string, and
never by an empty array. Empty collections are `[]`, never `null`. A nullable member is `null` **only** under the
stated condition, and every non-nullable member MUST be non-null.

**Domain separation (MUST).** The four recipes carry four distinct `schema` constants —
`"m12.6-expectation-v1"`, `"m12.6-evidence-identity-v1"`, `"m12.6-invariant-result-v1"`, `"m12.6-result-v1"` —
so digests produced by different recipes can never be confused. A digest is never computed over another digest's
byte string except where a digest is a declared member value.

**Derivation, uniqueness and independent reproducibility (MUST).** The whole-result canonical form is derived at
**serialization time** from the validated inputs and module constants — never read back from an assignable cache
(XIV.1). Exactly one implementation and one call site compute it (AST-asserted). An independent implementation
given `(source_task, plan, expectation, observation pairs, code constants)` reproduces the entry set, the
`invariant_result_digest`s and the `result_digest` **byte-for-byte without choosing any encoding convention**,
because every convention — member set, nested member sets, ordering, null representation, key ordering, escaping,
hash — is fixed above and in XI.1.

## XIV.4.6 Complete value derivation and nullability for the typed members (MUST — nothing may be invented)

Every member of the whole-result canonical input (XIV.4.5) whose table entry is not already a literal has
**exactly one** derivation below. No implementation may invent a value, a sentinel, a placeholder or empty
string, an extra member or an unlisted state; `null` appears **only** under the stated condition; and a member
absent from this subsection is a literal or a closed enum whose members are listed at its definition.

**Constants (never derived).** `schema = "m12.6-result-v1"`; `verifier_revision = "m12.6-v1"`;
`expectation_contract_revision = EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"`;
`resolver_revision = RESOLVER_REVISION = "m12.6-resolver-v1"` (VIII.1). All four are validated at construction;
a mismatch is a construction error, never a refusal path.

**`render_task`** — the expectation's declared `render_task` boolean, verbatim (Part IX). Never `null`, never
derived from the observed tree, the render inputs, the plan or the target table.

**`render_job_identity`** (`str | null`) — non-null **iff**
`evidence_trust_basis.render_evidence == "DURABLE_RECORD_BACKED"`, in which case it is the **`atlas_job_id`**
attribute of the durable render record that the unchanged M5 function `verify_render_job_evidence()` validated;
`null` in every other case. It MUST NOT be derived from the task, the plan, the expectation, the target table,
`digital_twin_id`, the render observation's own fields, or any caller-supplied value.

**`render_attempt_identity`** (`int ≥ 1 | null`) — the **same** condition, taking the **`attempt_ordinal`**
attribute of the **same** record; `int ≥ 1` with `bool` excluded; `null` otherwise.

**`render_evidence_identity`** (`64 hex | null`) — the **same** condition, taking the canonical digest of the
independently verified render evidence, computed by the **existing M12.5 recipe** (`_canonical_digest` over
exactly `{"operation_name", "entity_ids", "observed_state", "source"}` of the verified evidence object) —
adopted verbatim, **not** re-implemented and **not** re-canonicalized in Domain A. The member's *value* is that
digest string; the whole-result canonicalization hashes the string. `null` otherwise. This is a declared
cross-domain member value, not a second verifier and not a competing authority (Part XVII).

**Render-triple coherence (MUST).** The three members above are **simultaneously** non-null or **simultaneously**
`null`. A partially populated triple is a construction error and MUST be rejected (XIV.2), never emitted.

**`evidence_trust_basis.semantic_observation`** (closed 2-value enum; never `null`) — `"TRANSPORT_CORRELATED"`
**iff** `observation_identity != null` (i.e. at least one observation identity was established by the S5
transport-rooting checks); `"NOT_ESTABLISHED"` **iff** `observation_identity == null`. Measured pre-M12.6
behaviour: M12.5 emits the constant `"TRANSPORT_CORRELATED"` **unconditionally**, including on results with no
bound observation, which is a false basis claim; M12.6 **supersedes** it for M12.6 results. Verified impact: no
existing assertion pins that value (`semantic_observation` appears in `tests/m12` only as a copied provenance
member of the live-gate reporting path, and only `render_evidence` is asserted), so this change affects **no**
existing assertion and does not alter the single-affected-assertion statement of XIV.3.

**`evidence_trust_basis.render_evidence`** (closed 3-value enum; never `null`) — `"NOT_APPLICABLE"` **iff**
`render_task == false`; `"NOT_ESTABLISHED"` **iff** `render_task == true` and the three render identity members
are `null` (no render evidence was independently verified — whether none was supplied or the supplied evidence
failed independent verification); `"DURABLE_RECORD_BACKED"` **iff** `render_task == true` and the three render
identity members are non-null. There is **no fourth value** in v1, and `render_state = VERIFIED` remains
unreachable (Part XVII).

**`observation_digests`** (`array[64 hex]`, never `null`) — the **set** of `canonical_state_digest` values of all
observations bound to the result, deduplicated and sorted ascending by Domain-A canonical bytes; `[]` **iff** no
observation was bound. If `observation_identity != null`, the array MUST contain
`observation_identity.canonical_state_digest`. It MUST NOT contain any other digest (no expectation digest, no
render digest, no per-entry `evidence_identity`).

**`observation_identity`** (`object | null`) — `null` **iff** no observation was bound to the result (a refusal at
S1–S4, or an S5 refusal before any identity was established). When non-null, every nested member is non-null and
derived exactly as in XIV.4.6.1; when `null`, the three expectation-side nulls
(`production_target_id`/`target_revision`/`target_digest`) and the render nulls are **unaffected** — nullability
is per member, never propagated.

### XIV.4.6.1 `observation_identity` nested member derivations (MUST)

| Member | Type | Exact derivation | Nullability |
|---|---|---|---|
| `contract_revision` | int | the extraction contract revision carried by the reconstructed tree; MUST equal the verifier's committed constant, else S5 `EXTRACTION_CONTRACT_REVISION_MISMATCH` | non-null whenever the parent is non-null |
| `extractor_identity` | str | the reconstructed tree's `extraction_kind`, **verbatim** (no normalization, no case folding, no coercion, no default) | non-null whenever the parent is non-null |
| `engine_identity` | str | `session_identity["engine_version"]`, **verbatim**, and MUST equal the reconstructed tree's `world.engine_version` (else S5 `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`); it is the **engine-reported** version string — never a client-asserted value and never a code constant | non-null whenever the parent is non-null |
| `session_identity` | object | exactly the six keys below, copied **verbatim** from the transport response's `session_identity`; the key set MUST be **exactly** those six — a missing or extra key is S5 `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED` and MUST NOT be ignored, trimmed or defaulted | non-null whenever the parent is non-null |
| `scope_identity` | object | `operation_name`: the correlated request's `operation_name` verbatim; `entity_ids`: the correlated request's `entity_ids` **in declared order** (order is part of the request identity and MUST be preserved) | non-null whenever the parent is non-null |
| `request_identity` | str | the correlated request's `request_id`, verbatim | non-null whenever the parent is non-null |
| `canonical_state_digest` | 64 hex | the extraction module's canonical digest of the reconstructed tree (existing M12.5 recipe, unchanged) | non-null whenever the parent is non-null |

**The six `session_identity` keys (closed set, verbatim from the transport response).**

| Key | Type | Validity rule (any violation ⇒ S5 `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED`) |
|---|---|---|
| `editor_session_id` | str | non-empty after `strip()` |
| `process_id` | int | `int`, `bool` excluded, `>= 1` |
| `process_creation_time_utc` | str | non-empty after `strip()` |
| `server_start_time_utc` | str | non-empty after `strip()` |
| `engine_version` | str | non-empty after `strip()`; equals the tree's `world.engine_version` |
| `project_identity` | str | non-empty after `strip()` |

No other key is permitted, none may be added by M12.6, and no key may be omitted. Values are rendered in the
digest **verbatim** (Domain A escaping only). The two timestamp fields are carried as evidence and are **not**
interpreted: no freshness, ordering, age or same-session claim is derived from them (Part XVI non-detection
control), and no member of the result depends on their values beyond identity.

## XIV.5 Closed code vocabulary, and the retirement of the expectation canonicalization token

`failure_codes` MUST contain only tokens defined in Part XV. Measured defect: the verifier converts exception
messages into "codes" (`str(exc).split(":", 1)[0]`), so a correlation failure puts the prose sentence
`'response entity_ids do not match the originating request'` into `failure_codes`. M12.6 MUST map correlation
failures to `OBSERVATION_CORRELATION_MISMATCH`, MUST derive every code from a closed table, and a census test
MUST assert that no `failure_codes` entry contains whitespace, violates the token grammar, or is absent from the
table. R2 MUST additionally audit every `except …: code = str(exc)…` site for further exception-derived codes.

**Retirement (MUST, single-token policy).** Revision 3's `EXPECTATION_CANONICALIZATION_UNSUPPORTED` is
**retired**; it was a near-synonym of the preflight token and produced a contradictory double path for
expectation-side structural failures. The mapping is now exhaustive and single-tokened:

| Expectation-side condition | Token | Reason class |
|---|---|---|
| closed-schema failure — declared member set, count/name correspondence, tuple ordering/uniqueness | `EXPECTATION_INCOMPLETE` | `BINDING_ABSENT` |
| value-content structural failure — unsupported value type (F4), finite or non-finite float in a Domain-A position (F4/F5), depth or node budget (F6), lone surrogate (F7), digit limit (F8) | `RESOLVER_INPUT_STRUCTURE_INVALID` with the category | `BINDING_ABSENT` |

No other expectation-side structural token may exist, and `EXPECTATION_CANONICALIZATION_UNSUPPORTED` MUST NOT
appear in any implementation, test or record (a census test asserts its absence).

# PART XV — FAIL-CLOSED MATRIX (one token per condition, one stage, one reason class per row)

No refusal may become `SATISFIED`. Every refusal yields `overall_state ∈ {UNKNOWN, NOT_ESTABLISHED}` and no
positive claim. Each row states its **stage** (S1–S6, or `—` for a non-stage fault) and its **reason class**, per
the single discriminator and the digest-comparison-side rule of XIV.3. **The first failing stage decides, and
when several rows apply inside that stage the rule of XIV.3.1 decides** (lowest-numbered applicable row supplies
the primary code; `failure_codes` is the sorted deduplicated union of that stage's applicable tokens). Per-entry
invariant states follow the total precedence rule of XIV.4.2: `UNKNOWN` for an S1–S4 refusal, and
`MISSING`/`UNKNOWN` per its three cases for an S5 refusal.

| # | Condition | Token | Stage | Reason class |
|---|---|---|---|---|
| 1 | malformed supplied content — any F1–F9, including hostile/uninspectable containers (F4), cycles or budget (F6), surrogates (F7), digit limit (F8) | `RESOLVER_INPUT_STRUCTURE_INVALID` (+ `detail_category` F1–F9) | S1 | `BINDING_ABSENT` |
| 2 | residual internal fault (fault-injection reachable only) | `RESOLVER_INTERNAL_FAILURE` | — | `INTERNAL_FAILURE` |
| 3 | no expectation supplied **and** the required set cannot be covered by a `REGISTERED` definition | `EXPECTED_VALUE_UNAVAILABLE` | S4 | `AUTHORITY_ABSENT` |
| 4 | unknown expectation (identity does not recompute) | `EXPECTATION_IDENTITY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 5 | incomplete expectation (declared member missing/undeclared, count/name mismatch, empty required set inside the object) | `EXPECTATION_INCOMPLETE` | S3 | `BINDING_ABSENT` |
| 6 | unsupported invariant (canonical name, no `REGISTERED` definition) | `EXPECTED_VALUE_UNAVAILABLE` | S4 | `AUTHORITY_ABSENT` |
| 7 | identity mismatch (task/version/twin/entry-pair/registry/target/resolver) | `EXPECTATION_IDENTITY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 8 | **supplied-artifact** digest mismatch — `expectation_digest`, `value_digest`, or a `definition_digest` carried in the expectation, against a value recomputed from supplied artifacts + validated authority | `EXPECTATION_DIGEST_MISMATCH` | S3 | `BINDING_ABSENT` |
| 9 | **authority reviewed-constant** digest mismatch — registry content vs `REGISTRY_SOURCE_DIGEST` / a definition's reviewed digest | `REGISTRY_SOURCE_NOT_CANONICAL` | S2 | `AUTHORITY_ABSENT` |
| 10 | **authority reviewed-constant** digest mismatch — target table/entry content vs `TARGET_TABLE_DIGEST` / `target_digest` | `PRODUCTION_TARGET_NOT_CANONICAL` | S2 | `AUTHORITY_ABSENT` |
| 11 | two definitions for one invariant name (authority-table integrity) | `EXPECTATION_DEFINITION_DUPLICATE` | S2 | `AUTHORITY_ABSENT` |
| 12 | two mapping rows for one `(entry_name, entry_version, task_class)` triple (authority-table integrity) | `PRODUCTION_TARGET_MAPPING_DUPLICATE` | S2 | `AUTHORITY_ABSENT` |
| 13 | task mismatch (task↔plan identity or content) | `IDENTITY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 14 | plan mismatch (plan content digest recomputation differs) | `EXPECTATION_IDENTITY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 15 | observation not transport-rooted / identity mismatch | `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED` | S5 | `EVIDENCE_INSUFFICIENT` |
| 16 | correlation failure | `OBSERVATION_CORRELATION_MISMATCH` | S5 | `EVIDENCE_INSUFFICIENT` |
| 17 | extraction contract revision mismatch | `EXTRACTION_CONTRACT_REVISION_MISMATCH` | S5 | `EVIDENCE_INSUFFICIENT` |
| 18 | scope divergence between observations | `OBSERVATION_SCOPE_DIVERGENCE` | S5 | `EVIDENCE_INSUFFICIENT` |
| 19 | declared `subject_scope` not observed | `EXPECTATION_SCOPE_NOT_OBSERVED` | S5 | `EVIDENCE_INSUFFICIENT` |
| 20 | contradictory observation | `CONTRADICTORY` | S5 | `EVIDENCE_INSUFFICIENT` |
| 21 | stale source (expectation no longer matches supplied task/plan) | `EXPECTATION_IDENTITY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 22 | no target row for the derived triple (single-valued partial lookup miss) | `PRODUCTION_TARGET_NOT_ESTABLISHED` | S4 | `AUTHORITY_ABSENT` |
| 23 | absent observable path — `value_state = ABSENT` | `EXPECTED_VALUE_UNAVAILABLE` (+ invariant `MISSING`) | S5 | `EVIDENCE_INSUFFICIENT` |
| 24 | present value whose type is inadmissible for the definition, incl. `PRESENT_NULL` where null is not admitted | `EXPECTATION_CONTRADICTORY` (+ invariant `UNKNOWN`) | S5 | `EVIDENCE_INSUFFICIENT` |
| 25 | partial evaluation (an invariant not evaluated while another is) | `EXPECTED_VALUE_UNAVAILABLE` (+ `MISSING`) | S5 | `EVIDENCE_INSUFFICIENT` |
| 26 | vocabulary mismatch (name outside the declared pair's vocabulary) | `EXPECTATION_VOCABULARY_MISMATCH` | S3 | `BINDING_ABSENT` |
| 27 | plan step not a canonical fragment id | `PLAN_STEP_NOT_CANONICAL` | S3 | `BINDING_ABSENT` |
| 28 | expectation value-content structurally invalid (unsupported type / float / depth / surrogate / digit limit) — see XIV.5; the Revision-3 token is retired | `RESOLVER_INPUT_STRUCTURE_INVALID` (+ F category) | S1 | `BINDING_ABSENT` |
| 29 | **structurally valid** plan document bearing a float (sole condition, X.3); a structurally invalid plan is row 1 | `PLAN_CONTENT_UNSUPPORTED` | S1 | `BINDING_ABSENT` |
| 30 | required set empty / incomplete / extra | `EMPTY_REQUIRED_INVARIANT_SET` / `INCOMPLETE_REQUIRED_INVARIANT_SET` / `EXTRA_PLAN_VERIFICATION_REQUIREMENT` | S3 | `BINDING_ABSENT` |
| 31 | plan render classification ≠ digest-bound source class | `PLAN_RENDER_CLASSIFICATION_MISMATCH` | S3 | `BINDING_ABSENT` |
| 32 | render-bearing task (v1 contract state — unchanged) | `RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, `REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED`, `SEQUENCE_AGREEMENT_NOT_ESTABLISHED`, `RENDER_EVIDENCE_MISSING` | S4 | `AUTHORITY_ABSENT` |
| 33 | a definition carries an authority class **not admitted in R2** (the reserved `FROZEN_CONTRACT_DERIVATION`) — a registry-integrity failure | `REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED` | S2 | `AUTHORITY_ABSENT` |

**Vocabulary census (MUST):** the table MUST contain **no token whose name implies detection of a stale or
replayed observation** (no `STALE_OBSERVATION*`, no `REPLAY*`), and MUST NOT contain
`EXPECTATION_CANONICALIZATION_UNSUPPORTED` (retired, XIV.5). The stage/class census of XIV.3.1 clause 2 MUST be
computed **from this table** by test, and the within-stage rule of XIV.3.1 MUST be exercised with at least two
in-stage check orders (clause 4). Row 33 is a **load-and-validate** failure of the registry: it is not producible
from a conforming R2 registry (which admits `CODE_CONSTANT` only, VIII.2) and MUST be covered by a startup test
that loads a deliberately non-conforming table. Each row MUST be reachable by at least one test —
except rows whose reachability is fixed by Part XXIV (rows 15–20, 23–25 and, in R2-A, rows 3/6/22 only after the
rung's own tests; the R2-A reachability subset is enumerated in XXIV). Rows 4/7/14/21 share one token by declared
many-to-one mapping (all are supplied-artifact identity failures); row 1 and row 28 carry all nine F categories
as values of one token; no further synonym may be added.

**Scope note (MUST).** `RESOLVER_INPUT_STRUCTURE_INVALID` covers malformed content of **supplied artifacts**
(task, plan, expectation). `EXPECTATION_INCOMPLETE` covers the **expectation object's** closed schema only
(VII.4.4). `PLAN_CONTENT_UNSUPPORTED` covers the **single** float-policy condition (X.3). The three MUST NOT be
used for one another's conditions. **Authority-table integrity** failures are S2 / `AUTHORITY_ABSENT` (rows 9–12, 33);
**coverage** failures for a given input are S4 / `AUTHORITY_ABSENT` (rows 3, 6, 22, 32); **supplied-artifact**
failures are S1/S3 / `BINDING_ABSENT`; **observation** failures are S5 / `EVIDENCE_INSUFFICIENT`.

# PART XVI — REPLAY

## XVI.1 Detectable — with the exact authoritative field

| Case | Detected? | Field / mechanism |
|---|---|---|
| stale expectation (older task/plan/registry/target table) | **YES** | expectation identity recomputed from the supplied task+plan+code constants: `task_identity`, `task_version`, `source_content_digest`, `plan_content_digest`, `registry_revision`+`registry_digest`, `target_table_revision`+`target_table_digest`, `definition_digest`, `production_target_id`+`target_revision`+`target_digest` |
| stale task | **YES** | `task_version` + `source_content_digest` |
| stale plan | **YES** | `plan_content_digest` (X.2) |
| stale definition | **YES** | `definition_digest` (+ registry digests) |
| stale target | **YES** | `target_digest` (+ `target_table_digest`) |
| cross-task expectation | **YES** | `task_identity` / `task_version` / `source_content_digest` |
| cross-plan expectation | **YES** | `plan_content_digest` |
| envelope relabelling that changes a correlated field | **YES — as a mismatch, not as staleness** | `validate_response_correlation` on `request_id`/`operation_name`/`entity_ids`/`schema_version` ⇒ `OBSERVATION_CORRELATION_MISMATCH`; session-envelope change ⇒ `OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED` |
| two observations, same `(task, scope, request)` identity, different digests | **YES** | `canonical_state_digest` inequality ⇒ `CONTRADICTORY` |
| repeated legitimate observation (identical identity tuple) | not a failure | collapses to one observation |
| cached expectation presented with changed inputs | **YES** | identity recomputation; presented with byte-identical inputs it is indistinguishable from a fresh resolution **by design** (resolution is pure, so re-verification is idempotent, not an attack) |

## XVI.2 NOT detectable — normative non-detection controls

| Case | Status |
|---|---|
| **relabelled stale observation** (old bytes, consistently correlated new envelope) | **`NOT DETECTABLE`** — no authoritative record of "the true request" exists, so no field can compare against it. This is a **non-detection control**: no specific code is required, reserved, or permitted; the test MUST assert that the outcome is not a staleness refusal and that **no token in the vocabulary could name one**. |
| replay of a legitimate expectation against a **later legitimate execution** of the same task/plan | **`NOT DETECTABLE`** — no execution identity exists and none may be invented |
| cross-session staleness ordering with different request identities | **`NOT DETECTABLE`** |
| observation freshness / recency | **`NOT CLAIMED`** (XVI.3) |

## XVI.3 Non-claims (verbatim, to appear in the landed artifact and in each definition's `non_claim`)

> **`SATISFIED` means only: the evaluated observation satisfies the production target specification selected by
> the supplied task content and approved by the reviewed code target table.**
> It does **not** mean: *this particular execution was authorized*; *the observed world is the requested digital
> twin*; *the task originated from the canonical catalog authority*; *the selected target was appropriate,
> intended, authorized, or requested by an authorized actor*; **or that the observation is fresh or recent.**

---

# PART XVII — M5 BOUNDARY

M12.6 MUST NOT: replace M5; duplicate `verify_render_job_evidence()`; promote render evidence into semantic
success; establish sequence agreement; establish request-digest agreement; establish artifact identity; mint
receipts; authorize execution; establish execution identity.

1. `render_state = VERIFIED` MUST remain unreachable; the existing render codes
   (`RENDER_TASK_CORRESPONDENCE_NOT_DECIDED`, `RENDER_EVIDENCE_MISSING`,
   `RENDER_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED`, `RENDER_JOB_TWIN_MISMATCH`,
   `REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED`, `SEQUENCE_AGREEMENT_NOT_ESTABLISHED`) MUST NOT be substituted by a
   new M12.6 code.
2. Where M5 cannot establish a fact, M12.6 MUST preserve `UNKNOWN`/`NOT_ESTABLISHED` rather than infer it.
3. `render_configured` MUST be `DEFERRED` in the registry.
4. **No render evidence is an M12.6 expectation source**: `M5_RECORD_FIELD` is removed from R2 scope, and
   `ProductionTargetSpec.planned_sequence_asset_path` is a design-intent constant only — it MUST NOT be compared
   to any render record, MUST NOT populate `sequence_agreement`, and MUST NOT be surfaced as render evidence.
5. M12.6 MUST NOT import `planning.unreal_evidence_contract`, `planning/unreal_render_*`,
   `planning/unreal_journal_attestation`, or any M4–M10 authority module; the AST allowlist gate MUST extend to
   the new modules with aliased/deferred/string positive controls.

---

# PART XVIII — FIRST ADMISSIBLE INVARIANT

## XVIII.1 **NO FIRST POSITIVE INVARIANT IS CURRENTLY ADMISSIBLE**

| Candidate | Value source | Exists today? | Verdict |
|---|---|---|---|
| `scene_initialized` via world identity | reviewed production target | **NO** — no repository artifact declares a *production* twin's world/level; the only in-repo world identities are harness-fixture ones | **NOT ADMISSIBLE** |
| `cameras_configured` via `actors[*].actor_class` | reviewed production target | **NO** | **NOT ADMISSIBLE** |
| `sequence_configured` via `sequences[*].sequence_asset_object_path` | reviewed production target | **NO** (and Q9-adjacent) | **NOT ADMISSIBLE** |
| `environment_configured`, `lighting_configured` | — | caller parameters only | **NOT ADMISSIBLE** |
| `render_configured` | — | M5-owned | **DEFERRED** |
| `FROZEN_CONTRACT_DERIVATION` payload-consistency candidates | reviewed code rule | derivable today | **NOT ADMISSIBLE IN R2** — the class is not a legal `authority_class` value in R2 (V.1, VIII.2, XV row 33), in addition to being payload-fidelity and therefore not registrable (V.3) |
| schema-forced candidates | — | yes | **VACUOUS — not registrable** |

The fixture-constant shortcut is refused: the fixture module self-declares as test-only; the value is a
*harness* identity, not a production target; the name-pinned vocabulary would force it under
`scene_initialized`, making it read as production scene initialization; and the result contract has no field
that could carry a harness-scoped qualifier.

## XVIII.2 Blocking condition

R2-B remains blocked until (i) the reviewed production-target artifact exists (V.5/V.6, with a
`source_reference`, digests, and its own review gate) and (ii) the three witnesses of XVIII.3 are recorded.

## XVIII.3 Witness protocol (designed; NOT executed)

- **Positive witness** — must yield `invariant_state == SATISFIED` with no `EXPECTED_VALUE_UNAVAILABLE` in
  `failure_codes`. Two grades, **both** required before any `SATISFIED` may be presented as semantic
  verification: (i) contract-valid (deterministic, R2); (ii) independently valid (live, R3).
- **Negative witness** — a **minimal-difference** partner varying only the asserted dimension, yielding
  `NOT_SATISFIED` **from that definition** with its own `mismatch_reason` — proving the invariant was
  *evaluated*, never skipped, never an ambient `UNKNOWN`.
- **Lossy witness set** — wrong scope ⇒ `EXPECTATION_SCOPE_NOT_OBSERVED`; scope lacking `subject_scope` ⇒ same;
  foreign world ⇒ `NOT_SATISFIED`; absent observable ⇒ `EXPECTED_VALUE_UNAVAILABLE`; contradiction ⇒
  `CONTRADICTORY`; missing member ⇒ `EXPECTATION_INCOMPLETE`; unregistered name ⇒ `EXPECTED_VALUE_UNAVAILABLE`.
  **The relabelled stale envelope is NOT in this set** — it is a non-detection control (XVI.2).
- **Blocking:** until XVIII.2 holds, **no definition may be `REGISTERED`** and every resolution refuses.

---

# PART XIX — NON-VACUITY

Every `REGISTERED` definition requires **positive, negative and refusal/lossy** witnesses, under six properties:
(1) minimal-difference pair — positive and negative differ in exactly one labelled `dimension`; (2)
discrimination — the negative witness yields `NOT_SATISFIED` under the same registry and target revisions as the
positive; (3) no schema-forced observables; (4) every definition states a `non_claim`; (5) registry-level floor —
zero `REGISTERED` definitions makes `SATISFIED` a validation error, with `REGISTERED_COUNT` participating in
`registry_digest`; (6) result-level floor — one `DEFERRED` required invariant forces a non-`SATISFIED` outcome.
**"Vacuous"** is decidable by construction (schema-forced observables) and falsifiable by witness (no recorded
negative witness ⇒ treat as vacuous, do not register). **Non-detection controls are not witnesses**: they assert
the *absence of a claim*, may not satisfy a witness obligation, and may not demonstrate discrimination.

---

# PART XX — REQUIRED TEST ARCHITECTURE

**Design only.** Two transverse rules: every negative control asserts its **specific** code (never an ambient
`UNKNOWN`), and every identity/tamper control additionally asserts the **absence** of a positive state.

Required categories and their specific assertions: arbitrary task cannot become canonical by field matching
(full identity equality; `origin_status` constant and digest-neutral); caller expected-value injection ⇒
`EXPECTED_VALUE_UNAVAILABLE` with the injected value in no field and no digest input; caller invariant injection
⇒ `EXPECTATION_VOCABULARY_MISMATCH`, **including after a live fragment-registry mutation**; caller predicate
injection ⇒ signature + AST guards; caller target injection ⇒ no such parameter exists (F1); mutable/nested
registry and target mutation ⇒ `REGISTRY_SOURCE_NOT_CANONICAL` / `PRODUCTION_TARGET_NOT_CANONICAL` plus the
immutable-value-type structural test; catalog-object substitution ⇒ **non-detection / invariance control** (M12.6 reads no catalog object and has no
admissible catalog-origin input): for byte-identical task/plan documents produced by the canonical catalog and by
a custom catalog instance, the M12.6 output MUST be byte-identical and MUST contain **no refusal attributable to
catalog origin, catalog identity or resolution**, and M12.6 MUST NOT refuse *because of* a substitution; where a
substituted catalog yields *different* task content, the resulting refusal MUST be the content-level refusal
(vocabulary/reconciliation against the declared pair) and a control MUST assert that code and assert the absence
of any origin-shaped code — no catalog-origin channel may be introduced to make the control observable; and the
**declared transitive channel** ⇒ changing `catalog_version` changes `plan_content_digest` and
`source_content_digest` (variance asserted) while the code and reason class stay those of any other
supplied-document content difference (semantic-invariance asserted, no distinguished path); task content mutation ⇒ `IDENTITY_MISMATCH`/`EXPECTATION_IDENTITY_MISMATCH`; plan content
mutation ⇒ `EXPECTATION_IDENTITY_MISMATCH`; definition mutation ⇒ `EXPECTATION_DIGEST_MISMATCH`; expectation
mutation (every field, incl. any internal cache) ⇒ serialization-derived digests unchanged or refusal; identity
tampering element-by-element ⇒ each specific code; digest tampering ⇒ `EXPECTATION_DIGEST_MISMATCH`; zero
invariants ⇒ `EMPTY_REQUIRED_INVARIANT_SET` with `SATISFIED` unconstructible; empty expectation ⇒
`EXPECTATION_INCOMPLETE`; partial evaluation ⇒ `MISSING` + `EXPECTED_VALUE_UNAVAILABLE`; unsupported invariant ⇒
`EXPECTED_VALUE_UNAVAILABLE` (`AUTHORITY_ABSENT`); contradictory observation ⇒ `CONTRADICTORY`; observation
substitution ⇒ `EXPECTATION_SCOPE_NOT_OBSERVED` / genuine `NOT_SATISFIED`; stale expectation/definition/target ⇒
`EXPECTATION_IDENTITY_MISMATCH` / `REGISTRY_SOURCE_NOT_CANONICAL` / `PRODUCTION_TARGET_NOT_CANONICAL`;
**relabelled stale envelope ⇒ non-detection control (no staleness refusal; no such token exists)**;
canonicalization and preflight edge cases (Domain A: UTF-16 ordering, ECMAScript escaping, surrogate refusal,
`|n| > 2^53-1`, float refusal, depth, empty containers, null/bool; Domain B: non-string keys, depth, node budget,
non-canonicalizable provenance; hostile containers whose inspection raises ⇒ F4; cycles caught by the bound ⇒ F6;
lone surrogates ⇒ F7; integer digit limit ⇒ F8; and the single float-policy refusal `PLAN_CONTENT_UNSUPPORTED`
for a structurally valid float-bearing plan); `evidence_identity`, `invariant_result_digest` and the whole-result `result_digest` uniqueness and independent
recomputation (one implementation and one call site each; an independent reimplementation reproducing all three
byte-for-byte; two entries differing in any declared member having different `invariant_result_digest`s; the
whole-result digest changing when any declared member of XIV.4.5 changes, including a nested
`expectation_identity` or `observation_identity` member); **absent-vs-present-null** controls (`value_state`
`ABSENT` with an empty `resolved_observables` vs `PRESENT_NULL` with a `ResolvedObservable` whose `value` is
`null` MUST produce different `evidence_identity`s and MUST NOT be conflated by any sentinel, omission or empty
collection); **path-grammar and ordering** controls (concrete-path grammar, ascending sort, no
select/reorder/dedupe, no normalization or case folding); **rung-ownership** controls (R2-A: lookup algorithm
present with an empty table, every lookup refusing `PRODUCTION_TARGET_NOT_ESTABLISHED`; R2-B: no lookup value
reachable); **R2-A reachability exhaustion** (no R2-A input yields `SATISFIED`, `NOT_SATISFIED`,
`EVALUATED_MISMATCH`, `INVALID_OBSERVATION`, `EVIDENCE_INSUFFICIENT` or any R2-B-only member of Part XXIV); cross-process determinism
(subprocesses with differing `PYTHONHASHSEED` ⇒ byte-identical digests, recording `sys.version` and the digit
limit); resolver preflight categories F1–F9 each with its own case and **no uncaught exception**;
`RESOLVER_INTERNAL_FAILURE` by fault injection only, plus a census asserting it appears in no gate/live record;
positive/negative/lossy witnesses; the full result-state classifier table including the one changed assertion;
closed-code census (token grammar, no whitespace, in-table); invariant-result schema closure; M5 non-promotion
(`planned_sequence_asset_path` consumed by nothing); digital-twin non-claim.
Property tests: totality (as defined in VII.7), purity, observation blindness, determinism, idempotence,
fail-closed monotonicity, identity perturbation, exact-set completeness, attribution completeness, schema
closure, `SATISFIED` structural coherence, plan-digest recipe uniqueness (one call site; `catalog_version`
invariance plus any-other-field variance), `origin-status` constancy.

---

# PART XXI — EXPLICIT NON-GOALS

M12.6 MUST NOT: create a second task authority without explicit review · create a mutable semantic catalog ·
infer expectations from observations · infer expectations from the runtime mapping · create execution identity ·
prove digital-twin observation binding without upstream evidence · authorize · execute · dispatch · persist ·
recover · issue receipts · replace M5 · introduce render verification · introduce sequence verification ·
introduce request-digest verification · introduce artifact verification · introduce caller predicates ·
introduce environment overrides · introduce test bypasses · introduce trusted mode · modify frozen extraction
semantics · weaken existing M12.5 refusals.
**Enforcement rule:** each non-goal MUST have at least one test that fails if it is violated; a non-goal without
a test is not a non-goal. Additionally declared for R2 and to be recorded in the landed artifact: preventing
in-process monkey patching (VIII.5); detecting a relabelled stale observation (XVI.2); detecting cross-session
staleness ordering; establishing canonical task origin (Part II); claiming observation freshness (XVI.3);
claiming target appropriateness/authorization (V.4.5).
**Preserved strengths (with enforcing controls):** caller-supplied predicate prohibition (signature + AST
guards); caller-supplied expected-value prohibition (closed registry schema + allowlist + injection tests);
M12.4 non-authority (Part VI + mapping-changes-nothing assertion); extraction non-verdict boundary (digest is
identity only; no `verified` flag read; extraction untouched); M5 separation (Part XVII + non-promotion tests);
execution-identity non-claim (XVI.2/XVI.3 + absence of any such field); digital-twin `NOT_ESTABLISHED` boundary
(Part XIII + non-claim assertions); no-first-invariant-until-real-witness (Part XVIII + `DEFERRED` state).

---

# PART XXII — OPEN QUESTIONS

1. **Canonical task origin** — `DECIDED` (Part II): content-indistinguishable; explicit `NOT_ESTABLISHED`
   boundary; claim set fixed. `OPEN` only as reviewer judgement on the posture, provided the `non_claim` states it.
2. **Catalog authority** — `DECIDED` (Part III).
3. **Legitimate target-specification inputs** — `DECIDED`: `task_class` and `target_state.expects_render` (render
   limb only); identity keys are not values; `digital_twin_id` is neither a value nor a selector. Previously-open
   sub-item (need for a distinct target id) — **closed**: the id exists and is derived.
4. **First positive/negative witness** — `DEFERRED` with the XVIII.2 blocking condition.
5. **Canonical expectation value representation** — `DECIDED`: Domain A only; exact comparisons
   (`EQUALS`/`SET_EQUALS`/`CONTAINS_ALL`/`EXACTLY_ONE`/`SUBSET_OF`); no epsilon/tolerance/normalization/case
   folding; binary64 values, when they ever appear, are the extraction contract's own 16-hex-digit strings
   compared byte-exactly. `OPEN`: whether a future transform expectation needs an ordering-only comparison.
6. **Revalidation vs immutability** — `DECIDED`: the stated property is "revalidated against a reviewed constant
   digest" plus "no caller-reachable runtime write path"; the word "immutable" MUST NOT be used for the tables.
7. **Same-process mutation threat model** — `OUT OF SCOPE` as prevention; `DECIDED` as detection (VIII.5).
8. **Contradictory observations across sessions** — `OPEN`: same `(task, scope, request)` identity contradictions
   are detected; different request identities are two observations and cross-session ordering is `NOT CLAIMED`.
   Reviewer input requested on whether a stricter same-session rule is desirable; position: no — it would invent
   ordering semantics the contract does not carry.
9. **Eventual M5 / request / sequence binding** — `DECIDED as upstream`: Q9/Q10/Q11 remain open, out of scope and
   unapproximated; `render_state = VERIFIED` stays unreachable.
10. **Authority classes and construction guard — `DECIDED` (no OPEN item remains here).**
    (a) `FROZEN_CONTRACT_DERIVATION` is **NOT ADMITTED IN R2** (V.1, VIII.2, VIII.4, XVIII.1, XV row 33): the R2
    `authority_class` domain is exactly `{CODE_CONSTANT}`, and a definition carrying the reserved value is refused
    at S2 / `AUTHORITY_ABSENT` (`REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED`) with a startup test. The earlier
    "admitted by the architecture, empty at R2" recommendation is **withdrawn**; admission requires a future
    design-gate revision stating the restricted form, the reviewed digest and the witnesses.
    (b) The construction guard is a **module-private sentinel**, an accidental-construction guard only — never a
    security boundary; the true invariant is result-coherence validation (XIV.1, XIV.2).
    (c) Within-stage precedence and aggregation are **DECIDED** (XIV.3.1), and the whole-result members are fully
    derived (XIV.4.6).
    The two previously disclosed refinements (the `catalog_version` scoping and the two-condition
    `PLAN_CONTENT_UNSUPPORTED`) remain **flagged for challenge** — they are disclosed, not open decisions.

---

# PART XXIII — IMPLEMENTATION GATE

**R2-A** may proceed only when its **refusal and result schemas are fully defined**: the closed refusal
vocabulary with stage and reason class for every row (Part XV) and the prose-code defect fixed; the six reason
classes, the digest-comparison-side rule, the authority-table-integrity vs coverage split and the S1–S6 order
(XIV.3); the closed `InvariantVerificationResult` schema with `value_state`, `resolved_observables`,
`evidence_identity`, `invariant_result_digest` and the whole-result `result_digest` recipes (XIV.4); the
expectation schema with rejection rules (Part IX, XIV.5); the single plan-content-digest recipe over the **full**
canonical document (X.2); the two canonical domains with per-digest inputs and the pinned-runtime statement
(Part XI); the registry and (empty) target tables with digests, integrity tokens, the **single-value R2
`authority_class` domain** and the load-and-validate refusal for the reserved class (Part VIII, V.1, V.3, V.5);
the bounded structural preflight with traversal, cycle, exception-attribution and budget rules (VII.4) and the
attribution rule (VII.5); the totality definition (VII.7); and the **target lookup machinery against an empty
reviewed table** (V.4.9, V.5.1).

**R2-A MUST additionally implement** the four result-state enums, the mapper and the classifier in full, with the
**fixed reachable subset**, the **fixed R2-B-only subset** and the exhaustion obligation (XIV.3 clauses 1–4,
Part XXIV), the **within-stage precedence and aggregation rule** with its census and order-independence tests
(XIV.3.1), and the **per-entry refusal-state precedence** (XIV.4.2), plus the compatibility-table change and its
single affected assertion — all **decisions**, not implementation choices.

**R2-B** MUST remain blocked until all of the following hold:

1. an authoritative, reviewed **production target** exists (V.5/V.6) with `source_reference` and its digests, and
   the table is populated in R2-B — never in R2-A (V.4.9, V.5.1);
2. a **real positive witness** exists — independently valid, not merely contract-valid (XVIII.3 grade ii);
3. a **real negative witness** exists — a minimal-difference partner evaluated to `NOT_SATISFIED` **from that
   definition**, with its own `mismatch_reason`;
4. the **target-selection semantics** (V.4) are adopted and implemented verbatim, including the single-valued
   partial lookup and the excluded appropriation claim;
5. **R2-A is implemented, independently reviewed and green** on the implementation base, with the classifier, the
   digest recipes and the reachability exhaustion tests passing.

Both rungs additionally require **a final independent blind review of this Revision-6 artifact returning CLEAR**
(different model, separate process, frozen artifact copy, verdict quoted in the R2 handoff). This artifact does
**not** authorize implementation.

# PART XXIV — R2-A SCOPE (normative)

**R2-A IS:** machinery · expectation resolution · authority/identity binding · **target lookup against an empty
reviewed table** · refusal-only infrastructure · deterministic result/refusal machinery · the closed schemas,
digests, tables (with **zero** target entries) and preflight · the four result-state enums, the mapper and the
classifier · the tests and properties of Part XX.
**R2-A IS NOT:** a positive semantic invariant · a production semantic verifier · a digital-twin authority · an
execution authorization mechanism · a freshness authority · a render verifier · the owner of any production target
value.

**MUST:** no `SATISFIED` result is producible in R2-A (every required invariant is `DEFERRED`, and with an empty
target table every lookup refuses, so every resolution refuses with the **single deterministic outcome** of
XIV.3.1's R2-A demonstration: primary `EXPECTED_VALUE_UNAVAILABLE`, stage S4, class `AUTHORITY_ABSENT`,
`failure_codes = ["EXPECTED_VALUE_UNAVAILABLE", "PRODUCTION_TARGET_NOT_ESTABLISHED"]`, every required invariant
`UNKNOWN`, `semantic_state = NOT_ESTABLISHED`, `overall_state = NOT_ESTABLISHED`); no positive invariant is
registered; no production target value is invented; **no definition may carry `FROZEN_CONTRACT_DERIVATION`**
(V.1, VIII.2) and R2-A ships the single-value `authority_class` domain plus the S2 refusal for it (XV row 33);
the within-stage rule (XIV.3.1) is implemented, not merely described; no document may describe R2-A as semantic
verification; the R2-A output vocabulary is exercised only through refusal paths, with witness tests marked
`NOT PROVEN` rather than passing.

## XXIV.1 R2-A / R2-B state boundary (MUST — decided, not an implementation choice)

| Vocabulary | R2-A lands | Reachable in R2-A | R2-B-only (MUST NOT be producible in R2-A) |
|---|---|---|---|
| `invariant_state` (4) | the whole enum | `UNKNOWN`, `MISSING` | `SATISFIED`, `NOT_SATISFIED` |
| `semantic_state` (5) | the whole enum | `UNKNOWN`, `NOT_ESTABLISHED` | `SATISFIED`, `NOT_SATISFIED`, `INVALID_OBSERVATION` |
| `overall_state` (4) | the whole enum | `UNKNOWN`, `NOT_ESTABLISHED` | `SATISFIED`, `NOT_SATISFIED` |
| `outcome_reason_class` (6) | the whole enum | `BINDING_ABSENT`, `AUTHORITY_ABSENT`, `INTERNAL_FAILURE` | `SATISFIED`, `EVALUATED_MISMATCH`, `EVIDENCE_INSUFFICIENT` |
| stages S1–S6 | the whole classifier | S1, S2, S3, S4 | S5, S6 |
| refusal vocabulary | the whole closed table | every row **except** rows 15–20 and 23–25 (S5) and rows that require a resolved target; row 33 is reachable only through the load-and-validate startup test with a deliberately non-conforming table (a conforming R2 registry cannot contain it) | rows 15–20, 23–25 and any row that requires a resolved target or a `REGISTERED` definition |
| within-stage rule (XIV.3.1) | the rule, its census test and its order-independence test | the S4 aggregate of the R2-A demonstration (rows 6 + 22) | in-stage aggregation over S5 rows and over rows that require a resolved target |

Grounds (MUST be stated in the landed artifact): with **zero** `REGISTERED` definitions and an **empty** target
table, stage S4 always fails before S5 and S6 can run, so observation binding, evaluation and every
observation-level or evaluation reason class are **unreachable** in R2-A. That is a property of the empty
authority state, not a scope restriction on the *code*: R2-A ships the S5/S6 paths, the enums and the mapper, and
its tests MUST include an **exhaustion property** asserting that no R2-A input yields any R2-B-only member listed
above (the property is falsified, by construction, the moment a definition is `REGISTERED` — which is exactly
R2-B's opening condition).

**Absolute prohibition (MUST).** `SATISFIED` and `NOT_SATISFIED` are unreachable and MUST NOT be producible in
R2-A: no path, flag, override or test fixture may yield them, and the result-coherence validation (XIV.2) plus
the rung's startup tests MUST reject any construction that claims them.

# PART XXV — RELATIONSHIP TO M12.5 AND REPOSITORY BASE

1. **M12.5 remains the sole semantic-verdict owner.** M12.6 extends the M12.5 architecture; it does not replace
   it and does not create a second semantic-verdict authority. Only `verify_semantic_target` may produce a
   semantic verdict; the resolver produces expectations or refusals.
2. **M12.6 MUST NOT weaken existing M12.5 refusal semantics.** The required-set equality (both directions), the
   non-empty requirement, the render-classification rule, the contradiction and scope rules, the closed failure
   vocabulary, and every existing refusal token remain in force. The only permitted changes are (a) the declared
   result-state expansion (XIV.3) — **implemented in R2-A, one affected assertion, with its measured
   compatibility table**; (b) the Domain A migration of the M12.6 result canonical form (XIV.4.5); and (c) the
   **`verifier_revision` constant bump** to `"m12.6-v1"` (XIV.4.5), validated at construction. None of the three
   may alter an existing refusal's code or its non-positive outcome.
3. **Implementation base:** `4897d9d4524df6cc2fa59caf0c86fa0b269f35a6` — current `main`, containing the M12.5
   implementation and its post-implementation hardening (PR #140). Implementation instructions MUST NOT be based
   on any other head, in particular not on the obsolete PR #127 head and not on the unmerged live-promotion-gate
   branch head. Measured lineage: the live-promotion-gate head differs from this base **only** by
   `.github/workflows/m12-5-live-promotion.yml`, `docs/M12_5_LIVE_PROMOTION_GATE.md` and two `tests/m12` files;
   `planning/m12/**`, `planning/unreal_state_extraction/**`, `unreal_evidence_contract.py` and
   `unreal_transport_contract.py` are identical, and `verification.py` (`4d20d868…`) and
   `verification_result.py` (`ef518858…`) have byte-identical blobs on both. Every measurement in this artifact
   therefore holds on the base unchanged.

---

# PART XXVI — DOCUMENT CONSISTENCY AUDIT (Revision 6)

A full document-only consistency audit was performed over this Revision-6 text, searching the mandated term set
(`stage precedence`, `first failing stage`, `failure_codes`, `outcome_reason_class`, `S1`–`S6`,
`render_job_identity`, `render_attempt_identity`, `render_evidence_identity`, `evidence_trust_basis`,
`observation_digests`, `session_identity`, `engine_identity`, `extractor_identity`,
`FROZEN_CONTRACT_DERIVATION`, `R2-A`, `R2-B`, `NOT_ESTABLISHED`, `NOT_SATISFIED`, `SATISFIED`), and the complete
reason-class/stage matrix was re-verified programmatically row by row, including the stage-homogeneity census of
XIV.3.1. The audit's exact result (occurrence counts, per-row stage/class agreement, per-stage class homogeneity
and the blocker-by-blocker closure evidence) is recorded in the change report accompanying this revision. The
checks are: (1) within-stage precedence exists exactly once (XIV.3.1), the "no tie-resolution logic exists"
claim is gone, and the R2-A state yields exactly one outcome; (2) every typed member of XIV.4.5 has a
derivation and a nullability rule in XIV.4.6/XIV.4.6.1, the six `session_identity` keys are enumerated, and the
render triple is coherence-bound; (3) `FROZEN_CONTRACT_DERIVATION` appears as a **reserved, not admitted** class
in V.1, VIII.2, VIII.4, XVIII.1, XXII, XXIII and XXIV with no OPEN or recommendation wording remaining;
(4) the state expansion is stated as an R2-A obligation with the reachable subset, the R2-B-only set and the
R2-B authority/witness condition, in XIV.3, XXIII and XXIV.1 alike; (5) every `BINDING_ABSENT` row concerns a
supplied artifact and every `AUTHORITY_ABSENT` row a code-level authority source, with authority-table integrity
at S2, coverage at S4 and the digest-comparison-side rule applied to every digest row; (6) `NOT_ESTABLISHED` is
never collapsed into `UNKNOWN`, `NOT_SATISFIED` is never collapsed into `UNKNOWN`, and every state mention agrees
with XXIV.1; (7) the retired canonicalization token appears nowhere except as a retirement record;
(8) `result_digest` is the whole-result digest with exactly one enumerated member set and
`invariant_result_digest` the per-entry digest; (9) target-selection rung ownership is stated identically in
V.4.9, V.5.1, XXIII and XXIV; (10) no statement claims cross-runtime determinism, canonical task origin, twin
verification, execution identity, target appropriateness, or observation freshness.

## R1 REVISION 6 VERDICT

**R1 REVISION 6 COMPLETE — READY FOR INDEPENDENT BLIND REVIEW**

All four blockers of the third independent review are closed normatively and mechanically at their locations
(Part 0.1) — the within-stage precedence and aggregation rule with its R2-A demonstration, the complete
derivation and nullability of every typed member of the whole-result canonical input, the decision that
`FROZEN_CONTRACT_DERIVATION` is **not admitted in R2**, and the removal of the R2-B/R2-A state-wording
contradiction. The full consistency audit found no remaining contradiction, the stage/class matrix is
homogeneous by census, every vocabulary item is defined or withdrawn exactly once, and R2-B remains blocked on
the production-target artifact, the two real witnesses, and a green R2-A rung. Implementation is **not** authorized by this artifact: the next step is an independent **blind**
review, and R2-A may begin only after that review returns CLEAR. **Implementation-ready** is claimed only for
R2-A's *decision set* — every listed decision is closed without requiring implementer interpretation — never for
R2-B.