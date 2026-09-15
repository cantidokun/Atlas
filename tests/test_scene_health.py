"""Deterministic tests for the scene/organization checks. No Blender/bpy."""

import pytest

from planning.blender import (
    FindingCode,
    Finding,
    ObjectModel,
    SceneModel,
    check_scene,
    soccer_field_profile,
)
from planning.blender.scene_model import MeshModel


def _quad(mid, ox):
    return MeshModel(
        mesh_id=mid,
        vertices=((ox, 0, 0), (ox + 1, 0, 0), (ox, 1, 0), (ox + 1, 1, 0)),
        faces=((0, 1, 2), (1, 3, 2)),
    )


def _obj(oid, name, **kw):
    kw.setdefault("location", (0, 0, 0))
    kw.setdefault("scale", (1, 1, 1))
    kw.setdefault("mesh", _quad(f"{oid}_m", 0))
    return ObjectModel(object_id=oid, name=name, **kw)


def _codes(*objs):
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=objs)
    return sorted(f.code.value for f in check_scene(scene, soccer_field_profile()))


def test_valid_naming_passes():
    codes = _codes(_obj("pitch", "pitch"), _obj("goal_left", "goal_left.object"))
    assert FindingCode.OBJECT_NAME_INVALID.value not in codes


def test_invalid_naming():
    codes = _codes(_obj("goal_left", "Bad Name !"))
    assert FindingCode.OBJECT_NAME_INVALID.value in codes


def test_duplicate_object_id():
    codes = _codes(_obj("dup", "dup"), _obj("dup", "dup_other"))
    assert FindingCode.OBJECT_ID_DUPLICATE.value in codes


def test_unknown_parent_hierarchy():
    codes = _codes(_obj("pitch", "pitch", parent_object_id="ghost"))
    assert FindingCode.OBJECT_HIERARCHY_INVALID.value in codes


def test_hierarchy_cycle_detected():
    a = _obj("a", "a", parent_object_id="b")
    b = _obj("b", "b", parent_object_id="a")
    codes = _codes(a, b)
    assert FindingCode.OBJECT_HIERARCHY_INVALID.value in codes


def test_invalid_unit():
    scene = SceneModel(scene_id="s", unit_system="INCHES", objects=(_obj("pitch", "pitch"),))
    codes = sorted(f.code.value for f in check_scene(scene, soccer_field_profile()))
    assert FindingCode.SCENE_UNIT_INVALID.value in codes


def test_disallowed_collection():
    scene = SceneModel(
        scene_id="s", unit_system="METERS",
        objects=(_obj("pitch", "pitch", collection="Offworld"),),
    )
    codes = sorted(f.code.value for f in check_scene(scene, soccer_field_profile()))
    assert FindingCode.OBJECT_COLLECTION_INVALID.value in codes


def test_transform_invalid_nonfinite():
    scene = SceneModel(
        scene_id="s", unit_system="METERS",
        objects=(ObjectModel(
            object_id="p", name="p",
            location=(0, 0, 0), scale=(1, 1, 0),  # zero scale -> transform invalid
            mesh=_quad("m", 0),
        ),),
    )
    codes = sorted(f.code.value for f in check_scene(scene, soccer_field_profile()))
    assert FindingCode.OBJECT_TRANSFORM_INVALID.value in codes


def test_bounds_overlap_detected_not_containment():
    # two distinct objects with overlapping AABBs (not containment) -> overlap
    a = _obj("a", "a", location=(0, 0, 0), mesh=_quad("ma", 0))
    b = _obj("b", "b", location=(0.5, 0, 0), mesh=_quad("mb", 0))
    codes = _codes(a, b)
    assert FindingCode.OBJECT_BOUNDS_OVERLAP.value in codes


def test_containment_not_flagged_as_overlap():
    # one object's AABB entirely inside another's (a parent/child nesting) is NOT an overlap.
    big = MeshModel(
        mesh_id="big_m",
        vertices=((0, 0, 0), (4, 0, 0), (0, 4, 0), (4, 4, 0)),
        faces=((0, 1, 2), (1, 3, 2)),
    )
    small = _quad("small_m", 0)  # spans 0..1 in X, inside the big 0..4 AABB
    big_obj = ObjectModel(object_id="field", name="field", location=(0, 0, 0), scale=(1, 1, 1), mesh=big)
    small_obj = ObjectModel(object_id="pitch", name="pitch", location=(0, 0, 0), scale=(1, 1, 1), mesh=small)
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(big_obj, small_obj))
    codes = sorted(f.code.value for f in check_scene(scene, soccer_field_profile()))
    assert FindingCode.OBJECT_BOUNDS_OVERLAP.value not in codes
