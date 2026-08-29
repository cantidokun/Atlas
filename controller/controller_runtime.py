"""Deterministic execution gate for the current authorized midpoint task."""

from copy import deepcopy
from typing import Any, Callable, Dict, Optional

from planning.blender_result_contract import normalize_blender_result

from .controller_state import ControllerState, record_after, record_before, record_write
from .controller_checkpoint import snapshot_controller_state, restore_controller_state

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]
_FAILURE_STATUSES = {"error", "failed", "failure"}


class ControllerRuntime:
    """Run the authorized midpoint workflow without delegating sequencing to Qwen."""

    def __init__(self, file_name: str):
        self.state = ControllerState(file_name=file_name, object_a_name="Goal_Left_post", object_b_name="Goal_Right_Post")

    @classmethod
    def from_checkpoint(cls, payload: Dict[str, Any], fresh_evidence: Optional[Dict[str, Any]] = None) -> "ControllerRuntime":
        """Restore controller history; optional evidence is reconciled, never trusted historically."""
        state = restore_controller_state(payload)
        state.after = None
        runtime = cls(state.file_name)
        runtime.state = state
        if fresh_evidence is not None:
            if not isinstance(fresh_evidence, dict):
                raise ValueError("Fresh Blender evidence must be an object.")
            if fresh_evidence.get("error") or fresh_evidence.get("status") in _FAILURE_STATUSES or fresh_evidence.get("ok") is False:
                raise ValueError("Fresh Blender evidence is unavailable.")
            if state.writes:
                record_after(state, deepcopy(fresh_evidence))
        return runtime

    def checkpoint(self) -> Dict[str, Any]:
        return snapshot_controller_state(self.state)

    def step(self, execute: ToolExecutor) -> Dict[str, Any]:
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
        try:
            normalized = normalize_blender_result(action["tool"], result)
        except (TypeError, ValueError) as exc:
            return self._error(type(exc).__name__, str(exc))

        if not normalized.ok:
            return self._error("ToolExecutionError", normalized.details)

        # Preserve the existing controller state/result shape while accepting
        # the canonical {ok, state, details} contract as the preferred form.
        result_state = normalized.state
        if isinstance(result_state, dict):
            controller_result = deepcopy(result_state)
            if not controller_result:
                controller_result = deepcopy(dict(normalized.details))
        else:
            controller_result = deepcopy(dict(normalized.details))
            controller_result.setdefault("status", result_state)

        try:
            if action["kind"] == "evidence":
                record_before(self.state, controller_result)
            elif action["kind"] == "write":
                if result_state != "moved" and controller_result.get("status") != "moved":
                    return self._error("InvalidWriteResult", result)
                record_write(
                    self.state,
                    action["arguments"]["object_name"],
                    action["arguments"]["location"],
                    controller_result,
                )
            elif action["kind"] == "verification":
                record_after(self.state, controller_result)
        except (TypeError, ValueError, KeyError) as exc:
            return self._error(type(exc).__name__, str(exc))
        return {"status": "complete" if self.state.complete else "progress", "phase": self.state.phase, "next_action": deepcopy(self._next_action())}

    def _error(self, error_type: str, message: Any) -> Dict[str, Any]:
        return {"status": "error", "phase": self.state.phase, "error": {"type": error_type, "message": deepcopy(message)}}

    def _next_action(self) -> Dict[str, Any]:
        from .controller_state import next_required_action
        return next_required_action(self.state)
