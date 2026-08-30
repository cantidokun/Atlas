"""Durable stores for validated production sequence restart state."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from planning.durable_production_persistence import DurableProductionPersistenceBundle


class InMemoryDurableProductionPersistenceStore:
    """Small deterministic persistence seam used by production orchestration tests."""

    def __init__(self) -> None:
        self._snapshot: dict[str, Any] | None = None

    def save(self, bundle: DurableProductionPersistenceBundle) -> None:
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        snapshot = bundle.snapshot()
        self._snapshot = snapshot

    def load(self) -> DurableProductionPersistenceBundle:
        if self._snapshot is None:
            raise LookupError("no durable production persistence state is available")
        return DurableProductionPersistenceBundle.from_snapshot(self._snapshot)

    def snapshot(self) -> Mapping[str, Any] | None:
        if self._snapshot is None:
            return None
        snapshot = {
            "registry_snapshot": dict(self._snapshot["registry_snapshot"]),
            "checkpoint_snapshot": dict(self._snapshot["checkpoint_snapshot"]),
        }
        if "resume_identity" in self._snapshot:
            snapshot["resume_identity"] = dict(self._snapshot["resume_identity"])
            snapshot["resume_identity_digest"] = self._snapshot["resume_identity_digest"]
        return snapshot


class JsonDurableProductionPersistenceStore:
    """Persist one validated production bundle across an actual process restart."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        if self.path.exists() and not self.path.is_file():
            raise ValueError("persistence path must be a file")

    def save(self, bundle: DurableProductionPersistenceBundle) -> None:
        if not isinstance(bundle, DurableProductionPersistenceBundle):
            raise TypeError("bundle must be a DurableProductionPersistenceBundle")
        payload = bundle.snapshot()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def load(self) -> DurableProductionPersistenceBundle:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                snapshot: Any = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("durable production persistence file is unreadable") from exc
        try:
            return DurableProductionPersistenceBundle.from_snapshot(snapshot)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "durable production persistence file failed integrity validation"
            ) from exc
