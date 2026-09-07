# M11.2 — Actual Model/Provider Execution and Adaptive Routing

**Status:** Implementation complete. Design authority:
`docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md` (PR #81) + M11.1 core (PR #82).

## Boundary (unchanged, non-negotiable)

M11.2 adds the **provider-execution layer** in SAFE SHADOW/ADVISORY MODE. It is
development-tooling only. It does NOT modify Unreal production authority, render
authorization, recovery authority, receipts, scheduling, retry semantics, or
production job records. Atlas production execution is completely untouched.

## New/changed components

| Component | File | Notes |
|---|---|---|
| Provider configuration | `planning/m11_router/provider/providers_config.py` | `ProviderConfig`, `ProviderConfigError`, `load_provider_configs`, `extract_usage`, `estimate_cost`, `try_estimate_cost`, `CostUnavailable`. Fail-closed validation (missing provider/model/tier/task-classes/budget/timeout, ambiguous tier, unsupported class, malformed shape). |
| Invocation contract | `planning/m11_router/provider/invocation.py` | `ProviderAdapter` (vendor-agnostic Protocol), `ProviderInvocation`, `invoke_model`, `ModelResult` (immutable), `InvocationErrorKind`. Structured result: task/attempt/tier/provider/model/requested budget/usage/latency/status/error-class. Provider failures classified; never evidence; no uncontrolled retry. |
| Token/cost accounting | `providers_config.py` | `ProviderUsage` (input/output/total), `extract_usage` from provider responses, `estimate_cost` from config pricing (raises `CostUnavailable`), `try_estimate_cost` → explicit `None` (UNKNOWN, never fabricated). |
| Shadow/advisory mode | `planning/m11_router/provider/shadow.py` | `ShadowAdvisor.advise()`: resolve provider config → controlled invocation → evaluate objective evidence → append telemetry → return immutable `ShadowAdvisory` (recommendation/invocation/evidence/escalation/telemetry_written). Never replaces the authoritative Hermes path. |
| Benchmark execution | `planning/m11_router/benchmark.py` | `run_benchmark_task(..., advisor=...)` now executes the corpus through a shadow advisor, capturing evidence outcome, tokens, latency, cost, escalations, final tier. Useful-output metrics, not cheapest-token optimization. |
| M11.2 tests | `tests/m11/fake_provider.py`, `test_m11_provider_invocation.py`, `test_m11_shadow_advisory.py`, + updated benchmark/authority tests | Mocked provider adapters (no live API). |

## Separation of concerns

- **Qwen/model:** reason / propose (unchanged).
- **M11 router:** classify / select / escalate / measure (unchanged boundary).
- **Hermes execution layer:** invokes the development model and performs the work (authoritative; unchanged).
- **M11.2 shadow mode:** may recommend + invoke the selected model, collect telemetry + evidence, and COMPARE against the authoritative path — but never silently replaces it.
- **Atlas production authority:** unchanged and independent.

## Shadow/advisory mode semantics

- Records the router recommendation.
- Invokes the selected provider/model via the controlled adapter boundary.
- Collects result telemetry and evidence outcome.
- Compares recommendation/results with the existing path where practical.
- Never replaces the existing execution path; never mutates Atlas production authority.
- Model self-reported confidence is never treated as evidence. Only objective signals (tests/build/static/contract/diff via the M11 evidence gate) may classify an attempt as successful.

## Provider configuration strategy

Provider/model/pricing names are deployment configuration parameters. The
router (classify/select/escalate) never hard-codes them. `ShadowAdvisor`
resolves a configured `ProviderConfig` whose `capability_tier` satisfies the
selected model tier (fail-closed if none matches → `NEEDS_HUMAN_REVIEW`).
Example config shape:

```json
{"providers": [
  {"provider":"openrouter","model":"<id>","capability_tier":"L1",
   "supported_task_classes":["docs","test","refactor"],
   "token_budget":8000,"timeout_s":60,
   "endpoint_config_ref":"openrouter-default",
   "pricing":{"input_per_1k":0.0005,"output_per_1k":0.0015},
   "pricing_source_id":"openrouter-default"}
]}
```

## Escalation integration

Reuses the M11.1 bounded `EscalationController`:
`MAX_ESCALATIONS_PER_TASK = 3`, never downgrade, no blind rerun, no infinite
loop, `MAX_TIER = L3` terminal, exhausted/failed → `NEEDS_HUMAN_REVIEW`.
Provider failure alone never causes an uncontrolled retry (test asserts exactly
one invocation attempt on provider failure).

## Telemetry

Extends the existing M11 append-only `RouterTelemetryRecord`/`AppendOnlyTelemetry`
(no second telemetry authority). Records: task, selected tier, provider/model,
requested vs actual tokens, latency, estimated cost (where known), escalation,
objective evidence pass/fail, terminal outcome. Strict privacy allow-list
preserved; never persists API keys, credentials, `attempt_nonce`, HMAC keys,
credential-bearing prompts, or sensitive provider headers.

## Validation

- `pytest tests/m11` = **177 passed** (M11.1 136 + M11.2 41).
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/ tests/m11/` = **285 passed**.
- `pytest -m "not integration"` = **1389 passed** (1348 baseline + 41, no regressions).
- No workflow/action-runner tests; no live Unreal; no Blender.

## Authority-leak review (pre-PR)

Scanned the full M11 diff for production-coupling terms:
`unreal_render_*`, `apply_authorized`, `submit_render`, `reconcile_render_jobs`,
`receipt`, `schedul`, `authorization_id`, `attempt_nonce`. All hits are:
docstring/comment **prohibitions** ("MUST NOT contain attempt_nonce",
"cannot call apply_authorized..."), RISK-DIMENSION enum NAMES, or
critical-marker substrings for the classifier. There are NO imports of, and no
calls into, any Atlas production module. Enforced by deterministic tests.

## Known limitations

- Provider adapters are mocked in the deterministic suite; a real OpenRouter/DeepSeek
  adapter (reading credentials from secure config, never persisted) is a follow-up.
- Actual per-call token counts depend on provider support; missing usage stays
  UNKNOWN (never fabricated).
- Endpoint config (`endpoint_config_ref`) is carried as an identifier; the concrete
  endpoint resolution + auth (secure, non-repo) is deployment wiring.
- Shadow mode is advisory and not yet auto-wired into the Hermes runtime loop
  (acceptable: the existing DeepSeek V4 Flash/OpenRouter workflow is preserved).