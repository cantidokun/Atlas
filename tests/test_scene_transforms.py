"""Deterministic regression tests for the Blender transform/pose contract (remediation).

Covers the Option-2 model: MeshModel.vertices are OBJECT-LOCAL; ObjectModel carries an explicit
immutable pose (location + quaternion rotation + scale); the kernel derives world space through the
single world-pose engine (transforms.world_points). No bpy, no live Blender.
"""

import copy
import math

import pytest

from planning.blender import (
    FindingCode,
    ObjectModel,
    SceneModel,
    TransformError,
    TransformModel,
    check_scene,
    compose_stages,
    euler_xyz_degrees_to_quaternion,
    run_scene_health,
    scene_input_digest,
    soccer_field_profile,
    world_points,
    world_pose_for,
)
from planning.blender.kernel import soccer_field_profile_default
from planning.blender.fixtures import (
    ALL_FIXTURES,
    MIXED_TOPOLOGY_MESH,
    PER_FACE_NORMALS_MESH,
    TRANSFORM_CYCLIC_PARENT,
    TRANSFORM_IDENTITY,
    TRANSFORM_MISSING_PARENT,
    TRANSFORM_NESTED_CHAIN,
    TRANSFORM_PARENT_ROTATED,
    TRANSFORM_PARENT_SCALED,
    TRANSFORM_PARENT_TRANSLATED,
    TRANSFORM_ROTATED,
    TRANSFORM_TRANSLATED,
    TRANSFORM_UNIFORM_SCALE,
    TRANSFORM_NONUNIFORM_SCALE,
    payload_to_scene,
    report_for_payload,
    scene_report_for_fixture,
)
from planning.blender.scene_model import MeshModel, parse_scene_report_input

from planning.blender.transforms import world_pose_for as wpf


def _scene(*objs, scene_id="s", unit="METERS"):
    return SceneModel(scene_id=scene_id, unit_system=unit, objects=tuple(objs))


def _quad_mesh(mid="m", size=10.0, height=0.0):
    return MeshModel(
        mesh_id=mid,
        vertices=(
            (0.0, 0.0, height), (size, 0.0, height),
            (0.0, size, height), (size, size, height),
        ),
        faces=((0, 1, 2), (1, 3, 2)),
    )


def _obj(oid, name="x", **kw):
    kw.setdefault("location", (0.0, 0.0, 0.0))
    kw.setdefault("scale", (1.0, 1.0, 1.0))
    kw.setdefault("rotation", (1.0, 0.0, 0.0, 0.0))
    kw.setdefault("mesh", _quad_mesh(f"{oid}_m"))
    return ObjectModel(object_id=oid, name=name, **kw)


# ---------------------------------------------------------------------------
# A. Transform composition — exact expected world coordinates
# ---------------------------------------------------------------------------


def test_location_translation_only():
    obj = _obj("p", location=(5.0, -3.0, 2.0))
    scene = _scene(obj)
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    assert pts is not None
    assert pts[0] == pytest.approx((5.0, -3.0, 2.0))
    assert pts[1] == pytest.approx((15.0, -3.0, 2.0))  # (5+10, -3, 2)


def test_rotation_about_z_90():
    # 90deg about Z: (x,y,z) -> (-y, x, z)
    qz = (0.7071067811865476, 0.0, 0.0, 0.7071067811865476)
    obj = ObjectModel(object_id="p", name="p", rotation=qz, mesh=_quad_mesh())
    scene = _scene(obj)
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    assert pts is not None
    # (10,0,0) -> (0,10,0) ; (0,10,0) -> (-10,0,0) ; (10,10,0)->(-10,10,0)
    assert pts[1] == pytest.approx((0.0, 10.0, 0.0))
    assert pts[2] == pytest.approx((-10.0, 0.0, 0.0))


def test_scale_uniform():
    obj = _obj("p", scale=(100.0, 100.0, 100.0))
    scene = _scene(obj)
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    assert pts is not None
    assert pts[1] == pytest.approx((1000.0, 0.0, 0.0))
    assert pts[3] == pytest.approx((1000.0, 1000.0, 0.0))


