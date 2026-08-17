"""Authoritative model-request assembly for Atlas runtime calls."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from planning.runtime_context import RuntimeContext, build_runtime_context


@dataclass(frozen=True)
class ModelRequest:
    """A model request with a stable cache boundary and live runtime state."""

    context: RuntimeContext
    request: Dict[str, Any]

    def render(self) -> Dict[str, Any]:
        return {
            "stable_instructions": self.context.cacheable_prefix(),
            "dynamic_state": self.context.dynamic_payload(),
            "request": dict(self.request),
        }


def build_model_request(
    stable_instructions: str,
    *,
    request: Dict[str, Any],
    observation: Optional[Dict[str, Any]] = None,
    plan_digest: Optional[str] = None,
    current_step: Optional[Dict[str, Any]] = None,
    runtime_state: Optional[Dict[str, Any]] = None,
) -> ModelRequest:
    """Assemble a model call while keeping authoritative state dynamic."""
    if not isinstance(request, dict):
        raise TypeError("request must be a dictionary.")
    context = build_runtime_context(
        stable_instructions,
        observation=observation,
        plan_digest=plan_digest,
        current_step=current_step,
        runtime_state=runtime_state,
    )
    return ModelRequest(context=context, request=dict(request))
