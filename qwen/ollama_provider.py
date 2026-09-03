"""Proposal-only Ollama provider for Atlas soccer-production workflows.

The provider boundary can ask a local Qwen model for a semantic production
proposal, but it exposes no Atlas executor, authorization, persistence, or
recovery capability to the model. The returned text is always routed through
the strict provider-output parser before leaving this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol

import requests

from qwen.production_proposal import QwenProductionProposal
from qwen.provider_output import parse_qwen_production_output
from qwen.structured_plan import PRODUCTION_PROPOSAL_JSON_SCHEMA

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_QWEN_MODEL = "qwen3:8b"


class QwenProviderError(RuntimeError):
    """Raised when the provider cannot return a valid Qwen proposal."""


class HttpSession(Protocol):
    """Minimal requests-compatible interface used for deterministic testing."""

    def post(self, url: str, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class OllamaQwenProvider:
    """Call Ollama for proposal-only Qwen output."""

    url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_QWEN_MODEL
    timeout: float = 120.0
    session: Optional[HttpSession] = None

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("Ollama provider URL must be a non-empty string.")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Qwen model name must be a non-empty string.")
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)):
            raise ValueError("Ollama provider timeout must be numeric.")
        if self.timeout <= 0:
            raise ValueError("Ollama provider timeout must be positive.")

    def _session(self) -> HttpSession:
        return self.session if self.session is not None else requests

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the proposal layer for Atlas, an AI-assisted soccer-production system.\n"
            "Produce semantic production intent only.\n"
            "You do not have access to Blender, Unreal, files, executors, tools, authorization, "
            "persistence, scheduling, or recovery.\n"
            "Return exactly one JSON object matching the supplied schema.\n"
            "Choose only a workflow that Atlas can validate against its trusted catalog.\n"
            "Do not emit actions, tool calls, executor names, authorization requests, file writes, "
            "or recovery instructions.\n"
        )

    def propose(
        self,
        objective: str,
        *,
        context: Optional[str] = None,
        messages: Optional[List[Mapping[str, str]]] = None,
    ) -> QwenProductionProposal:
        """Request one proposal and return only the validated semantic proposal."""
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Qwen production objective must be a non-empty string.")
        if context is not None and not isinstance(context, str):
            raise ValueError("Qwen production context must be a string when provided.")
        if messages is not None:
            if not isinstance(messages, list) or any(
                not isinstance(message, Mapping)
                or set(message) != {"role", "content"}
                or not isinstance(message["role"], str)
                or not isinstance(message["content"], str)
                for message in messages
            ):
                raise ValueError("Qwen provider messages must contain only role and content strings.")
            request_messages: List[Dict[str, str]] = [
                {"role": str(message["role"]), "content": str(message["content"])}
                for message in messages
            ]
            if not request_messages or request_messages[0]["role"] != "system":
                request_messages.insert(0, {"role": "system", "content": self._system_prompt()})
            request_messages.append({"role": "user", "content": objective})
        else:
            user_content = objective
            if context:
                user_content = f"{objective}\n\nVerified context:\n{context}"
            request_messages = [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_content},
            ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": request_messages,
            "stream": False,
            "format": PRODUCTION_PROPOSAL_JSON_SCHEMA,
            "options": {"temperature": 0},
        }

        try:
            response = self._session().post(
                self.url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_body = response.json()
        except (requests.RequestException, ValueError, TypeError) as exc:
            raise QwenProviderError(f"Ollama Qwen request failed: {exc}") from exc

        if not isinstance(response_body, dict):
            raise QwenProviderError("Ollama Qwen response must be a JSON object.")
        message = response_body.get("message")
        if not isinstance(message, dict):
            raise QwenProviderError("Ollama Qwen response is missing a message object.")
        content = message.get("content")
        if not isinstance(content, (str, bytes, bytearray, dict)):
            raise QwenProviderError("Ollama Qwen response message is missing proposal content.")

        try:
            return parse_qwen_production_output(content)
        except (TypeError, ValueError) as exc:
            raise QwenProviderError(f"Ollama Qwen returned an invalid production proposal: {exc}") from exc


__all__ = [
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_QWEN_MODEL",
    "OllamaQwenProvider",
    "QwenProviderError",
]
