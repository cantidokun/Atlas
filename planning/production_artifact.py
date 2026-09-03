"""Immutable lineage contract for Atlas production artifacts.

The canonical Digital Twin is distinct from Blender/Unreal representations. This
module records that relationship without introducing execution, authorization,
or recovery behavior.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence


class ProductionArtifactError(ValueError):
    """Raised when a production-artifact lineage record is invalid."""


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
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
    workflow_provenance: Optional[Dict[str, Any]] = None
    evidence_digests: Tuple[str, ...] = ()
    receipt_digests: Tuple[str, ...] = ()
    engine: Optional[str] = None
    engine_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
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
        if self.workflow_provenance is not None and not isinstance(self.workflow_provenance, dict):
            raise ProductionArtifactError("workflow_provenance must be a dictionary when provided")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ProductionArtifactError("metadata must be a dictionary when provided")
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
            receipt_digests=(_canonical_digest({
                "tool": operation_receipt.tool,
                "arguments_digest": operation_receipt.arguments_digest,
                "result_digest": operation_receipt.result_digest,
            }),),
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
            "workflow_provenance": deepcopy(self.workflow_provenance or {}),
            "evidence_digests": list(self.evidence_digests),
            "receipt_digests": list(self.receipt_digests),
            "engine": self.engine,
            "engine_version": self.engine_version,
            "metadata": deepcopy(self.metadata or {}),
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
            workflow_provenance=deepcopy(snapshot["workflow_provenance"]),
            evidence_digests=tuple(snapshot["evidence_digests"]),
            receipt_digests=tuple(snapshot["receipt_digests"]),
            engine=snapshot["engine"],
            engine_version=snapshot["engine_version"],
            metadata=deepcopy(snapshot["metadata"]),
        )


__all__ = ["ProductionArtifactError", "ProductionArtifactManifest"]
