
"""Bridge explicit model controller requests into the generic agent runtime.

This module is intentionally provider-neutral. It recognizes only the explicit
ATLAS_CONTROLLER_REQUEST marker, parses the request, optionally enriches it
with trusted in-process context, and delegates submission to the existing
generic agent submission seam.

The model output is never treated as an authorization source.
"""

from typing import Any, Callable, Mapping, Optional

from controller.agent_controller_intent import (
    AgentControllerIntent,
    extract_agent_controller_intent,
)
from controller.agent_entrypoint_runtime import (
    AgentEntrypointExecution,
    AtlasAgentEntrypointRuntime,
)
from controller.agent_submission import submit_agent_task


TrustedContextProvider = Callable[
    [AgentControllerIntent],
    Mapping[str, Any],
]


def submit_controller_request_from_model_output(
    runtime: AtlasAgentEntrypointRuntime,
    content: str,
    *,
    trusted_context_provider: Optional[TrustedContextProvider] = None,
) -> Optional[AgentEntrypointExecution]:
    """Process one model response for an explicit controller request.

    Returns None when the model response does not contain the explicit
    ATLAS_CONTROLLER_REQUEST marker.

    Any trusted context comes from an in-process provider, never from the
    model. Trusted values take precedence over model-supplied context.
    """
    if not isinstance(runtime, AtlasAgentEntrypointRuntime):
        raise TypeError(
            "runtime must be an AtlasAgentEntrypointRuntime"
        )

    intent = extract_agent_controller_intent(content)
    if intent is None:
        return None

    context = dict(intent.context)

    if trusted_context_provider is not None:
        trusted_context = trusted_context_provider(intent)
        if not isinstance(trusted_context, Mapping):
            raise TypeError(
                "trusted_context_provider must return a mapping"
            )
        context.update(trusted_context)

    return submit_agent_task(
        runtime,
        intent.capability,
        provider=intent.provider,
        context=context,
        intent=intent.intent,
    )
