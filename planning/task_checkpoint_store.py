"""Durable, integrity-checked task-sequence checkpoint storage."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession


class TaskCheckpointStore:
    """Persist sequence checkpoints atomically and validate them on load."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, checkpoint: Dict[str, Any]) -> None:
        if not isinstance(checkpoint, dict):
            raise TypeError("checkpoint must be an object")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(checkpoint, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def load(self) -> Dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            checkpoint = json.load(handle)
        if not isinstance(checkpoint, dict):
            raise ValueError("stored checkpoint must be an object")
        return checkpoint

    def load_session(self, definition: TaskSequenceDefinition, execute, evidence_reducers):
        return TaskSequenceSession.resume_from_checkpoint(
            definition, execute, evidence_reducers, self.load()
        )
