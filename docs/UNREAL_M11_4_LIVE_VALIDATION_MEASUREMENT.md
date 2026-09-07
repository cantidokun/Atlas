# M11.4 — Live Provider Validation + Adaptive Routing Measurement

**Status:** Implementation complete. Builds on M11.3 (PR #84). Design authority:
`docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md`.

## Boundary (unchanged, non-negotiable)

M11.4 adds the **operator-invoked controlled live-validation path** and
machine-readable benchmark measurement. It is development-tooling only. Atlas
production authority, authorization, recovery, receipts, scheduling, retry, and
job records are completely untouched. No production execution authority is
enabled. The existing Hermes execution path is NOT silently replaced.

## Phase 1 — controlled live-provider smoke test

- `planning/m11_router/live_validation.py`: `ControlledLiveValidator`
  (operator gate `gated_enabled`; real `OpenRouterAdapter`; ONE request per
  invocation; bounded timeout; no auto retry; safe telemetry; never persists
  credentials) and `run_live_smoke` (trivial deterministic docs task).
- `planning/m11_router/live_operator.py`: operator CLI, `python -m
  planning.m11_router.live_operator --live --smoke` (or `--benchmark --out X`).
  Requires `--live` (explicit feature gate); fails closed with no credentials.

## Phase 2 — objective validation

- Every live response is evaluated with objective evidence (tests/build/static/
  contract/diff) via the M11 evidence gate. A provider HTTP-200 is NOT success;
  provider failure never becomes evidence (`test_provider_failure_never_becomes_evidence`).

## Phase 3/4 — benchmark corpus + baseline comparison

- `planning/m11_router/benchmark.py::run_benchmark_corpus` runs the 6-fixture
  M-file corpus through a live validator and emits a **machine-readable JSON
  report** (`summary` + per-task rows): selected/final tier, first-pass success,
  input/output/total tokens, latency, estimated cost, provider_errors,
  evidence_failures, tokens_unknown, escalations. UNKNOWN values are honest
  `None`/`0`, never fabricated.
- The report answers: did routing improve objective completion (first-pass/
  useful-output rate), which task classes map to lower tiers, where escalation /
  provider errors occur, and the token/cost/latency tradeoff. It deliberately
  does NOT optimize for token minimization alone.

## Phase 5 — routing calibration

- Real calibration is deferred until real live evidence is collected (operator
  must run with credentials). The frozen M11 risk formula (R1–R7) is NOT changed
  to game benchmark numbers. Any future calibration documents observed failure,
  evidence, why the rule is inadequate, the proposed rule, regression risks, and
  new tests.

## Phase 6 — telemetry integrity

- Strengthened `telemetry.SENSITIVE_SUBSTRINGS` + split key-vs-value sensitivity
  with a safe-canonical-name whitelist (so risk-dimension key names like
  `authorization_identity` are never false-flagged) and credential-shaped key
  markers. Tests cover: no credential material, no Authorization header, no API
  key, no `attempt_nonce`, no HMAC key, no credential-bearing prompt, append-only
  + stable task id + unique attempt id.

## Phase 7 — live-provider failure scenarios (deterministic tests)

Covered with mocked adapters (never live network in the default suite):
missing credentials (AUTH_ERROR), invalid credentials, unavailable endpoint
(PROVIDER_UNAVAILABLE), timeout (TIMEOUT), rate limit (RATE_LIMIT), malformed
response (MALFORMED_RESPONSE), missing usage (UNKNOWN). Rules enforced: exactly
one provider invocation per attempt, no uncontrolled retry, provider failure is
never evidence, failure stays visible in telemetry, escalation stays bounded.

## Deterministic CI is provider-independent

Live/network provider tests are gated behind `--live` / `gated_enabled`; the
default deterministic suite never touches a real endpoint. No real credentials
in repository configuration or tests.

## Validation (deterministic)

- `pytest tests/m11` = **229 passed** (204 M11.3 + 25 M11.4).
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/ tests/m11/` = **337 passed**.
- `pytest -m "not integration"` = **1441 passed** (1416 + 25, no regressions).
- No workflow/action-runner tests; no live Unreal; no Blender.

## Bench marked honestly

- Operator-gated live runs did NOT execute against a real provider in this
  change (no credentials provisioned). The smoke path was exercised with no key:
  it fails closed with `AUTH_ERROR` and `tokens_unknown=True`,
  `estimated_cost_usd=None`, `final_outcome=PROVIDER_UNAVAILABLE` — honest, no
  fabrication, no crash. A real baseline report requires the operator to run
  `--live --benchmark --out report.json` with credentials present; it is not
  committed into the deterministic suite.
- UNKNOWN/None values are reported as such; no synthetic token/cost numbers.

## Pre-PR review (performed)

- Complete diff inspected; no production-authority coupling (live_validation /
  live_operator import only M11 internals + OpenRouter adapter boundary).
- No credential leakage: values are env-var references / clearly-fake security
  test dummies / telemetry detector markers.
- Live-provider execution is explicitly gated (`--live`, `gated_enabled`).
- Deterministic CI is provider-independent.

## Known limitations

- A real end-to-end provider baseline requires operator-run `--live` with
  credentials in secure env; not executed here (no creds provisioned).
- Actual token counts depend on provider support; missing usage stays UNKNOWN.
- Cost only from explicit pricing config; this change leaves pricing None so
  cost is UNKNOWN until a deployment config provides it.
- Routing calibration (Phase 5) is deferred to after real live evidence is
  collected; the frozen risk formula is unchanged.
- Shadow/advisory only — the authoritative Hermes path is unchanged.