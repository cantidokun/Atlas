"""Durable runtime state for resumable Atlas futures.

This layer persists only controller state plus the immutable plan digest. It does
not persist executable callables or allow a persisted snapshot to define a new
future. The caller must supply the original FutureStep list when resuming.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep


class FutureRuntimeStateStore:
    """Atomically persist and restore one authorized future's execution state."""

    VERSION = 1

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def save(self, controller: FutureExecutionController) -> Dict[str, Any]:
        """Persist a controller snapshot atomically and return the envelope."""
        snapshot = controller.snapshot()
        envelope = {
            "version": self.VERSION,
            "plan_digest": controller.plan_digest,
            "snapshot": snapshot,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(envelope, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return envelope

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        with self.path.open("r", encoding="utf-8") as handle:
            envelope = json.load(handle)
        if not isinstance(envelope, dict) or envelope.get("version") != self.VERSION:
            raise RuntimeError("Unsupported or invalid future runtime state.")
        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, dict):
            raise RuntimeError("Future runtime state is missing its snapshot.")
        if envelope.get("plan_digest") != snapshot.get("plan_digest"):
            raise RuntimeError("Future runtime state digest is inconsistent.")
        return envelope

    def resume(self, steps: List[FutureStep]) -> FutureExecutionController:
        """Resume only against the caller-supplied original authorized future."""
        envelope = self.load()
        return FutureExecutionController.resume_from_snapshot(steps, envelope["snapshot"])
