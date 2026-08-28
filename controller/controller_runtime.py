"""Deterministic execution gate for the current authorized midpoint task."""

from copy import deepcopy
from typing import Any, Callable, Dict

from controller_state import ControllerState, record_after, record_before, record_write

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]
_FAILURE_STATUSES = {"error", "failed", "failure"}


class ControllerRuntime:
    """Run the authorized midpoint workflow without delegating sequencing to Qwen."""

    def __init__(self, file_name: str):
        self.state = ControllerState(file_name=file_name, object_a_name="Goal_Left_post", object_b_name="Goal_Right_Post")

    def step(self, execute: ToolExecutor) -> Dict[str, Any]:
        """Execute exactly the next required controller action."""
        action = deepcopy(self._next_action())
        if action["kind"] == "complete":
            return {"status": "complete", "phase": self.state.phase}

        try:
            result = execute(action["tool"], deepcopy(action["arguments"]))
        except Exception as exc:
            return self._error(type(exc).__name__, str(exc))

        if not isinstance(result, dict):
            return self._error("InvalidToolResult", "Tool result must be an object.")
        result = deepcopy(result)
        if result.get("error") or result.get("status") in _FAILURE_STATUSES:
            return self._error("ToolExecutionError", result)

        try:
            if action["kind"] == "evidence":
                record_before(self.state, result)
            elif action["kind"] == "write":
                record_write(self.state, action["arguments"]["object_name"], action["arguments"]["location"], result)
                if result.get("status") != "moved":
                    return self._error("InvalidWriteResult", result)
            elif action["kind"] == "verification":
                record_after(self.state, result)
        except (TypeError, ValueError, KeyError) as exc:
            return self._error(type(exc).__name__, str(exc))

        return {"status": "complete" if self.state.complete else "progress", "phase": self.state.phase, "next_action": deepcopy(self._next_action())}

    def _error(self, error_type: str, message: Any) -> Dict[str, Any]:
        return {"status": "error", "phase": self.state.phase, "error": {"type": error_type, "message": deepcopy(message)}}

    def _next_action(self) -> Dict[str, Any]:
        from controller_state import next_required_action
        return next_required_action(self.state)
