"""Autonomous multi-turn orchestration over the controller communication runtime.

The transport remains responsible for delivering individual commands.  This
module owns the higher-level conversation boundary: it records each model
turn, feeds the resulting output into the next model prompt, and stops on a
terminal controller state or a model failure.  No human relay is involved.

It deliberately does not choose controller actions or execute local tools;
those decisions remain inside ``ControllerCommunicationRuntime``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from controller.communication_gateway import CommunicationProtocolError
from controller.communication_runtime import ControllerCommunicationRuntime


ModelExecutor = Callable[[str, float], Any]


@dataclass(frozen=True)
class ConversationTurn:
    """Immutable record of one completed attempt to communicate with the model."""

    turn_id: str
    prompt: str
    status: str
    response: str
    error: str | None


class AutonomousCommunicationLoop:
    """Drive sequential model turns without requiring a human relay."""

    def __init__(
        self,
        runtime: ControllerCommunicationRuntime,
        session_id: str,
        *,
        model_executor: ModelExecutor,
    ) -> None:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        self._runtime = runtime
        self._session_id = session_id
        self._model_executor = model_executor
        self._turns: List[ConversationTurn] = []

    @property
    def turns(self) -> tuple[ConversationTurn, ...]:
        """Return the conversation transcript accumulated by this loop."""
        return tuple(self._turns)

    def run_turn(self, turn_id: str, prompt: str, timeout_seconds: float) -> Dict[str, Any]:
        """Run one model turn and retain its result for the next turn."""
        if any(turn.turn_id == turn_id for turn in self._turns):
            raise CommunicationProtocolError("turn_id has already been used by this loop")

        result = self._runtime.handle_command(
            self._session_id,
            f"model-run-{turn_id}",
            {
                "command": "model_run",
                "arguments": {
                    "turn_id": turn_id,
                    "message": prompt,
                    "timeout_seconds": timeout_seconds,
                },
            },
        )

        model_result = result.get("result", {})
        response = model_result.get("stdout", "")
        error = result.get("model_turn", {}).get("error")
        self._turns.append(
            ConversationTurn(
                turn_id=turn_id,
                prompt=prompt,
                status=result.get("status", "unknown"),
                response=response,
                error=error,
            )
        )
        return result

    def continue_from_last_turn(
        self,
        turn_id: str,
        instruction: str,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """Create the next model prompt from the retained conversation state."""
        if not self._turns:
            raise CommunicationProtocolError("cannot continue before the first model turn")
        previous = self._turns[-1]
        prompt = (
            "Continue the autonomous development session.\n"
            f"Previous model output:\n{previous.response}\n\n"
            f"Next instruction:\n{instruction}"
        )
        return self.run_turn(turn_id, prompt, timeout_seconds)

    def terminal(self) -> bool:
        """Whether the most recent model turn reached a terminal failure/timeout."""
        if not self._turns:
            return False
        return self._turns[-1].status in {"failed", "timed_out", "cancelled"}
