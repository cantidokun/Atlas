"""Provider-neutral parsing for explicit agent controller intents.

This module only validates an already-decided controller intent payload.
It does not route, authorize, or execute capabilities.
"""

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Optional

from controller.agent_task_request import AgentTaskRequest


_CONTROLLER_REQUEST_PATTERN = re.compile(
    r"ATLAS_CONTROLLER_REQUEST\s*:\s*(\{[\s\S]*?\})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentControllerIntent:
    """Explicit controller intent produced by an outer agent."""

    capability: str
    provider: Optional[str]
    context: dict[str, Any]
    intent: Optional[str]

    @property
    def requested_intent(self) -> Optional[str]:
        """Model-declared intent metadata; never an authorization source."""
        return self.intent

    def to_task_request(self) -> AgentTaskRequest:
        """Convert this validated intent into the canonical task request."""
        return AgentTaskRequest(
            capability=self.capability,
            provider=self.provider,
            context=dict(self.context),
            intent=self.intent,
        )


def parse_agent_controller_intent(
    payload: Mapping[str, Any],
) -> AgentControllerIntent:
    """Validate one explicit controller intent without executing it."""
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")

    capability = payload.get("capability")
    provider = payload.get("provider")
    context = payload.get("context")
    intent = payload.get("intent")

    if not isinstance(capability, str) or not capability.strip():
        raise ValueError("capability must be a non-empty string")

    if provider is not None and (
        not isinstance(provider, str) or not provider.strip()
    ):
        raise ValueError("provider must be a non-empty string when supplied")

    if context is None:
        context = {}

    if not isinstance(context, dict):
        raise TypeError("context must be a dictionary")

    if intent is not None and not isinstance(intent, str):
        raise TypeError("intent must be a string when supplied")

    return AgentControllerIntent(
        capability=capability,
        provider=provider,
        context=dict(context),
        intent=intent,
    )


def extract_agent_controller_intent(
    content: str,
) -> Optional[AgentControllerIntent]:
    """Extract one explicit controller intent from model output.

    The marker is deliberately opt-in. Ordinary model responses, including
    existing Blender reasoning and tool calls, produce no controller intent.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")

    marker_match = re.search(
        r"ATLAS_CONTROLLER_REQUEST\s*:",
        content,
        re.IGNORECASE,
    )
    if marker_match is None:
        return None

    payload_text = content[marker_match.end():].lstrip()
    if not payload_text:
        raise ValueError(
            "ATLAS_CONTROLLER_REQUEST contains invalid JSON"
        )

    decoder = json.JSONDecoder()

    try:
        payload, _ = decoder.raw_decode(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "ATLAS_CONTROLLER_REQUEST contains invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "ATLAS_CONTROLLER_REQUEST payload must be a JSON object"
        )

    return parse_agent_controller_intent(payload)
