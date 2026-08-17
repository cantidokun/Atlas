"""Stable/dynamic runtime context separation for Atlas model calls."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RuntimeContext:
    """Keep cacheable instructions separate from authoritative live state."""

    stable_instructions: str
    dynamic_state: Dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.stable_instructions, str) or not self.stable_instructions.strip():
            raise ValueError("stable_instructions must be a non-empty string.")
        if not isinstance(self.dynamic_state, dict):
            raise TypeError("dynamic_state must be a dictionary.")

    def cacheable_prefix(self) -> str:
        return self.stable_instructions

    def dynamic_payload(self) -> Dict[str, Any]:
        return dict(self.dynamic_state)

    def render(self) -> Dict[str, Any]:
        """Return a request shape that preserves the stable-prefix boundary."""
        return {
            "stable_instructions": self.cacheable_prefix(),
            "dynamic_state": self.dynamic_payload(),
        }


def build_runtime_context(
    stable_instructions: str,
    *,
    observation: Optional[Dict[str, Any]] = None,
    plan_digest: Optional[str] = None,
    current_step: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> RuntimeContext:
    """Build model context without placing live state into the stable prefix."""
    dynamic: Dict[str, Any] = {}
    if observation is not None:
        dynamic["observation"] = dict(observation)
    if plan_digest is not None:
        dynamic["plan_digest"] = plan_digest
    if current_step is not None:
        dynamic["current_step"] = dict(current_step)
    if runtime_state is not None:
        dynamic["runtime_state"] = dict(runtime_state)
    return RuntimeContext(stable_instructions=stable_instructions, dynamic_state=dynamic)
