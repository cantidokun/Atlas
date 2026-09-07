# Atlas M11 — Adaptive Development-Model Routing + Engineering Control Plane (Design)

**Status:** Design only. No implementation, no production-code change, no live scenario, no PR merge.
**Scope:** Development/reasoning orchestration. **Non-negotiable:** M11 is NOT Atlas production authority, authorization, scheduler, recovery, execution, receipt, or provenance authority.
**Source-of-truth files read:** `docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md`, `planning/unreal_render_recovery_coordinator.py`, `planning/unreal_render_submission.py`, `planning/model_request.py`, `planning/task_planner.py`, `controller/agent_controller_host.py`, `controller/capability_request.py`, `agent.py`, `.github/workflows/tests.yml`, `DEVELOPMENT_LOG.md`, and the M4–M10 review artifacts.

---

## 1. Executive summary

M11 introduces a **development-tooling control plane** that selects the cheapest model tier able to safely complete a dev task, escalates when objective evidence shows insufficient capability, and records durable cost/quality telemetry. It lives **strictly in the Hermes development orchestration layer** — it makes no decision and holds no state that affects Atlas production jobs, receipts, authorization, scheduling, or recovery. All production authority remains exactly as the existing architecture established: Atlas Python/Controller validates→resolves→authorizes→executes→tracks→verifies→recovers; Unreal is a witness-only execution worker.

The router's only outputs are: (a) a **model-tier selection** for a dev task, (b) an **escalation decision** with a preserved context packet, and (c) a **telemetry record**. It never signs, authorizes, mutates authoritative identity, or issues receipts.

## 2. Current-state findings

### 2.1 Agent / development orchestration

- **Hermes integration:** Hermes is the active driver for M4–M10 work; it operates the git/PR workflow, pytest suites, UBT builds, and GitHub Actions verification. There is **no explicit model-tier router today** — Hermes chooses the executing model implicitly (the platform/back-end default), and multi-model review is done **manually** via independent reviewer artifacts named `astra_unreal_m4_*`, `deepseek_unreal_m5_*`, `opus_unreal_*`, `sonnet_unreal_*` (up to ~9 independent reviews per PR head per the standing Atlas review-loop convention).
- **Task execution abstractions:** `planning/task_planner.py` validates structured model-produced plans against allowed tool schemas (`validate_tool_arguments`, `ActionPlan`, `EvidencePlan`). `planning/unreal_task_planner.py` and `planning/unreal_autonomous_executor.py` handle Atlas-specific plan/execution. `planning/model_request.py` assembles stable-cache + dynamic-state model calls via `build_runtime_context`.
- **Subprocess/tool execution:** Unreal renders are driven via named-pipe transport (`unreal_transport_named_pipe`), process supervision (`scripts/run_unreal_supervisor.py`); build/batch shims (`run_m*.bat`) wrap UBT. Deterministic tests run via pytest; GitHub Actions `.github/workflows/tests.yml` runs `pytest -q -m "not integration"` on python 3.9 + 3.11.
- **Prompt/context construction:** `ModelRequest.render()` merges stable instructions + dynamic state; `task_definition.py` encodes task contracts; `trusted_unreal_context` provides capability context.
- **Telemetry/logging:** logging is `planning`-module `logging` (coordinator uses `logger`). **No structured dev-task telemetry store, no cost/latency/tier capture.**

### 2.2 Architectural boundary (where a router safely sits)

The router must sit **above** the model call but **below** any Atlas authority path. Concretely: it wraps the **development orchestration loop** (task intake → plan → execute → verify → PR), not the Unreal transport, not the coordinator, not the submission gate. It never traverses `apply_authorized`/submit/reconcile paths. The existing `AgentControllerHost` classifies `CapabilityRequest(provider, capability, intent, context)` for the *production controller* — M11 must NOT become that controller; M11 is a **development-side** router that may **consume** the same risk classification signals but must not delegate to or from production capability.

