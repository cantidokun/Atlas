from __future__ import annotations

from dataclasses import replace

import pytest

from planning.blender.parent_cycle import CYCLE_CORRECTION_TYPE, execute_repair_parent_cycle, plan_parent_cycle_correction
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def _scene() -> SceneModel:
    mesh_a = MeshModel(
        mesh_id="mesh-a",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
    )
    return SceneModel(
        scene_id="scene",
        unit_system="METRIC",
        objects=(
            ObjectModel(object_id="a", name="target", collection="Field", parent_object_id="b", mesh=mesh_a),
            ObjectModel(object_id="b", name="parent", collection="Field", parent_object_id="a"),
        ),
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


@pytest.mark.parametrize("field", ["collection", "visible", "mesh"])
def test_objectmodel_target_fields_are_protected(field):
    before = _scene()
    plan = plan_parent_cycle_correction(before, "a" * 64, target_object_id="a", expected_parent_id="b")
    working = before

    def extract():
        return working, "a" * 64

    def mutate(object_id, expected_parent_id, new_parent_id):
        nonlocal working
        target = working.objects[0]
        if field == "collection":
            target = replace(target, collection="ForgedCollection")
        elif field == "visible":
            target = replace(target, visible=False)
        else:
            target = replace(target, mesh=replace(target.mesh, mesh_id="forged-mesh"))
        target = replace(target, parent_object_id=new_parent_id)
        working = replace(working, objects=(target, working.objects[1]))

    result = execute_repair_parent_cycle(plan, _auth(plan), extractor=extract, mutator=mutate)
    assert result.ok is False
    assert result.failure_code == "TARGET_NON_PARENT_CHANGED"
