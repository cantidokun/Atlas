from __future__ import annotations

import copy

import pytest

from planning.blender.object_name_normalization import (
    CORRECTION_TYPE,
    _SUPPORTED_PATTERN,
    execute_object_name_normalization,
    plan_object_name_normalization,
    scene_digest,
)
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def _scene(name: str = "Pitch Main") -> SceneModel:
    mesh = MeshModel(
        mesh_id="mesh.pitch",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
    )
    return SceneModel(
        scene_id="scene-9",
        unit_system="METERS",
        objects=(
            ObjectModel(
                object_id="obj.pitch",
                name=name,
                collection="Field",
                location=(1.0, 2.0, 3.0),
                scale=(1.0, 1.0, 1.0),
                rotation=(1.0, 0.0, 0.0, 0.0),
                mesh=mesh,
            ),
            ObjectModel(object_id="obj.goal", name="goal.left", collection="Goals"),
        ),
        coordinate_frame="world-z-up",
        world_bounds=((-2.0, -2.0, 0.0), (2.0, 2.0, 3.0)),
    )


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
    }


def test_plan_is_deterministic_and_bound_to_target_name():
    scene = _scene()
    digest = scene_digest(scene)
    a = plan_object_name_normalization(
        scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main"
    )
    b = plan_object_name_normalization(
        scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main"
    )
    assert a == b
    assert a["correction_type"] == CORRECTION_TYPE
    assert a["params"]["target_name"] == "pitch.main"
    assert a["params"]["name_pattern"] == _SUPPORTED_PATTERN


def test_execute_changes_only_target_name():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (_scene(), digest))
    assert out.ok
    assert out.scene is not None
    assert out.scene.objects[0].name == "pitch.main"
    assert out.scene.objects[0].object_id == "obj.pitch"
    assert out.scene.objects[1] == scene.objects[1]
    assert out.output_scene_digest == scene_digest(out.scene)


def test_non_name_payload_is_unchanged():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (scene, digest))
    assert out.ok
    assert [(o.object_id, o.collection, o.parent_object_id, o.location, o.scale, o.rotation, o.visible, o.mesh) for o in out.scene.objects] == [
        (o.object_id, o.collection, o.parent_object_id, o.location, o.scale, o.rotation, o.visible, o.mesh) for o in scene.objects
    ]
    assert out.scene.unit_system == scene.unit_system
    assert out.scene.coordinate_frame == scene.coordinate_frame
    assert out.scene.world_bounds == scene.world_bounds


@pytest.mark.parametrize("target", ["", "Upper.Name", "name with space", "a/b", "-bad", ".bad"])
def test_invalid_target_name_rejected(target):
    scene = _scene()
    with pytest.raises(ValueError):
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.pitch", current_name="Pitch Main", target_name=target)


def test_already_canonical_rejected():
    scene = _scene("Pitch Main")
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.pitch", current_name="Pitch Main", target_name="Pitch Main")
    assert exc.value.code == "ALREADY_CANONICAL"


def test_name_collision_rejected():
    scene = _scene()
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.pitch", current_name="Pitch Main", target_name="goal.left")
    assert exc.value.code == "NAME_COLLISION"


def test_unknown_pattern_rejected():
    scene = _scene()
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main", name_pattern=r".*")
    assert exc.value.code == "NAME_PATTERN_UNSUPPORTED"


def test_current_name_mismatch_rejected():
    scene = _scene()
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.pitch", current_name="wrong", target_name="pitch.main")
    assert exc.value.code == "CURRENT_NAME_MISMATCH"


def test_missing_object_rejected():
    scene = _scene()
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(scene, scene_digest(scene), expected_object_id="obj.missing", current_name="Pitch Main", target_name="pitch.main")
    assert exc.value.code == "OBJECT_ID_RESOLUTION_INVALID"


def test_stale_source_digest_fails_closed():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    changed = _scene("Pitch Main")
    changed = SceneModel(scene_id=changed.scene_id, unit_system=changed.unit_system, objects=(changed.objects[0], ObjectModel(object_id="obj.goal", name="goal.right", collection="Goals")), coordinate_frame=changed.coordinate_frame, world_bounds=changed.world_bounds)
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (changed, scene_digest(changed)))
    assert not out.ok
    assert out.outcome == "SOURCE_MISMATCH"
    assert out.failure_code == "SOURCE_DIGEST_MISMATCH"


def test_forged_plan_id_fails_closed():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    forged = copy.deepcopy(plan)
    forged["plan_id"] = "0" * 64
    out = execute_object_name_normalization(forged, _auth(plan), extractor=lambda: (scene, digest))
    assert not out.ok
    assert out.failure_code == "PLAN_ID_MISMATCH"


def test_forged_authorization_fails_closed():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    auth = _auth(plan)
    auth["target_name"] = "evil"  # unknown/irrelevant auth content must not create authority
    out = execute_object_name_normalization(plan, auth, extractor=lambda: (scene, digest))
    assert not out.ok
    assert out.failure_code == "AUTHORIZATION_INVALID"


def test_missing_parameter_fails_closed():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    plan["params"].pop("target_name")
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (scene, digest))
    assert not out.ok
    assert out.failure_code == "PARAMS_INVALID"


def test_extra_parameter_fails_closed():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    plan["params"]["unexpected"] = "x"
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (scene, digest))
    assert not out.ok
    assert out.failure_code == "PARAMS_INVALID"


def test_non_target_name_change_cannot_pass_postcondition():
    scene = _scene()
    digest = scene_digest(scene)
    plan = plan_object_name_normalization(scene, digest, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    tampered = SceneModel(
        scene_id=scene.scene_id,
        unit_system=scene.unit_system,
        objects=(
            scene.objects[0],
            ObjectModel(object_id="obj.goal", name="goal.touched", collection="Goals"),
        ),
        coordinate_frame=scene.coordinate_frame,
        world_bounds=scene.world_bounds,
    )
    # extractor is allowed to return a source whose digest claims to be fresh only if it really matches;
    # the mismatch must therefore fail before mutation.
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (tampered, digest))
    assert not out.ok
    assert out.failure_code == "NON_NAME_STATE_CHANGED" or out.outcome == "PRECONDITION_FAILED"


def test_source_scene_remains_immutable():
    scene = _scene()
    before = scene_digest(scene)
    plan = plan_object_name_normalization(scene, before, expected_object_id="obj.pitch", current_name="Pitch Main", target_name="pitch.main")
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (scene, before))
    assert out.ok
    assert scene.objects[0].name == "Pitch Main"
    assert scene_digest(scene) == before
