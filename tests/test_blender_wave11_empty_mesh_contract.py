from __future__ import annotations

import hashlib
import json

import pytest

from planning.blender import MeshModel, ObjectModel, SceneModel, parse_scene_report_input, run_scene_health, scene_input_digest, soccer_field_profile
from planning.blender.scene_model import SceneReportInputError


def _canonical_mesh_payload(mesh: MeshModel) -> dict:
    return {
        "mesh_id": mesh.mesh_id,
        "vertices": [list(v) for v in mesh.vertices],
        "faces": [list(f) for f in mesh.faces],
        "normals": [list(v) for v in mesh.normals],
        "uvs": [list(v) for v in mesh.uvs],
        "materials": list(mesh.materials),
        "local_frame_id": mesh.local_frame_id,
    }


def test_empty_mesh_and_zero_face_mesh_are_distinct_from_absent_mesh():
    empty = MeshModel(mesh_id="empty", vertices=(), faces=(), materials=("mat",))
    zero_face = MeshModel(mesh_id="zero", vertices=((0.0, 0.0, 0.0),), faces=())
    absent = ObjectModel(object_id="o", name="o", mesh=None)
    present_empty = ObjectModel(object_id="e", name="e", mesh=empty)
    present_zero_face = ObjectModel(object_id="z", name="z", mesh=zero_face)

    assert empty != zero_face
    assert present_empty.mesh is not None
    assert present_zero_face.mesh is not None
    assert absent.mesh is None


def test_empty_mesh_roundtrip_and_digest_are_deterministic():
    raw = {
        "scene_id": "s",
        "unit_system": "METERS",
        "objects": [{
            "object_id": "empty",
            "name": "empty",
            "mesh": {
                "mesh_id": "m",
                "vertices": [],
                "faces": [],
                "materials": ["mat"],
            },
        }],
    }
    first = parse_scene_report_input(raw)
    second = parse_scene_report_input(raw)
    mesh = first.objects[0].mesh
    assert mesh is not None
    assert mesh.vertices == ()
    assert mesh.faces == ()
    assert first == second
    assert scene_input_digest(first) == scene_input_digest(second)


def test_zero_face_mesh_with_vertices_survives_kernel():
    mesh = MeshModel(mesh_id="m", vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), faces=())
    scene = SceneModel(
        scene_id="s",
        unit_system="METERS",
        objects=(
            ObjectModel(object_id="pitch", name="pitch", mesh=mesh),
            ObjectModel(object_id="goal_left", name="goal_left"),
            ObjectModel(object_id="goal_right", name="goal_right"),
        ),
    )
    report = run_scene_health(scene, soccer_field_profile())
    assert report.scene_metrics["mesh_metrics"]["m"]["vertices"] == 2
    assert report.scene_metrics["mesh_metrics"]["m"]["faces"] == 0
    assert all(f.mesh_id != "m" or f.code.value not in {"MESH_INVALID_INDEX", "MESH_DUPLICATE_FACE", "MESH_DEGENERATE_FACE"} for f in report.findings)


def test_empty_vertices_with_nonempty_faces_fails_closed():
    with pytest.raises(SceneReportInputError):
        MeshModel(mesh_id="bad", vertices=(), faces=((0, 1, 2),))


def test_zero_face_per_face_metadata_cannot_be_fabricated():
    with pytest.raises(SceneReportInputError):
        MeshModel(mesh_id="bad_normals", vertices=((0.0, 0.0, 0.0),), faces=(), normals=((0.0, 0.0, 1.0),))
    with pytest.raises(SceneReportInputError):
        MeshModel(mesh_id="bad_uvs", vertices=((0.0, 0.0, 0.0),), faces=(), uvs=((0.0, 0.0),))


def test_empty_mesh_payload_digest_is_stable():
    mesh = MeshModel(mesh_id="m", vertices=(), faces=())
    a = json.dumps(_canonical_mesh_payload(mesh), sort_keys=True, separators=(",", ":"), allow_nan=False)
    b = json.dumps(_canonical_mesh_payload(mesh), sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert a == b
    assert hashlib.sha256(a.encode("utf-8")).hexdigest() == hashlib.sha256(b.encode("utf-8")).hexdigest()
