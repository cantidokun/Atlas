"""Checkpointed autonomous runtime for Atlas futures."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep
from planning.runtime_state import FutureRuntimeStateStore

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class AutonomousFutureRuntime:
    """Drive a deterministic future while checkpointing every safe transition."""

    def __init__(
        self,
        steps: List[FutureStep],
        state_store: FutureRuntimeStateStore,
        controller: Optional[FutureExecutionController] = None,
    ) -> None:
        self.state_store = state_store
        self.controller = controller or FutureExecutionController(steps)
        if controller is not None and controller.steps != steps:
            raise ValueError("Supplied controller does not match the authorized future.")
        self.steps = steps
        self._checkpoint()

    def _checkpoint(self) -> Dict[str, Any]:
        return self.state_store.save(self.controller)

    def snapshot(self) -> Dict[str, Any]:
        return self.controller.snapshot()

    def resume(self) -> "AutonomousFutureRuntime":
        controller = self.state_store.resume(self.steps)
        return AutonomousFutureRuntime(self.steps, self.state_store, controller=controller)

    def run_until_pause(
        self,
        execute: ToolExecutor,
        acknowledgements: Optional[Dict[str, Dict[str, Any]]] = None,
        verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Advance automatically until completion, failure, or missing external input."""
        acknowledgements = acknowledgements or {}
        verifications = verifications or {}

        while True:
            step = self.controller.current_step
            if step is None:
                return self._checkpoint()["snapshot"]

            if step.phase == "ACTION":
                self.controller.execute_current(execute)
                self._checkpoint()
                if self.controller.blocked:
                    return self.controller.snapshot()
                continue

            if step.phase == "VERIFICATION":
                if step.step_id not in verifications:
                    return self._checkpoint()["snapshot"]
                self.controller.verify(verifications[step.step_id])
                self._checkpoint()
                if self.controller.blocked:
                    return self.controller.snapshot()
                continue

            if step.phase == "COMPLETE":
                result = self.controller.finalize()
                self._checkpoint()
                return result

            if step.step_id not in acknowledgements:
                return self._checkpoint()["snapshot"]
            self.controller.acknowledge(acknowledgements[step.step_id])
            self._checkpoint()

    @classmethod
    def resume_and_run(
        cls,
        steps: List[FutureStep],
        state_store: FutureRuntimeStateStore,
        execute: ToolExecutor,
        acknowledgements: Optional[Dict[str, Dict[str, Any]]] = None,
        verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        runtime = cls(steps, state_store).resume()
        return runtime.run_until_pause(execute, acknowledgements, verifications)
