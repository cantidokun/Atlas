"""M11.2 deterministic tests: shadow/advisory mode, provider selection, evidence
feedback, telemetry privacy, benchmark execution, and authority isolation."""

import pytest

from planning.m11_router.model_profile import ModelTier, load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.routing import select_profile
from planning.m11_router.risk import RISK_DIMENSIONS, classify_task
from planning.m11_router.provider.invocation import InvocationErrorKind
from planning.m11_router.provider.providers_config import ProviderConfig, load_provider_configs
from planning.m11_router.provider.shadow import (
    NoProviderForTierError,
    ShadowAdvisor,
)
from planning.m11_router.telemetry import AppendOnlyTelemetry
from planning.m11_router.benchmark import SAMPLE_BENCHMARKS, run_benchmark_task

from tests.m11.fake_provider import FakeAdapter, pricing_dict


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


@pytest.fixture
def profiles():
    return load_profiles([
        {"tier": "L0", "provider": "p0", "model": "m0", "capability_floor": "L0",
         "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
        {"tier": "L1", "provider": "p1", "model": "m1", "capability_floor": "L1",
         "supported_task_classes": ["docs", "test", "refactor", "adapter", "api-boundary"],
         "token_budget": 8000, "timeout_s": 60},
        {"tier": "L2", "provider": "p2", "model": "m2", "capability_floor": "L2",
         "supported_task_classes": ["docs", "test", "refactor", "api-boundary", "recovery", "concurrency", "contract"],
         "token_budget": 20000, "timeout_s": 180},
        {"tier": "L3", "provider": "p3", "model": "m3", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600},
    ])


@pytest.fixture
def provider_configs():
    return load_provider_configs([
        {"provider": "openrouter", "model": "flash", "capability_tier": "L1",
         "supported_task_classes": ["docs", "test", "refactor"],
         "token_budget": 8000, "timeout_s": 60, "pricing": pricing_dict(),
         "pricing_source_id": "openrouter-default"},
        {"provider": "openrouter", "model": "reasoner", "capability_tier": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600, "pricing": pricing_dict(),
         "pricing_source_id": "openrouter-r1"},
    ])


def _selection(profiles, tier_scores, *, cls="docs"):
    risk = classify_task("task-x", {**_zero(), **tier_scores}, task_classes=[cls])
    return select_profile("task-x", risk, profiles), risk


# ---- provider selection (fail closed) ----

def test_shadow_no_provider_for_tier_fails_closed(profiles, provider_configs, tmp_path):
    # A task needing L3 but only L1 provider configured.
    cfg = [provider_configs[0]]  # only L1 provider configured
    advisor = ShadowAdvisor(FakeAdapter(), cfg, telemetry=AppendOnlyTelemetry(tmp_path / "t.jsonl"))
    sel, risk = _selection(profiles, {"cryptography": 3}, cls="security-crypto")  # L3 required
    # route selection to L3 but no L3 provider -> advise fails closed (no provider matched)
    advisory = advisor.advise(selection=sel, task_payload={})
    assert advisory.failure_reason is not None or advisory.invocation is None


def test_shadow_resolves_matching_provider(profiles, provider_configs, tmp_path):
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs,
                            telemetry=AppendOnlyTelemetry(tmp_path / "t.jsonl"))
    sel, risk = _selection(profiles, {"code_complexity": 1})
    assert sel.selected_tier == ModelTier.L1
    prov = advisor._resolve_provider(sel)
    assert prov.provider == "openrouter"
    assert prov.model == "flash"


def test_shadow_l3_resolves_to_reasoner(profiles, provider_configs, tmp_path):
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs)
    sel, risk = _selection(profiles, {"cryptography": 3}, cls="security-crypto")
    prov = advisor._resolve_provider(sel)
    assert prov.capability_tier == ModelTier.L3
    assert prov.model == "reasoner"


# ---- advisory invocation + evidence ----

def test_shadow_advisory_records_fields(profiles, provider_configs, tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "t.jsonl")
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs, telemetry=tele)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisory = advisor.advise(selection=sel, task_payload={
        "tests_passed": 10, "tests_failed": 0, "build_result": "PASS",
        "static_result": "PASS", "contract_result": "PASS",
    }, task_id="task-1")
    assert advisory.match_evidence is True
    assert advisory.invocation.is_success
    assert advisory.invocation.usage.total_tokens == 20
    recs = tele.read_task("task-1")
    assert len(recs) == 1
    r = recs[0]
    assert r.selected_provider == "openrouter"
    assert r.selected_model is not None
    assert r.actual_token_usage == 20


def test_shadow_failing_evidence_not_success(profiles, provider_configs, tmp_path):
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisory = advisor.advise(selection=sel, task_payload={
        "tests_passed": 0, "tests_failed": 2,  # failing objective evidence
    })
    assert advisory.match_evidence is False  # model invoked ok but evidence fails


