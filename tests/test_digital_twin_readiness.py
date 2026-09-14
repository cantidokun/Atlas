"""Deterministic tests for the digital-twin readiness gate. No Blender/bpy."""

from planning.blender import (
    FindingCode,
    Finding,
    ObjectModel,
    SceneModel,
    evaluate_readiness,
    run_scene_health,
    soccer_field_profile,
)
from planning.blender.digital_twin_readiness import (
    is_not_ready,
    is_ready,
    is_ready_with_warnings,
)
from planning.blender.scene_model import MeshModel
from planning.digital_twin_validation import ValidationState


def _quad(mid, ox):
    return MeshModel(
        mesh_id=mid,
        vertices=((ox, 0, 0), (ox + 1, 0, 0), (ox, 1, 0), (ox + 1, 1, 0)),
        faces=((0, 1, 2), (1, 3, 2)),
    )


def _obj(oid, name, mesh=True):
    return ObjectModel(
        object_id=oid, name=name, location=(0, 0, 0), scale=(1, 1, 1),
        mesh=_quad(f"{oid}_m", 0) if mesh else None,
    )


def _scene(*objs):
    return SceneModel(scene_id="s", unit_system="METERS", objects=objs)


def test_valid_scene_is_ready():
    scene = _scene(_obj("pitch", "pitch"), _obj("goal_left", "goal_left"), _obj("goal_right", "goal_right"))
    report = run_scene_health(scene, soccer_field_profile())
    assert report.validation_state == ValidationState.PRODUCTION_READY.value
    assert is_ready(report.validation_state)


def test_warning_only_is_ready_with_warnings():
    # A MESH_DUPLICATE_VERTEX is WARNING severity and must not block READY (it maps to ANALYZED).
    bad_mesh = MeshModel(
        # vertex 0 and 1 are coincident (duplicate), but the two triangles share NO edges,
        # so no winding/non-manifold/error is produced.
        mesh_id="m",
        vertices=((0, 0, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0), (1, -1, 0), (2, -1, 0)),
        faces=((0, 2, 3), (1, 4, 5)),
    )
    scene = _scene(
        ObjectModel(object_id="pitch", name="pitch", mesh=bad_mesh),
        _obj("goal_left", "goal_left"), _obj("goal_right", "goal_right"),
    )
    report = run_scene_health(scene, soccer_field_profile())
    assert report.validation_state == ValidationState.ANALYZED.value
    assert is_ready_with_warnings(report.validation_state)


def test_error_is_not_ready():
    bad_mesh = MeshModel(mesh_id="m", vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)), faces=((0, 1, 99),))
    scene = _scene(
        ObjectModel(object_id="pitch", name="pitch", mesh=bad_mesh),
        _obj("goal_left", "goal_left"), _obj("goal_right", "goal_right"),
    )
    report = run_scene_health(scene, soccer_field_profile())
    assert report.validation_state == ValidationState.NEEDS_REVIEW.value
    assert is_not_ready(report.validation_state)


def test_missing_required_role_not_ready():
    scene = _scene(_obj("pitch", "pitch"), _obj("goal_left", "goal_left"))  # missing goal_right
    report = run_scene_health(scene, soccer_field_profile())
    assert report.validation_state == ValidationState.NEEDS_REVIEW.value
    assert "required roles" in report.scene_metrics.get("readiness_reason", "")


def test_shallow_evaluate_readiness_state_only():
    scene = _scene(_obj("pitch", "pitch"), _obj("goal_left", "goal_left"), _obj("goal_right", "goal_right"))
    report = run_scene_health(scene, soccer_field_profile())
    # Ready path does not emit a readiness-failed code.
    assert not any(f.code is FindingCode.DIGITAL_TWIN_READINESS_FAILED for f in report.findings)


def test_ready_state_does_not_overclaim():
    # Even a warning-free scene that fails a required role is not production-ready.
    scene = _scene(_obj("pitch", "pitch"))
    report = run_scene_health(scene, soccer_field_profile())
    assert report.validation_state != ValidationState.PRODUCTION_READY.value
    assert is_not_ready(report.validation_state)
