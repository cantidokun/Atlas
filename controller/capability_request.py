"""Provider-neutral capability requests for the Atlas agent boundary.

The request layer identifies an intended capability without granting execution
authority. Concrete capability implementations validate and enforce their own
authorization contracts downstream.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class CapabilityRequest:
    """A normalized request for a named controller capability."""

    capability: str
    provider: Optional[str]
    context: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be a non-empty string")
        if self.provider is not None and (
            not isinstance(self.provider, str) or not self.provider.strip()
        ):
            raise ValueError("provider must be a non-empty string when supplied")

    @property
    def normalized_capability(self) -> str:
        return self.capability.strip().lower()

    @property
    def normalized_provider(self) -> Optional[str]:
        return self.provider.strip().lower() if self.provider else None
