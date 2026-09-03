"""Trusted, host-owned context for Unreal production capability requests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict


class TrustedUnrealContextError(ValueError):
    """Raised when trusted Unreal context is invalid."""


@dataclass(frozen=True)
class TrustedUnrealContext:
    authorized_production: Any
    intent: Any
    sequence_asset_path: str

    def __post_init__(self) -> None:
        if self.authorized_production is None:
            raise TrustedUnrealContextError("authorized_production is required")
        if self.intent is None:
            raise TrustedUnrealContextError("intent is required")
        if not isinstance(self.sequence_asset_path, str) or not self.sequence_asset_path.strip():
            raise TrustedUnrealContextError("sequence_asset_path must be a non-empty string")
        object.__setattr__(self, "sequence_asset_path", self.sequence_asset_path.strip())

    def snapshot(self) -> Dict[str, Any]:
        return {
            "authorized_production": deepcopy(self.authorized_production),
            "intent": deepcopy(self.intent),
            "sequence_asset_path": self.sequence_asset_path,
        }

    def capability_context(self) -> Dict[str, Any]:
        """Return host-owned context; model-supplied context is never merged over it."""
        return {
            "production": True,
            "authorized_production": self.authorized_production,
            "intent": self.intent,
            "sequence_asset_path": self.sequence_asset_path,
        }


__all__ = ["TrustedUnrealContext", "TrustedUnrealContextError"]
