from __future__ import annotations

import pytest

from planning.blender.isolated_vertex_removal import (
    CORRECTION_TYPE,
    IsolatedVertexRemovalError,
    execute_remove_isolated_vertices,
    plan_isolated_vertex_removal,
)
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def scene():
    mesh = MeshModel(
        mesh_id="mesh-a",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (9.0, 9.0, 9.0), (8.0, 8.0, 8.0)),
        faces=((0, 1, 2),),
        normals=((0.0, 0.0, 1.0),),
        materials=("mat",),
    )
    unrelated = ObjectModel(object_id="other", name="Other")
    target = ObjectModel(object_id="target", name="Target", location=(3.0, 4.0, 5.0), mesh=mesh)
    return SceneModel(scene_id="scene", unit_system="METERS", objects=(target, unrelated))


def test_planner_requires_exact_isolated_set():
    s = scene()
    plan = plan_isolated_vertex_removal(s, "a" * 64, target_object_id="target", expected_isolated_vertex_indices=[3, 4])
    assert plan["correction_type"] == CORRECTION_TYPE
    assert plan["params"]["expected_isolated_vertex_indices"] == [3, 4]
    with pytest.raises(IsolatedVertexRemovalError):
        plan_isolated_vertex_removal(s, "a" * 64, target_object_id="target", expected_isolated_vertex_indices=[3])


@pytest.mark.parametrize("bad", [[4, 3], [3, 3], [-1, 3], [True, 3], [3, 99], ()])
def test_planner_rejects_malformed_selection(bad):
    with pytest.raises(IsolatedVertexRemovalError):
        plan_isolated_vertex_removal(scene(), "a" * 64, target_object_id="target", expected_isolated_vertex_indices=bad)


def test_executor_remaps_only_surviving_vertices_and_faces():
    s = scene()
    digest = "a" * 64
    plan = plan_isolated_vertex_removal(s, digest, target_object_id="target", expected_isolated_vertex_indices=[3, 4])
    auth = {"decision": "APPROVED", "correction_type": CORRECTION_TYPE, "correction_id": plan["correction_id"], "plan_id": plan["plan_id"], "source_report_digest": digest}
    calls = []
    result = execute_remove_isolated_vertices(plan, auth, extractor=lambda: (s, digest))
    assert result.ok
    assert result.scene is not None
    out = result.scene.objects[0].mesh
    assert out.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert out.faces == ((0, 1, 2),)
    assert out.normals == s.objects[0].mesh.normals
    assert out.materials == s.objects[0].mesh.materials
    assert result.scene.objects[1] == s.objects[1]
    assert calls == []


def test_executor_rejects_stale_source_without_mutation():
    s = scene()
    plan = plan_isolated_vertex_removal(s, "a" * 64, target_object_id="target", expected_isolated_vertex_indices=[3, 4])
    auth = {"decision": "APPROVED", "correction_type": CORRECTION_TYPE, "correction_id": plan["correction_id"], "plan_id": plan["plan_id"], "source_report_digest": "a" * 64}
    result = execute_remove_isolated_vertices(plan, auth, extractor=lambda: (s, "b" * 64))
    assert not result.ok
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"
    assert s.objects[0].mesh.vertices[-2:] == ((9.0, 9.0, 9.0), (8.0, 8.0, 8.0))


def test_executor_rejects_forged_plan_identity():
    s = scene()
    digest = "a" * 64
    plan = dict(plan_isolated_vertex_removal(s, digest, target_object_id="target", expected_isolated_vertex_indices=[3, 4]))
    plan["plan_id"] = "b" * 64
    auth = {"decision": "APPROVED", "correction_type": CORRECTION_TYPE, "correction_id": plan["correction_id"], "plan_id": plan["plan_id"], "source_report_digest": digest}
    result = execute_remove_isolated_vertices(plan, auth, extractor=lambda: (s, digest))
    assert not result.ok
    assert result.failure_code == "PLAN_ID_MISMATCH"


def test_executor_rejects_partial_or_extra_set_at_execution():
    s = scene()
    digest = "a" * 64
    plan = plan_isolated_vertex_removal(s, digest, target_object_id="target", expected_isolated_vertex_indices=[3, 4])
    bad = dict(plan)
    bad["params"] = {"expected_isolated_vertex_indices": [3]}
    auth = {"decision": "APPROVED", "correction_type": CORRECTION_TYPE, "correction_id": plan["correction_id"], "plan_id": plan["plan_id"], "source_report_digest": digest}
    result = execute_remove_isolated_vertices(bad, auth, extractor=lambda: (s, digest))
    assert not result.ok
    assert result.failure_code == "PLAN_ID_MISMATCH"


def test_no_isolated_vertices_is_not_an_arbitrary_delete():
    s = scene()
    mesh = s.objects[0].mesh
    clean = MeshModel(mesh_id=mesh.mesh_id, vertices=mesh.vertices[:3], faces=mesh.faces)
    clean_scene = SceneModel(scene_id=s.scene_id, unit_system=s.unit_system, objects=(ObjectModel(object_id="target", name="Target", mesh=clean), s.objects[1]))
    with pytest.raises(IsolatedVertexRemovalError):
        plan_isolated_vertex_removal(clean_scene, "a" * 64, target_object_id="target", expected_isolated_vertex_indices=[])
