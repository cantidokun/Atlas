"""Wave-9 bounded object-name normalization.

Canonical-model-only mutation. The executor changes exactly one ObjectModel.name to an explicitly
authorized target name. It never infers names, rewrites stable identifiers, changes geometry or
transforms, touches Blender directly, persists anything, or owns workflow/receipt/recovery logic.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.blender.scene_model import ObjectModel, SceneModel

CORRECTION_TYPE = "NORMALIZE_OBJECT_NAME"
PLANNER_VERSION = "1"
_ALLOWED_PARAMS = frozenset({"expected_object_id", "current_name", "target_name", "name_pattern"})
_SUPPORTED_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"


class ObjectNameNormalizationError(ValueError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ObjectNamePlan:
    correction_id: str
    plan_id: str
    source_report_digest: str
    scene_id: str
    expected_object_id: str
    current_name: str
    target_name: str
    name_pattern: str

    def to_dict(self) -> dict:
        return {
            "planner_version": PLANNER_VERSION,
            "correction_type": CORRECTION_TYPE,
            "correction_id": self.correction_id,
            "source_report_digest": self.source_report_digest,
            "scene_id": self.scene_id,
            "params": {
                "expected_object_id": self.expected_object_id,
                "current_name": self.current_name,
                "target_name": self.target_name,
                "name_pattern": self.name_pattern,
            },
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
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


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
        "world_bounds": None if scene.world_bounds is None else [list(scene.world_bounds[0]), list(scene.world_bounds[1])],
    }


def scene_digest(scene: SceneModel) -> str:
    return _digest(_scene_payload(scene))


def _validate_str(value: Any, label: str) -> str:
    if type(value) is not str:
        raise ObjectNameNormalizationError(f"{label} must be an exact built-in string", "STRING_TYPE_INVALID")
    if not value:
        raise ObjectNameNormalizationError(f"{label} must be non-empty", "STRING_EMPTY")
    return value


def _validate_pattern(value: Any) -> str:
    pattern = _validate_str(value, "name_pattern")
    if pattern != _SUPPORTED_PATTERN:
        raise ObjectNameNormalizationError("name_pattern is outside the Wave 9 closed pattern contract", "NAME_PATTERN_UNSUPPORTED")
    return pattern


def _validate_target_name(value: Any, pattern: str) -> str:
    name = _validate_str(value, "target_name")
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name) is None:
        raise ObjectNameNormalizationError("target_name does not satisfy the supported Atlas naming pattern", "TARGET_NAME_INVALID")
    return name


def _plan_body(*, scene_id: str, expected_object_id: str, current_name: str, target_name: str, name_pattern: str, source_digest: str) -> dict:
    correction_id = _digest({
        "correction_type": CORRECTION_TYPE,
        "scene_id": scene_id,
        "expected_object_id": expected_object_id,
        "current_name": current_name,
        "target_name": target_name,
        "name_pattern": name_pattern,
        "source_report_digest": source_digest,
    })
    body = {
        "planner_version": PLANNER_VERSION,
        "correction_type": CORRECTION_TYPE,
        "correction_id": correction_id,
        "source_report_digest": source_digest,
        "scene_id": scene_id,
        "params": {
            "expected_object_id": expected_object_id,
            "current_name": current_name,
            "target_name": target_name,
            "name_pattern": name_pattern,
        },
    }
    return {**body, "plan_id": _digest(body)}


def plan_object_name_normalization(
    scene: SceneModel,
    source_report_digest: str,
    *,
    expected_object_id: Any,
    current_name: Any,
    target_name: Any,
    name_pattern: Any = _SUPPORTED_PATTERN,
) -> Mapping[str, Any]:
    if type(source_report_digest) is not str or len(source_report_digest) != 64 or any(c not in "0123456789abcdef" for c in source_report_digest):
        raise ObjectNameNormalizationError("source report digest must be a 64-character lowercase hex string", "SOURCE_DIGEST_INVALID")
    object_id = _validate_str(expected_object_id, "expected_object_id")
    current = _validate_str(current_name, "current_name")
    pattern = _validate_pattern(name_pattern)
    target = _validate_str(target_name, "target_name")
    if target == current:
        raise ObjectNameNormalizationError("already canonical; no normalization is required", "ALREADY_CANONICAL")
    target = _validate_target_name(target, pattern)
    matches = [obj for obj in scene.objects if obj.object_id == object_id]
    if len(matches) != 1:
        raise ObjectNameNormalizationError("expected object id must resolve to exactly one object", "OBJECT_ID_RESOLUTION_INVALID")
    if matches[0].name != current:
        raise ObjectNameNormalizationError("scene object name does not match requested current_name", "CURRENT_NAME_MISMATCH")
    if any(obj.name == target and obj.object_id != object_id for obj in scene.objects):
        raise ObjectNameNormalizationError("target name collides with another object", "NAME_COLLISION")
    return _plan_body(
        scene_id=scene.scene_id,
        expected_object_id=object_id,
        current_name=current,
        target_name=target,
        name_pattern=pattern,
        source_digest=source_report_digest,
    )


def _replace_object_name(scene: SceneModel, object_id: str, target_name: str) -> SceneModel:
    new_objects = tuple(
        ObjectModel(
            object_id=obj.object_id,
            name=target_name if obj.object_id == object_id else obj.name,
            collection=obj.collection,
            parent_object_id=obj.parent_object_id,
            location=obj.location,
            scale=obj.scale,
            rotation=obj.rotation,
            visible=obj.visible,
            mesh=obj.mesh,
        )
        for obj in scene.objects
    )
    return SceneModel(
        scene_id=scene.scene_id,
        unit_system=scene.unit_system,
        objects=new_objects,
        coordinate_frame=scene.coordinate_frame,
        world_bounds=scene.world_bounds,
    )


def _scene_non_name_payload(scene: SceneModel) -> dict:
    payload = _scene_payload(scene)
    for obj in payload["objects"]:
        obj.pop("name")
    return payload


def _authorization_is_exact(authorization: Mapping[str, Any], plan: Mapping[str, Any]) -> bool:
    expected = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan.get("correction_id"),
        "plan_id": plan.get("plan_id"),
        "source_report_digest": plan.get("source_report_digest"),
    }
    return type(authorization) is dict and authorization == expected


def execute_object_name_normalization(
    plan: Mapping[str, Any],
    authorization: Mapping[str, Any],
    *,
    extractor: Callable[[], Tuple[SceneModel, str]],
) -> ExecutionOutcome:
    source = str(plan.get("source_report_digest"))
    if plan.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "PLAN_INVALID", "CORRECTION_TYPE_MISMATCH", source, None)
    params = plan.get("params")
    if type(params) is not dict or set(params) != _ALLOWED_PARAMS:
        return ExecutionOutcome(False, "PLAN_INVALID", "PARAMS_INVALID", source, None)
    try:
        object_id = _validate_str(params.get("expected_object_id"), "expected_object_id")
        current = _validate_str(params.get("current_name"), "current_name")
        pattern = _validate_pattern(params.get("name_pattern"))
        target = _validate_str(params.get("target_name"), "target_name")
        if target == current:
            return ExecutionOutcome(False, "PLAN_INVALID", "ALREADY_CANONICAL", source, None)
        target = _validate_target_name(target, pattern)
    except ObjectNameNormalizationError as exc:
        return ExecutionOutcome(False, "PLAN_INVALID", exc.code, source, None)
    if not _authorization_is_exact(authorization, plan):
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "AUTHORIZATION_INVALID", source, None)
    scene_id = plan.get("scene_id")
    expected_plan = _plan_body(
        scene_id=scene_id,
        expected_object_id=object_id,
        current_name=current,
        target_name=target,
        name_pattern=pattern,
        source_digest=source,
    )
    if plan.get("correction_id") != expected_plan["correction_id"] or plan.get("plan_id") != expected_plan["plan_id"]:
        return ExecutionOutcome(False, "PLAN_INVALID", "PLAN_ID_MISMATCH", source, None)

    before, fresh_digest = extractor()
    actual_digest = scene_digest(before)
    if fresh_digest != actual_digest:
        return ExecutionOutcome(False, "SOURCE_MISMATCH", "SOURCE_DIGEST_INVALID", actual_digest, None)
    if actual_digest != source:
        return ExecutionOutcome(False, "SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH", actual_digest, None)
    if before.scene_id != scene_id:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "SCENE_ID_MISMATCH", actual_digest, None)
    matches = [obj for obj in before.objects if obj.object_id == object_id]
    if len(matches) != 1:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "OBJECT_ID_RESOLUTION_INVALID", actual_digest, None)
    if matches[0].name != current:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "CURRENT_NAME_MISMATCH", actual_digest, None)
    if any(obj.name == target and obj.object_id != object_id for obj in before.objects):
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "NAME_COLLISION", actual_digest, None)

    after = _replace_object_name(before, object_id, target)
    changed = [
        (before_obj.object_id, before_obj.name, after_obj.name)
        for before_obj, after_obj in zip(before.objects, after.objects)
        if before_obj.name != after_obj.name
    ]
    if changed != [(object_id, current, target)]:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNEXPECTED_NAME_CHANGES", actual_digest, None)
    if _scene_non_name_payload(after) != _scene_non_name_payload(before):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "NON_NAME_STATE_CHANGED", actual_digest, None)
    if len({obj.name for obj in after.objects}) != len(after.objects):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "NAME_NOT_UNIQUE", actual_digest, None)
    if next(obj for obj in after.objects if obj.object_id == object_id).name != target:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_NAME_NOT_APPLIED", actual_digest, None)

    return ExecutionOutcome(True, "COMPLETED", None, actual_digest, scene_digest(after), after)
