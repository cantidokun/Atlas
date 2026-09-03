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

from planning.soccer_production_catalog import available_soccer_production_workflows
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
        workflows = available_soccer_production_workflows()
        catalog_lines = []
        for spec in workflows:
            parameters = ", ".join(
                f"{name}:{kind}" for name, kind in spec.parameter_kinds
            )
            catalog_lines.append(
                f"- {spec.name}@{spec.version}: {spec.objective} Parameters: {parameters}."
            )
        catalog = "\n".join(catalog_lines)
        return (
            "You are the proposal layer for Atlas, an AI-assisted soccer-production system.\n"
            "Produce semantic production intent only.\n"
            "You do not have access to Blender, Unreal, files, executors, tools, authorization, "
            "persistence, scheduling, or recovery.\n"
            "Return exactly one JSON object matching the supplied schema.\n"
            "The workflow value MUST be copied exactly from the canonical catalog below, including spelling and hyphens. "
            "Do not invent aliases, synonyms, or new workflow names.\n"
            "Canonical soccer-production catalog:\n"
            f"{catalog}\n"
            "Do not emit actions, tool calls, executor names, authorization requests, file writes, "
            "or recovery instructions.\n"
        )

    @staticmethod
    def _history_messages(messages: Optional[List[Mapping[str, str]]]) -> List[Dict[str, str]]:
        if messages is None:
            return []
        if not isinstance(messages, list):
            raise ValueError("Qwen provider messages must be a list.")
        normalized: List[Dict[str, str]] = []
        for message in messages:
            if not isinstance(message, Mapping) or set(message) != {"role", "content"}:
                raise ValueError("Qwen provider history messages must contain only role and content.")
            role = message["role"]
            content = message["content"]
            if role not in {"user", "assistant"}:
                raise ValueError("Qwen provider history messages may only use user or assistant roles.")
            if not isinstance(content, str):
                raise ValueError("Qwen provider history message content must be strings.")
            normalized.append({"role": role, "content": content})
        return normalized

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

        user_content = objective
        if context:
            user_content = f"{objective}\n\nVerified context:\n{context}"

        request_messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._system_prompt()},
            *self._history_messages(messages),
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
