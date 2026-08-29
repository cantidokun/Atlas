"""Deterministic coordinator for authorized Blender action plans.

The coordinator owns sequencing, authorization checks, verification gates, and
checkpoint callbacks. The concrete Blender executor remains injected, keeping
this layer independent of bpy, subprocesses, or transport details.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from planning.action_plan import ActionPlan


class BlenderExecutionError(RuntimeError):
    """Raised when a Blender plan cannot safely advance."""


ExecuteAction = Callable[[str, Dict[str, Any]], Dict[str, Any]]
VerifyAction = Callable[[str, Dict[str, Any], Dict[str, Any]], bool]
Checkpoint = Callable[[Dict[str, Any]], None]


@dataclass(frozen=True)
class BlenderExecutionStep:
    """One isolated, observable coordinator outcome."""

    index: int
    tool: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    verified: bool
    complete: bool


class BlenderExecutionCoordinator:
    """Advance exactly one authorized Blender action at a time."""

    def __init__(
        self,
        plan: ActionPlan,
        execute: ExecuteAction,
        verify: Optional[VerifyAction] = None,
        checkpoint: Optional[Checkpoint] = None,
    ):
        self.plan = plan
        self._execute = execute
        self._verify = verify
        self._checkpoint = checkpoint

    @staticmethod
    def _execution_succeeded(result: Dict[str, Any]) -> bool:
        """Interpret both current and legacy Blender result success contracts."""
        if "ok" in result:
            return result["ok"] is True
        return "error" not in result and result.get("status") not in {"error", "failed", "failure"}

    def step(self) -> BlenderExecutionStep:
        if self.plan.blocked:
            raise BlenderExecutionError("Blender plan is blocked by a previous failure.")
        if self.plan.complete:
            raise BlenderExecutionError("Blender plan is already complete.")
        if not self.plan.authorized:
            raise BlenderExecutionError("Blender execution requires valid authorization.")

        action = self.plan.next_action
        assert action is not None
        index = self.plan.current_index

        result = self._execute(action.tool, deepcopy(action.arguments))
        if not isinstance(result, dict):
            raise BlenderExecutionError("Blender executor must return an object.")

        execution_success = self._execution_succeeded(result)
        verified = execution_success
        if execution_success and self._verify is not None:
            verified = bool(self._verify(action.tool, deepcopy(action.arguments), deepcopy(result)))

        self.plan.record_result(result, verified)

        if self._checkpoint is not None:
            self._checkpoint(self.plan.snapshot())

        return BlenderExecutionStep(
            index=index,
            tool=action.tool,
            arguments=deepcopy(action.arguments),
            result=deepcopy(result),
            verified=verified,
            complete=self.plan.complete,
        )

    def run(self) -> list[BlenderExecutionStep]:
        """Run until completion or the plan becomes blocked."""
        if self.plan.blocked:
            raise BlenderExecutionError("Blender plan is blocked by a previous failure.")
        if self.plan.complete:
            return []

        steps: list[BlenderExecutionStep] = []
        while not self.plan.complete and not self.plan.blocked:
            steps.append(self.step())
        return steps
