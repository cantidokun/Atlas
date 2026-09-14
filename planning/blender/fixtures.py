"""Deterministic Blender extraction payload fixtures (JSON-native, language-agnostic).

Each fixture is a plain dict conforming to :mod:`planning.blender.extraction_payload` (
``PAYLOAD_SCHEMA_VERSION`` "1"), used by adapter tests and the (future live) extraction primitive
to feed the kernel WITHOUT Blender. The same fixture always produces the same SceneModel and the
same SceneReport (deterministic conversion + report).
"""

from planning.blender.extraction_payload import (
    PAYLOAD_SCHEMA_VERSION,
    payload_to_scene_model,
    validate_payload_schema,
)
from planning.blender.kernel import run_scene_health, soccer_field_profile_default


def _obj(object_id, name, *, collection=None, parent_object_id=None, location=(0, 0, 0),
         scale=(1, 1, 1), rotation=(1.0, 0.0, 0.0, 0.0), visible=True, mesh=None):
    return {
        "object_id": object_id,
        "name": name,
        "collection": collection,
        "parent_object_id": parent_object_id,
        "location": [float(v) for v in location],
        "scale": [float(v) for v in scale],
        "rotation": [float(v) for v in rotation],
        "visible": visible,
        "mesh": mesh,
    }


HEALTHY_SCENE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "atlas_soccer_pitch_v0",
    "unit_system": "METERS",
    "coordinate_frame": "blender_world",
    "world_bounds": ([-30.0, -20.0, 0.0], [30.0, 20.0, 8.0]),
    "objects": [
        _obj("pitch", "pitch", collection="Field",
             mesh={
                 "mesh_id": "pitch_mesh",
                 "vertices": [
                     [-30.0, -20.0, 0.0], [30.0, -20.0, 0.0],
                     [-30.0, 20.0, 0.0], [30.0, 20.0, 0.0],
                 ],
                 "faces": [[0, 1, 2], [1, 3, 2]],
                 "normals": [[0, 0, 1], [0, 0, 1]],
                 "materials": ["AstroTurf"],
             }),
        _obj("goal_left", "goal.left.post", collection="Goals"),
        _obj("goal_right", "goal.right.post", collection="Goals"),
    ],
}

HEALTHY_MESH_WITH_NORMALS = dict(HEALTHY_SCENE)
HEALTHY_MESH_WITHOUT_NORMALS = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "no_normals",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch",
             mesh={
                 "mesh_id": "m",
                 "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 "faces": [[0, 1, 2]],
             }),
        _obj("goal_left", "goal_left"),
        _obj("goal_right", "goal_right"),
    ],
}

INVALID_INDEX_MESH = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "invalid_index",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch",
             mesh={"mesh_id": "m", "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 99]]}),
        _obj("goal_left", "goal_left"),
        _obj("goal_right", "goal_right"),
    ],
}

DUPLICATE_DEGENERATE_MESH = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "dup_deg",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch",
             mesh={
                 "mesh_id": "m",
                 "vertices": [[0, 0, 0], [0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0]],
                 "faces": [[0, 1, 2], [3, 1, 2], [0, 1, 4]],
             }),
        _obj("goal_left", "goal_left"),
        _obj("goal_right", "goal_right"),
    ],
}

HIERARCHY_SCENE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "hierarchy",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch", parent_object_id="ghost_missing"),
        _obj("goal_left", "goal_left"),
        _obj("goal_right", "goal_right"),
    ],
}

UNIT_SCALE_SCENE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "bad_unit",
    "unit_system": "INCHES",
    "objects": [
        _obj("pitch", "pitch", scale=(0, 0, 0)),
        _obj("goal_left", "goal_left", collection="Offworld"),
        _obj("goal_right", "goal_right"),
    ],
}

EMPTY_SCENE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "empty",
    "unit_system": "METERS",
    "objects": [],
}

MESHLESS_SCENE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "meshless",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch"),
        _obj("goal_left", "goal_left"),
        _obj("goal_right", "goal_right"),
    ],
}

# --- Transform / topology adversarial + representative fixtures (post-remediation) ---------
# Mesh vertices are OBJECT-LOCAL; the object carries the explicit pose. Same local mesh under two
# different poses -> different world-space bounds/findings while local data stays identical.

_OBJ_MESH = {
    "mesh_id": "m",
    "vertices": [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [10.0, 10.0, 0.0]],
    "faces": [[0, 1, 2], [1, 3, 2]],
}

TRANSFORM_IDENTITY = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_identity",
    "unit_system": "METERS",
    "objects": [_obj("pitch", "pitch", mesh=dict(_OBJ_MESH))],
}

TRANSFORM_TRANSLATED = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_trans",
    "unit_system": "METERS",
    "objects": [_obj("pitch", "pitch", location=(100.0, 0.0, 0.0), mesh=dict(_OBJ_MESH))],
}

TRANSFORM_ROTATED = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_rot",
    "unit_system": "METERS",
    "objects": [_obj("pitch", "pitch",
                     rotation=(0.9238795325112865, 0.0, 0.0, 0.3826834323650898),  # +45deg about Z
                     mesh=dict(_OBJ_MESH))],
}

TRANSFORM_UNIFORM_SCALE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_uscale",
    "unit_system": "METERS",
    "objects": [_obj("pitch", "pitch", scale=(100.0, 100.0, 100.0), mesh=dict(_OBJ_MESH))],
}