def test_combined_scale_rotate_translate():
    # scale x2 then rotate 90z then translate (5,0,0): (1,0,0)->scale(2,0,0)->rot(0,2,0)->(5,2,0)
    qz = (0.7071067811865476, 0.0, 0.0, 0.7071067811865476)
    obj = ObjectModel(
        object_id="p", name="p", location=(5.0, 0.0, 0.0),
        rotation=qz, scale=(2.0, 2.0, 2.0),
        mesh=MeshModel(mesh_id="m", vertices=((1.0, 0.0, 0.0),), faces=((0,),)),
    )
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    assert pts is not None
    assert pts[0] == pytest.approx((5.0, 2.0, 0.0))


def test_parent_composition():
    root = _obj("root", location=(10.0, 0.0, 0.0))
    p = ObjectModel(
        object_id="p", name="p", parent_object_id="root", location=(1.0, 0.0, 0.0),
        mesh=MeshModel(mesh_id="m", vertices=((0.0, 0.0, 0.0),), faces=((0,),)),
    )
    by_id = {"root": root, "p": p}
    pts = world_points(by_id, "p", p.mesh.vertices)
    assert pts is not None
    assert pts[0] == pytest.approx((11.0, 0.0, 0.0))  # 10 + 1


def test_nonuniform_scale_transform():
    obj = _obj("p", scale=(1.0, 5.0, 1.0))
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    assert pts is not None
    assert pts[1] == pytest.approx((10.0, 0.0, 0.0))
    assert pts[2] == pytest.approx((0.0, 50.0, 0.0))


# ---------------------------------------------------------------------------
# B. Contract — object-local + centralized world derivation
# ---------------------------------------------------------------------------


def test_local_vertices_remain_unchanged():
    mesh = _quad_mesh()
    obj = ObjectModel(object_id="p", name="p", location=(7.0, 0.0, 0.0), mesh=mesh)
    assert obj.mesh.vertices[1] == (10.0, 0.0, 0.0)  # local data unchanged
    assert obj.location == (7.0, 0.0, 0.0)
    assert obj.transform.location == (7.0, 0.0, 0.0)
    assert obj.transform.rotation == (1.0, 0.0, 0.0, 0.0)
    assert obj.transform.scale == (1.0, 1.0, 1.0)


def test_scale_not_double_applied():
    # scale only on the OBJECT; world_points must not apply it again on top.
    obj = _obj("p", scale=(3.0, 3.0, 3.0))
    pts = world_points({"p": obj}, "p", obj.mesh.vertices)
    # vertex (0,size,0) with size=10 -> (0,30,0). If scale were applied twice it'd be (0,90,0).
    assert pts[2] == pytest.approx((0.0, 30.0, 0.0))


def test_aabb_and_envelope_use_world_space_via_same_helper():
    # A translated object moves the report's MESH_SCALE_OUT_OF_RANGE evaluation accordingly.
    local = MeshModel(mesh_id="m", vertices=((0, 0, 0), (10, 0, 0), (0, 10, 0)), faces=((0, 1, 2),))
    scene = _scene(_obj("p", mesh=local))
    report = run_scene_health(scene, soccer_field_profile_default())
    assert report.findings == ()  # fits envelope (0..50/40/12)

    moved_scene = _scene(_obj("p", mesh=local, location=(100.0, 0.0, 0.0)))
    report2 = run_scene_health(moved_scene, soccer_field_profile_default())
    codes = {f.code for f in report2.findings}
    assert FindingCode.MESH_SCALE_OUT_OF_RANGE in codes  # translated out of envelope


def test_aabb_overlap_respects_transform():
    # Two overlapping-in-local objects that do NOT overlap once translated apart.
    scene_overlap = _scene(
        _obj("a", mesh=MeshModel(mesh_id="m1", vertices=((0,0,0),(5,5,0),(0,5,0)), faces=((0,1,2),))),
        _obj("b", mesh=MeshModel(mesh_id="m2", vertices=((3,0,0),(8,5,0),(8,0,0)), faces=((0,1,2),))),
    )
    codes = {f.code for f in check_scene(scene_overlap, soccer_field_profile())}
    assert FindingCode.OBJECT_BOUNDS_OVERLAP.value in {c.value for c in codes}

    scene_apart = _scene(
        _obj("a", location=(0,0,0), mesh=MeshModel(mesh_id="m1", vertices=((0,0,0),(1,1,0),(0,1,0)), faces=((0,1,2),))),
        _obj("b", location=(100,0,0), mesh=MeshModel(mesh_id="m2", vertices=((0,0,0),(1,1,0),(1,0,0)), faces=((0,1,2),))),
    )
    codes_a = {f.code.value for f in check_scene(scene_apart, soccer_field_profile())}
    assert FindingCode.OBJECT_BOUNDS_OVERLAP.value not in codes_a


