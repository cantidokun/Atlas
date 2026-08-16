"""Deterministic execution gate for the current authorized midpoint task.

This module is intentionally separate from the Qwen prompt. Qwen may reason
about the task, but once the task is in an authorized write workflow, Python
owns the execution sequence.
"""

from typing import Any, Callable, Dict

from controller_state import ControllerState, record_after, record_before, record_write


ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class ControllerRuntime:
    """Run the authorized midpoint workflow without delegating sequencing to Qwen."""

    def __init__(self, file_name: str):
        self.state = ControllerState(
            file_name=file_name,
            object_a_name="Goal_Left_post",
            object_b_name="Goal_Right_Post",
        )

    def step(self, execute: ToolExecutor) -> Dict[str, Any]:
        """Execute exactly the next required controller action."""
        action = self._next_action()

        if action["kind"] == "complete":
            return {
                "status": "complete",
                "phase": self.state.phase,
            }

        result = execute(action["tool"], action["arguments"])

        if action["kind"] == "evidence":
            if result.get("error"):
                return {
                    "status": "error",
                    "phase": self.state.phase,
                    "error": result,
                }
            record_before(self.state, result)

        elif action["kind"] == "write":
            record_write(
                self.state,
                action["arguments"]["object_name"],
                action["arguments"]["location"],
                result,
            )
            if result.get("status") != "moved":
                return {
                    "status": "error",
                    "phase": self.state.phase,
                    "error": result,
                }

        elif action["kind"] == "verification":
            if result.get("error"):
                return {
                    "status": "error",
                    "phase": self.state.phase,
                    "error": result,
                }
            record_after(self.state, result)

        return {
            "status": "complete" if self.state.complete else "progress",
            "phase": self.state.phase,
            "next_action": self._next_action(),
        }

    def _next_action(self) -> Dict[str, Any]:
        """Avoid a Qwen decision between mandatory controller phases."""
        from controller_state import next_required_action

        return next_required_action(self.state)