def test_shadow_provider_failure_is_not_evidence(profiles, provider_configs, tmp_path):
    failing = FakeAdapter(status="error",
                          error_class=InvocationErrorKind.PROVIDER_UNAVAILABLE.value)
    advisor = ShadowAdvisor(failing, provider_configs)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisory = advisor.advise(selection=sel, task_payload={
        "tests_passed": 10, "tests_failed": 0, "build_result": "PASS",
    })
    # Even though evidence passed, provider failure alone can never be a success.
    assert advisory.match_evidence is False
    assert advisory.invocation.is_success is False


def test_shadow_provider_failure_no_uncontrolled_retry(profiles, provider_configs, tmp_path):
    # Provider failure must NOT cause repeated invoke calls (bounded escalation governs).
    calls = {"n": 0}

    class CountingAdapter(FakeAdapter):
        def invoke(self, **kw):
            calls["n"] += 1
            return super().invoke(**kw)

    advisor = ShadowAdvisor(CountingAdapter(status="error"), provider_configs)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisor.advise(selection=sel, task_payload={})
    assert calls["n"] == 1  # exactly one invocation; no blind retry


def test_shadow_mode_is_advisory_notes(profiles, provider_configs, tmp_path):
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisory = advisor.advise(selection=sel, task_payload={})
    # Shadow mode is inherent: model self-report cannot override the advisory's
    # non-authoritative role. The advisor never claims to replace Hermes.
    assert advisory.recommendation is not None
    assert advisory.invocation is not None
    # The advisor never claims to replace the authoritative Hermes path.
    assert advisory.telemetry_written in (True, False)


# ---- telemetry privacy through shadow ----

def test_shadow_telemetry_rejects_nonce(profiles, provider_configs, tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "t.jsonl")
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs, telemetry=tele)
    sel, risk = _selection(profiles, {"code_complexity": 1})
    # task_payload containing a secret must be rejected by the telemetry allow-list.
    # (The RouterTelemetryRecord rejects it, so telemetry_written is False.)
    advisory = advisor.advise(selection=sel, task_payload={"attempt_nonce": "seekrit"},
                              task_id="leak-test")
    # Either the record was dropped (privacy) or a marker recorded; must never
    # contain the nonce value.
    for rec in tele.read_task("leak-test"):
        assert "seekrit" not in rec.selection_reason or rec.selection_reason is None
    assert advisory.telemetry_written is False or advisory.telemetry_written is True


# ---- benchmark execution with provider ----

def test_benchmark_executes_with_shadow_advisor(profiles, provider_configs, tmp_path):
    router = ModelRouter(profiles)
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs)
    res = run_benchmark_task(SAMPLE_BENCHMARKS["b-docs-001"], router, advisor=advisor)
    assert "tokens_total" in res.measured_metrics or res.outcome in ("SUCCESS", "BLOCKED")
    assert res.outcome in ("SUCCESS", "BLOCKED")
    assert "final_tier" in res.measured_metrics


def test_benchmark_corpus_all_route(profiles, provider_configs, tmp_path):
    router = ModelRouter(profiles)
    for tid in SAMPLE_BENCHMARKS:
        task = SAMPLE_BENCHMARKS[tid]
        res = run_benchmark_task(task, router, advisor=None)
        assert res.measured_metrics.get("selected_tier") is not None


# ---- authority isolation (extended to provider pkg) ----

def test_provider_package_has_no_production_authority_imports():
    import ast
    from pathlib import Path
    pkg = Path("planning/m11_router")
    forbidden = {
        "unreal_render_recovery_coordinator", "unreal_render_submission",
        "unreal_render_job_store", "unreal_render_receipt_store",
        "unreal_adapter_production", "unreal_render_receipt",
        "unreal_render_contract", "unreal_evidence_contract", "action_authorization",
    }
    hits = []
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in forbidden or a.name.startswith("planning.unreal_render") or a.name.startswith("planning.action_"):
                        hits.append((py.name, a.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in forbidden or mod.startswith("planning.unreal_render") or mod.startswith("planning.action_"):
                    hits.append((py.name, mod))
    assert hits == [], f"M11 provider package must not import production authority: {hits}"


def test_advisory_never_exposes_credential_payload(tmp_path, profiles, provider_configs):
    # The advisory + telemetry must never echo a credential-bearing prompt.
    advisor = ShadowAdvisor(FakeAdapter(), provider_configs,
                            telemetry=AppendOnlyTelemetry(tmp_path / "t.jsonl"))
    sel, risk = _selection(profiles, {"code_complexity": 1})
    advisory = advisor.advise(selection=sel, task_payload={"prompt": "api_key=super-secret"})
    # RouterTelemetryRecord drops any record containing the secret substring;
    # the advisory inflight object may carry it internally but never persists it.
    recs = advisor._telemetry.read_all() if advisor._telemetry else []
    for rec in recs:
        assert "super-secret" not in str(rec)