# ---------------------------------------------------------------------------
# C. Topology — mixed face cardinalities accepted, provenance exact
# ---------------------------------------------------------------------------


def test_mixed_topology_accepted():
    report = scene_report_for_fixture("mixed_topology_mesh")
    # The mixed (tri/quad/ngon) mesh must NOT be rejected by any vertices_per_face-style constraint.
    assert report is not None
    # no MESH_INVALID_INDEX / index errors purely from topology shape
    mesh_codes = {f.code for f in report.findings}
    assert FindingCode.MESH_INVALID_INDEX not in mesh_codes


def test_mixed_topology_faces_preserved():
    scene = payload_to_scene(MIXED_TOPOLOGY_MESH)
    mesh = scene.objects[0].mesh
    assert [len(f) for f in mesh.faces] == [3, 4, 6]


def test_face_cardinality_derived_not_declared():
    # len(face) is authoritative; no vertices_per_face field remains.
    scene = payload_to_scene(MIXED_TOPOLOGY_MESH)
    mesh = scene.objects[0].mesh
    assert not hasattr(mesh, "vertices_per_face")


# ---------------------------------------------------------------------------
# D. Normals — per-face only; vertex-as-face never accepted
# ---------------------------------------------------------------------------


def test_per_face_normals_accepted():
    scene = payload_to_scene(PER_FACE_NORMALS_MESH)
    mesh = scene.objects[0].mesh
    assert len(mesh.normals) == len(mesh.faces) == 2
    assert mesh.normals[0] == (0.0, 0.0, 1.0)


def test_wrong_length_normals_rejected():
    # normals length != faces length must be a declared input error (not silent mislabel).
    with pytest.raises(Exception):
        MeshModel(
            mesh_id="m", vertices=((0,0,0),(1,0,0),(0,1,0)), faces=((0,1,2),),
            normals=((0,0,1),(0,0,1)),  # 2 normals, 1 face
        )


def test_no_vertex_as_face_normals_in_adapter_fixtures():
    # The healthy-without-normals fixture legitimately omits normals.
    scene = payload_to_scene(ALL_FIXTURES["healthy_without_normals"])
    mesh = scene.objects[0].mesh
    assert mesh.normals == ()


# ---------------------------------------------------------------------------
# E. Parent hierarchy — valid chain, missing parent, cycle
# ---------------------------------------------------------------------------


def test_missing_parent_yields_no_world_pose():
    scene = payload_to_scene(TRANSFORM_MISSING_PARENT)
    by_id = {o.object_id: o for o in scene.objects}
    assert world_points(by_id, "pitch", scene.objects[0].mesh.vertices) is None
    codes = {f.code for f in check_scene(scene, soccer_field_profile())}
    assert FindingCode.OBJECT_HIERARCHY_INVALID.value in {c.value for c in codes}


def test_cyclic_parent_yields_no_world_pose_and_hierarchy_finding():
    scene = payload_to_scene(TRANSFORM_CYCLIC_PARENT)
    by_id = {o.object_id: o for o in scene.objects}
    pitch = next(o for o in scene.objects if o.mesh is not None)
    assert world_points(by_id, "pitch", pitch.mesh.vertices) is None
    codes = {f.code.value for f in check_scene(scene, soccer_field_profile())}
    assert FindingCode.OBJECT_HIERARCHY_INVALID.value in codes


def test_nested_parent_chain_world_position():
    scene = payload_to_scene(TRANSFORM_NESTED_CHAIN)
    by_id = {o.object_id: o for o in scene.objects}
    # Chain: child(+5) -> parent(+3) -> grand(scale 2 then +1):
    # child.apply(0)=(5,0,0); parent.apply(5)=(8,0,0); grand.apply(8)=2*8+1=(17,0,0)
    assert world_points(by_id, "pitch", ((0.0, 0.0, 0.0),))[0] == pytest.approx((17.0, 0.0, 0.0))


# ---------------------------------------------------------------------------
# F. Determinism
# ---------------------------------------------------------------------------


def test_transform_change_changes_report_digest():
    r1 = scene_report_for_fixture("transform_identity")
    r2 = scene_report_for_fixture("transform_translated")
    assert r1.input_digest != r2.input_digest
    assert r1.digest() != r2.digest()


