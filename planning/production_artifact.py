"""Immutable lineage contract for Atlas production artifacts.

The canonical Digital Twin is distinct from Blender/Unreal representations. This
module records that relationship without introducing execution, authorization,
or recovery behavior.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence


class ProductionArtifactError(ValueError):
    """Raised when a production-artifact lineage record is invalid."""


def _freeze(value: Any) -> Any:
    """Recursively freeze persisted mapping/list values used by the manifest."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    """Return ordinary JSON-compatible containers from immutable lineage data."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(item) for item in value]
    return value


def _canonicalize(value: Any) -> Any:
    """Normalize immutable containers before deterministic JSON serialization."""
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonicalize(item) for item in value)
    return value


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionArtifactError(f"{field} must be a non-empty string")
    return value.strip()


def _require_text_tuple(value: Any, field: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ProductionArtifactError(f"{field} must be a list or tuple of strings")
    normalized = tuple(_require_text(item, field) for item in value)
    if len(normalized) != len(set(normalized)):
        raise ProductionArtifactError(f"{field} must contain unique values")
    return normalized


@dataclass(frozen=True)
class ProductionArtifactManifest:
    """Provenance for one production representation of a canonical Digital Twin."""

    artifact_id: str
    canonical_digital_twin_id: str
    representation_type: str
    artifact_path: str
    source_artifact_ids: Tuple[str, ...] = ()
    workflow_provenance: Optional[Mapping[str, Any]] = None
    evidence_digests: Tuple[str, ...] = ()
    receipt_digests: Tuple[str, ...] = ()
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    metadata: Optional[Mapping[str, Any]] = None
    manifest_version: int = 1

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.canonical_digital_twin_id, "canonical_digital_twin_id")
        _require_text(self.representation_type, "representation_type")
        _require_text(self.artifact_path, "artifact_path")
        if not isinstance(self.manifest_version, int) or isinstance(self.manifest_version, bool) or self.manifest_version < 1:
            raise ProductionArtifactError("manifest_version must be a positive integer")
        object.__setattr__(self, "source_artifact_ids", _require_text_tuple(self.source_artifact_ids, "source_artifact_ids"))
        for field in ("evidence_digests", "receipt_digests"):
            object.__setattr__(self, field, _require_text_tuple(getattr(self, field), field))
        for field in ("engine", "engine_version"):
            value = getattr(self, field)
            if value is not None:
                _require_text(value, field)
        for field in ("workflow_provenance", "metadata"):
            value = getattr(self, field)
            if value is not None:
                if not isinstance(value, Mapping):
                    raise ProductionArtifactError(f"{field} must be a dictionary when provided")
                object.__setattr__(self, field, _freeze(value))
        if self.artifact_id in self.source_artifact_ids:
            raise ProductionArtifactError("artifact_id cannot reference itself as a source")

    @classmethod
    def from_blender_closed_loop(
        cls,
        *,
        artifact_id: str,
        canonical_digital_twin_id: str,
        representation_type: str,
        artifact_path: str,
        operation_receipt: BlenderExecutionReceipt,
        persistence_evidence: BlenderPersistenceEvidence,
        workflow_provenance: Optional[Dict[str, Any]] = None,
        source_artifact_ids: Tuple[str, ...] = (),
        engine: str = "Blender",
        engine_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ProductionArtifactManifest":
        """Bind a verified Blender write to artifact lineage.

        Only already-created immutable receipt/evidence objects are accepted;
        this method performs no execution, verification, or authorization.
        """
        if not isinstance(operation_receipt, BlenderExecutionReceipt):
            raise TypeError("operation_receipt must be a BlenderExecutionReceipt")
        if not isinstance(persistence_evidence, BlenderPersistenceEvidence):
            raise TypeError("persistence_evidence must be a BlenderPersistenceEvidence")
        return cls(
            artifact_id=artifact_id,
            canonical_digital_twin_id=canonical_digital_twin_id,
            representation_type=representation_type,
            artifact_path=artifact_path,
            source_artifact_ids=source_artifact_ids,
            workflow_provenance=workflow_provenance,
            evidence_digests=(persistence_evidence.digest(),),
            receipt_digests=(operation_receipt.digest(),),
            engine=engine,
            engine_version=engine_version,
            metadata=metadata,
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return detached, deterministic lineage data without the derived digest."""
        return {
            "manifest_version": self.manifest_version,
            "artifact_id": self.artifact_id,
            "canonical_digital_twin_id": self.canonical_digital_twin_id,
            "representation_type": self.representation_type,
            "artifact_path": self.artifact_path,
            "source_artifact_ids": list(self.source_artifact_ids),
            "workflow_provenance": _thaw(self.workflow_provenance or {}),
            "evidence_digests": list(self.evidence_digests),
            "receipt_digests": list(self.receipt_digests),
            "engine": self.engine,
            "engine_version": self.engine_version,
            "metadata": _thaw(self.metadata or {}),
        }

    def digest(self) -> str:
        """Return the deterministic integrity digest for this manifest."""
        return _canonical_digest(self.snapshot())

    def verify_integrity(self, expected_digest: Optional[str] = None) -> None:
        """Fail closed when an expected digest does not match current lineage data."""
        if expected_digest is not None:
            _require_text(expected_digest, "expected_digest")
            if self.digest() != expected_digest:
                raise ProductionArtifactError("production artifact manifest integrity check failed")

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "ProductionArtifactManifest":
        """Reconstruct a manifest and reject unknown or malformed persisted fields."""
        if not isinstance(snapshot, dict):
            raise ProductionArtifactError("production artifact manifest snapshot must be a dictionary")
        required = {
            "manifest_version", "artifact_id", "canonical_digital_twin_id", "representation_type",
            "artifact_path", "source_artifact_ids", "workflow_provenance", "evidence_digests",
            "receipt_digests", "engine", "engine_version", "metadata",
        }
        if set(snapshot) != required:
            raise ProductionArtifactError("production artifact manifest fields are invalid")
        return cls(
            manifest_version=snapshot["manifest_version"],
            artifact_id=snapshot["artifact_id"],
            canonical_digital_twin_id=snapshot["canonical_digital_twin_id"],
            representation_type=snapshot["representation_type"],
            artifact_path=snapshot["artifact_path"],
            source_artifact_ids=tuple(snapshot["source_artifact_ids"]),
            workflow_provenance=snapshot["workflow_provenance"],
            evidence_digests=tuple(snapshot["evidence_digests"]),
            receipt_digests=tuple(snapshot["receipt_digests"]),
            engine=snapshot["engine"],
            engine_version=snapshot["engine_version"],
            metadata=snapshot["metadata"],
        )


def verify_blender_closed_loop_lineage(
    manifest: ProductionArtifactManifest,
    operation_receipt: BlenderExecutionReceipt,
    persistence_evidence: BlenderPersistenceEvidence,
) -> None:
    """Verify that a manifest references the exact persisted Blender evidence records.

    This is a pure lineage check. It does not execute Blender, inspect an artifact,
    authorize an operation, or infer that the underlying scene is currently valid.
    """
    if not isinstance(manifest, ProductionArtifactManifest):
        raise TypeError("manifest must be a ProductionArtifactManifest")
    if not isinstance(operation_receipt, BlenderExecutionReceipt):
        raise TypeError("operation_receipt must be a BlenderExecutionReceipt")
    if not isinstance(persistence_evidence, BlenderPersistenceEvidence):
        raise TypeError("persistence_evidence must be a BlenderPersistenceEvidence")

    expected_receipt_digest = operation_receipt.digest()
    expected_evidence_digest = persistence_evidence.digest()
    if manifest.receipt_digests != (expected_receipt_digest,):
        raise ProductionArtifactError("production artifact receipt lineage does not match")
    if manifest.evidence_digests != (expected_evidence_digest,):
        raise ProductionArtifactError("production artifact evidence lineage does not match")


__all__ = [
    "ProductionArtifactError",
    "ProductionArtifactManifest",
    "verify_blender_closed_loop_lineage",
]
