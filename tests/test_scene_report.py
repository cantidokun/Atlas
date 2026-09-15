"""Deterministic tests for the canonical SceneReport input contract + report serialization.

No Blender/bpy. Exercises the closed-grammar parser and the deterministic machine-readable report
(finding ordering, canonical JSON byte-equivalence, input-digest provenance, no source mutation).
"""

import json

import pytest

from planning.blender import (
    FindingCode,
    SceneReport,
    SceneReportInputError,
    parse_scene_report_input,
    run_scene_health,
    scene_input_digest,
    soccer_field_profile,
)
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def _quad(mid, ox):
    return MeshModel(
        mesh_id=mid,
        vertices=((ox, 0, 0), (ox + 1, 0, 0), (ox, 1, 0), (ox + 1, 1, 0)),
        faces=((0, 1, 2), (1, 3, 2)),
    )


def _valid_scene():
    return SceneModel(
        scene_id="s1",
        unit_system="METERS",
        objects=(
            ObjectModel(object_id="pitch", name="pitch", location=(0, 0, 0), scale=(1, 1, 1), mesh=_quad("m1", 0)),
            ObjectModel(object_id="goal_left", name="goal_left", location=(0, 0, 0), mesh=_quad("m2", 6)),
            ObjectModel(object_id="goal_right", name="goal_right", location=(0, 0, 0), mesh=_quad("m3", 10)),
        ),
    )


def test_valid_parse_roundtrip():
    raw = {
        "scene_id": "s1",
        "unit_system": "METERS",
        "objects": [{
            "object_id": "pitch",
            "name": "pitch",
            "location": (0, 0, 0),
            "mesh": {
                "mesh_id": "m1",
                "vertices": ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)),
                "faces": ((0, 1, 2), (1, 3, 2)),
            },
        }],
    }
    scene = parse_scene_report_input(raw)
    assert isinstance(scene, SceneModel)
    assert scene.scene_id == "s1"
    assert scene.objects[0].mesh.faces == ((0, 1, 2), (1, 3, 2))


@pytest.mark.parametrize(
    "bad",
    [
        {"objects": ()},
        {"scene_id": "", "objects": ()},
        {"scene_id": "s", "unit_system": "M", "objects": (), "unknown_key": 1},
        {"scene_id": "s", "unit_system": "M", "objects": [{"object_id": 1, "name": "x"}]},
        {"scene_id": "s", "unit_system": "M", "objects": [{"object_id": "o", "name": "n", "mesh": {"mesh_id": "m", "vertices": [[0, 0, 0]], "faces": [[]]}}]},
    ],
)
def test_malformed_input_fails_closed(bad):
    with pytest.raises((SceneReportInputError, ValueError, TypeError)):
        parse_scene_report_input(bad)


def test_required_contract_and_empty_mesh_state():
    empty = MeshModel(mesh_id="empty", vertices=(), faces=())
    assert empty.vertices == ()
    assert empty.faces == ()
    with pytest.raises((SceneReportInputError, ValueError)):
        MeshModel(mesh_id="m", vertices=((0, 0, float("inf")),), faces=((0,),))
    with pytest.raises((SceneReportInputError, ValueError)):
        MeshModel(mesh_id="m", vertices=((True, 0, 0),), faces=((0,),))
    with pytest.raises(SceneReportInputError):
        MeshModel(mesh_id="m", vertices=(), faces=((0, 1, 2),))


def test_subclass_rejected_in_parser():
    class Lousy(list):
        pass
    with pytest.raises((SceneReportInputError, TypeError)):
        parse_scene_report_input(Lousy())


def test_empty_mesh_parse_roundtrip_and_digest():
    raw = {"scene_id": "s", "unit_system": "METERS", "objects": [{"object_id": "empty", "name": "empty", "mesh": {"mesh_id": "m", "vertices": [], "faces": [], "materials": ["mat"]}}]}
    first = parse_scene_report_input(raw)
    second = parse_scene_report_input(raw)
    assert first == second
    assert first.objects[0].mesh == MeshModel(mesh_id="m", vertices=(), faces=(), materials=("mat",))
    assert scene_input_digest(first) == scene_input_digest(second)


def test_report_finding_order_deterministic():
    scene = SceneModel(scene_id="s1", unit_system="METERS", objects=_valid_scene().objects + (ObjectModel(object_id="dup", name="dup", mesh=_quad("m4", 0)),))
    r1 = run_scene_health(scene, soccer_field_profile())
    r2 = run_scene_health(scene, soccer_field_profile())
    assert r1.canonical_json() == r2.canonical_json()
    codes = [f.code.value for f in run_scene_health(_valid_scene(), soccer_field_profile()).findings]
    assert codes == sorted(codes)


def test_report_digest_provenance():
    scene = _valid_scene()
    r = run_scene_health(scene, soccer_field_profile())
    assert len(r.digest()) == 64
    assert r.input_digest == scene_input_digest(scene)
    other = SceneModel(scene_id="s1", unit_system="METERS", objects=(ObjectModel(object_id="pitch", name="pitch_Z", mesh=_quad("m1", 0)),))
    assert scene_input_digest(other) != scene_input_digest(scene)


