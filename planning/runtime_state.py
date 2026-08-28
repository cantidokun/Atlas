"""Durable runtime state for resumable Atlas futures."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning.future_execution import FutureExecutionController
from planning.future_generator import FutureStep
from planning.runtime_integrity import RuntimeIntegrity


class FutureRuntimeStateStore:
    """Atomically persist and restore one authorized future's execution state."""

    VERSION = 1

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def save(
        self,
        controller: FutureExecutionController,
        integrity: Optional[RuntimeIntegrity] = None,
    ) -> Dict[str, Any]:
        """Persist a controller snapshot and optional continuation receipt."""
        snapshot = controller.snapshot()
        envelope = {
            "version": self.VERSION,
            "plan_digest": controller.plan_digest,
            "snapshot": snapshot,
        }
        if integrity is not None:
            if integrity.plan_digest != controller.plan_digest:
                raise ValueError("runtime integrity plan digest does not match controller")
            envelope["runtime_integrity"] = integrity.to_dict()
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
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                envelope = json.load(handle)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("Future runtime state is not valid JSON.") from exc
        if not isinstance(envelope, dict) or envelope.get("version") != self.VERSION:
            raise RuntimeError("Unsupported or invalid future runtime state.")
        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, dict):
            raise RuntimeError("Future runtime state is missing its snapshot.")
        if envelope.get("plan_digest") != snapshot.get("plan_digest"):
            raise RuntimeError("Future runtime state digest is inconsistent.")
        integrity_payload = envelope.get("runtime_integrity")
        if integrity_payload is not None:
            if not isinstance(integrity_payload, dict):
                raise RuntimeError("Future runtime integrity receipt is invalid.")
            RuntimeIntegrity.from_dict(integrity_payload)
        return envelope

    def resume(self, steps: List[FutureStep]) -> FutureExecutionController:
        """Resume only against the caller-supplied original authorized future."""
        envelope = self.load()
        return FutureExecutionController.resume_from_snapshot(steps, envelope["snapshot"])
