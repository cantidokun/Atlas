"""Bridge between the existing Atlas tool loop and ControllerRuntime.

The bridge keeps the existing agent architecture intact while giving the
controller ownership of mandatory actions for the current authorized
midpoint task. It is intentionally small so it can later be called from
agent.py's existing tool-execution boundary.
"""

from typing import Any, Dict

from controller_runtime import ControllerRuntime


class ControllerBridge:
    """Own controller state for one assessment when the task requires it."""

    def __init__(self, file_name: str):
        self.runtime = ControllerRuntime(file_name)

    @property
    def state(self):
        return self.runtime.state

    def next_action(self) -> Dict[str, Any]:
        """Return the next mandatory controller action."""
        return self.runtime._next_action()

    def is_complete(self) -> bool:
        return self.state.complete

    def requires_controller_action(self) -> bool:
        """Return whether the controller still has mandatory work."""
        return self.next_action().get("kind") != "complete"

    def execute_next(self, execute) -> Dict[str, Any]:
        """Execute exactly one controller-owned action."""
        return self.runtime.step(execute)


def controller_required_for_midpoint_task(
    task_text: str,
    evidence_ledger: list,
) -> bool:
    """Detect the narrow current midpoint workflow without changing the ledger.

    This helper is deliberately conservative. General task planning remains
    the responsibility of Qwen and the evidence planner; this only identifies
    the existing explicit midpoint workflow that already has a controller.
    """
    text = (task_text or "").lower()

    midpoint_required = "midpoint" in text and "[0.0, 0.0, 0.0]" in text
    authorized = any(
        phrase in text
        for phrase in (
            "authorized to modify",
            "authorized to execute",
            "permits the write operation",
        )
    )

    if not (midpoint_required and authorized):
        return False

    for item in reversed(evidence_ledger or []):
        if item.get("tool") != "inspect_object_relationship":
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("midpoint") == [0.0, 0.0, 0.0]:
            return False
        break

    return True
