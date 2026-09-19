"""Fail-closed registry for commands exposed through the controller boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


class CommandRegistryError(ValueError):
    """Raised when a controller command violates the capability contract."""


@dataclass(frozen=True)
class CommandCapability:
    """Declarative metadata for one controller-facing command."""

    name: str
    capability: str
    mutates_state: bool = False


class ControllerCommandRegistry:
    """Allow only explicitly registered controller commands.

    The registry is deliberately declarative: authorization and execution stay
    outside this module. Unknown commands fail closed instead of reaching the
    host command handler by accident.
    """

    def __init__(self, capabilities: Iterable[CommandCapability] = ()):
        self._capabilities: Dict[str, CommandCapability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: CommandCapability) -> None:
        if not isinstance(capability, CommandCapability):
            raise CommandRegistryError("capability must be a CommandCapability")
        if not capability.name:
            raise CommandRegistryError("command name must be non-empty")
        if not capability.capability:
            raise CommandRegistryError("capability name must be non-empty")
        if capability.name in self._capabilities:
            raise CommandRegistryError(f"command already registered: {capability.name}")
        self._capabilities[capability.name] = capability

    def resolve(self, command: str) -> CommandCapability:
        capability = self._capabilities.get(command)
        if capability is None:
            raise CommandRegistryError(f"command is not registered: {command}")
        return capability

    def contains(self, command: str) -> bool:
        return command in self._capabilities

    def get(self, command: str) -> Optional[CommandCapability]:
        return self._capabilities.get(command)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))