TRANSFORM_NONUNIFORM_SCALE = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_nscale",
    "unit_system": "METERS",
    "objects": [_obj("pitch", "pitch", scale=(1.0, 5.0, 1.0), mesh=dict(_OBJ_MESH))],
}

TRANSFORM_PARENT_TRANSLATED = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_ptrans",
    "unit_system": "METERS",
    "objects": [
        _obj("root", "root", location=(10.0, 0.0, 0.0)),
        _obj("pitch", "pitch", parent_object_id="root",
             location=(1.0, 0.0, 0.0), mesh=dict(_OBJ_MESH)),
    ],
}

TRANSFORM_PARENT_ROTATED = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_prot",
    "unit_system": "METERS",
    "objects": [
        _obj("root", "root", location=(5.0, 0.0, 0.0),
             rotation=(0.7071067811865476, 0.0, 0.0, 0.7071067811865476)),  # +90deg about Z
        _obj("pitch", "pitch", parent_object_id="root", mesh=dict(_OBJ_MESH)),
    ],
}

TRANSFORM_PARENT_SCALED = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_pscale",
    "unit_system": "METERS",
    "objects": [
        _obj("root", "root", scale=(10.0, 10.0, 10.0)),
        _obj("pitch", "pitch", parent_object_id="root", mesh=dict(_OBJ_MESH)),
    ],
}

TRANSFORM_NESTED_CHAIN = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_nested",
    "unit_system": "METERS",
    "objects": [
        _obj("grand", "grand", location=(1.0, 0.0, 0.0), scale=(2.0, 2.0, 2.0)),
        _obj("parent", "parent", parent_object_id="grand", location=(3.0, 0.0, 0.0)),
        _obj("pitch", "pitch", parent_object_id="parent", location=(5.0, 0.0, 0.0),
             mesh=dict(_OBJ_MESH)),
    ],
}

TRANSFORM_MISSING_PARENT = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_missing_parent",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch", parent_object_id="ghost", mesh=dict(_OBJ_MESH)),
    ],
}

TRANSFORM_CYCLIC_PARENT = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "tf_cycle",
    "unit_system": "METERS",
    "objects": [
        _obj("a", "a", parent_object_id="b"),
        _obj("b", "b", parent_object_id="a"),
        _obj("pitch", "pitch", parent_object_id="a", mesh=dict(_OBJ_MESH)),
    ],
}

MIXED_TOPOLOGY_MESH = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "mixed_topology",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch",
             mesh={
                 "mesh_id": "m",
                 "vertices": [
                     [0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0],
                     [0, 20, 0], [10, 20, 0],
                 ],
                 # triangle, quad, n-gon (5) mixed in one mesh
                 "faces": [[0, 1, 2], [0, 1, 3, 4], [0, 1, 2, 3, 4, 5]],
             }),
    ],
}

PER_FACE_NORMALS_MESH = {
    "schema_version": PAYLOAD_SCHEMA_VERSION,
    "scene_id": "per_face_normals",
    "unit_system": "METERS",
    "objects": [
        _obj("pitch", "pitch",
             mesh={
                 "mesh_id": "m",
                 "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
                 "faces": [[0, 1, 2], [1, 3, 2]],
                 "normals": [[0, 0, 1], [0, 0, 1]],  # genuine per-face (face order)
             }),
    ],
}

ALL_FIXTURES = {
    "healthy": HEALTHY_SCENE,
    "healthy_without_normals": HEALTHY_MESH_WITHOUT_NORMALS,
    "invalid_index_mesh": INVALID_INDEX_MESH,
    "duplicate_degenerate_mesh": DUPLICATE_DEGENERATE_MESH,
    "hierarchy": HIERARCHY_SCENE,
    "unit_scale": UNIT_SCALE_SCENE,
    "empty": EMPTY_SCENE,
    "meshless": MESHLESS_SCENE,
    "transform_identity": TRANSFORM_IDENTITY,
    "transform_translated": TRANSFORM_TRANSLATED,
    "transform_rotated": TRANSFORM_ROTATED,
    "transform_uniform_scale": TRANSFORM_UNIFORM_SCALE,
    "transform_nonuniform_scale": TRANSFORM_NONUNIFORM_SCALE,
    "transform_parent_translated": TRANSFORM_PARENT_TRANSLATED,
    "transform_parent_rotated": TRANSFORM_PARENT_ROTATED,
    "transform_parent_scaled": TRANSFORM_PARENT_SCALED,
    "transform_nested_chain": TRANSFORM_NESTED_CHAIN,
    "transform_missing_parent": TRANSFORM_MISSING_PARENT,
    "transform_cyclic_parent": TRANSFORM_CYCLIC_PARENT,
    "mixed_topology_mesh": MIXED_TOPOLOGY_MESH,
    "per_face_normals_mesh": PER_FACE_NORMALS_MESH,
}


def payload_to_scene(payload):
    """Deterministically convert a payload dict into a canonical SceneModel."""
    return payload_to_scene_model(payload)


def scene_report_for_fixture(name):
    """Deterministic fixture -> SceneReport (kernel default profile)."""
    if name not in ALL_FIXTURES:
        raise KeyError(f"unknown fixture {name!r}")
    scene = payload_to_scene(ALL_FIXTURES[name])
    return run_scene_health(scene, soccer_field_profile_default())


def report_for_payload(payload):
    """Deterministic payload -> SceneReport (kernel default profile)."""
    scene = payload_to_scene(payload)
    return run_scene_health(scene, soccer_field_profile_default())