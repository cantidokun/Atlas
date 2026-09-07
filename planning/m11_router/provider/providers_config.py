"""Provider configuration for the M11.2 router execution layer.

Implements design §8: configuration loading/validation for provider profiles.
Fails closed on malformed/incomplete/ambiguous config. Provider/model names and
pricing are configuration parameters — never hard-coded into routing logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from planning.m11_router.constants import TASK_CLASSES
from planning.m11_router.model_profile import ModelTier


class ProviderConfigError(ValueError):
    """Raised when provider configuration is missing/malformed/ambiguous (fail closed)."""


def _coerce_tier(value: Any) -> ModelTier:
    if isinstance(value, ModelTier):
        return value
    if isinstance(value, str):
        try:
            return ModelTier(value.strip().upper())
        except ValueError:
            raise ProviderConfigError(f"invalid capability tier: {value!r}")
    raise ProviderConfigError(f"invalid capability tier: {value!r}")


@dataclass(frozen=True)
class ProviderUsage:
    """Immutable token/cost observation from a provider response."""
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    pricing_source: Optional[str] = None

    @property
    def usage_unknown(self) -> bool:
        return self.input_tokens is None and self.output_tokens is None and self.total_tokens is None


@dataclass(frozen=True)
class ProviderConfig:
    """A validated provider execution profile (design §1, §8)."""

    provider: str
    model: str
    capability_tier: ModelTier
    supported_task_classes: frozenset[str]
    token_budget: int
    timeout_s: int
    endpoint: Optional[str] = None
    endpoint_config_ref: Optional[str] = None  # config-relative reference, never a secret
    pricing: Optional[Dict[str, Any]] = None
    pricing_source_id: Optional[str] = None

    def __post_init__(self) -> None:
        for f in ("provider", "model"):
            if not getattr(self, f) or not str(getattr(self, f)).strip():
                raise ProviderConfigError(f"{f} must be a non-empty string")
        if not isinstance(self.capability_tier, ModelTier):
            object.__setattr__(self, "capability_tier", _coerce_tier(self.capability_tier))
        if not isinstance(self.supported_task_classes, (set, frozenset, tuple, list)) or not len(self.supported_task_classes):
            raise ProviderConfigError("supported_task_classes must be non-empty")
        unknown = set(self.supported_task_classes) - set(TASK_CLASSES)
        if unknown:
            raise ProviderConfigError(f"unsupported task classes: {sorted(unknown)}")
        if isinstance(self.token_budget, bool) or not isinstance(self.token_budget, int) or self.token_budget <= 0:
            raise ProviderConfigError("token_budget must be a positive integer")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, int) or self.timeout_s <= 0:
            raise ProviderConfigError("timeout_s must be a positive integer")

    # a convenience accessor aligned with ModelProfile naming
    @property
    def model_id(self) -> str:
        return self.model


def _from_mapping(raw: Mapping[str, Any]) -> ProviderConfig:
    if not isinstance(raw, dict):
        raise ProviderConfigError("provider profile must be an object")
    for req in ("provider", "model", "capability_tier", "supported_task_classes", "token_budget", "timeout_s"):
        if req not in raw or raw[req] is None:
            raise ProviderConfigError(f"provider.{req} is required")
    endpoint = raw.get("endpoint")
    endpoint_ref = raw.get("endpoint_config_ref") or raw.get("endpoint_ref")
    return ProviderConfig(
        provider=_coerce_string(raw["provider"], "provider"),
        model=_coerce_string(raw["model"], "model"),
        capability_tier=_coerce_tier(raw["capability_tier"]),
        supported_task_classes=_coerce_task_classes(raw["supported_task_classes"]),
        token_budget=_coerce_int(raw["token_budget"], "token_budget"),
        timeout_s=_coerce_int(raw["timeout_s"], "timeout_s"),
        endpoint=endpoint,
        endpoint_config_ref=endpoint_ref,
        pricing=dict(raw.get("pricing")) if isinstance(raw.get("pricing"), dict) else _coerce_pricing(raw.get("pricing")),
        pricing_source_id=raw.get("pricing_source_id"),
    )


def _coerce_task_classes(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", " ").split() if p.strip()]
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = [v.strip() if isinstance(v, str) and v.strip() else "" for v in value]
    else:
        raise ProviderConfigError(f"unsupported supported_task_classes: {value!r}")
    parts = [p for p in parts if p]
    if not parts:
        raise ProviderConfigError("supported_task_classes must be non-empty")
    return frozenset(parts)


def _coerce_pricing(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    raise ProviderConfigError("pricing must be an object (or absent)")




def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProviderConfigError(f"{field_name} must be a positive integer")
    return value


def _coerce_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderConfigError(f"{field_name} must be a non-empty string")
    return value.strip()

def load_provider_configs(raw: Any) -> List[ProviderConfig]:
    """Load and validate a collection of provider profiles.

    ``raw`` may be a list, or a dict with a ``providers`` key. Fails closed on
    the first invalid profile (nothing partially loaded). Provider/model/pricing
    names are deployment configuration parameters.
    """
    if raw is None:
        raise ProviderConfigError("no provider configuration provided")
    if isinstance(raw, dict) and "providers" in raw:
        items = raw["providers"]
    elif isinstance(raw, dict) and "provider" in raw:
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = raw
    else:
        raise ProviderConfigError(f"unsupported provider configuration shape: {type(raw).__name__}")
    if not items:
        raise ProviderConfigError("no provider profiles configured")
    return [_from_mapping(item) for item in items]

def extract_usage(raw_response: Any) -> ProviderUsage:
    """Extract token usage from a structured provider response.

    Supports common ``usage`` shapes: {"input_tokens", "output_tokens",
    "total_tokens"}, {"prompt_tokens", "completion_tokens", "total_tokens"},
    and deep-nested {"usage": {...}}. Missing usage stays ``None`` (UNKNOWN);
    we never fabricate token counts.
    """
    if not isinstance(raw_response, dict):
        return ProviderUsage()
    usage = raw_response.get("usage")
    if not isinstance(usage, dict):
        usage = raw_response  # flat fallback
    in_tok = _pick(usage, "input_tokens", "prompt_tokens")
    out_tok = _pick(usage, "output_tokens", "completion_tokens")
    total = _pick(usage, "total_tokens")
    if total is None and in_tok is not None and out_tok is not None:
        total = in_tok + out_tok
    return ProviderUsage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=total,
    )


def _pick(mapping: Mapping[str, Any], *keys: str) -> Optional[int]:
    for k in keys:
        v = mapping.get(k)
        if isinstance(v, bool) or not isinstance(v, int):
            continue
        if v >= 0:
            return v
    return None


def estimate_cost(usage: ProviderUsage, pricing: Optional[Mapping[str, Any]]) -> float:
    """Estimate cost from usage + pricing config, or raise/cost-UNKNOWN.

    ``pricing`` is configuration (e.g. {"input_per_1k": 0.10, "output_per_1k": 0.30}).
    Returns an explicit float cost. If pricing or usage is missing/unknown,
    returns ``float("inf")`` is NOT used — instead we raise ``CostUnavailable``
    so callers record cost as UNKNOWN (never fabricated).

    We choose to surface UNKNOWN explicitly rather than fabricate a number. The
    design requires cost metadata to be configuration-driven and missing usage
    or pricing to remain explicitly UNKNOWN.
    """
    if usage is None or pricing is None:
        raise CostUnavailable("no usage or pricing config")
    per_in = pricing.get("input_per_1k")
    per_out = pricing.get("output_per_1k")
    if per_in is None or per_out is None:
        raise CostUnavailable("incomplete pricing config (missing input/output per 1k)")
    if usage.input_tokens is None or usage.output_tokens is None:
        raise CostUnavailable("usage missing input/output tokens; cost UNKNOWN")
    cost = usage.input_tokens / 1000.0 * per_in + usage.output_tokens / 1000.0 * per_out
    return round(cost, 6)


class CostUnavailable(RuntimeError):
    """Raised when cost cannot be determined (pricing/usage unknown)."""


def try_estimate_cost(usage: ProviderUsage, pricing: Optional[Mapping[str, Any]]) -> Optional[float]:
    """Best-effort cost estimate; returns None (explicit UNKNOWN) when not possible."""
    try:
        return estimate_cost(usage, pricing)
    except CostUnavailable:
        return None
