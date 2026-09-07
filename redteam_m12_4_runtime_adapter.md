# M12.4 Red-Team Package — REMEDIATED (PR #91)

**Scope:** `planning/m12/runtime_adapter.py` + M12.1/M12.2/M12.3 contracts + existing runtime boundary.
**Head:** `338573c84fbba9d2b79699e0f1e61845e8ca1b97` — current PR #91 head (after Round-4 structural hardening).
**Rounds covered:** Round-1 (original 8 findings), Round-2 (B1-B9 blockers, gate #1), Round-3 (gate #2), Round-4 (R4-1..R4-12).
**Method:** Original 8 findings reproduced black-box on head `ba3b360`; remediation applied as a single M12.4 change (no new milestone); each fix verified by deterministic adversarial regression tests and re-probed.

This document records, for every original finding: the attack scenario/invariant, how it was fixed, and the regression test that now prevents recurrence. A section at the end re-runs the original probes against the remediated code to confirm each behavior changed.

---

## Finding 1 — Authority/secret smuggling via plan provenance (HIGH)

- **Original behavior:** `map_unreal_execution_plan` copied `dict(plan.provenance)` verbatim into the mapping and its canonical JSON; a crafted plan with `authorization_id`/`hmac_key` in provenance forwarded them.
- **Fix (in `runtime_adapter.py`):** added `is_forbidden_authority_key()` (mirrors M12.1 exact+substring matcher) and `_validate_provenance()`; both plan-level and per-step provenance are validated and **rejected** on forbidden key (raise `UnrealRuntimeAdapterError`). Legitimate fields preserved.
- **Regression tests:** `test_fix1_forbidden_authority_in_plan_provenance_rejected` (parametrized over `authorization_id`, `receipt`, `attempt_nonce`, `hmac_key`, `api_key`, `credential`, `recovery_authority`, `artifact_id`, `manifest_id`, `scheduler`, `retry_controller`, `protected_flag`, `is_authorized`, ...), `test_fix1_forbidden_authority_in_step_provenance_rejected`, `test_fix1_legitimate_provenance_preserved`, `test_fix1_is_forbidden_helper`.
- **Re-probe result:** `plan.provenance={'authorization_id':'f','hmac_key':'s'}` → rejected; `{'proposal_source':'qwen'}` → preserved.

## Finding 2 — Runtime write-authority mismatch (MEDIUM)  [SUPERSEDED by R4-4]

- **Original behavior:** an all-inspect-only plan compiled to `AtlasTaskDefinition` with `allow_writes=True`.
- **Original fix (superseded):** the adapter reconciled `allow_writes` to the plan's capability by emitting `allow_writes=False` via `dataclasses.replace(compiled, allow_writes=False)`.
- **Round-4 supersession (R4-4 — REJECT, DON'T REWRITE):** silently dropping the source's write intent was flagged as a surviving concern (a caller asking for writes was silently downgraded). The `dataclasses.replace(..., allow_writes=False)` rewrite is **removed**. A source task that declares write mutations (`allowed_mutations` non-empty) under an inspect-only mapping, or a compiled task with `allow_writes=True`, is now **REJECTED** with `UnrealRuntimeAdapterError`. This is an intentional contract tightening: catalog-resolved tasks declare `allowed_mutations={task_class}`, so they must first be tied to genuinely inspect-only intent (empty `allowed_mutations`, expressible upstream in M12.1 via `normalize_unreal_semantic_request`) before the inspect-only adapter will map them.
- **Regression tests:** `test_r4_write_capable_source_rejected_not_rewritten`, `test_r4_compiled_allow_writes_rejected_not_rewritten`, `test_r4_allow_writes_tool_violation_rejected`; `test_fix2_inspect_only_plan_does_not_claim_write_authority` (now maps an inspect-only source).
- **Re-probe result:** a write-declaring source raises `UnrealRuntimeAdapterError` (was silently zeroed); a genuinely inspect-only source compiles to `allow_writes=False` and maps.

## Finding 3 — Dependency/target-state/input fidelity (MEDIUM)

- **Original behavior:** copied plan `dependencies`/`required_inputs`/`target_state_contributions` verbatim; crafted alterations mapped anyway.
- **Fix:** `_reconcile_step_fidelity()` re-derives required inputs, target-state contributions, idempotence, and dependencies from the **canonical fragment** (`canonical_fragment`) plus a reconstruction of M12.3's producer→step map; any mismatch raises `UnrealRuntimeAdapterError`. The mapping is now independent of crafted plan contents on these critical fields.
- **Regression tests:** `test_fix3_dropped_dependency_rejected`, `test_fix3_target_state_tamper_rejected`, `test_fix3_idempotence_tamper_rejected`, `test_fix3_operation_reorder_rejected`.
- **Re-probe result:** dropping a dependency, blanking target-state contributions, changing idempotence, or reordering operations all rejected. (Required-input tamper cannot diverge from canonical because every canonical M12 fragment has empty `inputs`; the check makes any non-empty divergence fail.)

## Finding 4 — Per-step fragment provenance lost (LOW/MEDIUM)

- **Original behavior:** `UnrealRuntimeStepMapping` had no provenance; `fragment_id`/`fragment_version` dropped.
- **Fix:** each step mapping now carries `fragment_id`, `fragment_version`, and a deep-frozen step `provenance`, included in `to_json_compatible()` and canonical JSON.
- **Regression test:** `test_fix4_fragment_identity_version_preserved_in_steps`.
- **Re-probe result:** steps carry `(scene_setup, 1)`, `(camera_setup, 1)`, `(sequence_setup, 1)` and serialized fragment ids/versions.

## Finding 5 — Render-plan classification trust (LOW)

- **Original behavior:** `require_render_boundary = plan.render_plan` trusted a caller-supplied flag (under-flag was only caught by the compile fence).
- **Fix:** reconcile `plan.render_plan` against authoritative `source_task.render_task`; fail closed on **any** mismatch (over-flag or under-flag). Render path preserved: render-bearing → `requires_existing_render_submission_path=True`, `runtime_task=None`, `can_execute=False`.
- **Regression tests:** `test_fix5_render_underflag_rejected`, `test_fix5_render_overflag_rejected`, `test_fix5_render_true_path_unchanged`.
- **Re-probe result:** under-flag and over-flag both rejected with `render_plan mismatch`; true render path yields boundary + no runtime task.

## Finding 6 — Immutable provenance (LOW)

- **Original behavior:** mapping frozen at attribute level but nested `provenance` dict mutable; mutation changed `canonical_json()`.
- **Fix:** `_deep_freeze()` converts mapping-level and step-level provenance to `MappingProxyType`/tuple at construction; mutation after construction raises `TypeError`.
- **Regression test:** `test_fix6_provenance_deep_frozen`.
- **Re-probe result:** `mapping.provenance['x']='y'` raises `TypeError`; canonical JSON stable.

## Finding 7 — Semantic fidelity (aggregation) — EXPLICIT CONCLUSION

- **Conclusion (code-carried, not doc-only):** the existing Atlas runtime represents an M12 task as **one aggregate `AtlasTaskDefinition`** (one `unreal_inspect` action via the M12.1 compiler); it has **no per-fragment runtime operations**. Therefore M12.4 does **not** claim per-fragment executable fidelity. The mapping carries `semantic_fidelity="aggregate"` (non-render) / `"unavailable"` (render); a step whose semantic operation is not a known canonical fragment fails closed. M12.4 does not redesign M4–M10 and introduces no second runtime; per-fragment distinctions remain declared semantics that M12.5's verifier consumes from the plan.
- **Regression test:** `test_fix7_semantic_fidelity_declared`.

## Finding 8 — Placeholder verifier (M12.5, documented)

- **Conclusion:** deferred to M12.5. M12.4 performs no verification and never claims verified status. Documentation distinguishes:
  - **target-state declaration** — declared semantic invariants (no verification authority);
  - **runtime evaluator representation** — M12.1 structural placeholder (must not be treated as independent verification);
  - **actual independent verification** — M12.5's job via the existing evidence machinery (must not trust self-reported evidence).
- **Regression test:** none added (M12.5 work); existing `test_mapping_object_has_no_authority_methods` (no `verify`) and `test_render_mapping_does_not_submit_or_fabricate` still pass.

---

## Verification of remediation (exact)

- `pytest tests/m12/` → **143 passed** (88 prior + 55 M12.4, of which 31 are adversarial regression tests)
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **511 passed**
- `pytest -m "not integration"` → **1594 passed** (no regressions)
- Authority-isolation import scan clean; no M4–M10 / Blender / authority module / C++ change; no new runtime or authority field.
- GitHub Actions on head `a90d021…`: `tests (3.9)` → success; `tests (3.11)` → success.

## Post-remediation re-probe (original adversarial cases)

| Probe | Before (ba3b360) | After (a90d021) |
|---|---|---|
| `authorization_id`/`hmac_key` in plan provenance | forwarded into mapping + canonical JSON | `UnrealRuntimeAdapterError` |
| spoofed render_plan under/over-flag | under-flag only blocked by compile fence | both rejected explicitly |
| dropped dependency / blanked target-state / idempotence tamper / op reorder | accepted (dependency silent drop) | `UnrealRuntimeAdapterError` |
| `allow_writes` on inspect-only plan | True | False |
| fragment id/version in step mapping | absent | present (id + version) |
| mutate `mapping.provenance` | succeeds, changes canonical | `TypeError` (deep-frozen) |
| identity mismatch / foreign plan | rejected | rejected (unchanged) |
| render → runtime task | None (boundary) | None (boundary), fidelity `unavailable` |

## Scope guard
No production authority changed, no M4–M10 behavior change, no Blender, no live Unreal launched, no workflow/action-runner tests, no M12.5 begun, PR #91 not merged.

---

# ROUND-2 REMEDIATION — Independent Red-Team BLOCKERS (head 648a657+)

## Blocker 1 — Nested / casing / alias provenance smuggling

- **Probe on a90d021 (confirmed):** nested `{"notes": {"authorization_id": ...}}` accepted; `apiKey`/`IS_AUTHORIZED`/`session_token` bypassed the filter.
- **Fix:** `is_forbidden_authority_key` now normalizes casing/separators (`api_key`/`apikey`/`API_KEY` → `apikey`; `is_authorized`/`IS_AUTHORIZED` → `isauthorized`) and checks a broad authority/credential vocabulary (authorization, receipt, nonce, HMAC, credential, password/secret, session, jwt, bearer, recovery, scheduler/retry, protected, artifact/manifest, token, api-key, cert). `_validate_provenance` recurses through mappings and sequences at any depth, rejects non-string keys and non-JSON values, rejects adapter-reserved keys, and never strips-and-continues.
- **Regression tests:** `test_r2_forbidden_authority_nested_casing_alias_rejected` (parametrized token × shape), `test_r2_nested_step_provenance_rejected`, `test_r2_is_forbidden_alias_vocabulary`.

## Blocker 2 — Embedded runtime_task mutability

- **Probe (confirmed):** `mapping.runtime_task.allowed_action_tools.add("unreal_render")` succeeded; canonical JSON did not bind it.
- **Fix:** the mapping no longer exposes a mutable `AtlasTaskDefinition`. It stores an immutable `runtime_task_snapshot` + `runtime_task_digest`; `materialize_runtime_task()` returns a fresh isolated deep copy. `canonical_json` serializes the full snapshot.
- **Regression tests:** `test_r2_runtime_task_no_mutable_handle_exposed`, `test_r2_canonical_binds_runtime_permissions`.

## Blocker 3 — Asymmetric render-path fidelity (and dropped preconditions/verification)

- **Probe (confirmed):** render-path steps bypassed `_reconcile_step_fidelity`; preconditions/verification_requirements dropped.
- **Fix:** the same `_reconcile_step_fidelity` (inputs, target-state, idempotence, prefix-only dependencies, preconditions, verification requirements) applies to EVERY step including render steps; preconditions/verification_requirements are now first-class reconciled fields carried in the mapping.
- **Regression tests:** `test_r2_render_path_step_fidelity_reconciled`, `test_r2_render_path_precondition_tamper_rejected`, `test_r2_preconditions_and_verification_preserved`, `test_r2_canonic_step_layout_has_preconditions_and_verification`.

## Blocker 4 — Source binding

- **Probe (confirmed):** same-identity / different-content substitution undetected from the plan alone.
- **Fix:** `compute_source_task_digest` deterministically binds resolved canonical source content; the mapping carries/serializes `source_task_digest`; optional `expected_source_task_digest` rejects substitution; plan target-state is reconciled against the source task's target-state invariants.
- **Regression tests:** `test_r2_source_digest_binds_resolved_content`, `test_r2_expected_source_digest_rejects_substitution`, `test_r2_deterministic_source_binding`.

## Blocker 5 — Adapter-owned provenance shadowing

- **Probe (confirmed):** `setdefault` let caller seed `recognized_render_plan`/`fragment_version` shadows.
- **Fix:** adapter-owned keys are reserved (caller-supplied → rejected); fragment identity in step provenance is overwritten with canonical truth.
- **Regression tests:** `test_r2_adapter_owned_provenance_not_shadowable`.

## Blocker 6 — Immutability / serialization (nested MappingProxyType crash)

- **Probe (confirmed):** nested MappingProxyType broke `canonical_json()` with `TypeError`.
- **Fix:** provenance and runtime-task snapshot are deeply frozen AND recursively thawed inside the canonical serializer; nested structures are both immutable and JSON-safe.
- **Regression tests:** `test_r2_nested_provenance_canonical_json_serializes`, `test_r2_nested_provenance_immutable_after_construction`.

## Blocker 7 — Contract / documentation alignment

See `docs/UNREAL_M12_4_RUNTIME_ADAPTER.md` "Contract alignment" section: authoritative vs validated vs immutable vs declared vs deferred-to-M12.5 are stated explicitly.

## Post-remediation replay (probes re-run on the fixed head)

| Probe (was true defect) | After remediation |
|---|---|
| nested `authorization_id`/`hmac_key` in plan provenance | `UnrealRuntimeAdapterError` |
| `apiKey`/`IS_AUTHORIZED`/`session_token` (casing/alias) | `UnrealRuntimeAdapterError` |
| `mapping.runtime_task.allowed_action_tools.add("unreal_render")` | no `runtime_task` attribute; snapshot toolset immutable; `materialize` copy isolated |
| render-path target-state / precondition tamper | `UnrealRuntimeAdapterError` |
| same-identity/different-content substitution | rejected with `expected_source_task_digest` |
| congruent fragment_version shadow | overwritten to canonical (1) |
| nested MappingProxyType in canonical_json | serializes cleanly (no TypeError) |

## Validation (Round-2 head)

- `pytest tests/m12/` → **226 passed**
- `pytest tests/m12/ tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/test_unreal_task_planner.py tests/test_unreal_autonomous_executor.py tests/test_task_definition.py tests/test_authorized_task_runtime.py tests/m10/ tests/m11/` → **594 passed**
- `pytest -m "not integration"` → **1677 passed** (was 1594, +83; no regressions)
- Authority-isolation import scan clean; no M4–M10 / Blender / authority change; no execution/verification authority added.

---

# ROUND-3 REMEDIATION — Independent Red-Team Gate #2 (Astra + Claude 5 BLOCK)

Second gate found 9 concrete blockers, all independently confirmed by both
reviewers + Hermes black-box probes. All remediated in this M12.4 line.

## Blocker -> root cause -> fix -> regression test -> post-fix result

| B | Root cause | Fix (code) | Regression test(s) | Post-fix probe |
|---|---|---|---|---|
| B1 Runtime action authority | compiled AtlasTaskDefinition tool/action authority never reconciled | `_reconcile_runtime_authority` rejects non-inspect tools/actions/evidence + allow_writes, fail closed | `test_b1_render_tool_in_inspect_task_rejected`, `test_b1_extra_render_tool_rejected`, `test_b1_unknown_tool_in_actions_rejected` | unreal_render/unknown tool -> rejected |
| B2 Render classification | derived only from task_class; render fragment escaped | UNION of class + canonical fragment render semantics; render fragment under non-render class fails closed | `test_b2_render_setup_via_non_render_class_rejected`, `test_b2_render_class_still_fails_toward_boundary`, `test_b2_artifact_validate_still_routes_to_boundary` | render_setup via non-render -> rejected |
| B3 Provenance smuggling | denylist-only + source metadata/snapshot unvalidated | CLOSED ALLOWLIST for caller provenance; source-metadata allowlist + recursive high-confidence authority scan on snapshot | `test_b3_unknown_provenance_key_rejected`, `test_b3_source_metadata_smuggling_rejected`, `test_b3_legitimate_provenance_preserved` | camera_slots authorization_id -> rejected |
| B4 Hidden mutable backing task | `__dict__["_materialized_runtime_task"]` retained | snapshot sole source of truth; materialize rebuilds from snapshot + asserts digest | `test_b4_no_hidden_backing_task`, `test_b4_materialize_rebuild_matches_digest` | no hidden attr; materialize isolated |
| B5 Unresolved requirements | missing producer -> empty deps accepted | every fragment requirement must resolve to earlier producer; else fail closed | `test_b5_orphan_step_fails_closed` | orphan camera -> rejected |
| B6 Catalog version override | caller could set catalog_version freely | catalog_version must equal plan (and source metadata); else fail closed | `test_b6_catalog_version_conflict_rejected`, `test_b6_catalog_version_agrees_accepted` | cv=999 -> rejected |
| B7 declared/validated | declared constant False; _RECONCILED_FIELDS doc-only | declared True only when non-canonical caller content carried; reconciled flag on mapping | `test_b7_declared_false_for_clean_mapping`, `test_b7_step_with_caller_provenance_is_declared` | clean steps declared=False |
| B8 Strict JSON | allow_nan=True; NaN/Infinity/Fraction; key coercion | allow_nan=False in all canonical paths; strict-JSON walk on snapshot | `test_b8_nan_via_source_parameter_rejected`, `test_b8_canonical_json_is_strict_and_stable` | NaN -> rejected |
| B9 Self-validating construction | UnrealRuntimeMapping could be constructed invalid | __post_init__ runs same canonical validation (provenance, digest, render, authority) | `test_b9_direct_invalid_render_contradiction_rejected`, `test_b9_direct_invalid_snapshot_tools_rejected` | invalid direct construction rejected |

## Validation (Round-3 head)

- `pytest tests/m12/` -> 246 passed
- semantic/runtime/Unreal subset -> 614 passed
- `pytest -m "not integration"` -> 1697 passed (was 1677, +20 Round-3 tests)
- authority-isolation import scan clean (5 passed); no M4-M10 / Blender / authority change


---

# ROUND-4 STRUCTURAL HARDENING — R4-1 .. R4-12

Fourth adversarial gate returned groups of surviving findings. Rather than expand
vocabulary-based filters further, Round-4 made the trust boundary STRUCTURAL:
invalid states are unrepresentable / fail closed, and the adapter never relies on
caller cooperation for security-critical invariants. Architecture changed to make
the invariants true; every fix is covered by deterministic `test_r4_*` adversarial
regression tests.

The reviewers' surviving concerns (source binding caller-cooperative; direct
construction not on the same validation path; `target_state.expects_render`
axis missing; `allow_writes` silently zeroed; vocabulary-scan provenance;
lossy catalog-version coercion; Fraction/unsupported-numeric acceptance;
snapshot metadata not authority-scanned on direct construction) map 1:1 to
R4-1/R4-2/R4-3/R4-4/R4-5/R4-8/R4-10 below.

## Blocker -> root cause -> structural fix -> regression test -> result

| R4 | Root cause | Structural fix | Regression test(s) | Post-fix result |
|---|---|---|---|---|
| R4-1 Mandatory source binding | `expected_source_task_digest` optional/omittable -> caller-cooperative binding; same identity could attach to different content | Digest is a REQUIRED keyword; adapter always recomputes from authoritative resolved source and requires the caller's assertion to match; omission/malformed/mismatch FAIL CLOSED. Caller's value is never the source of truth. | `test_r4_mandatory_source_digest_omitted_rejected`, `test_r4_mandatory_source_digest_malformed_rejected`, `test_r4_same_identity_different_content_binding`, `test_r4_changed_parameters_digest_differs` | omitted digest -> TypeError (required kw); malformed -> error; same-identity/different-content (main vs OTHER) -> rejected; correct binding succeeds and carries authoritative digest |
| R4-2 / R4-11 Single canonical validation path | direct `UnrealRuntimeMapping(...)` construction did not necessarily run the same security path as the factory | `__post_init__` now runs the SAME canonical validation (provenance typed schema + authority scan, source-digest shape, render/requirements consistency, runtime-action authority, snapshot<->digest binding, snapshot metadata strict-JSON + reserved-key scan). | `test_r4_direct_snapshot_metadata_authority_scan`, `test_b9_direct_invalid_render_contradiction_rejected`, `test_b9_direct_invalid_snapshot_tools_rejected` | directly-constructed invalid mapping (snapshot metadata carrying `authorization_id`) -> `UnrealRuntimeAdapterError`; identical to malformed factory input |
| R4-3 Complete render axes | `target_state.expects_render` not an authoritative axis; could disagree with class silently | Render classification = union of source class (`render_task`), canonical fragment render semantics (render-constrained / non-`expandable`), AND `target_state.expects_render`. Any authoritative render requirement -> render boundary; conflicting render/non-render -> FAIL CLOSED. Benign render-class-without-render-fragment (artifact-validate) preserved. | `test_r4_target_state_render_axis_recognized`, `test_r4_render_class_with_target_state_axis_authoritative`, `test_b2_render_setup_via_non_render_class_rejected` | target-state render axis recognized; forged under-flag of a render-class task -> rejected |
| R4-4 Runtime action authority (REJECT, DON'T REWRITE) | `allow_writes` silently zeroed (dataclasses.replace) when source asked for writes; caller/source intent rewritten | `dataclasses.replace(..., allow_writes=False)` REMOVED. Source declaring `allowed_mutations` under inspect-only mapping, or compiled task with `allow_writes=True`, now REJECTED. Inspect-only requires `allowed_action_tools == {unreal_inspect}` and all action/evidence tools inspect-only. Intentional contract tightening (see R4-4 CONTRACT DECISION below). | `test_r4_write_capable_source_rejected_not_rewritten`, `test_r4_compiled_allow_writes_rejected_not_rewritten`, `test_r4_allow_writes_tool_violation_rejected`, `test_b1_*` | write-declaring source -> `UnrealRuntimeAdapterError` (was zeroed); genuinely inspect-only source maps with `allow_writes=False` |
| R4-5 Closed TYPED provenance schema | provenance gated by vocabulary scan + allowlist; unknown/ambiguous/nested/free-form content still a concern; not structural | Caller provenance validated against an explicit typed schema (`proposal_source:str`, `source_task_version:int`, `note:str`, `fragment_id:str`, `fragment_version:int`, `target_state_contribution:list[str]`). Unknown keys, nested undeclared structures, free-form caller metadata, authority-shaped values REJECTED structurally (no keyword guessing). Fragment identity/version/contribution reconciled ADAPTER TRUTH (caller-forged overwritten). Scalar `note` is the only free-form shape, never promoted to trusted authority/verification. | `test_r2_nested_freeform_provenance_rejected_structural`, `test_r2_freeform_provenance_rejected_in_step_and_nested_list`, `test_r4_authority_value_structurally_rejected`, `test_r4_scalar_note_frozen_and_roundtripped`, `test_b3_*` | `auth_token`/`grant_id`/`capability`/nested-`note` -> structurally rejected; scalar `note` preserved + deep-frozen |
| R4-6 Snapshot is sole runtime source | (held at Round-3; re-verified) no hidden live `AtlasTaskDefinition`; materialize rebuilds from snapshot + asserts digest | No code change required beyond Round-3; verified | `test_b4_no_hidden_backing_task`, `test_b4_materialize_rebuild_matches_digest` | no hidden attr; materialized copy isolated; rebuilt snapshot digest matches |
| R4-7 Unresolved requirements fail closed | (held at Round-3; re-verified) empty-dependency representation forbidden | No code change required beyond Round-3; verified | `test_b5_orphan_step_fails_closed` | orphan step -> rejected |
| R4-8 Catalog version exact-int identity | lossy `int()` coercion could collapse `"1"`/`1.9`/`True`; single-authoritative-source violated | `catalog_version`/source metadata must be EXACT `int` and equal to plan; bool/float/str and coercion FAIL CLOSED; `used_catalog_version = plan.catalog_version` (no `int()`). | `test_r4_catalog_version_type_coercion_rejected`, `test_r4_source_metadata_catalog_version_exact_int`, `test_b6_catalog_version_conflict_rejected` | `"1"`/`True`/`1.9` override -> rejected; source metadata `"1"` (str) -> rejected; exact int 1 -> accepted |
| R4-9 Declared vs reconciled truthful | caller-carried data must not be presented as reconciled | `declared` True only when non-canonical caller content carried verbatim; reconciled fields re-derived from canonical fragment. | `test_b7_declared_false_for_clean_mapping`, `test_b7_step_with_caller_provenance_is_declared` | clean steps declared=False; caller-provenance step declared=True |
| R4-10 Strict JSON rejects unsupported numeric types | `Fraction` (a `numbers.Real`) passed validation then crashed `json.dumps` | `_validate_strict_json_value` uses exact `type() is int` / `type() is float`; Fraction/Decimal/numpy scalars/other `numbers.Real|Integral` subclasses REJECTED structurally with `UnrealRuntimeAdapterError` (declared canonical-contract error) before serialization. | `test_r4_fraction_rejected_structurally`, `test_r4_decimal_rejected_structurally`, `test_b8_*` | Fraction(3,4) and Decimal("1.5") -> `UnrealRuntimeAdapterError` (no leaked TypeError at json.dumps) |
| R4-12 M12.5 boundary | must not grant M12.4 verification authority; evaluator must stay a structural placeholder | No verification authority added; snapshot carries explicit disclosure (`m12.4.evaluator_kind`, `m12.4.independently_verified=False`, `m12.4.declared`). | existing M12.5-boundary tests | no verification; disclosure fields present |

## R4-4 CONTRACT DECISION (verified, intentional tightening)

`planning/m12/catalog.py:350` (`catalog.resolve()`) sets `allowed_mutations=[entry.task_class]`
for every catalog entry, so a catalog-resolved task compiles to `allow_writes=True`
(write intent). M12.4 is a semantically INSPECT-ONLY adapter. Per R4-4 it must
REJECT (not silently downgrade) a source that asks for writes. The genuinely
inspect-only state IS expressible upstream in M12.1: `normalize_unreal_semantic_request`
accepts `allowed_mutations=()` and a task with empty `allowed_mutations` compiles
to `allow_writes=False`. Therefore:

- **Decision:** M12.4 intentionally rejects catalog-resolved tasks that still carry
  `allowed_mutations` — the caller must have already resolved the source to
  genuinely inspect-only intent. This is an intentional contract tightening, NOT a
  contradiction with M12.1/M12.2 (read-only semantics are representable; they just
  must be declared). No authority was broadened; no silent mutation stripping was
  reintroduced.
- **Proof tests:** `test_r4_write_capable_source_rejected_not_rewritten` (catalog
  task with mutations -> rejected),
  `test_r4_compiled_allow_writes_rejected_not_rewritten` (inspect-only source
  compiles to `allow_writes=False` and passes unchanged),
  `test_r4_allow_writes_tool_violation_rejected` (compiled `allow_writes=True`
  -> `_reconcile_runtime_authority` rejects).

## Validation (current PR #91 head `338573c`)

- `pytest tests/m12/` -> **263 passed** (incl. Round-1/2/3 and new `test_r4_*`)
- `pytest -m "not integration"` -> **1714 passed** (no regressions)
- `tests/m12/test_m12_authority_isolation.py` -> **5 passed** (adapter imports only
  M12 + `AtlasTaskDefinition`; no production-authority module)
- No Unreal, no Blender, no workflow/action-runner, no production tests run.
- `can_execute` remains False; no execute/authorize/submit/recover/verify authority;
  no M4-M10 files changed; M12.5 untouched.