### 2.3 Current model/provider configuration

- `agent.py` (legacy Blender experiment): `MODEL="qwen3:8b"`, `OLLAMA_URL=http://localhost:11434/api/chat` — unrelated to M10 production; documents that a single hard-coded model and provider were used.
- `controller/capability_request.py` carries `provider` as a string; `AgentControllerHost` restricts `unreal/production` capability rather than model selection.
- External reviews: `astra`, `deepseek`, `opus`, `sonnet` (multi-model manual reviews) — confirms the org already uses several providers, but **no config file centralizes them; no tiering; no failure-driven escalation; no cost telemetry.**
- No token-budget, temperature, retry/fallback, reasoning-level config exists in the repo.

### 2.4 Existing failure / evaluation signals (objective)

- **pytest results:** `tests/m6..m10` plus `test_*`; live `1212` collected deterministic (`-m "not integration"`), authoritative green gate for the recovery milestone.
- **compile/build:** Unreal UBT `Result: Succeeded/Failed`; the M runs treat UBT_OK as a gate.
- **static checks:** plan schema validation (`task_planner.py`), tool-args validation, evidence-plan validation.
- **contract tests:** M6–M10 deterministic suites specifically assert fail-closed/authority invariants (Case A/B/C/D/E/F/G/H/I/J/K, HMAC attestation, receipt identity, attempt identity).
- **GitHub CI:** `tests.yml` matrix 3.9/3.11.
- **repeated correction loops:** M4–M10 histories show multiple correction rounds (e.g. multiple M5 review/corrections artifacts); count and content are recorded in handoffs.
- **diff size/complexity, security-sensitive files, production-impacting changes:** no formal classifier today; the review artifacts flag them manually.

### 2.5 Telemetry gaps (must add)

Metric | Purpose | Present today?
---|---|---|---
selected model | dev audit & cost | No |
task type | classification | No |
risk tier | routing | No |
token usage | cost | No (not tracked) |
latency | perf | No |
tool calls | effort | No |
retries/corrections | escalation | No (manual logs only) |
tests pass/fail | evidence | No machine parse of per-run |
escalation count | triggers | No |
final outcome | audit | No |
estimated/actual cost | cost | No |

---

## 3. Architectural insertion point

```
development task ingest (Hermes)
   └─> [M11 ROUTER]  (NEW, dev-only)
         ├── task-risk classifier  (deterministic, no model self-report)
         ├── tier selector          (cheapest model satisfying class & risk)
         ├── evidence gate on completion (tests/build/static/contract/diff)
         ├── escalation (packet to higher tier)
         └── telemetry ledger
   └─> [task executor + editors + pytest + UBT + GitHub Actions]   (unchanged)
   └─> [PR gate]                       (unchanged — stop-at-PR)
Production authority: untouched (Atlas shared authority, Unreal witness).
```

Boundary invariants:
- The router is a pure adviser: it never calls `apply_authoritative`/`apply_authorized`, `submit_render`, `reconcile_render_jobs` for authority, or any receipt/scheduling path.
- The router does not mint receipts, schedule executions, or issue/accept authorization.
- Its persistent state is confined to a dedicated `router.*` telemetry/config namespace so nothing it does can be confused with Atlas production state.
- Outside that advisory namespace, production flow and files are untouched by M11.

## 4. Task / risk taxonomy

### 4.1 Task classes (functional)

| Class | Example |
|---|---|
| `doc` | doc/readme/handoff edits |
| `test` | new/adjust deterministic tests |
| `test.fix` | fix a failing test |
| `refactor` | non-behavioral restructure |
| `api-boundary` | public signature / schema change |
| `adapter` | Unreal/transport adapter work |
| `contract` | contract-sensitive editing (authority/identity/durability) |
| `recovery` | coordinator/recovery-path change |
| `security-crypto` | HMAC/nonce/attestation/crypto |
| `concurrency` | cross-process/locking/racy |
| `docs` | documentation-only |

