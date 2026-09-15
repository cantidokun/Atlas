from __future__ import annotations

import pytest

from planning.blender.duplicate_vertex_removal import (
    CORRECTION_TYPE,
    DuplicateVertexRemovalError,
    execute_remove_duplicate_vertices,
    plan_duplicate_vertex_removal,
)
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def scene():
    mesh = MeshModel(
        mesh_id="mesh-a",
        vertices=(
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (3.0, 3.0, 3.0),
        ),
        faces=((0, 1, 2), (0, 3, 5)),
        normals=((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)),
        materials=("mat",),
        local_frame_id="frame",
    )
    target = ObjectModel(object_id="target", name="Target", location=(3.0, 4.0, 5.0), mesh=mesh)
    other = ObjectModel(object_id="other", name="Other")
    return SceneModel(scene_id="scene", unit_system="METERS", objects=(target, other))


def auth_for(s, groups=((1, 3), (2, 4))):
    digest = "a" * 64
    plan = plan_duplicate_vertex_removal(
        s,
        digest,
        target_object_id="target",
        expected_duplicate_vertex_groups=[list(g) for g in groups],
    )
    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": digest,
    }
    return plan, auth, digest


def test_planner_finds_complete_exact_groups():
    plan, _, _ = auth_for(scene())
    assert plan["params"]["expected_duplicate_vertex_groups"] == [[1, 3], [2, 4]]


def test_executor_keeps_lowest_survivors_and_remaps_faces():
    s = scene()
    plan, auth, digest = auth_for(s)
    result = execute_remove_duplicate_vertices(plan, auth, extractor=lambda: (s, digest))
    assert result.ok
    out = result.scene.objects[0].mesh
    assert out.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (3.0, 3.0, 3.0))
    assert out.faces == ((0, 1, 2), (0, 1, 3))
    assert out.normals == s.objects[0].mesh.normals
    assert out.materials == s.objects[0].mesh.materials
    assert result.scene.objects[1] == s.objects[1]


def test_source_is_immutable_and_repeated_execution_is_deterministic():
    s = scene()
    before = s
    plan, auth, digest = auth_for(s)
    first = execute_remove_duplicate_vertices(plan, auth, extractor=lambda: (s, digest))
    second = execute_remove_duplicate_vertices(plan, auth, extractor=lambda: (s, digest))
    assert first.ok and second.ok
    assert first.scene == second.scene
    assert s == before


@pytest.mark.parametrize("bad_groups", [
    [[1]],
    [[3, 1]],
    [[1, 3], [3, 4]],
    [[True, 3]],
    [[-1, 3]],
    [[1, 99]],
    [[1, 3], [2]],
])
def test_malformed_group_authorization_rejected(bad_groups):
    with pytest.raises(DuplicateVertexRemovalError):
        plan_duplicate_vertex_removal(
            scene(),
            "a" * 64,
            target_object_id="target",
            expected_duplicate_vertex_groups=bad_groups,
        )


def test_one_representable_coordinate_difference_is_not_duplicate():
    mesh = MeshModel(
        mesh_id="m",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1e-12), (0.0, 1.0, 0.0)),
        faces=((0, 1, 3),),
    )
    s = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),))
    with pytest.raises(DuplicateVertexRemovalError):
        plan_duplicate_vertex_removal(s, "a" * 64, target_object_id="target", expected_duplicate_vertex_groups=[])


def test_face_containing_two_group_members_is_rejected():
    s = scene()
    mesh = MeshModel(
        mesh_id="collision",
        vertices=((0.,0.,0.), (1.,0.,0.), (1.,0.,0.), (0.,1.,0.)),
        faces=((0,1,2),),
    )
    s = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),))
    with pytest.raises(DuplicateVertexRemovalError) as exc:
        plan_duplicate_vertex_removal(s, "a" * 64, target_object_id="target", expected_duplicate_vertex_groups=[[1,2]])
    assert exc.value.code == "FACE_VERTEX_COLLISION"


def test_distinct_faces_collapsing_to_same_face_are_rejected():
    mesh = MeshModel(
        mesh_id="face-collision",
        vertices=((0.,0.,0.), (1.,0.,0.), (0.,1.,0.), (1.,0.,0.)),
        faces=((0,1,2), (0,3,2)),
    )
    s = SceneModel(scene_id="s", unit_system="METERS", objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),))
    with pytest.raises(DuplicateVertexRemovalError) as exc:
        plan_duplicate_vertex_removal(s, "a" * 64, target_object_id="target", expected_duplicate_vertex_groups=[[1,3]])
    assert exc.value.code == "FACE_IMAGE_COLLISION"


def test_plan_identity_is_deterministic():
    s = scene()
    first, _, _ = auth_for(s)
    second, _, _ = auth_for(s)
    assert first == second


def test_executor_rejects_stale_digest_without_mutation():
    s = scene()
    plan, auth, _ = auth_for(s)
    result = execute_remove_duplicate_vertices(plan, auth, extractor=lambda: (s, "b" * 64))
    assert not result.ok
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert s == scene()


def test_executor_rejects_forged_plan_identity():
    s = scene()
    plan, auth, digest = auth_for(s)
    bad_plan = dict(plan)
    bad_plan["plan_id"] = "b" * 64
    bad_auth = dict(auth)
    bad_auth["plan_id"] = bad_plan["plan_id"]
    result = execute_remove_duplicate_vertices(bad_plan, bad_auth, extractor=lambda: (s, digest))
    assert not result.ok
    assert result.failure_code == "PLAN_ID_MISMATCH"


def test_executor_rejects_forged_authorization():
    s = scene()
    plan, auth, digest = auth_for(s)
    bad_auth = dict(auth)
    bad_auth["decision"] = "REJECTED"
    result = execute_remove_duplicate_vertices(plan, bad_auth, extractor=lambda: (s, digest))
    assert not result.ok
    assert result.failure_code == "AUTHORIZATION_INVALID"


def test_executor_rejects_forged_extractor_digest():
    s = scene()
    plan, auth, _ = auth_for(s)
    result = execute_remove_duplicate_vertices(plan, auth, extractor=lambda: (s, "c" * 64))
    assert not result.ok
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert result.scene is None
