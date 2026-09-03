
"""Trusted in-process context for agent controller execution.

This module does not authorize capabilities and does not create provider
authorization artifacts. It only carries trusted values that were supplied
by an already-authorized host and exposes them as request context.

Model output is never a source for trusted context.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class AgentTrustedContext:
    """Immutable container for host-supplied controller context."""

    _values: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self._values, Mapping):
            raise TypeError("values must be a mapping")

        normalized = {}
        for key, value in self._values.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "trusted context keys must be non-empty strings"
                )
            normalized[key] = value

        object.__setattr__(
            self,
            "_values",
            MappingProxyType(normalized),
        )

    @classmethod
    def empty(cls) -> "AgentTrustedContext":
        return cls({})

    @classmethod
    def from_values(
        cls,
        values: Mapping[str, Any],
    ) -> "AgentTrustedContext":
        return cls(values)

    def get(
        self,
        key: str,
        default: Optional[Any] = None,
    ) -> Any:
        return self._values.get(key, default)

    def contains(self, key: str) -> bool:
        return key in self._values

    def to_request_context(self) -> dict[str, Any]:
        return dict(self._values)
