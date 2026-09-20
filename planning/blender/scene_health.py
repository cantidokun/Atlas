"""Deterministic scene/organization health checks (kernel core, scene level).

Pure Python, no ``bpy``. Operates on the canonical ``SceneModel`` and a
``SoccerFieldValidationProfile`` (see :mod:`planning.blender.soccer_field_profile`), and returns
a list of ``Finding`` objects. Generic organization rules (names, hierarchy, ids, transforms) are
engine-independent; Atlas-specific plausibility (envelope, required roles) is applied through the
profile so the generic kernel stays reusable and C++-replacable.

Complexity: O(scene_size) with a per-object/per-edge pass; the AABB overlap check is O(m log m)
per axis after sorting by min-corner (no arbitrary quadratic meshing).
"""

from collections import defaultdict
from math import isfinite
from typing import Dict, List, Optional, Sequence, Tuple

from planning.blender.finding_codes import FindingCode
from planning.blender.scene_model import ObjectModel, SceneModel
from planning.blender.scene_report import Finding
from planning.blender.soccer_field_profile import SoccerFieldValidationProfile
from planning.blender.transforms import world_points



def _object_world_points(scene: SceneModel, object_: ObjectModel) -> Optional[Tuple[Tuple[float, float, float], ...]]:
    """World-space copy of an object's mesh vertices via its composed pose.

    Uses the SINGLE world-pose engine (transforms.world_points). Returns None when the object has
    no mesh/vertices or its parent chain cannot be resolved (missing/cyclic parent).
    """
    if object_.mesh is None or not object_.mesh.vertices:
        return None
    by_id = {o.object_id: o for o in scene.objects}
    return world_points(by_id, object_.object_id, object_.mesh.vertices)


def _aabb(
    scene: SceneModel,
    object_: ObjectModel,
) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """World-space AABB of an object's mesh vertices (via its composed pose), or None."""
    wpts = _object_world_points(scene, object_)
    if wpts is None:
        return None
    xs = [v[0] for v in wpts]
    ys = [v[1] for v in wpts]
    zs = [v[2] for v in wpts]
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _object_mesh_bounds_span(scene: SceneModel, object_: ObjectModel) -> Optional[Tuple[float, float, float]]:
    aabb = _aabb(scene, object_)
    if aabb is None:
        return None
    (mn, mx) = aabb
    return (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])


def check_scene(scene: SceneModel, profile: SoccerFieldValidationProfile) -> List[Finding]:
    """Run all deterministic scene-level checks and return findings (stable order)."""
    findings: List[Finding] = []

    _collect_duplicate_object_ids(scene, findings)
    _collect_unit_validity(scene, profile, findings)
    _collect_origin_validity(scene, profile, findings)
    for obj in scene.objects:
        _collect_object_name(obj, profile, findings)
        _collect_object_collection(obj, profile, findings)
        _collect_transform_validity(obj, findings)
    _collect_hierarchy_validity(scene, findings)
    _collect_bounds_overlap(scene, findings)
    # Everything is deterministic; sort by stable key.
    findings.sort(key=lambda f: (f.code.value, f.object_id or "", f.mesh_id or ""))
    return findings


def _collect_duplicate_object_ids(scene: SceneModel, findings: List[Finding]) -> None:
    seen: Dict[str, int] = {}
    for i, obj in enumerate(scene.objects):
        if obj.object_id in seen:
            findings.append(Finding(
                code=FindingCode.OBJECT_ID_DUPLICATE,
                object_id=obj.object_id,
                measured={"index_a": seen[obj.object_id], "index_b": i},
                message=f"duplicate object id {obj.object_id!r}",
            ))
        else:
            seen[obj.object_id] = i


def _collect_unit_validity(scene: SceneModel, profile: SoccerFieldValidationProfile, findings: List[Finding]) -> None:
    if profile.allowed_units and scene.unit_system not in profile.allowed_units:
        findings.append(Finding(
            code=FindingCode.SCENE_UNIT_INVALID,
            measured={"unit_system": scene.unit_system},
            expected={"allowed_units": sorted(profile.allowed_units)},
            message=f"scene unit system {scene.unit_system!r} not allowed by profile",
        ))


def _collect_origin_validity(scene: SceneModel, profile: SoccerFieldValidationProfile, findings: List[Finding]) -> None:
    # A declared coordinate frame/origin is plausible when origin is near the profile origin
    # (origin is the default (0,0,0) for the frame primitive). If a frame is declared with a
    # nonzero origin not inside the envelope, flag it as plausible-organization warning.
    if scene.coordinate_frame and scene.world_bounds:
        (mn, mx) = scene.world_bounds
        # world bounds entirely outside the profile envelope is suspicious, but checked by
        # MESH_SCALE_OUT_OF_RANGE on per-object; here we only flag non-finite/empty.
        if not all(isfinite(c) for corner in (mn, mx) for c in corner):
            findings.append(Finding(
                code=FindingCode.SCENE_ORIGIN_INVALID,
                measured={"world_bounds": [list(mn), list(mx)]},
                message="scene world bounds contain non-finite coordinates",
            ))


def _collect_object_name(obj: ObjectModel, profile: SoccerFieldValidationProfile, findings: List[Finding]) -> None:
    if profile.name_pattern is None:
        return
    import re
    if not profile.name_pattern.match(obj.name):
        findings.append(Finding(
            code=FindingCode.OBJECT_NAME_INVALID,
            object_id=obj.object_id,
            measured={"name": obj.name},
            expected={"pattern": profile.name_pattern.pattern},
            message=f"object {obj.object_id!r} name {obj.name!r} violates the naming convention",
        ))


