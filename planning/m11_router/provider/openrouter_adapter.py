"""Real OpenRouter provider adapter for the M11.3 router.

Lives strictly behind the vendor-agnostic ``ProviderAdapter`` Protocol
(M11.2). Provider-specific response parsing is confined here and does NOT leak
into router/risk/escalation logic.

Security:
- API key / Authorization header come from a ``SecureConfigResolver`` at call
  time; they are NEVER stored in source, telemetry, benchmarks, logs, PRs, or
  fixtures, and never returned inside a ``ModelResult``.
- Fail closed when credentials or endpoint config are unavailable. No silent
  fallback to another provider/model.
- Malformed provider responses are classified as invocation failures, never
  evidence.

Interface: ``OpenRouterAdapter.invoke`` conforms to ``ProviderAdapter``.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from planning.m11_router.model_profile import ModelTier
from planning.m11_router.provider.invocation import (
    InvocationErrorKind,
    ModelResult,
    ProviderAdapter,
)
from planning.m11_router.provider.providers_config import (
    ProviderConfig,
    ProviderUsage,
    extract_usage,
    try_estimate_cost,
)
from planning.m11_router.provider.secure_config import (
    OPENROUTER_DEFAULT_BASE_URL,
    SecureConfigResolver,
    SecureConfigUnavailableError,
)


class OpenRouterAdapter(ProviderAdapter):
    """Addresses the OpenAI-compatible /chat/completions shape on OpenRouter.

    ``session`` defaults to ``requests``; in deterministic tests a stubbed
    session is injected so no live API is used.
    """

    def __init__(
        self,
        resolver: Optional[SecureConfigResolver] = None,
        *,
        session=None,
        base_url: Optional[str] = None,
    ) -> None:
        self._resolver = resolver or SecureConfigResolver()
        self._session = session
        self._base_url_override = base_url

    # -- ProviderAdapter --
    def invoke(
        self,
        *,
        provider_config: ProviderConfig,
        task_payload: Dict[str, object],
        token_budget: Optional[int],
        timeout_s: Optional[int],
    ) -> ModelResult:
        start = time.monotonic()
        try:
            api_key = self._resolver.get_api_key(provider_config.endpoint_config_ref)
        except SecureConfigUnavailableError as exc:
            # Fail closed: credentials unavailable. Never a fallback.
            return _err(provider_config, task_payload, token_budget, start,
                             InvocationErrorKind.AUTH_ERROR.value, str(exc))
        try:
            endpoint = self._resolve_endpoint(provider_config)
        except SecureConfigUnavailableError as exc:
            return _err(provider_config, task_payload, token_budget, start,
                             InvocationErrorKind.REQUEST_ERROR.value, str(exc))

        body = self._build_body(provider_config, task_payload, token_budget)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        eff_timeout = timeout_s or provider_config.timeout_s or 120

        status_code, text, data = self._do_http(endpoint, headers, body, eff_timeout)
        if status_code is not None:
            return _err(provider_config, task_payload, token_budget, start,
                             _classify_status(status_code), text)

        # Response JSON present; parse it (malformed/error envelope -> failure).
        content, usage = self._parse(data)
        if content is None:
            return _err(provider_config, task_payload, token_budget, start,
                             InvocationErrorKind.MALFORMED_RESPONSE.value,
                             "OpenRouter response missing choices/message content")
        cost = try_estimate_cost(usage, provider_config.pricing)
        return ModelResult(
            task_id=str(task_payload.get("_task_id") or "t"),
            attempt_id=str(task_payload.get("_attempt_id") or "openrouter-adapter"),
            selected_tier=provider_config.capability_tier,
            provider=provider_config.provider,
            model=provider_config.model,
            requested_token_budget=token_budget,
            status="success",
            usage=ProviderUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=cost,
                pricing_source=provider_config.pricing_source_id,
            ),
            latency_ms=_ms(start),
            response=content,
            error_class=InvocationErrorKind.NONE.value,
        )

    # -- internals --
    def _resolve_endpoint(self, provider_config: ProviderConfig) -> str:
        if self._base_url_override:
            return self._base_url_override
        if provider_config.endpoint:
            return provider_config.endpoint
        # fall back to the public OpenRouter base (a non-secret URL), or the
        # resolver's configured endpoint env.
        try:
            return self._resolver.resolve_endpoint(provider_config.endpoint_config_ref, None)
        except SecureConfigUnavailableError:
            return OPENROUTER_DEFAULT_BASE_URL + "/chat/completions"

    def _build_body(self, provider_config, task_payload, token_budget) -> Dict[str, Any]:
        return {
            "model": provider_config.model,
            "messages": [{"role": "user", "content": _safe_prompt(task_payload)}],
            "max_tokens": token_budget or provider_config.token_budget,
        }

    def _do_http(self, endpoint, headers, body, timeout_s):
        """POST and return (status_code, text, json_or_None). Any transport
        failure returns a classified status (or raising is caught by caller)."""
        if self._session is not None:
            resp = self._session.post(endpoint, headers=headers, json=body, timeout=timeout_s)
            return _from_response(resp)
        import requests  # local import keeps module importable without requests present
        try:
            resp = requests.post(endpoint, headers=headers, json=body, timeout=timeout_s)
        except requests.exceptions.Timeout:
            return (1000, "OpenRouter request timed out", None)
        except Exception as exc:
            return (1001, f"OpenRouter request failed: {exc}", None)
        return _from_response(resp)

    def _parse(self, data: Any):
        """Parse a chat-completions JSON body into (content, usage) or a
        MALFORMED_RESPONSE ModelResult."""
        if not isinstance(data, dict):
            return None, None
        if data.get("error") is not None:
            return None, None
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return None, None
        first = choices[0]
        content = ""
        if isinstance(first, dict) and isinstance(first.get("message"), dict):
            content = first["message"].get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        usage = extract_usage(data)
        return content, usage


def _from_response(resp):
    """Normalize a session/requests response into (status_code, text, json)."""
    status_code = int(getattr(resp, "status_code", 200))
    text = ""
    try:
        text = str(getattr(resp, "text", ""))[:400]
    except Exception:
        pass
    if status_code is not None and not (200 <= status_code < 300):
        return status_code, text or f"HTTP {status_code}", None
    try:
        data = resp.json()
    except Exception:
        return status_code, text or "non-json response", None
    # detect OpenRouter error envelope even at 2xx
    if isinstance(data, dict) and data.get("error") is not None:
        return 400, str(data["error"])[:400], data
    return None, "", data


def _classify_status(status_code: int) -> str:
    if status_code in (401, 403):
        return InvocationErrorKind.AUTH_ERROR.value
    if status_code == 429:
        return InvocationErrorKind.RATE_LIMIT.value
    if status_code in (1000, 1001):
        return InvocationErrorKind.TIMEOUT.value if status_code == 1000 else InvocationErrorKind.PROVIDER_UNAVAILABLE.value
    return InvocationErrorKind.REQUEST_ERROR.value


def _safe_prompt(payload: Dict[str, object]) -> str:
    """Build a plain, credential-free prompt from the structured payload."""
    keys = ("description", "objective", "tests_passed", "tests_failed",
            "build_result", "static_result", "contract_result", "diff_checks")
    lines = []
    for k in keys:
        if k in payload:
            lines.append(f"{k}: {payload[k]}")
    return "\n".join(lines) if lines else "development task"


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _err(provider_config, task_payload, token_budget, start, error_class, message) -> ModelResult:
    return ModelResult(
        task_id=str(task_payload.get("_task_id") or "t"),
        attempt_id=str(task_payload.get("_attempt_id") or "openrouter-adapter"),
        selected_tier=provider_config.capability_tier,
        provider=provider_config.provider,
        model=provider_config.model,
        requested_token_budget=token_budget,
        status="error",
        latency_ms=_ms(start),
        error_class=error_class,
        error_message=message,
    )


def _fill_latency(result, start, task_id) -> ModelResult:
    from dataclasses import replace
    return replace(result, latency_ms=_ms(start))