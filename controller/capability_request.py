"""Validated model-to-controller capability request envelope."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict


class CapabilityRequestError(ValueError):
    """Raised when a capability request violates the controller boundary."""


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    provider: str
    intent: str
    context: Dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise CapabilityRequestError("capability must be a non-empty string")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise CapabilityRequestError("provider must be a non-empty string")
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise CapabilityRequestError("intent must be a non-empty string")
        if not isinstance(self.context, dict):
            raise CapabilityRequestError("context must be an object")
        object.__setattr__(self, "capability", self.capability.strip())
        object.__setattr__(self, "provider", self.provider.strip())
        object.__setattr__(self, "intent", self.intent.strip())
        object.__setattr__(self, "context", deepcopy(self.context))

    @property
    def normalized_capability(self) -> str:
        return self.capability.lower()

    @property
    def normalized_provider(self) -> str:
        return self.provider.lower()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "provider": self.provider,
            "intent": self.intent,
            "context": deepcopy(self.context),
        }


__all__ = ["CapabilityRequest", "CapabilityRequestError"]
