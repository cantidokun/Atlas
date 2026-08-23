"""Fail-closed retry loop for corrective replans."""
from __future__ import annotations

from typing import Any, Callable, List

from action_plan import ActionSpec
from planning.fresh_state_replan import FreshStateReplan


class CorrectiveReplanExecutor:
    """Re-observe and rebuild a replan when its authorization becomes stale."""

    def __init__(self, boundary: Any):
        self._boundary = boundary

    def execute_until_stable(
        self,
        evidence_supplier: Callable[[], Any],
        planner: Callable[[Any], List[ActionSpec]],
        authorization_id: str,
        before_execute: Callable[[int, Any], None] | None = None,
        max_attempts: int = 3,
    ) -> Any:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")

        for attempt in range(max_attempts):
            replan = FreshStateReplan.create(evidence_supplier, planner, authorization_id)
            if len(replan.actions) != 1:
                raise RuntimeError("corrective execution requires exactly one replacement action")

            current_evidence = evidence_supplier()
            if before_execute is not None:
                before_execute(attempt, current_evidence)
            try:
                return self._boundary.execute_authorized_replan(replan, current_evidence)
            except RuntimeError as exc:
                if "stale" not in str(exc).lower() and "invalid" not in str(exc).lower():
                    raise
                if attempt + 1 >= max_attempts:
                    raise RuntimeError("corrective replan remained stale after retry budget") from exc

        raise RuntimeError("corrective replan execution exhausted unexpectedly")
