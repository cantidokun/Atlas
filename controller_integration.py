"""Drop-in controller integration for the Atlas agent loop.

This module keeps the live agent loop small: the caller owns the model
conversation, evidence ledger, and tool executor; this module decides whether
Python must take over a mandatory controller action.
"""

from typing import Any, Callable, Dict, List, Optional

from controller_execution_adapter import ControllerExecutionAdapter

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class AgentControllerIntegration:
    """Bridge object intended to live for one Atlas assessment."""

    def __init__(
        self,
        file_name: str,
        task_text: str,
        evidence_ledger: List[dict],
        tool_execution_history: List[dict],
    ):
        self.adapter = ControllerExecutionAdapter(
            file_name=file_name,
            task_text=task_text,
            evidence_ledger=evidence_ledger,
        )
        self.tool_execution_history = tool_execution_history

    @property
    def active(self) -> bool:
        return self.adapter.active

    @property
    def complete(self) -> bool:
        return self.adapter.complete

    def before_model_tool_execution(self) -> Optional[Dict[str, Any]]:
        """Return None when Qwen may choose a tool; otherwise return a forced action.

        The caller should execute the returned action through the same TOOLS
        registry used by the normal agent loop, then call
        ``record_controller_result``.
        """
        self.adapter.refresh()

        if not self.adapter.should_override_model_tool():
            return None

        action = self.adapter.bridge.next_action()

        if action.get("kind") == "complete":
            return {"kind": "complete"}

        return {
            "kind": action.get("kind"),
            "tool": action.get("tool"),
            "arguments": action.get("arguments", {}),
            "controller_owned": True,
        }

    def execute_forced_action(self, execute: ToolExecutor) -> Dict[str, Any]:
        """Execute exactly one controller-selected action and mirror its state."""
        return self.adapter.execute_required_step(
            execute,
            self.tool_execution_history,
        )
