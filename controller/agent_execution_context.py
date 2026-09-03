
"""Trusted execution context owned by the Atlas host.

This object carries explicitly installed trusted provider contexts for one
agent execution. It does not create authorization and does not accept model
output as a source of trusted state.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from controller.agent_controller_intent import AgentControllerIntent
from controller.agent_trusted_context import AgentTrustedContext
from controller.trusted_unreal_context import TrustedUnrealContext


@dataclass
class AgentExecutionContext:
    """Mutable host-owned registry of trusted contexts for one agent run."""

    _contexts: dict[str, AgentTrustedContext] = field(default_factory=dict)

    def install_unreal(
        self,
        context: TrustedUnrealContext,
    ) -> None:
        """Install trusted Unreal context supplied by the host."""
        if not isinstance(context, TrustedUnrealContext):
            raise TypeError(
                "context must be a TrustedUnrealContext instance"
            )

        self._contexts["unreal"] = context.to_trusted_agent_context()

    def install(
        self,
        provider: str,
        context: AgentTrustedContext,
    ) -> None:
        """Install a provider-neutral trusted context."""
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(
                "provider must be a non-empty string"
            )

        if not isinstance(context, AgentTrustedContext):
            raise TypeError(
                "context must be an AgentTrustedContext instance"
            )

        self._contexts[provider.strip().lower()] = context

    def get(
        self,
        provider: Optional[str],
    ) -> Optional[AgentTrustedContext]:
        if provider is None:
            return None

        if not isinstance(provider, str):
            raise TypeError("provider must be a string or None")

        return self._contexts.get(provider.strip().lower())

    def context_for_request(
        self,
        provider: Optional[str],
    ) -> Mapping[str, Any]:
        context = self.get(provider)
        if context is None:
            return {}

        return context.to_request_context()

    def context_for_controller_intent(
        self,
        intent: AgentControllerIntent,
    ) -> AgentTrustedContext:
        """Resolve trusted context from the parsed model request's provider.

        The provider is used only to select an already-installed trusted
        context. The model-declared capability, intent metadata, and context
        values never select or create trusted state.
        """
        if not isinstance(intent, AgentControllerIntent):
            raise TypeError(
                "intent must be an AgentControllerIntent instance"
            )

        context = self.get(intent.provider)
        if context is None:
            return AgentTrustedContext.empty()

        return context

    def has(self, provider: str) -> bool:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(
                "provider must be a non-empty string"
            )

        return provider.strip().lower() in self._contexts