def _collect_object_collection(obj: ObjectModel, profile: SoccerFieldValidationProfile, findings: List[Finding]) -> None:
    if profile.allowed_collections is None:
        return
    if obj.collection is not None and obj.collection not in profile.allowed_collections:
        findings.append(Finding(
            code=FindingCode.OBJECT_COLLECTION_INVALID,
            object_id=obj.object_id,
            measured={"collection": obj.collection},
            expected={"allowed_collections": sorted(profile.allowed_collections)},
            message=f"object {obj.object_id!r} in disallowed collection {obj.collection!r}",
        ))


def _collect_transform_validity(obj: ObjectModel, findings: List[Finding]) -> None:
    for name, vec in (("location", obj.location), ("scale", obj.scale)):
        if any(not isfinite(c) for c in vec):
            findings.append(Finding(
                code=FindingCode.OBJECT_TRANSFORM_INVALID,
                object_id=obj.object_id,
                measured={name: list(vec)},
                message=f"object {obj.object_id!r} has non-finite {name}",
            ))
    if any(abs(c) < 1e-9 for c in obj.scale):
        findings.append(Finding(
            code=FindingCode.OBJECT_TRANSFORM_INVALID,
            object_id=obj.object_id,
            measured={"scale": list(obj.scale)},
            message=f"object {obj.object_id!r} has zero scale (invalid)",
        ))


def _collect_hierarchy_validity(scene: SceneModel, findings: List[Finding]) -> None:
    ids = {o.object_id for o in scene.objects}
    children: Dict[str, List[str]] = defaultdict(list)
    for obj in scene.objects:
        if obj.parent_object_id is not None:
            children[obj.parent_object_id].append(obj.object_id)
            if obj.parent_object_id not in ids:
                findings.append(Finding(
                    code=FindingCode.OBJECT_HIERARCHY_INVALID,
                    object_id=obj.object_id,
                    measured={"parent": obj.parent_object_id},
                    message=f"object {obj.object_id!r} references unknown parent {obj.parent_object_id!r}",
                ))
    # Detect cycles by iterative DFS on the (possible) parent graph.
    visiting: set = set()
    visited: set = set()
    # Use a set so each cycle participant is emitted exactly once; the previous list
    # accumulation could depend on unordered object-ID traversal and change report digests.
    cycle_nodes: set[str] = set()

    def visit(node: str, stack: List[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            # Record every participant in the detected cycle exactly once.
            if node in stack:
                cycle_nodes.update(stack[stack.index(node):])
            else:
                cycle_nodes.add(node)
            return
        visiting.add(node)
        stack.append(node)
        for child in children.get(node, ()):
            visit(child, stack)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for oid in ids:
        visit(oid, [])
    for node in cycle_nodes:
        findings.append(Finding(
            code=FindingCode.OBJECT_HIERARCHY_INVALID,
            object_id=node,
            message=f"object {node!r} participates in a hierarchy cycle",
        ))


def _collect_bounds_overlap(scene: SceneModel, findings: List[Finding]) -> None:
    """Detect AABB overlap between distinct objects (suspicious, policy-dependent).

    Deliberately conservative: reports overlaps that are NOT exact containment of a smaller
    object within a larger one (containment is normalized, not necessarily an error). This is a
    single coarse AABB signal; geometric detail is left to the C++-replacable seam.
    """
    boxes: List[Tuple[str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]]] = []
    for obj in scene.objects:
        aabb = _aabb(scene, obj)
        if aabb is not None:
            boxes.append((obj.object_id, aabb))
    # Sort by min-x for a sweep; O(m log m).
    boxes.sort(key=lambda item: item[1][0][0])
    for i in range(len(boxes)):
        oid_i, (mn_i, mx_i) = boxes[i]
        # Only look at later boxes whose min-x precedes our max-x (classic sweep).
        j = i + 1
        while j < len(boxes) and boxes[j][1][0][0] < mx_i[0]:
            oid_j, (mn_j, mx_j) = boxes[j]
            if _aabbs_overlap((mn_i, mx_i), (mn_j, mx_j)):
                # Skip pure containment (one inside other) — that is normalized, not overlap.
                if not (_contains((mn_i, mx_i), (mn_j, mx_j)) or _contains((mn_j, mx_j), (mn_i, mx_i))):
                    findings.append(Finding(
                        code=FindingCode.OBJECT_BOUNDS_OVERLAP,
                        object_id=oid_i,
                        measured={"other": oid_j},
                        message=f"AABB of {oid_i!r} overlaps {oid_j!r}",
                    ))
            j += 1


def _aabbs_overlap(a, b) -> bool:
    ((ax0, ay0, az0), (ax1, ay1, az1)) = a
    ((bx0, by0, bz0), (bx1, by1, bz1)) = b
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0 or az1 < bz0 or bz1 < az0)


def _contains(outer, inner) -> bool:
    ((ox0, oy0, oz0), (ox1, oy1, oz1)) = outer
    ((ix0, iy0, iz0), (ix1, iy1, iz1)) = inner
    return (ox0 <= ix0 and ix1 <= ox1 and oy0 <= iy0 and iy1 <= oy1 and oz0 <= iz0 and iz1 <= oz1)