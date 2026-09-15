"""Wave-8 bounded scene unit metadata normalization.

Canonical-model mutation only. This operation canonicalizes an explicit alias of the Atlas
meters token to ``METERS``. It never converts physical units or scales geometry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.blender.scene_model import ObjectModel, SceneModel

CORRECTION_TYPE = "NORMALIZE_UNIT_METADATA"
PLANNER_VERSION = "1"
_ALLOWED_PARAMS = frozenset({"current_unit", "target_unit"})
_ALLOWED_UNIT_ALIASES = frozenset({"METERS", "meters", "m"})
_CANONICAL_UNIT = "METERS"


class UnitMetadataNormalizationError(ValueError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UnitMetadataPlan:
    correction_id: str
    plan_id: str
    source_report_digest: str
    scene_id: str
    current_unit: str
    target_unit: str

    def to_dict(self) -> dict:
        return {
            "planner_version": PLANNER_VERSION,
            "correction_type": CORRECTION_TYPE,
            "correction_id": self.correction_id,
            "source_report_digest": self.source_report_digest,
            "scene_id": self.scene_id,
            "params": {"current_unit": self.current_unit, "target_unit": self.target_unit},
            "plan_id": self.plan_id,
        }


@dataclass(frozen=True)
class ExecutionOutcome:
    ok: bool
    outcome: str
    failure_code: Optional[str]
    source_report_digest: str
    output_scene_digest: Optional[str]
    scene: Optional[SceneModel] = None


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _scene_payload(scene: SceneModel) -> dict:
    def object_payload(obj: ObjectModel) -> dict:
        mesh = obj.mesh
        return {
            "object_id": obj.object_id,
            "name": obj.name,
            "collection": obj.collection,
            "parent_object_id": obj.parent_object_id,
            "location": list(obj.location),
            "scale": list(obj.scale),
            "rotation": list(obj.rotation),
            "visible": obj.visible,
            "mesh": None if mesh is None else {
                "mesh_id": mesh.mesh_id,
                "vertices": [list(v) for v in mesh.vertices],
                "faces": [list(f) for f in mesh.faces],
                "normals": [list(v) for v in mesh.normals],
                "uvs": [list(v) for v in mesh.uvs],
                "materials": list(mesh.materials),
                "local_frame_id": mesh.local_frame_id,
            },
        }

    return {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "objects": [object_payload(o) for o in scene.objects],
        "coordinate_frame": scene.coordinate_frame,
        "world_bounds": None
        if scene.world_bounds is None
        else [list(scene.world_bounds[0]), list(scene.world_bounds[1])],
    }


def scene_digest(scene: SceneModel) -> str:
    return _digest(_scene_payload(scene))


def _validate_alias(value: Any, label: str) -> str:
    if type(value) is not str:
        raise UnitMetadataNormalizationError(f"{label} must be an exact built-in string", "UNIT_TYPE_INVALID")
    if value not in _ALLOWED_UNIT_ALIASES:
        raise UnitMetadataNormalizationError(
            f"{label} is not an approved meters alias", "PHYSICAL_UNIT_MISMATCH"
        )
    return value


def _plan_body(*, scene_id: str, current_unit: str, target_unit: str, source_digest: str) -> dict:
    correction_id = _digest({
        "correction_type": CORRECTION_TYPE,
        "scene_id": scene_id,
        "current_unit": current_unit,
        "target_unit": target_unit,
        "source_report_digest": source_digest,
    })
    body = {
        "planner_version": PLANNER_VERSION,
        "correction_type": CORRECTION_TYPE,
        "correction_id": correction_id,
        "source_report_digest": source_digest,
        "scene_id": scene_id,
        "params": {"current_unit": current_unit, "target_unit": target_unit},
    }
    return {**body, "plan_id": _digest(body)}


def plan_unit_metadata_normalization(
    scene: SceneModel,
    source_report_digest: str,
    *,
    current_unit: Any,
    target_unit: Any = _CANONICAL_UNIT,
) -> Mapping[str, Any]:
    if type(source_report_digest) is not str or len(source_report_digest) != 64:
        raise UnitMetadataNormalizationError(
            "source report digest must be a 64-character string", "SOURCE_DIGEST_INVALID"
        )
    if target_unit != _CANONICAL_UNIT:
        raise UnitMetadataNormalizationError(
            "Wave 8 target unit is fixed to METERS", "TARGET_UNIT_INVALID"
        )
    current = _validate_alias(current_unit, "current_unit")
    if current == _CANONICAL_UNIT:
        raise UnitMetadataNormalizationError(
            "already canonical; no normalization is required", "ALREADY_CANONICAL"
        )
    if scene.unit_system != current:
        raise UnitMetadataNormalizationError(
            "scene unit token does not match authorization input", "CURRENT_UNIT_MISMATCH"
        )
    return _plan_body(
        scene_id=scene.scene_id,
        current_unit=current,
        target_unit=_CANONICAL_UNIT,
        source_digest=source_report_digest,
    )


def _replace_unit(scene: SceneModel, target_unit: str) -> SceneModel:
    return SceneModel(
        scene_id=scene.scene_id,
        unit_system=target_unit,
        objects=scene.objects,
        coordinate_frame=scene.coordinate_frame,
        world_bounds=scene.world_bounds,
    )


def _scene_non_unit_payload(scene: SceneModel) -> dict:
    payload = _scene_payload(scene)
    payload.pop("unit_system")
    return payload


def execute_unit_metadata_normalization(
    plan: Mapping[str, Any],
    authorization: Mapping[str, Any],
    *,
    extractor: Callable[[], Tuple[SceneModel, str]],
) -> ExecutionOutcome:
    """Execute only an exactly-authorized alias-only unit metadata normalization."""
    source = str(plan.get("source_report_digest"))
    if plan.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "PLAN_INVALID", "CORRECTION_TYPE_MISMATCH", source, None)
    params = plan.get("params")
    if type(params) is not dict or set(params) != _ALLOWED_PARAMS:
        return ExecutionOutcome(False, "PLAN_INVALID", "PARAMS_INVALID", source, None)
    current = params.get("current_unit")
    target = params.get("target_unit")
    try:
        _validate_alias(current, "current_unit")
    except UnitMetadataNormalizationError as exc:
        return ExecutionOutcome(False, "PLAN_INVALID", exc.code, source, None)
    if target != _CANONICAL_UNIT:
        return ExecutionOutcome(False, "PLAN_INVALID", "TARGET_UNIT_INVALID", source, None)
    if current == _CANONICAL_UNIT:
        return ExecutionOutcome(False, "PLAN_INVALID", "ALREADY_CANONICAL", source, None)
    if authorization.get("decision") != "APPROVED" or authorization.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "AUTHORIZATION_INVALID", source, None)
    for key in ("correction_id", "plan_id", "source_report_digest"):
        if authorization.get(key) != plan.get(key):
            return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", key.upper() + "_MISMATCH", source, None)

    scene_id = plan.get("scene_id")
    expected_plan = _plan_body(
        scene_id=scene_id,
        current_unit=current,
        target_unit=target,
        source_digest=source,
    )
    if plan.get("correction_id") != expected_plan["correction_id"] or plan.get("plan_id") != expected_plan["plan_id"]:
        return ExecutionOutcome(False, "PLAN_INVALID", "PLAN_ID_MISMATCH", source, None)

    before, fresh_digest = extractor()
    if fresh_digest != source:
        return ExecutionOutcome(False, "SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH", fresh_digest, None)
    if before.scene_id != scene_id:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "SCENE_ID_MISMATCH", fresh_digest, None)
    if before.unit_system != current:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "CURRENT_UNIT_MISMATCH", fresh_digest, None)
    if current not in _ALLOWED_UNIT_ALIASES or target != _CANONICAL_UNIT:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "PHYSICAL_UNIT_MISMATCH", fresh_digest, None)

    after = _replace_unit(before, target)
    if after.unit_system != _CANONICAL_UNIT:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNIT_NOT_CANONICAL", fresh_digest, None)
    if _scene_non_unit_payload(after) != _scene_non_unit_payload(before):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "NON_UNIT_STATE_CHANGED", fresh_digest, None)
    return ExecutionOutcome(
        True,
        "COMPLETED",
        None,
        fresh_digest,
        scene_digest(after),
        after,
    )
