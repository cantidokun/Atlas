from __future__ import annotations

import copy

import pytest

from planning.blender.object_name_normalization import (
    CORRECTION_TYPE,
    execute_object_name_normalization,
    plan_object_name_normalization,
    scene_digest,
)
from planning.blender.scene_model import ObjectModel, SceneModel


def _scene() -> SceneModel:
    return SceneModel(
        scene_id="adv-9",
        unit_system="METERS",
        objects=(
            ObjectModel(object_id="obj.a", name="Bad Name"),
            ObjectModel(object_id="obj.b", name="good.name"),
        ),
    )


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
    }


def _plan(scene=None):
    scene = scene or _scene()
    digest = scene_digest(scene)
    return scene, plan_object_name_normalization(
        scene,
        digest,
        expected_object_id="obj.a",
        current_name="Bad Name",
        target_name="good_name",
    )


def test_duplicate_object_id_is_refused_during_planning():
    scene = SceneModel(
        scene_id="dup",
        unit_system="METERS",
        objects=(
            ObjectModel(object_id="obj.a", name="Bad Name"),
            ObjectModel(object_id="obj.a", name="other.name"),
        ),
    )
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj.a",
            current_name="Bad Name",
            target_name="fixed.name",
        )
    assert exc.value.code == "OBJECT_ID_RESOLUTION_INVALID"


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (lambda a, p: a.update(decision="REJECTED"), "AUTHORIZATION_INVALID"),
        (lambda a, p: a.update(correction_type="OTHER"), "AUTHORIZATION_INVALID"),
        (lambda a, p: a.update(correction_id="0" * 64), "CORRECTION_ID_MISMATCH"),
        (lambda a, p: a.update(plan_id="0" * 64), "PLAN_ID_MISMATCH"),
        (lambda a, p: a.update(source_report_digest="0" * 64), "SOURCE_REPORT_DIGEST_MISMATCH"),
    ],
)
def test_authorization_bindings_fail_closed(mutator, expected):
    scene, plan = _plan()
    auth = _auth(plan)
    mutator(auth, plan)
    out = execute_object_name_normalization(plan, auth, extractor=lambda: (scene, scene_digest(scene)))
    assert not out.ok
    assert out.failure_code == expected


def test_fresh_object_name_mismatch_fails_closed():
    scene, plan = _plan()
    fresh = SceneModel(
        scene_id=scene.scene_id,
        unit_system=scene.unit_system,
        objects=(ObjectModel(object_id="obj.a", name="different.name"), scene.objects[1]),
    )
    out = execute_object_name_normalization(plan, _auth(plan), extractor=lambda: (fresh, scene_digest(fresh)))
    assert not out.ok
    assert out.failure_code == "SOURCE_DIGEST_MISMATCH"


def test_forged_params_target_name_fail_closed():
    scene, plan = _plan()
    forged = copy.deepcopy(plan)
    forged["params"]["target_name"] = "good.name"
    out = execute_object_name_normalization(forged, _auth(plan), extractor=lambda: (scene, scene_digest(scene)))
    assert not out.ok
    assert out.failure_code in {"PLAN_ID_MISMATCH", "NAME_COLLISION"}


def test_non_string_target_is_rejected():
    scene = _scene()
    with pytest.raises(ValueError) as exc:
        plan_object_name_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj.a",
            current_name="Bad Name",
            target_name=123,
        )
    assert exc.value.code == "STRING_TYPE_INVALID"
