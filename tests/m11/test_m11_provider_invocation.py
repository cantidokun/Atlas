"""M11.2 deterministic tests: provider configuration validation + invocation contract."""

import pytest

from planning.m11_router.provider.providers_config import (
    CostUnavailable,
    ProviderConfigError,
    ProviderUsage,
    estimate_cost,
    extract_usage,
    load_provider_configs,
    try_estimate_cost,
)
from planning.m11_router.provider.invocation import (
    InvocationErrorKind,
    ProviderInvocation,
    invoke_model,
)
from planning.m11_router.model_profile import ModelTier
from planning.m11_router.provider.providers_config import ProviderConfig

from tests.m11.fake_provider import FakeAdapter, pricing_dict


def _good_cfg():
    return {
        "provider": "openrouter", "model": "dd", "capability_tier": "L1",
        "supported_task_classes": ["docs", "test", "refactor"],
        "token_budget": 8000, "timeout_s": 60,
        "endpoint_config_ref": "openrouter", "pricing": pricing_dict(),
        "pricing_source_id": "openrouter-default",
    }


# ---- provider config validation (fail closed) ----

def test_provider_config_ok():
    cfgs = load_provider_configs([_good_cfg()])
    assert cfgs[0].provider == "openrouter"
    assert cfgs[0].capability_tier == ModelTier.L1
    assert cfgs[0].pricing_source_id == "openrouter-default"


@pytest.mark.parametrize("field", ["provider", "model", "capability_tier", "supported_task_classes", "token_budget", "timeout_s"])
def test_provider_missing_required_field_rejected(field):
    cfg = dict(_good_cfg())
    del cfg[field]
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_empty_model_rejected():
    cfg = dict(_good_cfg()); cfg["model"] = "   "
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_unsupported_task_class_rejected():
    cfg = dict(_good_cfg()); cfg["supported_task_classes"] = ["made-up"]
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_invalid_token_budget_rejected():
    cfg = dict(_good_cfg()); cfg["token_budget"] = 0
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_invalid_timeout_rejected():
    cfg = dict(_good_cfg()); cfg["timeout_s"] = -1
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_ambiguous_capability_tier_rejected():
    cfg = dict(_good_cfg()); cfg["capability_tier"] = "L9"
    with pytest.raises(ProviderConfigError):
        load_provider_configs([cfg])


def test_provider_malformed_config_shape_rejected():
    with pytest.raises(ProviderConfigError):
        load_provider_configs("not-a-list")


def test_provider_empty_config_rejected():
    with pytest.raises(ProviderConfigError):
        load_provider_configs([])


# ---- usage extraction ----

def test_extract_usage_nested():
    u = extract_usage({"usage": {"prompt_tokens": 100, "completion_tokens": 50}})
    assert u.input_tokens == 100
    assert u.output_tokens == 50
    assert u.total_tokens == 150


def test_extract_usage_flat():
    u = extract_usage({"input_tokens": 7, "output_tokens": 3, "total_tokens": 10})
    assert u.total_tokens == 10


def test_extract_usage_missing_stays_unknown():
    u = extract_usage({"foo": "bar"})
    assert u.usage_unknown is True
    assert u.input_tokens is None


# ---- cost accounting ----

def test_cost_estimated_from_pricing():
    u = ProviderUsage(input_tokens=1000, output_tokens=2000)
    cost = estimate_cost(u, {"input_per_1k": 0.5, "output_per_1k": 1.0})
    assert cost == pytest.approx(0.5 + 2.0)  # 0.5*1 + 1.0*2


def test_cost_unknown_when_pricing_missing():
    u = ProviderUsage(input_tokens=1000, output_tokens=2000)
    with pytest.raises(CostUnavailable):
        estimate_cost(u, None)


def test_cost_unknown_when_usage_missing():
    with pytest.raises(CostUnavailable):
        estimate_cost(ProviderUsage(), {"input_per_1k": 0.5, "output_per_1k": 1.0})


def test_try_estimate_cost_returns_none_not_fabricated():
    assert try_estimate_cost(ProviderUsage(), pricing_dict()) is None  # UNKNOWN, not 0


def test_cost_never_fabricated():
    u = extract_usage({"not_usage": True})
    assert u.estimated_cost_usd is None


# ---- invocation contract ----

def _invocation():
    cfg = ProviderConfig(
        provider="openrouter", model="dd", capability_tier=ModelTier.L1,
        supported_task_classes=frozenset({"docs"}),
        token_budget=8000, timeout_s=60, pricing=pricing_dict(),
    )
    return ProviderInvocation(
        task_id="t", attempt_id="a1", selected_tier=ModelTier.L1,
        provider_config=cfg, task_payload={"desc": "doc"},
        requested_token_budget=8000, timeout_s=60,
    )


def test_invocation_success():
    res = invoke_model(_invocation(), FakeAdapter())
    assert res.is_success is True
    assert res.status == "success"
    assert res.provider == "openrouter"
    assert res.model == "dd"
    assert res.latency_ms is not None
    assert res.requested_token_budget == 8000


def test_invocation_timeout_classified():
    res = invoke_model(_invocation(), FakeAdapter(raise_timeout=True))
    assert res.is_success is False
    assert res.error_class == InvocationErrorKind.TIMEOUT.value


def test_invocation_unavailable_classified():
    class Boom:
        def invoke(self, **kw):
            raise ConnectionError("provider down")
    res = invoke_model(_invocation(), Boom())
    assert res.is_success is False
    assert res.error_class == InvocationErrorKind.PROVIDER_UNAVAILABLE.value


def test_invocation_malformed_response_classified():
    class Bad:
        def invoke(self, **kw):
            return None  # not a ModelResult
    res = invoke_model(_invocation(), Bad())
    assert res.error_class == InvocationErrorKind.MALFORMED_RESPONSE.value


def test_invocation_returns_immutable_result():
    res = invoke_model(_invocation(), FakeAdapter())
    with pytest.raises(AttributeError):
        res.status = "hacked"  # dataclass frozen


def test_result_self_report_confidence_not_present():
    # ModelResult has no confidence field; confidence can never be evidence.
    res = invoke_model(_invocation(), FakeAdapter())
    assert not hasattr(res, "confidence")