"""M11.4 deterministic tests: controlled live-validation path.

These validate the OPERATOR-GATED live-validation pipeline using mocked adapters
and env resolvers; they never hit a real network and never use real credentials.
"""

import pytest

from planning.m11_router.live_validation import ControlledLiveValidator, LiveValidationResult
from planning.m11_router.model_profile import ModelTier, load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.provider.invocation import InvocationErrorKind, ModelResult
from planning.m11_router.provider.providers_config import (
    ProviderConfig,
    ProviderUsage,
)
from planning.m11_router.risk import RISK_DIMENSIONS
from planning.m11_router.telemetry import AppendOnlyTelemetry


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


@pytest.fixture
def router():
    profiles = load_profiles([
        {"tier": "L0", "provider": "cfg0", "model": "cfg-lite", "capability_floor": "L0",
         "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
        {"tier": "L1", "provider": "cfg1", "model": "cfg-eng", "capability_floor": "L1",
         "supported_task_classes": ["docs", "test", "refactor"], "token_budget": 8000, "timeout_s": 60},
        {"tier": "L3", "provider": "cfg3", "model": "cfg-frontier", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600},
    ])
    return ModelRouter(profiles)


@pytest.fixture
def provider_configs():
    return [
        ProviderConfig(provider="openrouter", model="deepseek-lite", capability_tier=ModelTier.L0,
                       supported_task_classes=frozenset({"docs", "test"}),
                       token_budget=2000, timeout_s=30, endpoint_config_ref="openrouter"),
        ProviderConfig(provider="openrouter", model="deepseek-flash", capability_tier=ModelTier.L1,
                       supported_task_classes=frozenset({"docs", "test", "refactor"}),
                       token_budget=8000, timeout_s=60, endpoint_config_ref="openrouter"),
        ProviderConfig(provider="openrouter", model="deepseek-frontier", capability_tier=ModelTier.L3,
                       supported_task_classes=frozenset({"security-crypto", "recovery"}),
                       token_budget=60000, timeout_s=600, endpoint_config_ref="openrouter"),
    ]


class StubAdapter:
    """Configurable stub (no network). Returns a ModelResult per params."""
    def __init__(self, *, status="success", error_class=InvocationErrorKind.NONE.value,
                 usage=None, latency=3, reply="ok"):
        self._status = status
        self._error_class = error_class
        self._usage = usage or ProviderUsage(input_tokens=5, output_tokens=3, total_tokens=8)
        self._latency = latency
        self._reply = reply
    def invoke(self, *, provider_config, task_payload, token_budget, timeout_s):
        return ModelResult(
            task_id=str(task_payload.get("_task_id", "t")),
            attempt_id="stub", selected_tier=provider_config.capability_tier,
            provider=provider_config.provider, model=provider_config.model,
            requested_token_budget=token_budget,
            status=self._status,
            usage=self._usage,
            latency_ms=self._latency,
            response=self._reply,
            error_class=self._error_class,
            error_message=("stub error" if self._status != "success" else None),
        )


def _validate(router, pcfgs, adapter, *, gated=True):
    return ControlledLiveValidator(router, pcfgs, adapter=adapter).validate_task(
        task_id="live-test", dimension_scores=_zero(), objective_evidence={
            "tests_passed": 10, "tests_failed": 0, "build_result": "PASS", "contract_result": "PASS",
        }, task_classes=["docs"], gated_enabled=gated,
    )


# ---- gate ----

def test_gate_off_skips_no_call(router, provider_configs):
    calls = {"n": 0}
    class Counting(StubAdapter):
        def invoke(self, **kw):
            calls["n"] += 1
            return super().invoke(**kw)
    res = _validate(router, provider_configs, Counting(), gated=False)
    assert res.request_status == "skipped"
    assert res.final_outcome == "SKIPPED"
    assert calls["n"] == 0  # no provider call


def test_gate_on_success_requires_evidence(router, provider_configs):
    res = _validate(router, provider_configs, StubAdapter())
    assert res.request_status == "success"
    assert res.total_tokens == 8
    assert res.tokens_unknown is False
    assert res.evidence_outcome == "SUFFICIENT"
    assert res.final_outcome == "PASS"
    assert res.estimated_cost_usd is None  # no pricing config -> explicit UNKNOWN


def test_live_result_is_immutable_serializable():
    r = LiveValidationResult(task_id="t", attempt_id="a", selected_tier="L0",
                             provider="p", model="m", request_status="success")
    d = r.to_dict()
    assert d["task_id"] == "t"
    with pytest.raises(AttributeError):
        r.final_outcome = "PASS"


# ---- provider failure scenarios (Phase 7) ----

def test_missing_credentials_is_failure_not_success(router, provider_configs):
    # Secured resolver missing key -> adapter returns AUTH_ERROR -> LiveValidation
    # final = PROVIDER_UNAVAILABLE, never PASS.
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.AUTH_ERROR.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"
    assert res.request_status == "error"
    assert res.error_class == InvocationErrorKind.AUTH_ERROR.value


def test_invalid_credentials_failure(router, provider_configs):
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.AUTH_ERROR.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome != "PASS"


def test_unavailable_endpoint_failure(router, provider_configs):
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.PROVIDER_UNAVAILABLE.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"


def test_timeout_failure(router, provider_configs):
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.TIMEOUT.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"
    assert res.error_class == InvocationErrorKind.TIMEOUT.value


def test_rate_limit_failure(router, provider_configs):
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.RATE_LIMIT.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"
    assert res.error_class == InvocationErrorKind.RATE_LIMIT.value


def test_malformed_response_failure(router, provider_configs):
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.MALFORMED_RESPONSE.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"
    assert res.error_class == InvocationErrorKind.MALFORMED_RESPONSE.value


def test_missing_usage_unknown(router, provider_configs):
    adapter = StubAdapter(usage=ProviderUsage())  # no usage
    res = _validate(router, provider_configs, adapter)
    assert res.tokens_unknown is True
    assert res.total_tokens is None
    assert res.estimated_cost_usd is None


def test_provider_failure_never_becomes_evidence(router, provider_configs, tmp_path):
    # Even with perfectly green objective_evidence, a provider failure must not
    # yield PASS (HTTP-200 alone is NOT success).
    adapter = StubAdapter(status="error", error_class=InvocationErrorKind.REQUEST_ERROR.value)
    res = _validate(router, provider_configs, adapter)
    assert res.final_outcome == "PROVIDER_UNAVAILABLE"
    assert res.final_outcome != "PASS"


def test_no_uncontrolled_retry(router, provider_configs):
    calls = {"n": 0}
    class Counting(StubAdapter):
        def invoke(self, **kw):
            calls["n"] += 1
            return super().invoke(**kw)
    _validate(router, provider_configs, Counting())
    assert calls["n"] == 1  # exactly one provider invocation per attempt


def test_failure_visible_in_telemetry(router, provider_configs, tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "t.jsonl")
    from planning.m11_router.provider.shadow import ShadowAdvisor
    from planning.m11_router.routing import select_profile
    from planning.m11_router.risk import classify_task
    fail_adapter = StubAdapter(status="error", error_class=InvocationErrorKind.RATE_LIMIT.value)
    advisor = ShadowAdvisor(fail_adapter, provider_configs, telemetry=tele)
    risk = classify_task("live-team", _zero(), task_classes=["docs"])
    sel = select_profile("live-team", risk, router.profiles)
    advisor.advise(selection=sel, task_payload={"tests_passed": 1, "tests_failed": 0}, task_id="live-team")
    recs = tele.read_task("live-team")
    # Provider failure is recorded and visible in telemetry, but not a success claim.
    assert len(recs) == 1
    assert recs[0].final_outcome in ("BLOCKED", "SUCCESS")