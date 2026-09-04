"""Immutable lineage contract for Atlas production artifacts.

The canonical Digital Twin is distinct from Blender/Unreal representations. This
module records that relationship without introducing execution, authorization,
or recovery behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


class ProductionArtifactError(ValueError):
    """Raised when a production-artifact lineage record is invalid."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(item) for item in value]
    return value


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        canonical = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProductionArtifactError("production artifact canonical data requires string mapping keys")
            canonical[key] = _canonicalize(item)
        return canonical
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical_items = [_canonicalize(item) for item in value]
        try:
            return sorted(canonical_items)
        except TypeError as exc:
            raise ProductionArtifactError("production artifact canonical data contains unordered values") from exc
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProductionArtifactError("production artifact canonical data requires finite floats")
        return value
    raise ProductionArtifactError(
        "production artifact canonical data contains an unsupported value type"
    )


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
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


def _verify_blender_pair_binding(
    operation_receipt: BlenderExecutionReceipt,
    persistence_evidence: BlenderPersistenceEvidence,
) -> None:
    """Require persistence evidence to describe the exact recorded operation."""
    if operation_receipt.tool != persistence_evidence.operation_tool:
        raise ProductionArtifactError("Blender receipt and persistence evidence operation tools do not match")
    if operation_receipt.arguments_digest != persistence_evidence.operation_arguments_digest:
        raise ProductionArtifactError("Blender receipt and persistence evidence operation arguments do not match")


