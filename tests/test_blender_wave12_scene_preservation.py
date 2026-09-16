from __future__ import annotations

from dataclasses import replace

from planning.blender.parent_cycle import CYCLE_CORRECTION_TYPE, execute_repair_parent_cycle, plan_parent_cycle_correction
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def _scene() -> SceneModel:
    mesh = MeshModel(
        mesh_id="mesh",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
    )
    return SceneModel(
        scene_id="scene",
        unit_system="METRIC",
        objects=(
            ObjectModel(object_id="a", name="target", parent_object_id="b", mesh=mesh),
            ObjectModel(object_id="b", name="parent", parent_object_id="a"),
        ),
        coordinate_frame="WORLD",
        world_bounds=((0.0, 0.0, 0.0), (10.0, 10.0, 10.0)),
    )


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": "a" * 64,
        "target_object_id": "a",
        "expected_parent_id": "b",
    }


def test_scene_level_state_must_remain_unchanged():
    before = _scene()
    plan = plan_parent_cycle_correction(before, "a" * 64, target_object_id="a", expected_parent_id="b")
    working = before

    def extract():
        return working, "a" * 64

    def mutate(object_id, expected_parent_id, new_parent_id):
        nonlocal working
        target = replace(working.objects[0], parent_object_id=new_parent_id)
        working = replace(working, scene_id="forged-scene", objects=(target, working.objects[1]))

    result = execute_repair_parent_cycle(plan, _auth(plan), extractor=extract, mutator=mutate)
    assert result.ok is False
    assert result.failure_code == "SCENE_STATE_CHANGED"
