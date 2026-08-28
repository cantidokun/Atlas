"""Normalized request boundary between the agent process and Atlas controllers.

This module contains no execution logic. It gives the outer agent process a
stable, provider-neutral representation of an intended capability request.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AgentTaskRequest:
    """Explicit task intent presented to the Atlas controller layer."""

    capability: str
    provider: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    intent: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("provider must be a non-empty string when supplied")
        if not isinstance(self.context, dict):
            raise TypeError("context must be a dictionary")
        if self.intent is not None and not isinstance(self.intent, str):
            raise TypeError("intent must be a string when supplied")

    def routing_kwargs(self) -> Dict[str, Any]:
        """Return only the normalized fields consumed by capability routing."""
        return {
            "capability": self.capability,
            "provider": self.provider,
            "context": dict(self.context),
        }
