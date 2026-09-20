"""Deterministic companion coverage for the scene/profile compliance evidence boundary."""
import pytest

from planning.blender.kernel import run_scene_health
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.soccer_field_profile import soccer_field_profile


def tri(mesh_id, verts):
    return MeshModel(mesh_id, tuple(verts), ((0, 1, 2),))


def scene(*objects, unit="METERS"):
    return SceneModel("fixture", unit, tuple(objects))


def obj(name, mesh=None, **kw):
    return ObjectModel(name, name, mesh=mesh, **kw)


def codes(report):
    return {f.code.value for f in report.findings}


def test_profile_identity_and_defaults():
    p = soccer_field_profile()
    assert p.envelope_min == (-50.0, -40.0, 0.0)
    assert p.envelope_max == (50.0, 40.0, 12.0)
    assert p.tolerance_bounds_metres == 0.05
    assert p.allowed_units == frozenset({"METERS", "m", "meters"})
    assert p.allowed_collections == frozenset({"Field", "Sidelines", "Goals", "Players", "Structure"})
    assert p.required_object_roles == ("pitch", "goal_left", "goal_right")
    assert p.permitted_hierarchy_depth == 4
    assert p.expected_up_axis == "z"
    assert p.expected_ground_level == 0.0


def test_envelope_exact_boundary_and_one_float32_step():
    p = soccer_field_profile()
    exact = tri("m", ((50.05, 0.0, 1.0), (50.0, 0.0, 1.0), (50.0, 0.1, 1.0)))
    ulp = tri("m", ((50.05000305175781, 0.0, 1.0), (50.0, 0.0, 1.0), (50.0, 0.1, 1.0)))
    assert "MESH_SCALE_OUT_OF_RANGE" not in codes(run_scene_health(scene(obj("pitch", exact)), p))
    assert "MESH_SCALE_OUT_OF_RANGE" in codes(run_scene_health(scene(obj("pitch", ulp)), p))


def test_envelope_emits_one_finding_per_mesh():
    m = tri("m", ((50.05000305175781, 0.0, 1.0), (50.05000305175781, 0.1, 1.0), (50.0, 0.2, 1.0)))
    report = run_scene_health(scene(obj("pitch", m)), soccer_field_profile())
    findings = [f for f in report.findings if f.code.value == "MESH_SCALE_OUT_OF_RANGE"]
    assert len(findings) == 1
    assert findings[0].mesh_id == "m"


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (((0,0,1),(1,0,1),(1,1,1),(0,1,1)), ((0.75,0,1),(1.75,0,1),(1.75,1,1),(0.75,1,1)), True),
        (((0,0,1),(4,0,1),(4,4,1),(0,4,1)), ((1,1,1),(2,1,1),(2,2,1),(1,2,1)), False),
        (((0,0,1),(1,0,1),(1,1,1),(0,1,1)), ((0,0,1),(1,0,1),(1,1,1),(0,1,1)), False),
        (((0,0,1),(1,0,1),(1,1,1),(0,1,1)), ((1,0,1),(2,0,1),(2,1,1),(1,1,1)), False),
        (((0,0,1),(2,0,1),(2,1,1),(0,1,1)), ((0,1,1),(2,1,1),(2,2,1),(0,2,1)), True),
    ],
)
def test_aabb_boundary_semantics(a, b, expected):
    objs = (
        obj("pitch", tri("pitch", ((-20,-20,0),(-19,-20,0),(-20,-19,0)))),
        obj("a", MeshModel("a", tuple(a), ((0,1,2,3),))),
        obj("b", MeshModel("b", tuple(b), ((0,1,2,3),))),
    )
    report = run_scene_health(scene(*objs), soccer_field_profile())
    assert ("OBJECT_BOUNDS_OVERLAP" in codes(report)) is expected


def test_missing_required_role_is_readiness_state_not_finding():
    p = soccer_field_profile()
    report = run_scene_health(
        scene(obj("pitch", tri("pitch", ((-20,-20,0),(-19,-20,0),(-20,-19,0))))),
        p,
    )
    assert codes(report) == set()
    assert report.validation_state == "needs_review"
    assert report.scene_metrics["readiness_reason"] == "missing required roles: goal_left, goal_right"
    assert "DIGITAL_TWIN_READINESS_FAILED" not in codes(report)


def test_scene_profile_findings_are_independent_of_correction_authority():
    p = soccer_field_profile()
    bad = obj("Bad Name!", tri("bad", ((0,0,1),(1,0,1),(0,1,1))), collection="Misc")
    report = run_scene_health(scene(bad), p)
    assert codes(report) == {"OBJECT_COLLECTION_INVALID", "OBJECT_NAME_INVALID"}
    assert all(f.code.value not in {"REPAIR_MERGE_VERTEX", "REMOVE_DUPLICATE_FACE"} for f in report.findings)


def test_report_input_digest_is_reproducible():
    m = tri("m", ((0,0,1),(1,0,1),(0,1,1)))
    a = run_scene_health(scene(obj("pitch", m)), soccer_field_profile())
    b = run_scene_health(scene(obj("pitch", m)), soccer_field_profile())
    assert a.input_digest == b.input_digest
    assert a.digest() == b.digest()
