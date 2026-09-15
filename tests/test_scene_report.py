"""Deterministic tests for the canonical SceneReport input contract + report serialization.

No Blender/bpy. Exercises the closed-grammar parser and the deterministic machine-readable report
(finding ordering, canonical JSON byte-equivalence, input-digest provenance, no source mutation).
"""

import json

import pytest

from planning.blender import (
    Finding,
    FindingCode,
    SceneReport,
    SceneReportInputError,
    compute_input_digest,
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


# --------------------------------------------------------------------------- contract

def test_valid_parse_roundtrip():
    raw = {
        "scene_id": "s1",
        "unit_system": "METERS",
        "objects": [
            {
                "object_id": "pitch",
                "name": "pitch",
                "location": (0, 0, 0),
                "mesh": {
                    "mesh_id": "m1",
                    "vertices": ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)),
                    "faces": ((0, 1, 2), (1, 3, 2)),
                },
            }
        ],
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
        {"scene_id": "s", "unit_system": "M", "objects": [{"object_id": "o", "name": "n", "mesh": {"mesh_id": "m", "vertices": ((0, 0, 0),), "faces": (())}}]},
    ],
)
def test_malformed_input_fails_closed(bad):
    with pytest.raises((SceneReportInputError, ValueError, TypeError)):
        parse_scene_report_input(bad)


def test_required_versus_optional_enforced():
    # mesh requires vertices and faces
    with pytest.raises((SceneReportInputError, ValueError)):
        MeshModel(mesh_id="m", vertices=(), faces=())
    # coordinates must be finite
    with pytest.raises((SceneReportInputError, ValueError)):
        MeshModel(mesh_id="m", vertices=((0, 0, float("inf")),), faces=((0,),))
    # bool rejected as coordinate
    with pytest.raises((SceneReportInputError, ValueError)):
        MeshModel(mesh_id="m", vertices=((True, 0, 0),), faces=((0,),))


def test_subclass_rejected_in_parser():
    class Lousy(list):
        pass

    with pytest.raises((SceneReportInputError, TypeError)):
        parse_scene_report_input(Lousy())


# --------------------------------------------------------------------------- report determinism

def test_report_finding_order_deterministic():
    scene = _valid_scene()
    scene = SceneModel(
        scene_id="s1", unit_system="METERS",
        objects=scene.objects + (ObjectModel(object_id="dup", name="dup", location=(0, 0, 0), mesh=_quad("m4", 0)),),
    )
    r1 = run_scene_health(scene, soccer_field_profile())
    r2 = run_scene_health(scene, soccer_field_profile())
    assert r1.canonical_json() == r2.canonical_json()
    # repeated objects identical, findings sorted
    r3 = run_scene_health(_valid_scene(), soccer_field_profile())
    codes = [f.code.value for f in r3.findings]
    assert codes == sorted(codes)


def test_report_digest_provenance():
    scene = _valid_scene()
    r = run_scene_health(scene, soccer_field_profile())
    assert len(r.digest()) == 64
    # digest binds the scene input
    assert r.input_digest == scene_input_digest(scene)
    # modifying one object changes the input digest
    other = SceneModel(
        scene_id="s1", unit_system="METERS",
        objects=(ObjectModel(object_id="pitch", name="pitch_Z", location=(0, 0, 0), scale=(1, 1, 1), mesh=_quad("m1", 0)),),
    )
    assert scene_input_digest(other) != scene_input_digest(scene)


def test_no_source_mutation():
    scene = _valid_scene()
    verts_before = [list(v) for v in scene.objects[0].mesh.vertices]
    report = run_scene_health(scene, soccer_field_profile())
    assert [list(v) for v in scene.objects[0].mesh.vertices] == verts_before
    assert report.scene_id == scene.scene_id


def test_canonical_json_deterministic_byte_equivalence():
    scene = _valid_scene()
    r = run_scene_health(scene, soccer_field_profile())
    a = r.canonical_json()
    b = r.canonical_json()
    assert a == b
    # JSON parse stable
    parsed = json.loads(a)
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
    r = run_scene_health(scene, soccer_field_profile())
    assert r.findings_for(mesh_id="m1") == ()
    # introduce an error on m1
    m1 = scene.objects[0].mesh
    bad = MeshModel(mesh_id="m1", vertices=m1.vertices, faces=((0, 1, 99),))
    obj0 = ObjectModel(object_id="pitch", name="pitch", mesh=bad)
    scene2 = SceneModel(scene_id="s1", unit_system="METERS", objects=(obj0,) + scene.objects[1:])
    r2 = run_scene_health(scene2, soccer_field_profile())
    assert any(f.mesh_id == "m1" and f.code is FindingCode.MESH_INVALID_INDEX for f in r2.findings)

# ---- priority contract-lock tests (review §13) ----

