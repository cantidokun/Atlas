"""Bounded local-model gateway for the autonomous Atlas controller.

The gateway gives the controller a hard wall-clock read timeout. A model that
gets stuck generating cannot hold the controller indefinitely. There are no
automatic retries here: a timeout is a controller-visible failure and the
controller must fail closed.
"""

from typing import Any, Dict, List, Optional

import requests

from controller.autonomous_runtime import ModelTurn, ToolCall


class ModelGatewayError(RuntimeError):
    """Raised when a model response cannot be obtained or normalized."""


class OllamaChatGateway:
    """Call an Ollama-compatible local chat endpoint with a hard timeout."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        timeout_seconds: float = 30.0,
        session: Optional[requests.Session] = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def __call__(self, messages: List[Dict[str, Any]]) -> ModelTurn:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise ModelGatewayError("model_timeout") from exc
        except requests.RequestException as exc:
            raise ModelGatewayError("model_transport_failure") from exc
        except ValueError as exc:
            raise ModelGatewayError("model_invalid_json") from exc

        return self._normalize(data)

    @staticmethod
    def _normalize(data: Dict[str, Any]) -> ModelTurn:
        if not isinstance(data, dict):
            raise ModelGatewayError("model_response_not_object")

        message = data.get("message")
        if not isinstance(message, dict):
            raise ModelGatewayError("model_message_missing")

        content = message.get("content") or ""
        if not isinstance(content, str):
            raise ModelGatewayError("model_content_invalid")

        raw_tool_calls = message.get("tool_calls") or []
        if not isinstance(raw_tool_calls, list):
            raise ModelGatewayError("model_tool_calls_invalid")

        tool_calls = []
        for raw in raw_tool_calls:
            if not isinstance(raw, dict):
                raise ModelGatewayError("model_tool_call_invalid")
            function = raw.get("function")
            if not isinstance(function, dict):
                raise ModelGatewayError("model_tool_function_missing")
            name = function.get("name")
            arguments = function.get("arguments", {})
            if not isinstance(name, str) or not name:
                raise ModelGatewayError("model_tool_name_invalid")
            if not isinstance(arguments, dict):
                raise ModelGatewayError("model_tool_arguments_invalid")
            tool_calls.append(
                ToolCall(
                    name=name,
                    arguments=arguments,
                    call_id=str(raw.get("id", "")),
                )
            )

        return ModelTurn(
            tool_calls=tuple(tool_calls),
            content=content,
            done=not tool_calls,
        )
