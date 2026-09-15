from __future__ import annotations

import copy

import pytest

from planning.blender.duplicate_vertex_removal import CORRECTION_TYPE, execute_remove_duplicate_vertices, plan_duplicate_vertex_removal
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def make_scene():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0.,0.,0.), (1.,0.,0.), (0.,1.,0.), (1.,0.,0.), (0.,1.,0.), (3.,3.,3.)),
        faces=((0,1,2), (0,3,5)),
        normals=((0.,0.,1.), (0.,0.,1.)),
        uvs=((0.,0.), (1.,0.)),
        materials=("mat",),
        local_frame_id="frame",
    )
    return SceneModel(
        scene_id="s", unit_system="METERS",
        objects=(
            ObjectModel(object_id="target", name="Target", collection="Field", location=(4.,5.,6.), mesh=mesh),
            ObjectModel(object_id="other", name="Other", collection="Field"),
        ),
    )


def authorized(s):
    digest = "a" * 64
    plan = plan_duplicate_vertex_removal(s, digest, target_object_id="target", expected_duplicate_vertex_groups=[[1,3],[2,4]])
    auth = {"decision":"APPROVED", "correction_type":CORRECTION_TYPE, "correction_id":plan["correction_id"], "plan_id":plan["plan_id"], "source_report_digest":digest}
    return plan, auth, digest


def test_source_immutability():
    s = make_scene()
    before = copy.deepcopy(s)
    plan, auth, digest = authorized(s)
    result = execute_remove_duplicate_vertices(plan, auth, extractor=lambda:(s,digest))
    assert result.ok
    assert s == before


@pytest.mark.parametrize("mutation", [
    lambda p: p.update({"correction_type":"REMOVE_ISOLATED_VERTICES"}),
    lambda p: p["params"].update({"unexpected":1}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[1,3]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[1,3],[2,4,4]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[3,1],[2,4]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[1,3],[1,4]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[True,3],[2,4]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[-1,3],[2,4]]}),
    lambda p: p["params"].update({"expected_duplicate_vertex_groups":[[1,99],[2,4]]}),
    lambda p: p.update({"mesh_id":"wrong"}),
    lambda p: p.update({"target_object_id":"other"}),
    lambda p: p.update({"source_report_digest":"b"*64}),
    lambda p: p.update({"plan_id":"b"*64}),
    lambda p: p.update({"correction_id":"b"*64}),
])
def test_hostile_plan_mutations_fail_without_source_mutation(mutation):
    s = make_scene()
    plan, auth, digest = authorized(s)
    bad = dict(plan)
    bad["params"] = dict(plan["params"])
    mutation(bad)
    result = execute_remove_duplicate_vertices(bad, auth, extractor=lambda:(s,digest))
    assert not result.ok
    assert s == make_scene()


@pytest.mark.parametrize("auth_change", [
    lambda a: a.update({"decision":"REJECTED"}),
    lambda a: a.update({"correction_type":"REMOVE_ISOLATED_VERTICES"}),
    lambda a: a.update({"plan_id":"b"*64}),
    lambda a: a.update({"correction_id":"b"*64}),
    lambda a: a.update({"source_report_digest":"b"*64}),
])
def test_hostile_authorization_fails_without_mutation(auth_change):
    s = make_scene()
    plan, auth, digest = authorized(s)
    bad = dict(auth)
    auth_change(bad)
    result = execute_remove_duplicate_vertices(plan, bad, extractor=lambda:(s,digest))
    assert not result.ok
    assert s == make_scene()


def test_repeated_execution_is_deterministic():
    s = make_scene()
    plan, auth, digest = authorized(s)
    first = execute_remove_duplicate_vertices(plan, auth, extractor=lambda:(s,digest))
    second = execute_remove_duplicate_vertices(plan, auth, extractor=lambda:(s,digest))
    assert first.ok and second.ok
    assert first.scene == second.scene
    assert s == make_scene()


def test_extractor_digest_mismatch_fails_closed():
    s = make_scene()
    plan, auth, _ = authorized(s)
    result = execute_remove_duplicate_vertices(plan, auth, extractor=lambda:(s,"b"*64))
    assert not result.ok
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert result.scene is None
    assert s == make_scene()


def test_no_tolerance_or_near_duplicate_selection():
    mesh = MeshModel(
        mesh_id="near",
        vertices=((0.,0.,0.), (1.,0.,0.), (1.,0.,1e-12), (0.,1.,0.)),
        faces=((0,1,3),),
    )
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),))
    with pytest.raises(ValueError):
        plan_duplicate_vertex_removal(scene, "a"*64, target_object_id="target", expected_duplicate_vertex_groups=[[1,2]])


def test_malformed_face_index_fails_closed():
    mesh = MeshModel(mesh_id="bad", vertices=((0.,0.,0.), (1.,0.,0.), (1.,0.,0.)), faces=((0,1,99),))
    scene = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),))
    with pytest.raises(ValueError):
        plan_duplicate_vertex_removal(scene, "a"*64, target_object_id="target", expected_duplicate_vertex_groups=[[1,2]])


def test_plan_is_not_authority():
    s = make_scene()
    plan, _, digest = authorized(s)
    result = execute_remove_duplicate_vertices(plan, {}, extractor=lambda:(s,digest))
    assert not result.ok
    assert result.outcome == "AUTHORIZATION_REFUSED"
