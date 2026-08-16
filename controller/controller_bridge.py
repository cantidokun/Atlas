"""Bridge between the existing Atlas tool loop and ControllerRuntime.

The bridge keeps the existing agent architecture intact while giving the
controller ownership of mandatory actions for the current authorized
midpoint task. It can also hydrate its BEFORE state from evidence already
collected by the main agent loop.
"""

from typing import Any, Dict

from controller_runtime import ControllerRuntime
from controller_state import record_before


class ControllerBridge:
    """Own controller state for one assessment when the task requires it."""

    def __init__(self, file_name: str):
        self.runtime = ControllerRuntime(file_name)

    @property
    def state(self):
        return self.runtime.state

    def sync_evidence(self, evidence_ledger: list) -> None:
        """Hydrate controller state from already verified agent evidence."""
        if self.state.before is not None:
            return

        for item in evidence_ledger or []:
            if item.get("tool") != "inspect_object_relationship":
                continue

            result = item.get("result")
            if not isinstance(result, dict) or "error" in result:
                continue

            object_a = result.get("object_a", {})
            object_b = result.get("object_b", {})
            if (
                object_a.get("name") == self.state.object_a_name
                and object_b.get("name") == self.state.object_b_name
            ):
                record_before(self.state, result)
                return

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

    General task planning remains the responsibility of Qwen and the evidence
    planner; this only identifies the explicit midpoint workflow that already
    has a deterministic controller.
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
