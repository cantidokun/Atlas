# M11.1 — Adaptive Development Model Router Core

**Status:** Implementation complete (core). Design authority:
`docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md` (merged PR #81).

## Scope & boundary

M11.1 implements the **development-tooling router core** only. It is NOT Atlas
production or recovery authority. The router has **no ability** to authorize
production work, issue production capabilities, call `apply_authorized`,
`submit_render`, `reconcile_render_jobs`, create receipts, schedule production
jobs, retry uncertain production execution, or modify authoritative Atlas
records. Its persistence is confined to its own `m11_router` telemetry ledger.

## Implemented components

| Concept (design) | Module | Notes |
|---|---|---|
| Model tier + validated config | `planning/m11_router/model_profile.py` | `ModelTier`, `ModelProfile`, `load_profiles`, `ProfileLoadError` (fails closed). Capability comes from validated static config only; names are deployment params. |
| Deterministic risk classification | `planning/m11_router/risk.py` | `classify_task` implements frozen rules R1–R7 (per-dimension 0–3, max-dim raw tier, hard-selector floors R4, multiple→max R5, unknown→L3 R6, final=R7). Model confidence ignored. `hard_file_tokens` supported. |
| Routing decision | `planning/m11_router/routing.py` | `select_profile` picks lowest-capable validated profile; `ModelSelection`, `RouterDecision` (immutable). No-capable-profile fails closed. |
| Finite escalation | `planning/m11_router/escalation.py` | `EscalationController`, `EscalationState`. `MAX_ESCALATIONS_PER_TASK=3`, `MAX_TIER=L3`, terminal `NEEDS_HUMAN_REVIEW` (budget/L3-fail/insufficient-evidence). No downgrade/blind-rerun/loop. |
| Append-only telemetry | `planning/m11_router/telemetry.py` | `RouterTelemetryRecord`, `AppendOnlyTelemetry` (JSONL). Strict allow-list; disallowed sensitive fields rejected fail-closed; records immutable; new attempts append. |
| Evidence gate | `planning/m11_router/evidence_gate.py` | `EvidenceGate`, `EvidenceGateResult` (SUFFICIENT/INSUFFICIENT/FAILED/ESCALATION/TERMINAL_HUMAN_REVIEW). Free-form model claims cannot pass. |
| Escalation packet | `planning/m11_router/escalation_packet.py` | `EscalationPacket` (serializable; identity + evidence + failures + prior attempts). |
| Router facade | `planning/m11_router/router.py` | `ModelRouter` ties classify→select→telemetry→gate. No production modules imported. |
| Benchmark skeleton | `planning/m11_router/benchmark.py` | `BenchmarkTask`/`BenchmarkResult` + 6 representative fixtures (docs/test/refactor/api/recovery/crypto). Full corpus deferred to M11.2. |
| Shared constants | `planning/m11_router/constants.py` | Task classes (no circular import). |

## API snapshot

- `classify_task(task_id, dimension_scores, *, task_classes, confidence, hard_file_tokens) -> RiskAssessment`
- `select_profile(task_id, risk, profiles) -> ModelSelection` (raises `NoCapableProfileError`)
- `EscalationController(max_escalations=3).initial(task_id, tier, attempt)` / `.escalate(...)`
- `AppendOnlyTelemetry(path).append(record)` / `.read_task(...)` / `.read_all()`
- `ModelRouter(profiles, *, escalation_max, evidence_gate, telemetry).route_task(...) -> RouterDecision`

## Configuration format

Profiles are validated on load; any missing/null/inconsistent field is rejected
(fail-closed), e.g.:

```json
{
  "profiles": [
    {"tier":"L0","provider":"<deployment>","model":"<id>","capability_floor":"L0",
     "supported_task_classes":["docs","test"],"token_budget":2000,"timeout_s":30,"cost_metadata":null}
  ]
}
```

Provider/model identifiers are deployment configuration parameters (never
hard-coded here). See `tests/m11/conftest.py` for the standard 4-tier fixture.

## Security / privacy controls

- Strict allow-list; any record containing a secret/credential/API key/
  `attempt_nonce`/HMAC key/key material is rejected and dropped (fail-closed).
- Escalation packets carry evidence + identity, no credential-bearing data.
- Router package imports no production authority modules (enforced by test).

## Test coverage (deterministic)

- `tests/m11/` (5 modules, 136 tests): risk (R1–R7, hard selectors, unknown→L3,
  confidence ignored, determinism), profiles/routing (malformed→reject, lowest
  capable, self-report can't lower), escalation (0→1→2→3, budget=3, L3 terminal,
  no downgrade/loop, terminal prevents further), telemetry (append-only,
  immutability, sensitive→reject, write-fail→unknown), evidence gate, escalation
  packets, router facade + authority isolation (no production imports/methods),
  benchmark skeleton.
- Full deterministic suite: 1348 passed (1212 baseline + 136 new, no regressions).

## Validation performed

- `pytest tests/m11` = 136 passed.
- `pytest tests/test_unreal_render_submission.py tests/test_unreal_recovery_coordinator.py tests/m10/` = 111 passed.
- `pytest -m "not integration"` = 1348 passed.
- No workflow/action-runner tests; no live Unreal; no Blender.

## Non-goals / known limitations

- Model execution orchestration, provider invocation, and token accounting are
  OUT of scope (M11.2+). `requested_token_budget` flows through; actual usage is
  a field only.
- Benchmark harness is a skeleton; the full corpus run is deferred to M11.2.
- The router does not yet integrate into the Hermes runtime loop (default off /
  advisory); it is a standalone core with a clean API for later wiring.
- Provider/model names are not bound (deployment config parameter).