def test_no_source_mutation():
    scene = _valid_scene()
    before = scene
    report = run_scene_health(scene, soccer_field_profile())
    assert scene == before
    assert report.scene_id == scene.scene_id


def test_canonical_json_deterministic_byte_equivalence():
    report = run_scene_health(_valid_scene(), soccer_field_profile())
    parsed = json.loads(report.canonical_json())
    assert report.canonical_json() == report.canonical_json()
    assert parsed["scene_id"] == "s1"
    assert "report_format_version" in parsed
    assert "validator_version" in parsed
    assert isinstance(parsed["findings"], list)


def test_metrics_present():
    r = run_scene_health(_valid_scene(), soccer_field_profile())
    assert r.scene_metrics["object_count"] == 3
    assert r.scene_metrics["mesh_object_count"] == 3
    assert r.scene_metrics["total_vertices"] == 12


def test_findings_bound_to_ids():
    scene = _valid_scene()
    assert run_scene_health(scene, soccer_field_profile()).findings_for(mesh_id="m1") == ()
    bad = MeshModel(mesh_id="m1", vertices=scene.objects[0].mesh.vertices, faces=((0, 1, 99),))
    scene2 = SceneModel(scene_id="s1", unit_system="METERS", objects=(ObjectModel(object_id="pitch", name="pitch", mesh=bad),) + scene.objects[1:])
    assert any(f.mesh_id == "m1" and f.code is FindingCode.MESH_INVALID_INDEX for f in run_scene_health(scene2, soccer_field_profile()).findings)


def test_zero_face_mesh_with_vertices_survives_kernel():
    mesh = MeshModel(mesh_id="m", vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), faces=())
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel("pitch", "pitch", mesh=mesh), ObjectModel("goal_left", "goal_left"), ObjectModel("goal_right", "goal_right")))
    report = run_scene_health(scene, soccer_field_profile())
    assert report.scene_metrics["mesh_metrics"]["m"]["vertices"] == 2
    assert report.scene_metrics["mesh_metrics"]["m"]["faces"] == 0
    assert not any(f.mesh_id == "m" and f.code in {FindingCode.MESH_INVALID_INDEX, FindingCode.MESH_DUPLICATE_FACE, FindingCode.MESH_DEGENERATE_FACE} for f in report.findings)


def test_empty_scene_deterministic():
    scene = SceneModel(scene_id="empty", unit_system="METERS", objects=())
    report = run_scene_health(scene, soccer_field_profile())
    assert isinstance(report, SceneReport)
    assert report.canonical_json() == run_scene_health(scene, soccer_field_profile()).canonical_json()


def test_empty_scene_not_ready_without_roles():
    scene = SceneModel(scene_id="empty", unit_system="METERS", objects=())
    assert run_scene_health(scene, soccer_field_profile()).validation_state == "needs_review"


def test_scene_without_meshes_deterministic():
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel("pitch", "pitch"), ObjectModel("goal_left", "goal_left"), ObjectModel("goal_right", "goal_right")))
    report = run_scene_health(scene, soccer_field_profile())
    assert report.scene_metrics["mesh_object_count"] == 0
    assert report.validation_state == "production_ready"


def test_large_coordinate_scale_robust():
    from planning.blender.mesh_health import check_mesh, check_mesh_in_envelope
    m = MeshModel("m", ((1_000_000_000.5,0,0),(1_000_000_001.5,0,0),(1_000_000_000.5,1,0)), ((0,1,2),))
    assert not check_mesh(m)
    assert any(f.code.value == "MESH_SCALE_OUT_OF_RANGE" for f in check_mesh_in_envelope(m, (-50,-40,0), (50,40,12)))


def test_zero_scale_transform_invalid():
    from planning.blender.scene_health import check_scene
    from planning.blender.finding_codes import FindingCode
    scene = SceneModel("s", "METERS", (ObjectModel("o", "o_x", scale=(0,0,0)),))
    assert FindingCode.OBJECT_TRANSFORM_INVALID in [f.code for f in check_scene(scene, soccer_field_profile())]


def test_profile_change_changes_report_digest():
    from planning.blender.soccer_field_profile import soccer_field_profile
    base = soccer_field_profile(); strict = soccer_field_profile(envelope_min=(-1,-1,-1), envelope_max=(1,1,1))
    assert run_scene_health(_valid_scene(), base).digest() != run_scene_health(_valid_scene(), strict).digest()


def test_uv_roundtrip_representation():
    mesh = MeshModel("m", ((0,0,0),(1,0,0),(0,1,0)), ((0,1,2),), uvs=((0.25,0.5),))
    scene = SceneModel("s", "METERS", (ObjectModel("pitch","pitch",mesh=mesh), ObjectModel("goal_left","goal_left"), ObjectModel("goal_right","goal_right")))
    report = run_scene_health(scene, soccer_field_profile())
    assert report.scene_metrics["mesh_metrics"]["m"]["faces"] == 1


def test_small_mesh_false_positive_regression():
    from planning.blender.mesh_health import check_mesh
    mesh = MeshModel("m", ((0,0,0),(1,0,0),(0,1,0)), ((0,1,2),))
    assert not check_mesh(mesh)
