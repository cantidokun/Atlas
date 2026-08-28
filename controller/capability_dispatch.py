"""Provider-neutral dispatch for controller-owned capabilities.

The dispatcher does not execute work itself. It selects an already-registered
capability from immutable task context and leaves authorization/execution to
that capability's own boundary.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional


CapabilityPredicate = Callable[[str, Mapping[str, Any]], bool]


@dataclass(frozen=True)
class ControllerCapability:
    """One controller-owned capability with an explicit activation predicate."""

    name: str
    predicate: CapabilityPredicate
    handler: Any


class ControllerCapabilityDispatcher:
    """Select exactly one applicable controller capability without executing it."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, ControllerCapability] = {}

    def register(
        self,
        name: str,
        predicate: CapabilityPredicate,
        handler: Any,
    ) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("capability name must be a non-empty string")
        if not callable(predicate):
            raise TypeError("capability predicate must be callable")
        if name in self._capabilities:
            raise ValueError("capability is already registered")
        self._capabilities[name] = ControllerCapability(name, predicate, handler)

    def resolve(
        self,
        task_text: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Optional[ControllerCapability]:
        state = context or {}
        matches = [
            capability
            for capability in self._capabilities.values()
            if capability.predicate(task_text, state)
        ]
        if len(matches) > 1:
            names = ", ".join(item.name for item in matches)
            raise RuntimeError(f"multiple controller capabilities matched: {names}")
        return matches[0] if matches else None

    def names(self) -> tuple[str, ...]:
        return tuple(self._capabilities)
