"""Wave-7 bounded exact-duplicate vertex removal.

Pure canonical-model mutation only. No bpy, operators, persistence, recovery, or
implicit spatial tolerance is permitted here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel

CORRECTION_TYPE = "REMOVE_DUPLICATE_VERTICES"
PLANNER_VERSION = "1"
_ALLOWED_PARAMS = frozenset({"expected_duplicate_vertex_groups"})


class DuplicateVertexRemovalError(ValueError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DuplicateVertexPlan:
    correction_id: str
    plan_id: str
    source_report_digest: str
    target_object_id: str
    mesh_id: str
    expected_duplicate_vertex_groups: Tuple[Tuple[int, ...], ...]

    def to_dict(self) -> dict:
        return {
            "planner_version": PLANNER_VERSION,
            "correction_type": CORRECTION_TYPE,
            "correction_id": self.correction_id,
            "source_report_digest": self.source_report_digest,
            "target_object_id": self.target_object_id,
            "mesh_id": self.mesh_id,
            "params": {"expected_duplicate_vertex_groups": [list(g) for g in self.expected_duplicate_vertex_groups]},
            "plan_id": self.plan_id,
        }


@dataclass(frozen=True)
class ExecutionOutcome:
    ok: bool
    outcome: str
    failure_code: Optional[str]
    source_report_digest: str
    output_report_digest: Optional[str]
    scene: Optional[SceneModel] = None


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _find_object(scene: SceneModel, object_id: str) -> Optional[ObjectModel]:
    matches = [o for o in scene.objects if o.object_id == object_id]
    return matches[0] if len(matches) == 1 else None


def _validate_face_indices(mesh: MeshModel) -> None:
    vertex_count = len(mesh.vertices)
    for face_index, face in enumerate(mesh.faces):
        for vertex_index in face:
            if type(vertex_index) is not int or isinstance(vertex_index, bool):
                raise DuplicateVertexRemovalError(f"face {face_index} contains a non-integer vertex index", "FACE_INDEX_INVALID")
            if not (0 <= vertex_index < vertex_count):
                raise DuplicateVertexRemovalError(f"face {face_index} contains vertex index {vertex_index} outside 0..{vertex_count - 1}", "FACE_INDEX_OUT_OF_RANGE")


def _validate_coordinate(vertex: Any, index: int) -> Tuple[float, ...]:
    if type(vertex) not in (tuple, list):
        raise DuplicateVertexRemovalError(f"vertex {index} coordinates are not a tuple/list", "COORDINATE_TYPE_INVALID")
    if not vertex:
        raise DuplicateVertexRemovalError(f"vertex {index} coordinates are empty", "COORDINATE_EMPTY")
    result = tuple(vertex)
    for component in result:
        if type(component) not in (int, float) or isinstance(component, bool):
            raise DuplicateVertexRemovalError(f"vertex {index} contains a non-numeric coordinate", "COORDINATE_COMPONENT_INVALID")
        if component != component:
            raise DuplicateVertexRemovalError(f"vertex {index} contains NaN", "COORDINATE_NAN")
    return result


def _duplicate_groups(mesh: MeshModel) -> Tuple[Tuple[int, ...], ...]:
    _validate_face_indices(mesh)
    groups: Dict[Tuple[Any, ...], List[int]] = {}
    for index, vertex in enumerate(mesh.vertices):
        key = _validate_coordinate(vertex, index)
        groups.setdefault(key, []).append(index)
    result = [tuple(indices) for indices in groups.values() if len(indices) >= 2]
    result.sort()
    return tuple(result)


def _validate_groups(groups: Any, vertex_count: int) -> Tuple[Tuple[int, ...], ...]:
    if type(groups) not in (list, tuple):
        raise DuplicateVertexRemovalError("expected_duplicate_vertex_groups must be a tuple/list", "GROUPS_TYPE_INVALID")
    parsed: List[Tuple[int, ...]] = []
    seen = set()
    for group in groups:
        if type(group) not in (list, tuple):
            raise DuplicateVertexRemovalError("duplicate groups must be tuple/list values", "GROUP_TYPE_INVALID")
        if len(group) < 2:
            raise DuplicateVertexRemovalError("duplicate groups require at least two indices", "GROUP_SIZE_INVALID")
        values = tuple(group)
        if any(type(i) is not int or isinstance(i, bool) for i in values):
            raise DuplicateVertexRemovalError("duplicate indices must be exact integers", "INDEX_TYPE_INVALID")
        if tuple(sorted(set(values))) != values:
            raise DuplicateVertexRemovalError("duplicate groups must be sorted and unique", "GROUP_ORDER_INVALID")
        if any(i < 0 or i >= vertex_count for i in values):
            raise DuplicateVertexRemovalError("duplicate index outside vertex range", "INDEX_OUT_OF_RANGE")
        overlap = seen.intersection(values)
        if overlap:
            raise DuplicateVertexRemovalError("duplicate groups must be disjoint", "GROUP_OVERLAP")
        seen.update(values)
        parsed.append(values)
    result = tuple(parsed)
    if tuple(sorted(result)) != result:
        raise DuplicateVertexRemovalError("duplicate groups must be lexicographically sorted", "GROUP_LIST_ORDER_INVALID")
    return result


def _survivor_mapping(vertex_count: int, groups: Tuple[Tuple[int, ...], ...]) -> Dict[int, int]:
    """Map every original vertex index to the compact output index.

    Duplicate members map to their group's deterministic survivor; non-duplicate
    vertices map to themselves before compacting. Survivor order is the original
    index order, so output indices remain deterministic and stable.
    """
    survivor_for: Dict[int, int] = {index: index for index in range(vertex_count)}
    for group in groups:
        survivor = group[0]
        for index in group[1:]:
            survivor_for[index] = survivor

    survivors = [index for index in range(vertex_count) if survivor_for[index] == index]
    survivor_to_new = {old: new for new, old in enumerate(survivors)}
    return {index: survivor_to_new[survivor_for[index]] for index in range(vertex_count)}


def _face_edge_valence(faces: Tuple[Tuple[int, ...], ...]) -> Dict[Tuple[int, int], int]:
    valence: Dict[Tuple[int, int], int] = {}
    for face in faces:
        if len(face) < 2:
            continue
        for a, b in zip(face, face[1:] + face[:1]):
            edge = (a, b) if a <= b else (b, a)
            valence[edge] = valence.get(edge, 0) + 1
    return valence


def _face_collision_exists(mesh: MeshModel, groups: Tuple[Tuple[int, ...], ...]) -> bool:
    group_of = {index: group for group in groups for index in group}
    for face in mesh.faces:
        seen_groups = set()
        for index in face:
            group = group_of.get(index)
            if group is not None:
                if group in seen_groups:
                    return True
                seen_groups.add(group)
    return False


def _remapped_faces(mesh: MeshModel, mapping: Mapping[int, int]) -> Tuple[Tuple[int, ...], ...]:
    try:
        return tuple(tuple(mapping[index] for index in face) for face in mesh.faces)
    except KeyError as exc:
        raise DuplicateVertexRemovalError(f"face references unmapped vertex {exc.args[0]}", "FACE_REMAP_INVALID")


def _face_image_collision_exists(source_faces: Tuple[Tuple[int, ...], ...], remapped_faces: Tuple[Tuple[int, ...], ...]) -> bool:
    seen: Dict[Tuple[int, ...], int] = {}
    for source_index, face in enumerate(source_faces):
        prior = seen.get(face)
        if prior is not None:
            raise DuplicateVertexRemovalError(f"source mesh already contains duplicate face images at {prior} and {source_index}", "SOURCE_DUPLICATE_FACE")
        seen[face] = source_index
    seen_output: Dict[Tuple[int, ...], int] = {}
    for source_index, face in enumerate(remapped_faces):
        prior = seen_output.get(face)
        if prior is not None and prior != source_index:
            return True
        seen_output[face] = source_index
    return False


def _new_nonmanifold_edges(source_faces: Tuple[Tuple[int, ...], ...], remapped_faces: Tuple[Tuple[int, ...], ...], mapping: Mapping[int, int]) -> bool:
    """Detect non-manifold edge valence newly created by duplicate-vertex quotienting."""
    source_valence = _face_edge_valence(source_faces)
    output_valence = _face_edge_valence(remapped_faces)
    source_edges_for_output: Dict[Tuple[int, int], set] = {}

    for face in source_faces:
        if len(face) < 2:
            continue
        for a, b in zip(face, face[1:] + face[:1]):
            old_edge = (a, b) if a <= b else (b, a)
            new_a = mapping[a]
            new_b = mapping[b]
            new_edge = (new_a, new_b) if new_a <= new_b else (new_b, new_a)
            source_edges_for_output.setdefault(new_edge, set()).add(old_edge)

    for new_edge, count in output_valence.items():
        if count <= 2:
            continue
        old_edges = source_edges_for_output.get(new_edge, set())
        if len(old_edges) > 1:
            return True
        if len(old_edges) != 1:
            return True
        old_edge = next(iter(old_edges))
        if source_valence.get(old_edge, 0) != count:
            return True
    return False


def _collision_flags(mesh: MeshModel, groups: Tuple[Tuple[int, ...], ...]) -> Tuple[bool, bool, bool]:
    if _face_collision_exists(mesh, groups):
        return True, False, False
    mapping = _survivor_mapping(len(mesh.vertices), groups)
    remapped = _remapped_faces(mesh, mapping)
    face_collision = _face_image_collision_exists(mesh.faces, remapped)
    repeated_vertex = any(len(face) != len(set(face)) for face in remapped)
    new_nonmanifold = _new_nonmanifold_edges(mesh.faces, remapped, mapping)
    return repeated_vertex, face_collision, new_nonmanifold


def _plan_body(*, target_object_id: str, mesh_id: str, expected: Tuple[Tuple[int, ...], ...], source_digest: str) -> dict:
    correction_id = _digest({
        "correction_type": CORRECTION_TYPE,
        "target_object_id": target_object_id,
        "mesh_id": mesh_id,
        "expected_duplicate_vertex_groups": [list(group) for group in expected],
        "source_report_digest": source_digest,
    })
    body = {
        "planner_version": PLANNER_VERSION,
        "correction_type": CORRECTION_TYPE,
        "correction_id": correction_id,
        "source_report_digest": source_digest,
        "target_object_id": target_object_id,
        "mesh_id": mesh_id,
        "params": {"expected_duplicate_vertex_groups": [list(group) for group in expected]},
    }
    return {**body, "plan_id": _digest(body)}


def plan_duplicate_vertex_removal(scene: SceneModel, source_report_digest: str, *, target_object_id: str, expected_duplicate_vertex_groups: Any) -> Mapping[str, Any]:
    if type(source_report_digest) is not str or len(source_report_digest) != 64:
        raise DuplicateVertexRemovalError("source report digest must be a 64-character string", "SOURCE_DIGEST_INVALID")
    if type(target_object_id) is not str or not target_object_id:
        raise DuplicateVertexRemovalError("target object id is required", "TARGET_OBJECT_INVALID")
    target = _find_object(scene, target_object_id)
    if target is None or target.mesh is None:
        raise DuplicateVertexRemovalError("target object must resolve to one mesh", "TARGET_NOT_FOUND")
    expected = _validate_groups(expected_duplicate_vertex_groups, len(target.mesh.vertices))
    actual = _duplicate_groups(target.mesh)
    if actual != expected:
        raise DuplicateVertexRemovalError("authorized groups must exactly equal current duplicate grouping", "DUPLICATE_GROUPS_MISMATCH")
    repeated_vertex, face_collision, nonmanifold = _collision_flags(target.mesh, expected)
    if repeated_vertex:
        raise DuplicateVertexRemovalError("duplicate collapse would create repeated face vertex indices", "FACE_VERTEX_COLLISION")
    if face_collision:
        raise DuplicateVertexRemovalError("duplicate collapse would create duplicate face images", "FACE_IMAGE_COLLISION")
    if nonmanifold:
        raise DuplicateVertexRemovalError("duplicate collapse would introduce non-manifold edge valence", "NONMANIFOLD_INTRODUCED")
    return _plan_body(target_object_id=target.object_id, mesh_id=target.mesh.mesh_id, expected=expected, source_digest=source_report_digest)


def _replace_target(scene: SceneModel, target_id: str, new_mesh: MeshModel) -> SceneModel:
    objects = tuple(ObjectModel(object_id=o.object_id, name=o.name, collection=o.collection, parent_object_id=o.parent_object_id, location=o.location, scale=o.scale, rotation=o.rotation, visible=o.visible, mesh=new_mesh if o.object_id == target_id else o.mesh) for o in scene.objects)
    return SceneModel(scene_id=scene.scene_id, unit_system=scene.unit_system, objects=objects, coordinate_frame=scene.coordinate_frame, world_bounds=scene.world_bounds)


def execute_remove_duplicate_vertices(plan: Mapping[str, Any], authorization: Mapping[str, Any], *, extractor: Callable[[], Tuple[SceneModel, str]]) -> ExecutionOutcome:
    source = plan.get("source_report_digest")
    if plan.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "PLAN_INVALID", "CORRECTION_TYPE_MISMATCH", str(source), None)
    params = plan.get("params")
    if type(params) is not dict or set(params) != _ALLOWED_PARAMS:
        return ExecutionOutcome(False, "PLAN_INVALID", "PARAMS_INVALID", str(source), None)
    try:
        expected = _validate_groups(params["expected_duplicate_vertex_groups"], 1 << 30)
    except DuplicateVertexRemovalError as exc:
        return ExecutionOutcome(False, "PLAN_INVALID", exc.code, str(source), None)
    if authorization.get("decision") != "APPROVED" or authorization.get("correction_type") != CORRECTION_TYPE:
        return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", "AUTHORIZATION_INVALID", str(source), None)
    for key in ("correction_id", "plan_id", "source_report_digest"):
        if authorization.get(key) != plan.get(key):
            return ExecutionOutcome(False, "AUTHORIZATION_REFUSED", key.upper() + "_MISMATCH", str(source), None)

    target_id = plan.get("target_object_id")
    mesh_id = plan.get("mesh_id")
    expected_plan = _plan_body(target_object_id=target_id, mesh_id=mesh_id, expected=expected, source_digest=source)
    if plan.get("correction_id") != expected_plan["correction_id"] or plan.get("plan_id") != expected_plan["plan_id"]:
        return ExecutionOutcome(False, "PLAN_INVALID", "PLAN_ID_MISMATCH", str(source), None)

    before, fresh_digest = extractor()
    if fresh_digest != source:
        return ExecutionOutcome(False, "SOURCE_MISMATCH", "SOURCE_DIGEST_MISMATCH", fresh_digest, None)
    target = _find_object(before, target_id)
    if target is None or target.mesh is None or target.mesh.mesh_id != mesh_id:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "TARGET_MISMATCH", fresh_digest, None)
    try:
        actual = _duplicate_groups(target.mesh)
        expected = _validate_groups(expected, len(target.mesh.vertices))
    except DuplicateVertexRemovalError as exc:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", exc.code, fresh_digest, None)
    if actual != expected:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "DUPLICATE_GROUPS_MISMATCH", fresh_digest, None)
    try:
        repeated_vertex, face_collision, nonmanifold = _collision_flags(target.mesh, expected)
    except DuplicateVertexRemovalError as exc:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", exc.code, fresh_digest, None)
    if repeated_vertex:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "FACE_VERTEX_COLLISION", fresh_digest, None)
    if face_collision:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "FACE_IMAGE_COLLISION", fresh_digest, None)
    if nonmanifold:
        return ExecutionOutcome(False, "PRECONDITION_FAILED", "NONMANIFOLD_INTRODUCED", fresh_digest, None)

    mapping = _survivor_mapping(len(target.mesh.vertices), expected)
    removed = {index for group in expected for index in group[1:]}
    new_mesh = MeshModel(mesh_id=target.mesh.mesh_id, vertices=tuple(target.mesh.vertices[i] for i in range(len(target.mesh.vertices)) if i not in removed), faces=_remapped_faces(target.mesh, mapping), normals=target.mesh.normals, uvs=target.mesh.uvs, materials=target.mesh.materials, local_frame_id=target.mesh.local_frame_id)
    after = _replace_target(before, target_id, new_mesh)

    after_target = _find_object(after, target_id)
    if after_target is None or after_target.mesh is None:
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_MISSING", fresh_digest, None)
    if _duplicate_groups(after_target.mesh):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "DUPLICATE_VERTICES_REMAIN", fresh_digest, None)
    if any(len(face) != len(set(face)) for face in after_target.mesh.faces):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "FACE_VERTEX_COLLISION", fresh_digest, None)
    if len(set(after_target.mesh.faces)) != len(after_target.mesh.faces):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "DUPLICATE_FACE_CREATED", fresh_digest, None)
    if _new_nonmanifold_edges(target.mesh.faces, after_target.mesh.faces, mapping):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "NONMANIFOLD_INTRODUCED", fresh_digest, None)
    if len(after.objects) != len(before.objects) or tuple(o.object_id for o in after.objects) != tuple(o.object_id for o in before.objects):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "OBJECT_IDENTITY_CHANGED", fresh_digest, None)
    for before_obj, after_obj in zip(before.objects, after.objects):
        if before_obj.object_id == target_id:
            if (before_obj.name, before_obj.collection, before_obj.parent_object_id, before_obj.location, before_obj.scale, before_obj.rotation, before_obj.visible) != (after_obj.name, after_obj.collection, after_obj.parent_object_id, after_obj.location, after_obj.scale, after_obj.rotation, after_obj.visible):
                return ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_OBJECT_STATE_CHANGED", fresh_digest, None)
        elif before_obj != after_obj:
            return ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNRELATED_OBJECT_CHANGED", fresh_digest, None)
    expected_faces = _remapped_faces(target.mesh, mapping)
    if after_target.mesh.faces != expected_faces or len(after_target.mesh.faces) != len(target.mesh.faces):
        return ExecutionOutcome(False, "POSTCONDITION_FAILED", "FACE_REMAP_MISMATCH", fresh_digest, None)
    output_digest = _digest({"mesh_id": after_target.mesh.mesh_id, "vertices": after_target.mesh.vertices, "faces": after_target.mesh.faces})
    return ExecutionOutcome(True, "CORRECTION_APPLIED", None, fresh_digest, output_digest, after)