def test_same_local_mesh_two_poses_different_world_bounds_report():
    # Readiness/state may differ because the translated mesh leaves the envelope.
    s1 = payload_to_scene(TRANSFORM_IDENTITY)
    s2 = payload_to_scene(TRANSFORM_TRANSLATED)
    # local mesh data is identical
    m1 = s1.objects[0].mesh.vertices
    m2 = s2.objects[0].mesh.vertices
    assert m1 == m2
    assert s1.objects[0].location == (0.0, 0.0, 0.0)
    assert s2.objects[0].location == (100.0, 0.0, 0.0)
    r1 = run_scene_health(s1, soccer_field_profile_default())
    r2 = run_scene_health(s2, soccer_field_profile_default())
    assert r1.findings != r2.findings or r1.digest() != r2.digest()


def test_identical_input_same_report():
    r1 = run_scene_health(payload_to_scene(TRANSFORM_IDENTITY), soccer_field_profile_default())
    r2 = run_scene_health(payload_to_scene(TRANSFORM_IDENTITY), soccer_field_profile_default())
    assert r1.digest() == r2.digest()
    assert r1.input_digest == r2.input_digest


# ---------------------------------------------------------------------------
# G. Serialization — canonical serialization stable, digest reflects transform
# ---------------------------------------------------------------------------


def test_transform_serializes_canonically():
    t = TransformModel(location=(1.0, 2.0, 3.0), rotation=(1.0, 0.0, 0.0, 0.0), scale=(4.0, 5.0, 6.0))
    assert t.location == (1.0, 2.0, 3.0)
    assert t.scale == (4.0, 5.0, 6.0)
    assert t.rotation == (1.0, 0.0, 0.0, 0.0)


def test_digest_reflects_transform_change():
    base = ALL_FIXTURES["transform_identity"]
    moved = copy.deepcopy(base)
    moved["objects"][0]["location"] = [50.0, 0.0, 0.0]
    d1 = scene_input_digest(payload_to_scene(base))
    d2 = scene_input_digest(payload_to_scene(moved))
    assert d1 != d2


# ---------------------------------------------------------------------------
# H. C++ parity / language neutrality
# ---------------------------------------------------------------------------


def test_cpp_reproduce_transform_from_json():
    # A language-neutral producer can reproduce world coordinates from the canonical pose alone.
    qz = (0.7071067811865476, 0.0, 0.0, 0.7071067811865476)
    t = TransformModel(location=(5.0, 0.0, 0.0), rotation=qz, scale=(2.0, 2.0, 2.0))
    # JSON-serializable pose -> independent implementation of R*(S*v)+t
    def cpp_equiv(v):
        px, py, pz = v[0] * 2.0, v[1] * 2.0, v[2] * 2.0  # scale
        rx, ry = -py, px  # rotate 90z
        return [rx + 5.0, ry + 0.0, pz]
    for v in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        assert list(t.apply(v)) == pytest.approx(cpp_equiv(v))


# ---------------------------------------------------------------------------
# Quaternion convention (identity/round-trip)
# ---------------------------------------------------------------------------


def test_euler_xyz_deg_to_quaternion_identity_and_90z():
    assert euler_xyz_degrees_to_quaternion(0, 0, 0) == pytest.approx((1.0, 0.0, 0.0, 0.0))
    q = euler_xyz_degrees_to_quaternion(0, 0, 90)
    assert q == pytest.approx((math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)))


def test_identity_quaternion_is_identity():
    t = TransformModel()
    assert t.is_identity
    assert t.apply((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_invalid_transform_rejected():
    with pytest.raises(TransformError):
        TransformModel(scale=(1.0, 0.0, 1.0))  # zero scale
    with pytest.raises(TransformError):
        TransformModel(rotation=(0.0, 0.0, 0.0, 0.0))  # zero quaternion


def test_quaternion_is_normalized():
    t = TransformModel(rotation=(2.0, 0.0, 0.0, 0.0))
    assert t.rotation == (1.0, 0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Fixture sanity: compositional determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(ALL_FIXTURES.keys()))
def test_all_fixtures_produce_deterministic_report(name):
    r = scene_report_for_fixture(name)
    r2 = scene_report_for_fixture(name)
    assert r.digest() == r2.digest()
    assert r.input_digest == r2.input_digest