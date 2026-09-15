from __future__ import annotations

import pytest

from planning.blender.duplicate_vertex_removal import (
    CORRECTION_TYPE,
    DuplicateVertexRemovalError,
    execute_remove_duplicate_vertices,
    plan_duplicate_vertex_removal,
)
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def make_nonmanifold_after_collapse_scene() -> SceneModel:
    # Vertices 0 and 1 are exact duplicates. Before collapse, edge (0,2)
    # has valence 1 and edge (1,2) has valence 2. After 1 -> 0, the three
    # source incidences collapse onto edge (0,2), producing valence 3.
    # No face contains both duplicate members and no two remapped faces collide.
    mesh = MeshModel(
        mesh_id="nm",
        vertices=(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 2.0, 0.0),
        ),
        faces=((0, 2, 3), (1, 2, 4), (1, 2, 5)),
    )
    return SceneModel(
        scene_id="s",
        unit_system="METERS",
        objects=(ObjectModel(object_id="target", name="Target", mesh=mesh),),
    )


def test_planner_rejects_new_nonmanifold_edge_from_duplicate_collapse():
    scene = make_nonmanifold_after_collapse_scene()
    with pytest.raises(DuplicateVertexRemovalError) as exc:
        plan_duplicate_vertex_removal(
            scene,
            "a" * 64,
            target_object_id="target",
            expected_duplicate_vertex_groups=[[0, 1]],
        )
    assert exc.value.code == "NONMANIFOLD_INTRODUCED"


def test_executor_rejects_same_case_without_mutation():
    scene = make_nonmanifold_after_collapse_scene()
    source_digest = "a" * 64
    try:
        plan = plan_duplicate_vertex_removal(
            scene,
            source_digest,
            target_object_id="target",
            expected_duplicate_vertex_groups=[[0, 1]],
        )
    except DuplicateVertexRemovalError as exc:
        assert exc.code == "NONMANIFOLD_INTRODUCED"
        return

    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": source_digest,
    }
    before = scene
    result = execute_remove_duplicate_vertices(
        plan,
        auth,
        extractor=lambda: (scene, source_digest),
    )
    assert not result.ok
    assert result.failure_code == "NONMANIFOLD_INTRODUCED"
    assert result.scene is None
    assert scene == before