def test_empty_scene_deterministic():
    from planning.blender import SceneModel, run_scene_health, soccer_field_profile, SceneReportInputError
    from planning.blender.scene_report import SceneReport
    scene = SceneModel(scene_id="empty", unit_system="METERS", objects=())
    report = run_scene_health(scene, soccer_field_profile())
    assert isinstance(report, SceneReport)
    assert report.scene_id == "empty"
    # deterministic and repeatable
    assert report.canonical_json() == run_scene_health(scene, soccer_field_profile()).canonical_json()
    assert report.validation_state in ("needs_review", "production_ready")  # role-presence => not ready until roles


def test_empty_scene_not_ready_without_roles():
    from planning.blender import SceneModel, run_scene_health, soccer_field_profile
    scene = SceneModel(scene_id="empty", unit_system="METERS", objects=())
    report = run_scene_health(scene, soccer_field_profile())
    # missing required roles => NOT_READY (needs_review), never overclaim
    assert report.validation_state == "needs_review"


def test_scene_without_meshes_deterministic():
    from planning.blender import ObjectModel, SceneModel, run_scene_health, soccer_field_profile
    scene = SceneModel(
        scene_id="s", unit_system="METERS",
        objects=(
            ObjectModel(object_id="pitch", name="pitch"),
            ObjectModel(object_id="goal_left", name="goal_left"),
            ObjectModel(object_id="goal_right", name="goal_right"),
        ),
    )
    report = run_scene_health(scene, soccer_field_profile())
    assert report.scene_metrics["mesh_object_count"] == 0
    # organization still validated; object names valid -> readiness only gated by roles (present)
    assert report.validation_state == "production_ready"


def test_large_coordinate_scale_robust():
    from planning.blender import MeshModel, check_mesh_in_envelope
    from planning.blender.mesh_health import check_mesh
    # vertices at 1e6 magnitude must not float-blow up; a valid small triangle stays valid
    m = MeshModel(
        mesh_id="m",
        vertices=((1_000_000_000.5, 0, 0), (1_000_000_001.5, 0, 0), (1_000_000_000.5, 1, 0)),
        faces=((0, 1, 2),),
    )
    found = check_mesh(m)
    assert all(f.code.value != "MESH_DEGENERATE_FACE" for f in found)
    assert [f.code.value for f in found] == []
    # and outside the soccer envelope it is flagged
    from planning.blender.mesh_health import check_mesh_in_envelope
    env = check_mesh_in_envelope(m, (-50, -40, 0), (50, 40, 12))
    assert any(f.code.value == "MESH_SCALE_OUT_OF_RANGE" for f in env)


def test_zero_scale_transform_invalid():
    from planning.blender import ObjectModel, SceneModel, check_scene, soccer_field_profile
    from planning.blender.scene_health import check_scene as ck
    from planning.blender.finding_codes import FindingCode
    o = ObjectModel(object_id="o", name="o_x", scale=(0, 0, 0))
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(o,))
    codes = [f.code for f in ck(scene, soccer_field_profile())]
    assert FindingCode.OBJECT_TRANSFORM_INVALID in codes


def test_profile_change_changes_report_digest():
    from planning.blender import run_scene_health
    from planning.blender.soccer_field_profile import soccer_field_profile
    scene = _valid_scene()
    base = soccer_field_profile()
    strict = soccer_field_profile(envelope_min=(-1, -1, -1), envelope_max=(1, 1, 1))
    r1 = run_scene_health(scene, base)
    r2 = run_scene_health(scene, strict)
    assert r1.digest() != r2.digest()


def test_uv_roundtrip_representation():
    from planning.blender import SceneModel, run_scene_health, soccer_field_profile
    from planning.blender.scene_model import ObjectModel, MeshModel
    m = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2),),
        uvs=((0.25, 0.5),),
    )
    # include the three default required roles so readiness is not blocked by roles
    scene = SceneModel(
        scene_id="s", unit_system="METERS",
        objects=(
            ObjectModel(object_id="pitch", name="pitch", mesh=m),
            ObjectModel(object_id="goal_left", name="goal_left"),
            ObjectModel(object_id="goal_right", name="goal_right"),
        ),
    )
    report = run_scene_health(scene, soccer_field_profile())
    # UVs are accepted + mesh processed (round-trip), never validated/erased in findings
    assert report.scene_metrics["mesh_metrics"]["m"]["faces"] == 1
    assert report.validation_state in ("production_ready", "analyzed")


def test_small_mesh_false_positive_regression():
    from planning.blender import MeshModel, check_mesh, FindingCode
    m = MeshModel(
        mesh_id="m",
        vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        faces=((0, 1, 2),),
    )
    found = check_mesh(m)
    codes = {f.code for f in found}
    # single valid triangle: no duplicate/degenerate/non-manifold/winding/normal/invalid finding
    assert not codes
