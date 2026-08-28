"""Immutable capability selection result for the Atlas runtime boundary."""

from dataclasses import dataclass
from typing import Any

from controller.agent_capability_runtime import AgentCapabilityResolution


@dataclass(frozen=True)
class CapabilitySelection:
    """A resolved capability plus the originating request."""

    resolution: AgentCapabilityResolution

    @property
    def matched(self) -> bool:
        return self.resolution.matched

    @property
    def name(self) -> str | None:
        return None if not self.matched else self.resolution.capability.name

    @property
    def handler(self) -> Any:
        return None if not self.matched else self.resolution.capability.handler
