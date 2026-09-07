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
|---|---|---|
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

### 4.2 Risk dimensions (each scored 0–3, deterministic)

| Dimension | Scale | Notes |
|---|---|---|
| code complexity | lines/cyclo/control-flow | coarse, tool-assessable |
| security sensitivity | key/nonce/HMAC/crypto | flag fields |
| authorization/identity | authorization_id, attempt, session | flag |
| cryptography | attestation/nonce/key | flag |
| concurrency | locks/registry/mutex/parallel triads | flag |
| cross-process | transport/pipe/process/job-object | flag |
| recovery/statefulness | coordinator/recovery_status/lifecycle | flag |
| provenance/receipt impact | receipt/lineage/digest | flag |
| external side effects | live render/steam/pipe/file writes | flag |
| production/destructive | delete/overwrite/kill/production runs | flag |
| difficulty of verification | requires live engine, CI, UBT | flag |

`risk = heavy_sum(flags) * enforcement_weight`. Model confidence NOT in the formula.

### 4.3 Model tiers

| Tier | Role | Intended use |
|---|---|---|
| `L0/lite` | routine | doc, trivial test, trivial edit |
| `L1/base` | engineering | normal tests/refactors/adapter |
| `L2/strong` | strong reasoning | api/recovery/concurrency/contract |
| `L3/frontier` | critical | security-crypto, full-contract, ambiguous conflict |

`L0` is cheapest; `L3` most capable. Router picks **lowest tier whose `capability_floor` ≥ task risk score**.

---

## 5. Model report mapping

| Tier | Profile config (design parameters, not fixed provider) |
|---|---|
| L0 | `{model:<p>, provider:<p>, budget:<budget>, temp:0.1}` |
| L1 | `{model:<p>, provider:<p>, budget:<budget>, temp:0.2}` |
| L2 | `{... strong..., temp:0.0}` |
| L3 | `{... frontier..., extreme budget}` |

Provider/model **names are design parameters** — repository does not establish them; they pivot to config.

## 6. Routing algorithm (deterministic, no model self-confidence)

1. Ingest task → pre-parse into class(es), scan files → compute risk factors (2-4 + file-hit flags).
2. Compute `task_risk = max(risk_factor_scores)` bounded by class ceiling.
3. Select `lowest tier T` with `tier_capability >= task_risk`.
4. If hard-selector flags (contract/authority/crypto/recovery cross-process) rise tier to **at least L2** (or L3 if security/crypto) regardless of raw score.
5. Emit `ModelSelection(task_id, tier, model_cfg, reasons, risk_scores)`.
6. Execute; the evidence gatekeeper (below) decides success/runs-escalation.
7. On escalation up-tier, jump to next tier with full escalation packet (no blind re-run).

## 7. HARD escalation triggers (immediate minimum tier jump)

Escalate **immediately** (no re-run; skip to next tier) when any of:

- crypto / auth / identity / receipt / provenance file touched;
- cross-process / concurrent / lock / shared-registry / mutex editing;
- contract contradiction detected (two authoritative statements disagree);
- deterministic test FAILED that must pass (gate);
- repeated failed corrections (2+ same-area correction without confirming fix);
- inability to establish a required invariant within budget;
- production-side effect would be triggered by the change;
- destructive operation (kill/delete/overwrite);
- repeated model disagreement (same output converges → conflict);
- CI red on new head (since we never declare success on local-only pytest per #18-convention);

Escalation is monotonic (never decrease tier mid-task).

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

## 11. Telemetry schema (durable, privacy-safe)

A JSON/record with at least:

```
task_id, timestamp_utc, task_class, task_risk, risk_factors,
tier_selected, model, provider,
requested_token_budget, actual_token_usage, latency_ms,
tool_call_count (tool type histogram),
correction_count, escalation_count,
tests_passed, tests_failed, build_result, static_result,
contract_result (green/fail/unknown), final_outcome (PASS/ESCALATED/BLOCKED/FAILED),
estimated_cost_usd, selection_reason
```

**Never stores:** API keys, secrets, prompts containing credentials, unspecified credentials, `attempt_nonce`, HMAC secrets, private keys, or anything in the `authoritative`/secret category. This is a privacy-safe telemetry record with a strict allow-list.

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
- routing failure fail-closed: if tier capability black-box unknown → default to a conservative HEAD (FATEST) and make it security-aware.

## 14. Failure modes

| Failure | Mitigation |
|---|---|
| classifier misclassifies (too low tier) | hard trigger duties match a floor, CI review |
| model overrun token budget | cap+ramp; monotonic |
| blind retry/loop | escalation packet, budget cap |
| telemetry leak | allow-list + redaction test |
| router becomes authority | boundary test: router can't call authority op (block) |
| self-confidence gating bypass | confidence derived from evidence only; switch key off |
| provider/config drift | versioned config + validation |

## 15. Atlas authority boundary (proof)

M11 is architecture-safe because:
- Per Contract §2: "No model may write or modify authoritative identity, lifecycle, evidence, artifact, or recovery fields" → M11 (development tool) inherits this: it **never writes** those fields; its output is advisory/route.
- M11 never sits in `/authoritative/` pathways; the Atlas coordinator remains sole authority: Atlas Python/controller authorizes, schedules, verifies, corrects.
- M11 cannot `submit_render`, cannot route a production job, cannot recovery-coordinate, cannot issue a receipt, cannot mutate production state except through legitimate dev-tool edit path (which itself requires the existing authority + user approval-to-PR). It does not add a second scheduler or recovery coordinator.
- The only "authority" M11 holds is **over its own model selection + dev recommendation** — not over Atlas execution.

## 16. Implementation plan (phased; this milestone is design-only)

Phase 0 (this): design doc + findings + authority analysis + benchmark plan.
Phase 1: deterministic risk classifier + tier registry (pure, no prod change).
Phase 2: scoring & routing selection.
Phase 3: evidence gatekeeper + execution signals wiring.
Phase 4: escalation packets; telemetry ledger with redaction; benchmark harness.
Phase 5: integration into Hermes dev loop as an optional adviser (default advisory), plus unit tests for routing determinism/tier/escalation.
Each phase keeps Atlas production authority untouched; no production side effect.

## 17. Test strategy

- Unit tests: deterministic class→tier mapping, escalation triggers, budget cap, telemetry redaction.
- Contract tests: router cannot call authority methods (mock guard).
- Integration: routing an existing M4-8 task through the pipeline reproduces same green gates with ≤ tier.
- Live-change: routing pipeline must not alter production behavior (shadow-mode assertions).
- Benchmark: pre/post tier cost/quality on corpus; escalation rate measured.

## 18. Acceptance criteria

- Router deterministically selects cheapest tier for all benchmark tasks; statement passes green gates.
- Escalation fires only on objective triggers (no self-confidence).
- ≥1 correction → confidence decreases, tier may.
- Telemetry redacts secrets; no `attempt_nonce` or key surfaces.
- Router never calls production authority / scheduler / receipt, tests enforce.
- Full benchmark: each task's usable output (gates) at token cost measured; higher-tier only used when evidence requires.
- PR rule unchanged (stop at PR; never merge on local-only).

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