### 4.2 Risk dimensions (each scored 0–3, deterministic, no self-confidence)

Each dimension is scored independently on a fixed deterministic scale (0 = none, 1 = low, 2 = medium, 3 = high) computed by static/tool evidence — file-path hits, symbol/API references, diff size, control-flow complexity, required runtime (live-engine/build/CI) gates. A model can NEVER set these scores; they come from the classifier.

| Dimension | Scale (0–3) | Evidence source (static, tool-assessable) |
|---|---|---|
| code complexity | 0–3 | diff size, cyclomatic/control-flow, scope of touch |
| security sensitivity | 0–3 | path/key/nonce/HMAC/crypto vocab hits |
| authorization/identity | 0–3 | authorization_id/attempt/session/realm refs |
| cryptography | 0–3 | attestation/nonce/key/digest constructs |
| concurrency | 0–3 | lock/mutex/registry/parallel constructs |
| cross-process | 0–3 | transport/pipe/process/job-object spawn |
| recovery/statefulness | 0–3 | coordinator/recovery_status/lifecycle refs |
| provenance/receipt impact | 0–3 | receipt/lineage/digest refs |
| external side effects | 0–3 | live render/steam/pipe/file writes |
| production/destructive | 0–3 | delete/overwrite/kill/production-run paths |
| difficulty of verification | 0–3 | requires live engine / CI / UBT |

### 4.3 Frozen risk→tier mapping (deterministic, normative)

**Rule R1 (raw-risk score).** Each dimension scored 0–3 as above by the classifier. If any required dimension cannot be computed (unknown/missing/unparseable), it FAILS CLOSED to score = 3 (max) for that dimension, and marks `data_complete=False`. Model self-confidence is NEVER an input; a model cannot report or affect any dimension score.

**Rule R2 (aggregate).** Define two quantities:

```
max_dim   = max(dimension scores)            # worst single dimension, 0..3
hard_flag = count of hard-selector dimensions that are nonzero   # see R4
```

**Rule R3 (tier by raw score).** If `data_complete=True` and no hard selector is active:

| max_dim (worst single dimension) | minimum tier |
|---|---|
| 0 | L0 |
| 1 | L1 |
| 2 | L2 |
| 3 | L3 |

Tie / monotonic rule: when multiple dimensions share the same max, the tier is driven by that max alone (no extra penalty). Escalation is monotonic — a tier, once selected, can only increase, never decrease.

**Rule R4 (hard selectors override).** A dimension score of ≥2 in ANY of the following dimensions IMMEDIATELY forces the minimum tier to **L2**; a score ≥3 forces **L3**:

- security sensitivity, authorization/identity, cryptography (≥2 → L2, ≥3 → L3)
- recovery/statefulness, concurrency, cross-process, provenance/receipt (≥2 → L2, ≥3 → L3)

If any hard file/field is touched that is listed in the hard-selector set (§7 list), that alone raises to at least L2 even if raw score is 1.

**Rule R5 (combined hard selectors).** When MULTIPLE hard selectors are active, take the MAXIMUM of their individually forced minimum tiers. E.g. a cryptography edit (→L3) + a concurrency edit (→L2) => final floor L3.

**Rule R6 (missing/unknown data).** If ANY required risk signal (dimension or hard-selector membership) is unknown: fail closed to the highest applicable default — set `data_unknown=True`, force tier = L3 (UNSAFE_TO_DOWNGRADE), and mark the selection `selection_reason=UNKNOWN_RISK_SIGNAL` so it is recorded. The router must NOT lower the tier below L3 when data is incomplete.

**Rule R7 (final).** Final selected tier = `max(R3 tier, R4 floor, R6 floor)`. No model self-confidence is used anywhere in R1–R7.

---

## 5. Model capability as validated configuration

### 5.1 Three distinct normative roles

