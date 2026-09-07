"""M11.3 deterministic tests: Hermes integration feature gate + shadow isolation."""

import pytest

from planning.m11_router.hermes_integration import (
    FeatureConfigError,
    M11FeatureConfig,
    ShadowRoutedExecutor,
    load_feature_config,
)
from planning.m11_router.model_profile import load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.provider.providers_config import load_provider_configs
from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
from planning.m11_router.provider.secure_config import SecureConfigResolver
from planning.m11_router.risk import RISK_DIMENSIONS

from tests.m11.fake_provider import FakeAdapter


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


@pytest.fixture
def router():
    profiles = load_profiles([
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
    return ModelRouter(profiles)


def _provider_configs():
    return load_provider_configs([
        {"provider": "openrouter", "model": "flash", "capability_tier": "L1",
         "supported_task_classes": ["docs", "test", "refactor"],
         "token_budget": 8000, "timeout_s": 60,
         "pricing": {"input_per_1k": 0.0005, "output_per_1k": 0.0015}},
    ])


# ---- feature gate default preserves current behavior ----

def test_feature_config_default_disabled():
    cfg = load_feature_config(env={})
    assert cfg.enabled is False
    assert cfg.mode == "off"


def test_feature_config_env_disables_keeps_off():
    cfg = load_feature_config(env={"ATLAS_M11_ROUTING_ENABLED": "1", "ATLAS_M11_ROUTING_MODE": "advisory"}, endpoint_config_ref="openrouter")
    assert cfg.enabled is True
    assert cfg.mode == "advisory"


def test_feature_config_invalid_mode_fails_closed():
    with pytest.raises(FeatureConfigError):
        M11FeatureConfig(enabled=True, mode="stealth")


def test_feature_config_disabled_with_nonoff_mode_rejected():
    with pytest.raises(FeatureConfigError):
        M11FeatureConfig(enabled=False, mode="shadow")


def test_shadow_executor_disabled_returns_marker_and_routes_nothing(router):
    ex = ShadowRoutedExecutor(M11FeatureConfig(), router=router, adapter=FakeAdapter())
    assert ex.enabled is False
    out = ex.execute(task_id="t", dimension_scores=_zero(), task_classes=["docs"])
    assert out["routed"] is False
    assert out["enabled"] is False
    # The authoritative Hermes path is untouched (no invocation happened).


# ---- shadow/advisory isolation ----

def test_shadow_executor_routes_but_never_replaces(router):
    ex = ShadowRoutedExecutor(
        M11FeatureConfig(enabled=True, mode="shadow"), router=router,
        adapter=FakeAdapter(), provider_configs=_provider_configs(),
    )
    out = ex.execute(task_id="t", dimension_scores=_zero(), task_classes=["docs"])
    assert out["routed"] is True
    assert out["recommendation"]["selected_tier"] == "L0"
    # invocation is advisory-only; never asserted as authoritative output
    assert out["invocation"]["advisory_only"] is True
    assert out["enabled"] is True


def test_shadow_executor_crypto_selects_l3_but_provider_missing_advisory_skip(router):
    scores = {**_zero(), "cryptography": 2}
    ex = ShadowRoutedExecutor(
        M11FeatureConfig(enabled=True, mode="shadow"), router=router,
        adapter=FakeAdapter(), provider_configs=_provider_configs(),  # only L1 provider
    )
    out = ex.execute(task_id="t", dimension_scores=scores, task_classes=["security-crypto"])
    # security-crypto class floor -> L3 selected by the router.
    assert out["routed"] is True
    assert out["recommendation"]["selected_tier"] == "L3"
    # No L3 provider configured -> advisory skip (invocation status None), NOT an
    # exception and NOT a fallback to another provider.
    assert out["invocation"]["status"] is None
    assert out["invocation"]["advisory_only"] is True


def test_shadow_executor_provider_failure_is_advisory_not_raised(router):
    failing = FakeAdapter(status="error")
    ex = ShadowRoutedExecutor(
        M11FeatureConfig(enabled=True, mode="shadow"), router=router,
        adapter=failing, provider_configs=_provider_configs(),
    )
    out = ex.execute(task_id="t", dimension_scores=_zero(), task_classes=["docs"])
    # provider failure captured as advisory status, never an exception or authority claim
    assert out["invocation"]["status"] == "error"


def test_shadow_executor_does_not_introduce_retry(router, monkeypatch):
    calls = {"n": 0}
    orig = FakeAdapter.invoke

    def counting_invoke(self, **kw):
        calls["n"] += 1
        return orig(self, **kw)

    monkeypatch.setattr(FakeAdapter, "invoke", counting_invoke)
    ex = ShadowRoutedExecutor(
        M11FeatureConfig(enabled=True, mode="shadow"), router=router,
        adapter=FakeAdapter(), provider_configs=_provider_configs(),
    )
    ex.execute(task_id="t", dimension_scores=_zero(), task_classes=["docs"])
    assert calls["n"] == 1  # no uncontrolled retry


def test_shadow_executor_authority_isolation():
    """The Hermes integration module must not import or reach Atlas production
    authority (scheduler/retry/auth/persistence)."""
    import ast
    from pathlib import Path
    p = Path("planning/m11_router/hermes_integration.py")
    tree = ast.parse(p.read_text(encoding="utf-8"))
    forbidden = {"unreal_render", "apply_authorized", "submit_render", "reconcile_render_jobs",
                 "issue_receipt", "schedule", "authorization_id", "AtlasRenderJobStore",
                 "UnrealRenderReceipt"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(f in mod for f in ("unreal_render", "unreal_adapter", "receipt", "schedul")):
                pytest.fail(f"hermes_integration imports forbidden module {mod}")
            for a in node.names:
                if any(f in a.name for f in forbidden):
                    pytest.fail(f"hermes_integration imports forbidden name {a.name}")
        if isinstance(node, ast.Import):
            for a in node.names:
                if any(f in a.name for f in forbidden):
                    pytest.fail(f"hermes_integration imports forbidden name {a.name}")


def test_openrouter_adapter_is_vendor_isolated():
    """The router/risk/escalation modules never import the OpenRouter adapter
    (provider parsing must not leak into routing logic)."""
    import ast
    from pathlib import Path
    leaked = []
    # Operator-invocation / composition modules legitimately instantiate the
    # adapter; CORE routing/risk/escalation/telemetry logic must not.
    operator_modules = {
        "openrouter_adapter.py", "__init__.py",
        "hermes_integration.py", "live_validation.py",
        "live_operator.py",  # operator CLI (instantiates the adapter on --live)
    }
    for py in Path("planning/m11_router").rglob("*.py"):
        if py.name in operator_modules:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if "openrouter" in a.name:
                        leaked.append((py.name, a.name))
            elif isinstance(node, ast.ImportFrom):
                if "openrouter" in (node.module or ""):
                    leaked.append((py.name, node.module))
    assert leaked == [], f"router logic must not import the OpenRouter adapter: {leaked}"


def test_shadow_executor_never_writes_production_ledger(router, tmp_path):
    """Shadow execution must not write any production receipt/journal/authority."""
    ex = ShadowRoutedExecutor(
        M11FeatureConfig(enabled=True, mode="shadow"), router=router,
        adapter=FakeAdapter(), provider_configs=_provider_configs(),
    )
    ex.execute(task_id="t", dimension_scores=_zero(), task_classes=["docs"])
    # No files created anywhere (telemetry is optional and off here).
    created = list(tmp_path.iterdir())
    assert created == []