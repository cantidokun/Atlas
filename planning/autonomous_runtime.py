"""Checkpointed autonomous runtime for Atlas futures."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, List, Optional

from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep
from planning.runtime_context import RuntimeContext
from planning.runtime_integrity import (
    RuntimeIntegrity,
    authorize_continuation,
    require_continuation_integrity,
)
from planning.runtime_state import FutureRuntimeStateStore

ToolExecutor = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class AutonomousFutureRuntime:
    """Drive a deterministic future while checkpointing every safe transition.

    Every persisted continuation is bound to stable instructions, the exact
    authorized future, and the exact controller snapshot at the checkpoint.
    Resume therefore fails closed if any of those identities changed.
    """

    def __init__(
        self,
        steps: List[FutureStep],
        state_store: FutureRuntimeStateStore,
        runtime_context: RuntimeContext,
        controller: Optional[FutureExecutionController] = None,
        integrity: Optional[RuntimeIntegrity] = None,
    ) -> None:
        self.state_store = state_store
        self.runtime_context = runtime_context
        self.controller = controller or FutureExecutionController(steps)
        if controller is not None and controller.steps != steps:
            raise ValueError("Supplied controller does not match the authorized future.")
        self.steps = steps
        if integrity is not None:
            require_continuation_integrity(
                integrity,
                runtime_context,
                plan_digest=self.controller.plan_digest,
                state_digest=self._state_digest(self.controller.snapshot()),
            )
        self.integrity = integrity
        self._checkpoint()

    @staticmethod
    def _state_digest(snapshot: Dict[str, Any]) -> str:
        payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _checkpoint(self) -> Dict[str, Any]:
        snapshot = self.controller.snapshot()
        self.integrity = authorize_continuation(
            self.runtime_context,
            plan_digest=self.controller.plan_digest,
            state_digest=self._state_digest(snapshot),
        )
        return self.state_store.save(self.controller, self.integrity)

    def snapshot(self) -> Dict[str, Any]:
        return self.controller.snapshot()

    def resume(self) -> "AutonomousFutureRuntime":
        envelope = self.state_store.load()
        raw_integrity = envelope.get("runtime_integrity")
        if raw_integrity is None:
            raise RuntimeError("runtime continuation integrity receipt is missing")
        integrity = RuntimeIntegrity.from_dict(raw_integrity)
        controller = FutureExecutionController.resume_from_snapshot(
            self.steps, envelope["snapshot"]
        )
        require_continuation_integrity(
            integrity,
            self.runtime_context,
            plan_digest=controller.plan_digest,
            state_digest=self._state_digest(controller.snapshot()),
        )
        return AutonomousFutureRuntime(
            self.steps,
            self.state_store,
            self.runtime_context,
            controller=controller,
            integrity=integrity,
        )

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
        runtime_context: RuntimeContext,
        execute: ToolExecutor,
        acknowledgements: Optional[Dict[str, Dict[str, Any]]] = None,
        verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        runtime = cls(steps, state_store, runtime_context).resume()
        return runtime.run_until_pause(execute, acknowledgements, verifications)