| Concept | Definition | Who sets it |
|---|---|---|
| **task risk requirement** | deterministic score/floor from §4 (R1–R7) | classifier (static) — NEVER the model |
| **model capability floor** | the minimum tier this model can be trusted for; a static, validated property of the profile | configuration (validated on load), NOT the model |
| **provider/model configuration** | the concrete runtime binding (provider, model id, budget, timeout, cost) | deployment configuration (design parameter) |

A model can NEVER declare its own capability. Capability comes solely from static, validated model-tier profiles.

### 5.2 Normative model-tier profile (minimum required fields)

Each profile is validated at load time; any missing/`null`/unparseable field → the profile is REJECTED (not usable) and routing fails closed to `NEEDS_HUMAN_REVIEW` rather than guessing.

| Field | Type | Meaning | Cannot be null |
|---|---|---|---|
| `tier` | enum L0·L1·L2·L3 | which tier this profile serves | yes |
| `provider` | string | deployment provider id | yes |
| `model_id` | string | concrete model identifier | yes |
| `capability_floor` | tier enum | the minimum tier this model satisfies (declared by config) | yes |
| `supported_classes` | set of task-class names | which task classes this profile may handle | yes |
| `token_budget` | int | max reasoning/completion tokens for the attempt | yes |
| `timeout_s` | int | max wall-clock seconds for the attempt | yes |
| `cost_metadata` | optional | estimated/known cost basis (per token or per call) if available | no — may be omitted |

**Validation rule (normative):** at load, the router asserts `profile.capability_floor == profile.tier` (a profile must never under/over-claim relative to its tier), `profile.supported_classes` non-empty, `token_budget > 0`, `timeout > 0`. Any violation → profile rejected → `NEEDS_HUMAN_REVIEW`. A model's in-band self-report ("I am capable of X") is never consulted.

### 5.3 Example (design parameter — actual names resolved at deployment)

| Tier | provider/model are deployment-configuration placeholders |
|---|---|
| L0 | `{tier:L0, provider:?, model_id:?, capability_floor:0, supported_classes:[doc,test,docs], token_budget:?, timeout:?}` |
| L1 | `{tier:L1, ..., capability_floor:1, supported_classes:[test,refactor,adapter], ...}` |
| L2 | `{tier:L2, ..., capability_floor:2, supported_classes:[api-boundary,recovery,concurrency,contract], ...}` |
| L3 | `{tier:L3, ..., capability_floor:3, supported_classes:[security-crypto,full-contract], ...}` |

In the table above `provider`, `model_id`, `token_budget`, `timeout` are left as parameters. Provider/model **names are deployment configuration parameters** — repository does not establish them.

## 6. Routing algorithm (deterministic, no model self-confidence)

1. Ingest task → class(es) (§4.1) + scan files → compute risk dimensions (R1) → `max_dim`, `hard_flag`, `data_complete`, `data_unknown` (R2).
2. Compute raw tier by §4.3 R3. Mark if unknown data → R6.
3. Apply any hard-selector floors R4/R5; compute final tier = R7.
4. Look up the LEAST-capable validated profile whose `capability_floor ≥ final_tier` AND whose `supported_classes` ⊆ task classes; if none exists → `NEEDS_HUMAN_REVIEW`.
5. Emit `Selection{{task_id, tier_required, final_tier, profile, reasons, risk_scores}}`.
6. Execute; the post-execution gate (below) decides pass, escalate, or stop.
7. On escalation, move to next HIGHER tier with the escalation packet (no blind re-run, no reusing an unchanged attempt).

## 6.1 Finite escalation budget (normative)

Define explicit, finite resource / tier budgets; escalation cannot be unbounded.

- `MAX_ESCALATIONS_PER_TASK = 3` (tunable config constant, default 3).
- Maximum possible tier = `L3`; no tier above L3 exists.
- Each escalation consumes one budget token; if it produces new evidence (new test/build signal) the same budget did not reset.
- BLOCKED: More than `MAX_ESCALATIONS_PER_TASK`, blind reruns of the same tier/attempt, attempts referencing the same unchanged evidence, downgrade (monotonic-only up), escalation to a model not in config.

