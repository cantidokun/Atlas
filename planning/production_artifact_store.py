"""Durable, fail-closed persistence for production artifact manifests.

The store persists immutable ``ProductionArtifactManifest`` snapshots without
executing, authorizing, or verifying the underlying production work. Integrity
is established by the manifest's deterministic digest and checked again when
loading persisted data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from planning.production_artifact import ProductionArtifactError, ProductionArtifactManifest


class ProductionArtifactStoreError(ValueError):
    """Raised when a production artifact manifest cannot be safely persisted or loaded."""


class ProductionArtifactStore:
    """Persist production artifact manifests using atomic, fail-closed writes."""

    _STORE_VERSION = 1

    def __init__(self, path: str):
        if not isinstance(path, str) or not path.strip():
            raise ProductionArtifactStoreError("path must be a non-empty string")
        self._path = Path(path)

    @property
    def path(self) -> str:
        """Return the configured persistence path."""
        return str(self._path)

    def save(self, manifest: ProductionArtifactManifest) -> None:
        """Atomically persist a manifest and its integrity digest."""
        if not isinstance(manifest, ProductionArtifactManifest):
            raise TypeError("manifest must be a ProductionArtifactManifest")

        payload = {
            "store_version": self._STORE_VERSION,
            "manifest": manifest.snapshot(),
            "manifest_digest": manifest.digest(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self._path.parent.mkdir(parents=True, exist_ok=True)

        fd = None
        temporary_path = None
        try:
            fd, temporary_path = tempfile.mkstemp(
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                dir=str(self._path.parent),
            )
            with os.fdopen(fd, "wb") as handle:
                fd = None
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
        except OSError as exc:
            raise ProductionArtifactStoreError("failed to persist production artifact manifest") from exc
        finally:
            if fd is not None:
                os.close(fd)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass

        try:
            directory_fd = os.open(str(self._path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise ProductionArtifactStoreError("production artifact manifest persisted but directory flush failed") from exc

    def load(self) -> ProductionArtifactManifest:
        """Load and fail closed if the persisted envelope or manifest digest is invalid."""
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ProductionArtifactStoreError("failed to load production artifact manifest") from exc

        if not isinstance(payload, dict):
            raise ProductionArtifactStoreError("production artifact store payload must be a dictionary")
        if set(payload) != {"store_version", "manifest", "manifest_digest"}:
            raise ProductionArtifactStoreError("production artifact store fields are invalid")
        if payload["store_version"] != self._STORE_VERSION:
            raise ProductionArtifactStoreError("production artifact store version is unsupported")
        if not isinstance(payload["manifest_digest"], str) or not payload["manifest_digest"].strip():
            raise ProductionArtifactStoreError("production artifact manifest digest is invalid")

        try:
            manifest = ProductionArtifactManifest.from_snapshot(payload["manifest"])
            manifest.verify_integrity(payload["manifest_digest"])
        except (ProductionArtifactError, TypeError, ValueError) as exc:
            raise ProductionArtifactStoreError("persisted production artifact manifest integrity check failed") from exc
        return manifest


__all__ = ["ProductionArtifactStore", "ProductionArtifactStoreError"]
