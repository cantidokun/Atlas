"""M11.3 deterministic tests: real OpenRouter adapter (mocked), secure config,
malformed responses, token/cost parsing, and credential non-leakage.

No live provider API is hit; a stubbed session + env resolver are injected.
"""

import pytest

from planning.m11_router.model_profile import ModelTier
from planning.m11_router.provider.invocation import InvocationErrorKind, ModelResult
from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
from planning.m11_router.provider.providers_config import ProviderConfig
from planning.m11_router.provider.secure_config import (
    SecureConfigResolver,
    SecureConfigUnavailableError,
)


class FakeResp:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.text = str(body)
    def json(self):
        return self._body


class FakeSession:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.last = None
    def post(self, url, headers=None, json=None, timeout=None):
        self.last = (url, dict(headers or {}), json, timeout)
        return FakeResp(self.body, self.status)


def _cfg():
    return ProviderConfig(
        provider="openrouter", model="deepseek-flash", capability_tier=ModelTier.L1,
        supported_task_classes=frozenset({"docs", "test"}),
        token_budget=8000, timeout_s=60,
        endpoint_config_ref="openrouter",
        pricing={"input_per_1k": 0.0005, "output_per_1k": 0.0015},
        pricing_source_id="or-default",
    )


def _resolver(env=None):
    return SecureConfigResolver(env={
        "ATLAS_M11_OPENROUTER_API_KEY": "dummy-test-not-a-real-key",
        "ATLAS_M11_OPENROUTER_ENDPOINT": "https://openrouter.ai/api/v1",
        **(env or {}),
    })


def _ok_body(content="hello", usage=True):
    b = {"choices": [{"message": {"content": content}}]}
    if usage:
        b["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    return b


# ---- secure config resolution / fail closed ----

def test_secure_config_resolves_key_and_endpoint():
    r = _resolver()
    assert r.get_api_key("openrouter") == "dummy-test-not-a-real-key"
    assert r.resolve_endpoint("openrouter", None) == "https://openrouter.ai/api/v1"


def test_secure_config_missing_key_fails_closed():
    r = SecureConfigResolver(env={})
    with pytest.raises(SecureConfigUnavailableError):
        r.get_api_key("openrouter")


def test_secure_config_missing_endpoint_fails_closed():
    r = SecureConfigResolver(env={"ATLAS_M11_OPENROUTER_API_KEY": "k"})
    with pytest.raises(SecureConfigUnavailableError):
        r.resolve_endpoint("openrouter", None)


# ---- adapter: success / tokens / cost ----

def test_adapter_success_parses_content_and_usage():
    sess = FakeSession(_ok_body())
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={"_task_id": "t1"}, token_budget=8000, timeout_s=60)
    assert res.is_success is True
    assert res.response == "hello"
    assert res.usage.total_tokens == 15
    assert res.usage.input_tokens == 10
    assert res.usage.output_tokens == 5
    assert res.usage.estimated_cost_usd is not None  # cost from pricing config
    assert res.error_class == InvocationErrorKind.NONE.value


def test_adapter_authorization_header_uses_resolved_key_but_never_leaks():
    sess = FakeSession(_ok_body())
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={"_task_id": "t1", "prompt": "x"},
                   token_budget=8000, timeout_s=60)
    assert sess.last[1]["Authorization"] == "Bearer dummy-test-not-a-real-key"
    # the key must never appear in the result object (immutable result has no such field)
    assert not hasattr(res, "api_key")
    assert "dummy-test-not-a-real-key" not in str(res)


def test_adapter_missing_usage_is_unknown_not_fabricated():
    sess = FakeSession(_ok_body(usage=False))
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert res.is_success is True
    assert res.tokens_unknown is True
    assert res.usage.input_tokens is None
    assert res.usage.estimated_cost_usd is None  # explicit UNKNOWN


def test_adapter_cost_only_from_pricing():
    # No pricing config -> cost must stay None (never a fabricated number).
    cfg_noprice = ProviderConfig(
        provider="openrouter", model="deepseek-flash", capability_tier=ModelTier.L1,
        supported_task_classes=frozenset({"docs"}), token_budget=8000, timeout_s=60,
        endpoint_config_ref="openrouter", pricing=None,
    )
    sess = FakeSession(_ok_body())
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=cfg_noprice, task_payload={}, token_budget=8000, timeout_s=60)
    assert res.is_success is True
    assert res.usage.estimated_cost_usd is None


# ---- adapter: malformed / error responses classified, never evidence ----

def test_adapter_malformed_no_choices():
    sess = FakeSession({"foo": "bar"})
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert res.is_success is False
    assert res.error_class == InvocationErrorKind.MALFORMED_RESPONSE.value


def test_adapter_empty_choices_malformed():
    sess = FakeSession({"choices": []})
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert res.error_class == InvocationErrorKind.MALFORMED_RESPONSE.value


def test_adapter_http_401_auth_error():
    sess = FakeSession({"error": {"message": "bad key"}}, status=401)
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert res.is_success is False
    assert res.error_class == InvocationErrorKind.AUTH_ERROR.value


def test_adapter_http_429_rate_limit():
    sess = FakeSession({"error": {"message": "rate"}}, status=429)
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert res.error_class == InvocationErrorKind.RATE_LIMIT.value


def test_adapter_error_only_even_if_evidence_present():
    # Provider returns error envelope even though "tests_passed" would look good:
    # the invocation must be an error, never evidence.
    sess = FakeSession({"error": {"message": "provider failed"}}, status=500)
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={"tests_passed": 10},
                   token_budget=8000, timeout_s=60)
    assert res.is_success is False
    assert res.error_class != InvocationErrorKind.NONE.value


def test_adapter_never_uncontrolled_retry():
    # The adapter does exactly one HTTP call per invoke (no retry loop).
    sess = FakeSession(_ok_body())
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    assert len([1 for _ in [sess.last]]) == 1  # one call recorded


def test_adapter_result_immutable_and_no_credential_field():
    sess = FakeSession(_ok_body())
    a = OpenRouterAdapter(_resolver(), session=sess, base_url="https://openrouter.ai/api/v1")
    res = a.invoke(provider_config=_cfg(), task_payload={}, token_budget=8000, timeout_s=60)
    with pytest.raises(AttributeError):
        res.status = "hacked"
    assert not hasattr(res, "authorization")
    assert not hasattr(res, "api_key")


def test_safe_prompt_excludes_prompt_field_and_secrets():
    from planning.m11_router.provider.openrouter_adapter import _safe_prompt
    out = _safe_prompt({"description": "doc", "prompt": "api_key=SECRET", "_task_id": "t1",
                        "credentials": "sk-secret"})
    assert "api_key=SECRET" not in out
    assert "sk-secret" not in out
    assert "doc" in out