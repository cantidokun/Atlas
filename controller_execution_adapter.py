"""Controller-aware execution adapter.

This module is the narrow integration point between the existing Atlas agent
loop and the deterministic ControllerRuntime. It owns the controller's
mandatory actions while leaving the evidence ledger and model reasoning in the
caller.
"""

from typing import Any, Callable, Dict, List

from controller_bridge import ControllerBridge, controller_required_for_midpoint_task

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class ControllerExecutionAdapter:
    """Coordinate controller-owned actions with the existing agent state."""

    def __init__(self, file_name: str, task_text: str, evidence_ledger: List[dict]):
        self.file_name = file_name
        self.task_text = task_text
        self.evidence_ledger = evidence_ledger
        self.bridge = (
            ControllerBridge(file_name)
            if controller_required_for_midpoint_task(task_text, evidence_ledger)
            else None
        )

    @property
    def active(self) -> bool:
        return self.bridge is not None

    @property
    def complete(self) -> bool:
        return self.bridge is not None and self.bridge.is_complete()

    def refresh(self) -> None:
        """Activate the controller after the required BEFORE evidence appears."""
        if self.bridge is not None:
            return
        if controller_required_for_midpoint_task(self.task_text, self.evidence_ledger):
            self.bridge = ControllerBridge(self.file_name)

    def execute_required_step(self, execute: ToolExecutor, tool_execution_history: List[dict]) -> Dict[str, Any]:
        """Execute one mandatory controller step and mirror it into agent state."""
        self.refresh()
        if self.bridge is None:
            return {"status": "inactive"}

        action = self.bridge.next_action()
        result = self.bridge.execute_next(execute)
        tool_name = action.get("tool")
        arguments = action.get("arguments", {})
        raw = result.get("error") if result.get("status") == "error" else None

        if raw is None:
            if self.bridge.state.writes:
                raw = self.bridge.state.writes[-1]["result"]
            elif self.bridge.state.after is not None:
                raw = self.bridge.state.after
            elif self.bridge.state.before is not None:
                raw = self.bridge.state.before
            else:
                raw = result

        successful = isinstance(raw, dict) and "error" not in raw
        tool_execution_history.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": raw,
            "successful": successful,
            "controller_owned": True,
        })

        if successful:
            self.evidence_ledger.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": raw,
                "controller_owned": True,
            })

        return {
            "status": result.get("status"),
            "phase": result.get("phase"),
            "tool": tool_name,
            "arguments": arguments,
            "result": raw,
            "next_action": result.get("next_action"),
            "controller_complete": self.complete,
        }

    def should_override_model_tool(self) -> bool:
        """Return True when Python must choose the next mandatory action."""
        return self.active and not self.complete
