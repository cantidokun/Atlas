"""Validated model-tier configuration for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §5.2.

- A model can never declare its own capability; ``capability_floor`` and
  frozen==tier come only from validated static configuration.
- Configuration is validated at load time; unknown/malformed config fails
  closed (the profile is rejected, routing then needs human review).
- Provider/model names are deployment configuration parameters, never
  hard-coded here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Mapping

from planning.m11_router.constants import TASK_CLASSES


class ModelTier(str, Enum):
    """Frozen model tiers (design §4.3)."""

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


_TIER_ORDER = (ModelTier.L0, ModelTier.L1, ModelTier.L2, ModelTier.L3)


def tier_index(tier: ModelTier) -> int:
    """Return a monotonic index for the tier (L0=0..L3=3)."""
    return _TIER_ORDER.index(tier)


def tier_max(a: ModelTier, b: ModelTier) -> ModelTier:
    """Return the higher (more capable) of two tiers (design R5/R7)."""
    return a if tier_index(a) >= tier_index(b) else b


class ProfileLoadError(ValueError):
    """Raised when a model-tier profile is unknown/malformed (fails closed)."""


@dataclass(frozen=True)
class ModelProfile:
    """A validated model-tier profile (design §5.2, minimum required fields).

    Immutable after creation. ``cost_metadata`` is optional and is ``None`` when
    unknown. All other fields are required and validated in ``__post_init__``.
    """

    tier: ModelTier
    provider: str
    model_id: str
    capability_floor: ModelTier
    supported_task_classes: frozenset[str]
    token_budget: int
    timeout_s: int
    cost_metadata: Any = None

    def __post_init__(self) -> None:
        # Coerce tier values that may arrive as plain strings from config.
        object.__setattr__(self, "tier", _coerce_tier(self.tier))
        object.__setattr__(self, "capability_floor", _coerce_tier(self.capability_floor))
        if not self.provider or not isinstance(self.provider, str) or not self.provider.strip():
            raise ProfileLoadError("profile.provider must be a non-empty string")
        if not self.model_id or not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ProfileLoadError("profile.model_id must be a non-empty string")
        # Design §5.2: a profile must never over/under-claim relative to its tier.
        if self.capability_floor != self.tier:
            raise ProfileLoadError(
                f"profile.capability_floor ({self.capability_floor}) must equal "
                f"profile.tier ({self.tier})"
            )
        if not isinstance(self.supported_task_classes, (frozenset, set, tuple, list)) or len(
            self.supported_task_classes
        ) == 0:
            raise ProfileLoadError("profile.supported_task_classes must be non-empty")
        unknown = set(self.supported_task_classes) - set(TASK_CLASSES)
        if unknown:
            raise ProfileLoadError(
                f"unsupported task classes in profile: {sorted(unknown)}"
            )
        if isinstance(self.token_budget, bool) or not isinstance(self.token_budget, int) or self.token_budget <= 0:
            raise ProfileLoadError("profile.token_budget must be a positive integer")
        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, int) or self.timeout_s <= 0:
            raise ProfileLoadError("profile.timeout_s must be a positive integer")

    def supports_task_class(self, task_class: str) -> bool:
        return task_class in self.supported_task_classes


def _coerce_tier(value: Any) -> ModelTier:
    if isinstance(value, ModelTier):
        return value
    if isinstance(value, str):
        try:
            return ModelTier(value.strip().upper())
        except ValueError:
            raise ProfileLoadError(f"invalid tier value: {value!r}")
    raise ProfileLoadError(f"invalid tier value: {value!r}")


def _coerce_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileLoadError(f"{field_name} must be a non-empty string")
    return value.strip()


def _coerce_task_classes(value: Any) -> frozenset:
    if value is None:
        raise ProfileLoadError("supported_task_classes is required (non-empty)")
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", " ").split() if p.strip()]
    elif isinstance(value, (list, tuple, set, frozenset)):
        parts = [v.strip() if isinstance(v, str) and v.strip() else "" for v in value]
    else:
        raise ProfileLoadError(f"unsupported supported_task_classes: {value!r}")
    parts = [p for p in parts if p]
    if not parts:
        raise ProfileLoadError("supported_task_classes must be non-empty")
    return frozenset(parts)


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileLoadError(f"{field_name} must be a positive integer")
    return value


def _from_mapping(raw: dict) -> ModelProfile:
    if not isinstance(raw, dict):
        raise ProfileLoadError(f"each profile must be an object, got {type(raw).__name__}")
    for req in ("tier", "provider", "capability_floor", "supported_task_classes", "token_budget", "timeout_s"):
        if req not in raw or raw[req] is None:
            raise ProfileLoadError(f"profile.{req} is required")
    model_id = raw.get("model_id", raw.get("model"))
    if model_id is None:
        raise ProfileLoadError("profile.model_id (or profile.model) is required")
    if raw.get("timeout") is not None and "timeout_s" not in raw:
        raw = {**raw, "timeout_s": raw["timeout"]}
    return ModelProfile(
        tier=_coerce_tier(raw["tier"]),
        provider=_coerce_string(raw["provider"], "provider"),
        model_id=_coerce_string(model_id, "model_id"),
        capability_floor=_coerce_tier(raw["capability_floor"]),
        supported_task_classes=_coerce_task_classes(raw["supported_task_classes"]),
        token_budget=_coerce_int(raw["token_budget"], "token_budget"),
        timeout_s=_coerce_int(raw["timeout_s"], "timeout_s"),
        cost_metadata=raw.get("cost_metadata"),
    )


def load_profiles(raw: Any) -> List[ModelProfile]:
    """Validate and load a collection of model-tier profiles.

    ``raw`` may be a list of mappings, or a mapping containing a ``profiles``
    key. Fails closed: any single malformed profile raises ``ProfileLoadError``
    (nothing is partially loaded). Returns validated, immutable profiles.
    """
    if raw is None:
        raise ProfileLoadError("no model profile configuration provided")
    if isinstance(raw, dict):
        items = raw.get("profiles") if "profiles" in raw else [raw]
    elif isinstance(raw, (list, tuple)):
        items = raw
    else:
        raise ProfileLoadError(f"unsupported configuration shape: {type(raw).__name__}")
    if not items:
        raise ProfileLoadError("no model profiles configured")
    profiles = [_from_mapping(item) for item in items]
    return profiles