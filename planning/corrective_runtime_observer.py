"""Observation hook for interruption-aware corrective execution."""
from __future__ import annotations

from typing import Any, Callable, Optional


class CorrectiveRuntimeObserver:
    """Wrap an observer and allow a deterministic external-change hook between steps."""

    def __init__(self, observe: Callable[[], Any], on_step: Optional[Callable[[int, Any], None]] = None) -> None:
        self._observe = observe
        self._on_step = on_step
        self._step = 0

    def __call__(self) -> Any:
        evidence = self._observe()
        if self._on_step is not None:
            self._on_step(self._step, evidence)
        self._step += 1
        return evidence