Terminal states:

- On exhausting `MAX_ESCALATIONS_PER_TASK`: transition to **`NEEDS_HUMAN_REVIEW`** terminal state; record outcome, escalate packet preserved; no further automatic escalation allowed.
- On L3 failure (L3 attempt also fails to satisfy required evidence): same **`NEEDS_HUMAN_REVIEW`** terminal.
- When objective evidence remains insufficient (e.g. cannot establish invariant, CI not green, unexplained unknown signal): **`NEEDS_HUMAN_REVIEW`**; the record marks `final_outcome=NEEDS_HUMAN_REVIEW`. No auto-retry, no auto-regression loop.
- `NEEDS_HUMAN_REVIEW` is terminal for that task_id: further attempts require explicit human/interrupt action (environmental intervention), never the router.

Bane prevention: the router cannot modify the guard book to self-grant additional budget; budget is fixed config.

## 7. HARD escalation triggers (objective, immediate minimum tier jump)

Escalate **immediately** (no re-run; skip to next tier with a fresh packet) when any objective trigger fires:

- crypto / auth / identity / receipt / provenance file touched;
- cross-process / concurrency / lock / shared-registry / mutex editing;
- contract mismatch detected (two authoritative statements disagree);
- deterministic test FAILED (must pass gate);
- repeated failed same-area corrections (2+ without a confirmed fix);
- inability to establish a required invariant within the task budget;
- live/production side-effect would be triggered by the change;
- destructive operation (kill/delete/overwrite) beyond the authorized scope;
- repeated model disagreement (non-overlapping results after ≥1 difference);
- CI red on the PR head (never treat local-only pytest as sufficient per established convention).

**Merge rule:** combine triggers with `max-of-individual-min-tiers`, per R5. Triggers are static/CFG-sourced plus the CIGREEN/real-gate signals; model self-confidence is NOT a trigger.

## 8. Evidence-based confidence model

- Self-reported confidence **never** drives success. Confidence is a derived score:
  `confidence = f(green_tests, build_ok, static_ok, diff_review_ok, contract_ok, corrections_needed)`.