def _verify_unreal_artifact_path_binding(
    artifact_path: str,
    render_evidence: UnrealEvidence,
) -> None:
    """Require the manifest artifact path to be an independently observed render output."""
    state = render_evidence.observed_state
    if not isinstance(state, Mapping):
        raise ProductionArtifactError("Unreal render evidence observed_state must be a mapping")
    output_files = state.get("output_files")
    if not isinstance(output_files, (list, tuple)):
        raise ProductionArtifactError("Unreal render evidence must include output_files for artifact lineage")
    normalized_outputs = []
    for output_file in output_files:
        if not isinstance(output_file, str) or not output_file.strip():
            raise ProductionArtifactError("Unreal render evidence output_files must contain non-empty strings")
        normalized_outputs.append(output_file.strip())
    if artifact_path not in normalized_outputs:
        raise ProductionArtifactError("Unreal production artifact path is not present in verified render outputs")


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
        """Bind a verified Blender write to artifact lineage without execution or authorization."""
        if not isinstance(operation_receipt, BlenderExecutionReceipt):
            raise TypeError("operation_receipt must be a BlenderExecutionReceipt")
        if not isinstance(persistence_evidence, BlenderPersistenceEvidence):
            raise TypeError("persistence_evidence must be a BlenderPersistenceEvidence")
        _verify_blender_pair_binding(operation_receipt, persistence_evidence)
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

    @classmethod
    def from_unreal_render_receipt(
        cls,
        *,
        artifact_id: str,
        canonical_digital_twin_id: str,
        representation_type: str,
        artifact_path: str,
        render_receipt: UnrealRenderReceipt,
        render_evidence: UnrealEvidence,
        workflow_provenance: Optional[Dict[str, Any]] = None,
        source_artifact_ids: Tuple[str, ...] = (),
        engine: str = "Unreal",
        engine_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ProductionArtifactManifest":
        """Bind an evidence-backed Unreal render receipt to artifact lineage."""
        if not isinstance(render_receipt, UnrealRenderReceipt):
            raise TypeError("render_receipt must be a UnrealRenderReceipt")
        if not isinstance(render_evidence, UnrealEvidence):
            raise TypeError("render_evidence must be a UnrealEvidence")
        if not render_receipt.matches(render_evidence):
            raise ProductionArtifactError("Unreal render receipt does not match render evidence")
        _verify_unreal_artifact_path_binding(artifact_path, render_evidence)
        return cls(
            artifact_id=artifact_id,
            canonical_digital_twin_id=canonical_digital_twin_id,
            representation_type=representation_type,
            artifact_path=artifact_path,
            source_artifact_ids=source_artifact_ids,
            workflow_provenance=workflow_provenance,
            evidence_digests=(render_receipt.evidence_digest,),
            receipt_digests=(render_receipt.receipt_digest,),
            engine=engine,
            engine_version=engine_version,
            metadata=metadata,
        )

    def snapshot(self) -> Dict[str, Any]:
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
        return _canonical_digest(self.snapshot())

    def verify_integrity(self, expected_digest: Optional[str] = None) -> None:
        if expected_digest is not None:
            _require_text(expected_digest, "expected_digest")
            if self.digest() != expected_digest:
                raise ProductionArtifactError("production artifact manifest integrity check failed")

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "ProductionArtifactManifest":
        if not isinstance(snapshot, dict):
            raise ProductionArtifactError("production artifact manifest snapshot must be a dictionary")
        required = {
            "manifest_version", "artifact_id", "canonical_digital_twin_id",
            "representation_type", "artifact_path", "source_artifact_ids",
            "workflow_provenance", "evidence_digests", "receipt_digests",
            "engine", "engine_version", "metadata",
        }
        if set(snapshot) != required:
            raise ProductionArtifactError("production artifact manifest fields are invalid")
        return cls(
            manifest_version=snapshot["manifest_version"],
            artifact_id=snapshot["artifact_id"],
            canonical_digital_twin_id=snapshot["canonical_digital_twin_id"],
            representation_type=snapshot["representation_type"],
            artifact_path=snapshot["artifact_path"],
            source_artifact_ids=snapshot["source_artifact_ids"],
            workflow_provenance=snapshot["workflow_provenance"],
            evidence_digests=snapshot["evidence_digests"],
            receipt_digests=snapshot["receipt_digests"],
            engine=snapshot["engine"],
            engine_version=snapshot["engine_version"],
            metadata=snapshot["metadata"],
        )


def verify_blender_closed_loop_lineage(
    manifest: ProductionArtifactManifest,
    operation_receipt: BlenderExecutionReceipt,
    persistence_evidence: BlenderPersistenceEvidence,
) -> None:
    if not isinstance(manifest, ProductionArtifactManifest):
        raise TypeError("manifest must be a ProductionArtifactManifest")
    if not isinstance(operation_receipt, BlenderExecutionReceipt):
        raise TypeError("operation_receipt must be a BlenderExecutionReceipt")
    if not isinstance(persistence_evidence, BlenderPersistenceEvidence):
        raise TypeError("persistence_evidence must be a BlenderPersistenceEvidence")
    _verify_blender_pair_binding(operation_receipt, persistence_evidence)
    if manifest.receipt_digests != (operation_receipt.digest(),):
        raise ProductionArtifactError("production artifact receipt lineage does not match")
    if manifest.evidence_digests != (persistence_evidence.digest(),):
        raise ProductionArtifactError("production artifact evidence lineage does not match")


def verify_unreal_render_lineage(
    manifest: ProductionArtifactManifest,
    render_receipt: UnrealRenderReceipt,
    render_evidence: UnrealEvidence,
) -> None:
    """Verify exact Unreal receipt/evidence lineage without execution or recovery."""
    if not isinstance(manifest, ProductionArtifactManifest):
        raise TypeError("manifest must be a ProductionArtifactManifest")
    if not isinstance(render_receipt, UnrealRenderReceipt):
        raise TypeError("render_receipt must be a UnrealRenderReceipt")
    if not isinstance(render_evidence, UnrealEvidence):
        raise TypeError("render_evidence must be a UnrealEvidence")
    if not render_receipt.matches(render_evidence):
        raise ProductionArtifactError("Unreal render receipt does not match render evidence")
    _verify_unreal_artifact_path_binding(manifest.artifact_path, render_evidence)
    if manifest.receipt_digests != (render_receipt.receipt_digest,):
        raise ProductionArtifactError("production artifact Unreal receipt lineage does not match")
    if manifest.evidence_digests != (render_receipt.evidence_digest,):
        raise ProductionArtifactError("production artifact Unreal evidence lineage does not match")


__all__ = ["ProductionArtifactError", "ProductionArtifactManifest", "verify_blender_closed_loop_lineage", "verify_unreal_render_lineage"]
