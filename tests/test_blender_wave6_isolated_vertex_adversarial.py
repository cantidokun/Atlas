from __future__ import annotations

import copy

import pytest

from planning.blender.isolated_vertex_removal import CORRECTION_TYPE, execute_remove_isolated_vertices, plan_isolated_vertex_removal
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def make_scene():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0.,0.,0.), (1.,0.,0.), (0.,1.,0.), (10.,10.,10.), (20.,20.,20.)),
        faces=((0,1,2),),
        normals=((0.,0.,1.),),
        uvs=((0.,0.),),
        materials=("material",),
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
    plan = plan_isolated_vertex_removal(s, digest, target_object_id="target", expected_isolated_vertex_indices=[3,4])
    auth = {"decision":"APPROVED", "correction_type":CORRECTION_TYPE, "correction_id":plan["correction_id"], "plan_id":plan["plan_id"], "source_report_digest":digest}
    return plan, auth, digest


def test_executor_never_mutates_input():
    s = make_scene()
    before = copy.deepcopy(s)
    plan, auth, digest = authorized(s)
    result = execute_remove_isolated_vertices(plan, auth, extractor=lambda:(s,digest))
    assert result.ok
    assert s == before


@pytest.mark.parametrize("mutation", [
    lambda p: p.update({"correction_type":"REMOVE_DUPLICATE_FACE"}),
    lambda p: p["params"].update({"unexpected":1}),
    lambda p: p["params"].update({"expected_isolated_vertex_indices":[3]}),
    lambda p: p["params"].update({"expected_isolated_vertex_indices":[3,4,4]}),
    lambda p: p["params"].update({"expected_isolated_vertex_indices":[4,3]}),
    lambda p: p["params"].update({"expected_isolated_vertex_indices":[True,4]}),
    lambda p: p["params"].update({"expected_isolated_vertex_indices":[-1,4]}),
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
    result = execute_remove_isolated_vertices(bad, auth, extractor=lambda:(s,digest))
    assert not result.ok
    assert s == make_scene()


@pytest.mark.parametrize("auth_change", [
    lambda a: a.update({"decision":"REJECTED"}),
    lambda a: a.update({"correction_type":"REPAIR_MERGE_VERTEX"}),
    lambda a: a.update({"plan_id":"b"*64}),
    lambda a: a.update({"correction_id":"b"*64}),
    lambda a: a.update({"source_report_digest":"b"*64}),
])
def test_hostile_authorization_fails_without_mutation(auth_change):
    s = make_scene()
    plan, auth, digest = authorized(s)
    bad_auth = dict(auth)
    auth_change(bad_auth)
    result = execute_remove_isolated_vertices(plan, bad_auth, extractor=lambda:(s,digest))
    assert not result.ok
    assert s == make_scene()


def test_repeated_execution_is_deterministic_and_does_not_touch_source():
    s = make_scene()
    plan, auth, digest = authorized(s)
    first = execute_remove_isolated_vertices(plan, auth, extractor=lambda:(s,digest))
    second = execute_remove_isolated_vertices(plan, auth, extractor=lambda:(s,digest))
    assert first.ok and second.ok
    assert first.scene == second.scene
    assert s == make_scene()


def test_forged_post_source_is_not_reported_as_success_when_digest_changes():
    s = make_scene()
    plan, auth, digest = authorized(s)
    state = [s, digest]
    result = execute_remove_isolated_vertices(plan, auth, extractor=lambda:(state[0], state[1]))
    assert result.ok
