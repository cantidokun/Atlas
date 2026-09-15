"""Wave-10 bounded object-collection normalization.

Canonical-model-only mutation. The executor changes exactly one ObjectModel.collection to an
explicitly authorized target collection from an exact allowlist. It never infers destinations,
creates collections, changes geometry/transforms, touches Blender directly, persists anything, or
owns workflow/receipt/recovery logic.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.blender.scene_model import ObjectModel, SceneModel

CORRECTION_TYPE = "NORMALIZE_OBJECT_COLLECTION"
PLANNER_VERSION = "1"
_ALLOWED_PARAMS = frozenset({"expected_object_id", "current_collection", "target_collection", "allowed_collections"})
_AUTHORIZATION_FIELDS = frozenset({
    "decision",
    "correction_type",
    "correction_id",
    "plan_id",
    "source_report_digest",
})


class CollectionNormalizationError(ValueError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


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


def _validate_nonempty_str(value: Any, label: str) -> str:
    if type(value) is not str:
        raise CollectionNormalizationError(f"{label} must be an exact built-in string", "STRING_TYPE_INVALID")
    if not value:
        raise CollectionNormalizationError(f"{label} must be non-empty", "STRING_EMPTY")
    return value


def _validate_current_collection(value: Any) -> Optional[str]:
    if value is None:
        raise CollectionNormalizationError("current_collection must be explicit; null has no executable collection target", "CURRENT_COLLECTION_INVALID")
    return _validate_nonempty_str(value, "current_collection")


def _validate_allowed_collections(value: Any) -> Tuple[str, ...]:
    if type(value) not in (list, tuple):
        raise CollectionNormalizationError("allowed_collections must be a list/tuple of exact strings", "ALLOWED_COLLECTIONS_INVALID")
    if not value:
        raise CollectionNormalizationError("allowed_collections must not be empty", "ALLOWED_COLLECTIONS_INVALID")
    items = tuple(_validate_nonempty_str(v, "allowed_collections entry") for v in value)
    if len(set(items)) != len(items):
        raise CollectionNormalizationError("allowed_collections must not contain duplicates", "ALLOWED_COLLECTIONS_INVALID")
    return tuple(sorted(items))


def _validate_digest(value: Any, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise CollectionNormalizationError(f"{label} must be a 64-character lowercase hex string", "SOURCE_DIGEST_INVALID")
    return value


def _plan_body(*, scene_id: str, expected_object_id: str, current_collection: str,
               target_collection: str, allowed_collections: Tuple[str, ...], source_digest: str) -> dict:
    correction_id = _digest({
        "correction_type": CORRECTION_TYPE,
        "scene_id": scene_id,
        "expected_object_id": expected_object_id,
        "current_collection": current_collection,
        "target_collection": target_collection,
        "allowed_collections": list(allowed_collections),
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
            "current_collection": current_collection,
            "target_collection": target_collection,
            "allowed_collections": list(allowed_collections),
        },
    }
    return {**body, "plan_id": _digest(body)}


def plan_object_collection_normalization(
    scene: SceneModel,
    source_report_digest: str,
    *,
    expected_object_id: Any,
    current_collection: Any,
    target_collection: Any,
    allowed_collections: Any,
) -> Mapping[str, Any]:
    source = _validate_digest(source_report_digest, "source_report_digest")
    object_id = _validate_nonempty_str(expected_object_id, "expected_object_id")
    current = _validate_current_collection(current_collection)
    target = _validate_nonempty_str(target_collection, "target_collection")
    allowed = _validate_allowed_collections(allowed_collections)
    if target == current:
        raise CollectionNormalizationError("already canonical; no normalization is required", "ALREADY_CANONICAL")
    if target not in allowed:
        raise CollectionNormalizationError("target_collection is outside the exact authorized allowlist", "TARGET_COLLECTION_INVALID")

    matches = [obj for obj in scene.objects if obj.object_id == object_id]
    if len(matches) != 1:
        raise CollectionNormalizationError("expected object id must resolve to exactly one object", "OBJECT_ID_RESOLUTION_INVALID")
    if matches[0].collection != current:
        raise CollectionNormalizationError("scene object collection does not match requested current_collection", "CURRENT_COLLECTION_MISMATCH")
    return _plan_body(
        scene_id=scene.scene_id,
        expected_object_id=object_id,
        current_collection=current,
        target_collection=target,
        allowed_collections=allowed,
        source_digest=source,
    )


def _replace_collection(scene: SceneModel, object_id: str, target_collection: str) -> SceneModel:
    return SceneModel(
        scene_id=scene.scene_id,
        unit_system=scene.unit_system,
        objects=tuple(
            ObjectModel(
                object_id=obj.object_id,
                name=obj.name,
                collection=target_collection if obj.object_id == object_id else obj.collection,
                parent_object_id=obj.parent_object_id,
                location=obj.location,
                scale=obj.scale,
                rotation=obj.rotation,
                visible=obj.visible,
                mesh=obj.mesh,
            )
            for obj in scene.objects
        ),
        coordinate_frame=scene.coordinate_frame,
        world_bounds=scene.world_bounds,
    )


def _scene_non_collection_payload(scene: SceneModel) -> dict:
    payload = _scene_payload(scene)
    for obj in payload["objects"]:
        obj.pop("collection")
    return payload


def _authorization_shape_is_valid(authorization: Mapping[str, Any]) -> bool:
    return type(authorization) is dict and set(authorization) == _AUTHORIZATION_FIELDS


def execute_object_collection_normalization(
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
        object_id = _validate_nonempty_str(params.get("expected_object_id"), "expected_object_id")
        current = _validate_current_collection(params.get("current_collection"))
        target = _validate_nonempty_str(params.get("target_collection"), "target_collection")
        allowed = _validate_allowed_collections(params.get("allowed_collections"))
        if target == current:
            return ExecutionOutcome(False, "PLAN_INVALID", "ALREADY_CANONICAL", source, None)
        if target not in allowed:
            return ExecutionOutcome(False, "PLAN_INVALID", "TARGET_COLLECTION_INVALID", source, None)
    except CollectionNormalizationError as exc:
        return ExecutionOutcome(False, "PLAN_INVALID", exc.code, source, None)

    if not _authorization_shape_is_valid(authorization):
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "AUTHORIZATION_INVALID", source, None)
    if authorization.get("decision") != "APPROVED" or authorization.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "AUTHORIZATION_INVALID", source, None)
    if authorization.get("correction_id") != plan.get("correction_id"):
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "CORRECTION_ID_MISMATCH", source, None)
    if authorization.get("plan_id") != plan.get("plan_id"):
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "PLAN_ID_MISMATCH", source, None)
    if authorization.get("source_report_digest") != plan.get("source_report_digest"):
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "SOURCE_REPORT_DIGEST_MISMATCH", source, None)

    scene_id = plan.get("scene_id")
    if type(scene_id) is not str or not scene_id:
        return ExecutionOutcome(False, "PLAN_INVALID", "SCENE_ID_INVALID", source, None)
    expected_plan = _plan_body(
        scene_id=scene_id,
        expected_object_id=object_id,
        current_collection=current,
        target_collection=target,
        allowed_collections=allowed,
        source_digest=source,
    )
    if plan.get("correction_id") != expected_plan["correction_id"] or plan.get("plan_id") != expected_plan["plan_id"]:
        return ExecutionOutcome(False, "PLAN_INVALID", "PLAN_ID_MISMATCH", source, None)

    before, fresh_digest = extractor()
    actual_digest = scene_digest(before)
    if fresh_digest != actual_digest:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "SOURCE_DIGEST_INVALID", actual_digest, None)
    if actual_digest != source:
        return ExecutionOutcome(False, "SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH", actual_digest, None)
    if before.scene_id != scene_id:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "SCENE_ID_MISMATCH", actual_digest, None)
    matches = [obj for obj in before.objects if obj.object_id == object_id]
    if len(matches) != 1:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "OBJECT_ID_RESOLUTION_INVALID", actual_digest, None)
    if matches[0].collection != current:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "CURRENT_COLLECTION_MISMATCH", actual_digest, None)
    if target not in allowed:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "TARGET_COLLECTION_INVALID", actual_digest, None)

    after = _replace_collection(before, object_id, target)
    changed = [
        (before_obj.object_id, before_obj.collection, after_obj.collection)
        for before_obj, after_obj in zip(before.objects, after.objects)
        if before_obj.collection != after_obj.collection
    ]
    if changed != [(object_id, current, target)]:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNEXPECTED_COLLECTION_CHANGES", actual_digest, None)
    if _scene_non_collection_payload(after) != _scene_non_collection_payload(before):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "NON_COLLECTION_STATE_CHANGED", actual_digest, None)
    if next(obj for obj in after.objects if obj.object_id == object_id).collection != target:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_COLLECTION_NOT_APPLIED", actual_digest, None)

    return ExecutionOutcome(True, "COMPLETED", None, actual_digest, scene_digest(after), after)
