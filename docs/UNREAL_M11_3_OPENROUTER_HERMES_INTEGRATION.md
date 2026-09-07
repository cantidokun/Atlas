# M11.3 — Real Provider Adapter + Controlled Hermes Integration

**Status:** Implementation complete. Design authority:
`docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md` (PR #81) + M11.1 core + M11.2
provider abstraction (PR #83).

## Boundary (unchanged, non-negotiable)

M11.3 adds the REAL OpenRouter adapter behind the vendor-agnostic
`ProviderAdapter` boundary, and wires M11 routing into the Hermes development
loop behind an explicit SHADOW/ADVISORY feature gate. It is development-tooling
only. Atlas production authority, authorization, recovery, receipts, scheduling,
retry semantics, and production job records are completely untouched. The existing
Hermes execution path remains authoritative until independently validated.

## New/changed components

| Component | File | Notes |
|---|---|---|
| Secure deployment config | `planning/m11_router/provider/secure_config.py` | `SecureConfigResolver` resolves `endpoint_config_ref` to a live API key + endpoint from env/secure config at call time. Credentials NEVER in repo/source/fixtures/telemetry/benchmarks/logs/PRs. Fail-closed when unavailable. |
| Real OpenRouter adapter | `planning/m11_router/provider/openrouter_adapter.py` | `OpenRouterAdapter` implements `ProviderAdapter`. Uses `requests` (or injected session for tests) against the OpenAI-compatible `/chat/completions` shape. Parses content + usage into immutable `ModelResult`; classifies transport/malformed/auth/rate-limit errors; never uncontrolled retry; never returns credentials; provider parsing stays behind the boundary. |
| Hermes feature gate | `planning/m11_router/hermes_integration.py` | `M11FeatureConfig` + `load_feature_config` + `ShadowRoutedExecutor`. Explicit flag `ATLAS_M11_ROUTING_ENABLED`/`ATLAS_M11_ROUTING_MODE`; default `off` preserves current behavior. In `shadow`/`advisory` mode it routes the task, may invoke the routed model via an injected adapter, and returns advisory metrics — never replaces the authoritative path. |

## Security requirements met

- Never persist API keys, Authorization headers, credentials, or
  credential-bearing prompts: the key exists only transiently in the request
  header and is never written to telemetry, benchmark output, logs, fixtures, or
  returned in `ModelResult`.
- Never place credentials in Git history / source / fixtures / telemetry /
  benchmark output / PR bodies / logs: the repo stores only the
  `endpoint_config_ref` identifier.
- Fail closed when credentials or endpoint configuration are unavailable:
  `SecureConfigUnavailableError` -> error `ModelResult` (AUTH_ERROR /
  REQUEST_ERROR); no silent fallback.
- Malformed provider responses are treatment as invocation failures
  (MALFORMED_RESPONSE), never as evidence.
- No uncontrolled retries: exactly one HTTP call per invoke; bounded M11
  escalation governs any next step.

## Provider boundary (vendored properly)

- `ProviderAdapter` remains vendor-agnostic (M11.2).
- `OpenRouterAdapter` is the only module touching provider-specific parsing.
- Router/risk/escalation logic never imports the OpenRouter adapter (test-enforced):
  only package `__init__.py` (export aggregator) references it.

## Hermes integration

- Explicit config flag; default preserves current behavior (disabled).
- Shadow mode may invoke the routed model and collect evidence/metrics.
- Does NOT automatically replace the authoritative Hermes execution path.
- No second scheduler, retry controller, authorization layer, or persistence
  authority introduced.

## Validation (deterministic)

- `pytest tests/m11` = **204 passed** (177 M11.2 + 27 M11.3).
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/ tests/m11/` = **312 passed**.
- `pytest -m "not integration"` = **1416 passed** (1389 + 27, no regressions).
- No workflow/action-runner tests; no live Unreal; no Blender.

## Pre-PR review (performed)

- Credential-leak scan across the diff: no `sk-`, `Bearer `, `api_key=`,
  `Authorization` value, or credential-bearing prompt appears in any committed
  source, fixture, telemetry, benchmark, or literal. Keys are only referenced as
  the env-var *name* / identifier, never the value.
- Production-authority isolation: the provider adapter + Hermes integration
  import no Atlas production module and expose no authority-shaped method.
  Enforced by tests (`test_shadow_executor_authority_isolation`, `test_adapter_...`).

## What remains shadow-only

- M11 routing / provider invocation is advisory only.
- The authoritative Hermes execution path is unchanged and remains authoritative.
- No automatic promotion to "advisory writes/decisions" — the router may recommend
  and invoke, but the caller decides. A future milestone (after independent
  validation) may enable an explicit non-shadow mode.

## Known limitations

- Live network calls are NOT made in the deterministic suite; the OpenRouter
  adapter is tested against a stubbed session + env resolver. A real end-to-end
  call requires a running OpenRouter credential in secure env (out of scope here).
- `base_url` override is used in tests; production resolution honors
  `endpoint_config_ref` -> env endpoint -> public OpenRouter base.
- Per-call token counts depend on provider support; missing usage stays
  UNKNOWN (never fabricated). Cost only from explicit pricing config.
- Shadow integration is not yet auto-wired into the Hermes runtime loop; it is a
  callable advisory executor the operator may invoke when the flag is enabled.