- Success threshold per tier; a task is only "pass" when its required gates each produce objective green signals.
- A test passing because its fixture hand-supplies a field the real path lacks → flagged **hardened defect** (per user's reviewer bar item 6) and must FAIL the gate, not "pass".
- Independent review / re-review and live-boundary checks = separate mandatory gates for adapter/live paths.

## 9. Adaptive token budgets

- Base budget = `tier.budget`.
- On a failed gate (investigation), increase budget within a capped ramp: `budget_next = min(base × ramp_factor^n, cap)`; never below base; never indefinite.
- Budget only grows within same tier or upon escalation to new tier; **no** blind infinite retry (monotonic cap).

## 10. Escalation packet (what higher tier receives)

- task_id, task statement (verbatim)
- repo state: branch/HEAD/SHA, working diff
- prior model output (collapsed, deduped)
- attempted changes + per-step evidence
- test failures (exact names, output snippet), build log, CI checks
- relevant contract excerpts (authority, Case codes, § that conflict)
- unresolved questions
- the current risk classification + reason

## 11. Telemetry schema (durable, privacy-safe, append-only)

Telemetry is a durable **append-only** ledger. Records are never mutated or overwritten after creation; corrections and escalations produce NEW records.

### 11.1 Identity model

- `task_id` — stable identity of the development task (unique across the task's lifetime; does not change on correction/escalation).
- `attempt_id` — unique id per routing + execution attempt (a model/tier invocation, possibly retried with new evidence).
- `escalation_id` (optional) — present when the record is created by an escalation hop; links to the prior `attempt_id` (parent) and its `task_id`.

Fields are recorded in a durable ledger keyed by `(task_id, attempt_id, escalation_id?)`. New evidence → a NEW record appended; the original records remain unchanged.

### 11.2 Frame

`Record (append-only)`:

| Field | type | mutable after create? |
|---|---|---|
| task_id | str | immutable |
| attempt_id | str (unique) | immutable |
| escalation_id | str? | immutable |
| timestamp_utc | iso | immutable (creation only) |
| task_class | enum | immutable |
| risk_factors (all dimension scores + max_dim/hard/data flags) | map | immutable |
| final_tier | L0..L3 | immutable |
| profile_tier | enum | immutable |
| requested_token_budget | int | immutable |
| actual_token_usage | int | append-only (or in a separate usage log) |
| latency_ms | int | append-only |
| tool_call_count (histogram) | int | append-only |
| correction_count | int | immutable for this attempt |
| escalation_count | int | immutable |
| tests_passed / tests_failed | int | immutable at outcome |
| build_result | enum PASS/FAIL/UNKNOWN | immutable at outcome |
| static_result / contract_result | enum | immutable at outcome |
| final_outcome | enum PASS/ESCALATED/BLOCKED/NEEDS_HUMAN_REVIEW/FAILED | append-only (may be appended once at terminal) |
| estimated_cost_usd | float | append-only |
| selection_reason | str (crypt / selectors) | immutable |

Append-only rule: any field with "append-only" may only appear in a NEWER record; existing records are never edited in place. Corrections/escalations write fresh records under (task_id, newer attempt_id).

Immutability rule: `task_id`, `attempt_id`, `escalation_id`, `risk_factors`, `tier`, `profile_tier` are immutable for the life of the ledger.

**Never stores:** API keys, secrets, credentials, prompts containing credentials, `attempt_nonce`, HMAC secrets, private keys, or anything in the `authoritative`/secret category. This is a strict allow-list; a telemetry-record input that contains any protected token is rejected and dropped (fail-closed), never written.

## 12. Benchmark methodology

Build a corpus from real Atlas tasks (create a `benchmarks/` dir when implementing):

| Class | Example | risk tier | min model | objective success | escalation trigger |
|---|---|---|---|---|---|
| `trivial` | doc-edit / trivial pytest-compatible change | L0 | lite | markdown lint + passing unrelated suite | any diff beyond the single trivial edit |
| `test` | new deterministic test | L0 | lite | new test passes within full suite | test only passes by weakening/mocking |
| `refactor` | move a helper, no behavior change | L1 | engineering | full suite green + build ok | any refactor changes behavior or breaks a test |
| `api-boundary` | change a transport request shape | L2 | strong | green suite + transport contract tests | any unenforced shape / missing invariant |
| `adapter` | edit the Unreal transport/adapter frame | L1/L2 | strong | green + UBT build ok + live-boundary review | cross-process value not proven on boundary |
| `security` | HMAC/nonce/attestation/crypto | L3 | frontier | green + HMAC vectors + contract | any attestation or nonce rule change |
| `recovery` | coordinator Case J/G/H path | L2 | strong | green + deterministic fail-closed tests | torn-state misclassification |
| `concurrency` | job-object/lock/mutex change | L2 | strong | green + deterministic concurrency | any lock/ordering invariant regression |
| `docs` | documentation-only | L0 | lite | markdown + link consistency | doc contradicts an authoritative value |

For each: expected tier, min acceptable model, objective success (tests+build+CI+contract), escalation criteria, token/cost measurement. Measurement is **useful engineering output** (green gates), not token count alone — success = gates; token = lower-bound cost.

## 13. Security / privacy controls

- allow-list telemetry only (no secret/nonce/key values).
- no prompt exposure beyond the task model; escalation packet must be stripped of credentials before hand-off.
- model provider keys stored in secure config (outside repo), never in telemetry.
- routing failure fail-closed: if tier capability is unknown at runtime → refuse to downgrade (default to the most conservative available tier per R6/R7) and route to `NEEDS_HUMAN_REVIEW` rather than guessing.

## 14. Router failure modes (explicit, fail-closed behavior)

| Failure | Fail-closed behavior |
|---|---|
| missing model configuration | No usable profile for the required tier/class → terminal `NEEDS_HUMAN_REVIEW`; no fallback to a guessed model |
| unavailable provider | Provider ping/health fail or response not received → abort that attempt, route to the next-tier profile (if budget remains) else `NEEDS_HUMAN_REVIEW`; never downgrade |
| timeout | Attempt times out → fail the attempt, do NOT accept partial output; escalate with the timeout recorded; on L3 timeout → `NEEDS_HUMAN_REVIEW` |
| malformed model response | Response fails schema validation → not promoted, fail that attempt; escalate (malformed = no valid evidence); L3 malformed → `NEEDS_HUMAN_REVIEW` |
| invalid tool request | Tool arguments fail schema/safety validation → task plan rejected, escalate; never execute a malformed plan |
| failing evidence gate | Required gate red (tests/build/static/CI) → task NOT pass, escalate; terminal gap after budget → `NEEDS_HUMAN_REVIEW` |
| exhausted escalation budget | Stop; `NEEDS_HUMAN_REVIEW`; no further automatic escalation or rerun |
| telemetry write failure | Router may not proceed on a silent telemetry loss: if the append-only write cannot be persisted, the attempt is treated as UNKNOWN and fails closed (no success is claimed without a durable outcome record) |
| configuration ambiguity | Conflicting/missing config → reject selection, `NEEDS_HUMAN_REVIEW`; never guess a tier |

Router is designed so every failure path terminates in a non-success state (abort/incomplete → escalate → eventually `NEEDS_HUMAN_REVIEW`). No success is ever inferred without durable, gate-passing evidence.

## 15. Atlas authority boundary (proof)

M11 is architecture-safe because:
- Per Contract §2: "No model may write or modify authoritative identity, lifecycle, evidence, artifact, or recovery fields" → M11 (development tool) inherits this: it **never writes** those fields; its output is advisory/route.
- M11 never sits in `/authoritative/` pathways; the Atlas coordinator remains sole authority: Atlas Python/controller authorizes, schedules, verifies, corrects.
- M11 cannot `submit_render`, cannot route a production job, cannot recovery-coordinate, cannot issue a receipt, cannot mutate production state except through legitimate dev-tool edit path (which itself requires the existing authority + user approval-to-PR). It does not add a second scheduler or recovery coordinator.
- The only "authority" M11 holds is **over its own model selection + dev recommendation** — not over Atlas execution.

## 16. Implementation plan (phased; this milestone is design-only)

Phase 0 (this): design doc + findings + authority + benchmark plan + frozen risk→tier rules (R1–R7) + finite escalation budget + append-only telemetry schema.
Phase 1: deterministic risk classifier + tier registry (pure, no prod change), implementing R1–R7 with fail-closed unknown handling.
Phase 2: scoring & routing selection using validated tier profiles (§5) and the frozen mapping; monotonic floor enforcement.
Phase 3: evidence gatekeeper + execution signals wiring; bind to the existing pytest/build/CI gates.
Phase 4: escalation packets (bounded by §6.1), append-only telemetry ledger with redaction + immutable-attempt enforcement.
Phase 5: integration into Hermes dev loop as an optional adviser (default off), plus unit tests for routing determinism/tier/escalation/telemetry-boundary.
Each phase keeps Atlas production authority untouched; no production side effect.

## 17. Test strategy

- Unit tests: deterministic class→tier mapping (R1–R7), unknown-data fail-closed, escalation trigger + finite-budget handling, telemetry redaction + append-only/immutability enforcement, and each acceptance criterion 1–9.
- Contract tests: router cannot call authority methods (mock guard) and cannot mint receipts / schedule / authorize.
- Integration: routing an existing M4-8 task through the pipeline reproduces same green gates with ≤ tier.
- Live-change: routing pipeline must not alter production behavior (shadow-mode assertions).
- Benchmark: pre/post tier cost/quality on corpus; escalation rate measured.

## 18. Acceptance criteria (objective, verifiable)

1. **Deterministic risk classification.** Identical task input (files, diff, symbols) always yields the same risk-dimension scores and `data_complete` flag (a pure function; test asserts equality across runs).
2. **Deterministic tier selection.** Same risk + same config → same final tier (per R1–R7). Test asserts no non-determinism over repeated invocations.
3. **Model self-confidence cannot lower the selected tier.** Inject a model response claiming low capability / high confidence with failing evidence → the router must NOT downgrade; it must escalate red gates only. Unit test asserts tier remains at the R1–R7 floor.
4. **Hard selectors cannot be bypassed.** Touching any hard-selector file/field forces ≥ the R4 floor regardless of raw score; a test asserts a low `max_dim` with a crypto/hard field still yields ≥L2 (≥L3 when ≥3). Tests assert no path lowers it.
5. **Escalation budget is finite.** A test forces repeated gate failures and asserts the router reaches `NEEDS_HUMAN_REVIEW` after `≤ MAX_ESCALATIONS_PER_TASK` and never auto-escapes beyond it.
6. **No production authority operation reachable from the router.** Boundary test that any authority method (`submit_render`, `reconcile_render_jobs`, `apply_authorized`, receipt issuance, `authorization_id` mutation) invoked by/through the router raises and that the router holds no such pathway.
7. **Telemetry never stores protected secrets.** Unit test that any record containing an `attempt_nonce`, key, credential, or prompt-with-credential is rejected/dropped and never persisted.
8. **Previous routing attempts remain immutable.** Test writes two attempt records and asserts the earlier `task_id/attempt_id/risk_factors/tier` are byte-unchanged after the later append (append-only, no overwrite).
9. **Terminal `NEEDS_HUMAN_REVIEW` prevents further automatic escalation.** Test asserts that once a task_id reaches `NEEDS_HUMAN_REVIEW`, no further escalation/rerun is permitted by the router without explicit external action.

Plus existing criteria: cheapest-tier selection across the benchmark, evidence-gated success, CI-green-or-not, redact telemetry, and the standing PR rule (stop at PR; never merge on local-only evidence).

## 19. Open questions

- Which provider/tier names map to actual config at runtime? (not resolved; design param)
- How to obtain token/cost (provider API) vs estimate? — access this at integration.
- Whether the independent multi-model review step (M4-M10 convention) is folded into escalation (L3/L4) or retained as separate "Atlas review gate" — keep as review/log separate initially.
- Concurrency/cross-process: should a shared multi-model review of one PR head reuse a single model tier or review independently per model? — open (the M4-M10 convention runs per-model independent review artifacts).
- Whether telemetry is per-task or per-milestone aggregated — proposal: per-task records, aggregated summaries on milestone completion.
- Does M11 ever auto-re-run to "confirm green" — no (monotonic, no blind) unless user authorizes (matches project rules: "verify green on new head, never merge local-only").

---

## Appendix A — Performance / related-signal inventory (from current run)
- deterministic tests: 1212 collected (`pytest --collect-only -m "not integration"`).
- CI: GitHub Actions matrix 3.9/3.11 green on PR heads.
- UBT: build Success required for C++ changes.
- independent review artifact families: `astra_*`, `deepseek_*`, `opus_*`, `sonnet_*`.

## Appendix B — Authority boundary call-outs (from contract)
- §2 list; "model-controlled authorization" prohibited.
- §3; "No model may write/modify authoritative identity..." (line 168).
- Case codes A-J with fail-closed.
- M8 HMAC uses attempt_nonce persisted (never plaintext in telemetry/journal).