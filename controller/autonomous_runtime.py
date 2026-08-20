"""Autonomous model-to-machine controller runtime.

The controller owns the communication loop between an LLM and a local tool
executor. The LLM proposes; Python validates, authorizes, executes, records,
and decides whether another model turn is required.

This module is deliberately independent of Blender, Unreal, or any other
production environment. Those systems enter through the ToolExecutor
boundary.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set


ModelCall = Callable[[List[Dict[str, Any]]], "ModelTurn"]
ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class ToolCall:
    """One model-proposed tool invocation."""

    name: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass(frozen=True)
class ModelTurn:
    """Normalized model output consumed by the controller."""

    tool_calls: Sequence[ToolCall] = field(default_factory=tuple)
    content: str = ""
    done: bool = False


@dataclass(frozen=True)
class ControllerPolicy:
    """Hard execution limits owned by Python, not by the model."""

    read_only_tools: Set[str]
    write_tools: Set[str]
    authorized_write_tools: Set[str] = field(default_factory=set)
    max_turns: int = 32
    max_tool_calls_per_turn: int = 1
    max_identical_tool_calls: int = 2

    @property
    def allowed_tools(self) -> Set[str]:
        return self.read_only_tools | self.write_tools

    def validate(self) -> None:
        if self.max_turns < 1:
            raise ValueError("max_turns must be positive")
        if self.max_tool_calls_per_turn != 1:
            raise ValueError("Atlas currently permits exactly one tool call per turn")
        if self.max_identical_tool_calls < 1:
            raise ValueError("max_identical_tool_calls must be positive")
        if self.read_only_tools.intersection(self.write_tools):
            raise ValueError("a tool cannot be both read-only and write-enabled")
        if not self.authorized_write_tools.issubset(self.write_tools):
            raise ValueError("authorized write tools must be declared write tools")


@dataclass
class ControllerResult:
    """Terminal state returned by the autonomous controller."""

    status: str
    reason: str
    turns: int
    messages: List[Dict[str, Any]]
    tool_history: List[Dict[str, Any]]
    final_content: str = ""


class AutonomousController:
    """Run the model/tool loop without a human selecting intermediate steps."""

    def __init__(self, policy: ControllerPolicy):
        policy.validate()
        self.policy = policy

    def run(
        self,
        initial_messages: List[Dict[str, Any]],
        ask_model: ModelCall,
        execute_tool: ToolExecutor,
    ) -> ControllerResult:
        messages = list(initial_messages)
        tool_history: List[Dict[str, Any]] = []
        identical_calls: Dict[str, int] = {}

        for turn_number in range(1, self.policy.max_turns + 1):
            try:
                model_turn = ask_model(messages)
            except Exception as exc:
                detail = str(exc).strip()
                reason = "model_call_failed: " + type(exc).__name__
                if detail:
                    reason += ":" + detail
                return self._blocked(
                    reason,
                    turn_number,
                    messages,
                    tool_history,
                )

            if not isinstance(model_turn, ModelTurn):
                return self._blocked(
                    "malformed_model_turn",
                    turn_number,
                    messages,
                    tool_history,
                )

            if len(model_turn.tool_calls) > self.policy.max_tool_calls_per_turn:
                return self._blocked(
                    "multiple_tool_calls_not_permitted",
                    turn_number,
                    messages,
                    tool_history,
                )

            if not model_turn.tool_calls:
                if model_turn.done or model_turn.content:
                    messages.append({
                        "role": "assistant",
                        "content": model_turn.content,
                    })
                    return ControllerResult(
                        status="complete",
                        reason="model_completed",
                        turns=turn_number,
                        messages=messages,
                        tool_history=tool_history,
                        final_content=model_turn.content,
                    )

                return self._blocked(
                    "empty_model_turn",
                    turn_number,
                    messages,
                    tool_history,
                )

            call = model_turn.tool_calls[0]
            validation_error = self._validate_tool_call(call)
            if validation_error is not None:
                return self._blocked(
                    validation_error,
                    turn_number,
                    messages,
                    tool_history,
                )

            call_key = self._call_key(call)
            identical_calls[call_key] = identical_calls.get(call_key, 0) + 1
            if identical_calls[call_key] > self.policy.max_identical_tool_calls:
                return self._blocked(
                    "repeated_identical_tool_call",
                    turn_number,
                    messages,
                    tool_history,
                )

            try:
                result = execute_tool(call.name, dict(call.arguments))
            except Exception as exc:
                detail = str(exc).strip()
                reason = "tool_execution_failed: " + type(exc).__name__
                if detail:
                    reason += ":" + detail
                return self._blocked(
                    reason,
                    turn_number,
                    messages,
                    tool_history,
                )

            if not isinstance(result, dict):
                return self._blocked(
                    "malformed_tool_result",
                    turn_number,
                    messages,
                    tool_history,
                )

            tool_history.append({
                "tool": call.name,
                "arguments": dict(call.arguments),
                "result": result,
                "call_id": call.call_id,
            })
            messages.append({
                "role": "assistant",
                "tool_calls": [{
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": dict(call.arguments),
                    },
                }],
            })
            messages.append({
                "role": "tool",
                "content": result,
                "tool_call_id": call.call_id,
            })

        return self._blocked(
            "turn_budget_exhausted",
            self.policy.max_turns,
            messages,
            tool_history,
        )

    def _validate_tool_call(self, call: ToolCall) -> Optional[str]:
        if not isinstance(call.name, str) or not call.name:
            return "invalid_tool_name"
        if call.name not in self.policy.allowed_tools:
            return "tool_not_authorized"
        if not isinstance(call.arguments, dict):
            return "invalid_tool_arguments"
        if call.name in self.policy.write_tools and call.name not in self.policy.authorized_write_tools:
            return "write_not_authorized"
        return None

    @staticmethod
    def _call_key(call: ToolCall) -> str:
        return call.name + "|" + repr(sorted(call.arguments.items()))

    @staticmethod
    def _blocked(
        reason: str,
        turns: int,
        messages: List[Dict[str, Any]],
        tool_history: List[Dict[str, Any]],
    ) -> ControllerResult:
        return ControllerResult(
            status="blocked",
            reason=reason,
            turns=turns,
            messages=messages,
            tool_history=tool_history,
        )
