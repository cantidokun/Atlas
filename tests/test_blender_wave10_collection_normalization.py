"""Wave-10 deterministic/adversarial tests for bounded object collection normalization."""
from __future__ import annotations

import copy

import pytest

from planning.blender.collection_normalization import (
    CollectionNormalizationError,
    execute_object_collection_normalization,
    plan_object_collection_normalization,
    scene_digest,
)
from planning.blender.scene_model import ObjectModel, SceneModel


def _scene(*, collection: str = "Offworld", extra: bool = True) -> SceneModel:
    objects = [
        ObjectModel(object_id="obj-1", name="pitch", collection=collection),
    ]
    if extra:
        objects.append(ObjectModel(object_id="obj-2", name="goal", collection="Field"))
    return SceneModel(scene_id="scene-1", unit_system="METERS", objects=tuple(objects))


def _plan(scene: SceneModel):
    return plan_object_collection_normalization(
        scene,
        scene_digest(scene),
        expected_object_id="obj-1",
        current_collection="Offworld",
        target_collection="Field",
        allowed_collections=["Field", "Goals"],
    )


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": plan["correction_type"],
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
    }


def _extractor(scene: SceneModel, supplied_digest=None):
    return lambda: (scene, scene_digest(scene) if supplied_digest is None else supplied_digest)


def test_plan_is_deterministic_and_binds_allowlist():
    scene = _scene()
    p1 = _plan(scene)
    p2 = _plan(scene)
    assert p1 == p2
    assert p1["correction_type"] == "NORMALIZE_OBJECT_COLLECTION"
    assert p1["params"]["allowed_collections"] == ["Field", "Goals"]


def test_success_changes_only_target_collection():
    scene = _scene()
    plan = _plan(scene)
    result = execute_object_collection_normalization(plan, _auth(plan), extractor=_extractor(scene))
    assert result.ok is True
    assert result.failure_code is None
    assert result.scene.objects[0].collection == "Field"
    assert result.scene.objects[0].name == "pitch"
    assert result.scene.objects[1].collection == "Field"
    assert result.output_scene_digest == scene_digest(result.scene)


def test_source_scene_remains_immutable():
    scene = _scene()
    before = copy.deepcopy(scene)
    plan = _plan(scene)
    execute_object_collection_normalization(plan, _auth(plan), extractor=_extractor(scene))
    assert scene == before


def test_already_canonical_rejected():
    scene = _scene(collection="Field")
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Field",
            target_collection="Field",
            allowed_collections=["Field", "Goals"],
        )
    assert exc.value.code == "ALREADY_CANONICAL"


def test_target_outside_allowlist_rejected():
    scene = _scene()
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Offworld",
            target_collection="GoalsArchive",
            allowed_collections=["Field", "Goals"],
        )
    assert exc.value.code == "TARGET_COLLECTION_INVALID"


def test_current_collection_mismatch_rejected():
    scene = _scene()
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Wrong",
            target_collection="Field",
            allowed_collections=["Field", "Goals"],
        )
    assert exc.value.code == "CURRENT_COLLECTION_MISMATCH"


def test_missing_collection_is_not_executable():
    scene = _scene(collection="Offworld")
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection=None,
            target_collection="Field",
            allowed_collections=["Field"],
        )
    assert exc.value.code == "CURRENT_COLLECTION_INVALID"


def test_duplicate_object_id_fails_closed():
    scene = SceneModel(
        scene_id="scene-1",
        unit_system="METERS",
        objects=(
            ObjectModel(object_id="obj-1", name="pitch", collection="Offworld"),
            ObjectModel(object_id="obj-1", name="other", collection="Field"),
        ),
    )
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Offworld",
            target_collection="Field",
            allowed_collections=["Field"],
        )
    assert exc.value.code == "OBJECT_ID_RESOLUTION_INVALID"


def test_extra_plan_parameter_fails_closed():
    scene = _scene()
    plan = _plan(scene)
    plan = copy.deepcopy(plan)
    plan["params"]["inferred_collection"] = "Field"
    result = execute_object_collection_normalization(plan, _auth(_plan(scene)), extractor=_extractor(scene))
    assert result.failure_code == "PARAMS_INVALID"


def test_forged_authorization_extra_key_fails_closed():
    scene = _scene()
    plan = _plan(scene)
    auth = _auth(plan)
    auth["target_collection"] = "Goals"
    result = execute_object_collection_normalization(plan, auth, extractor=_extractor(scene))
    assert result.failure_code == "AUTHORIZATION_INVALID"


def test_forged_correction_id_preserves_specific_mismatch_code():
    scene = _scene()
    plan = _plan(scene)
    auth = _auth(plan)
    auth["correction_id"] = "0" * 64
    result = execute_object_collection_normalization(plan, auth, extractor=_extractor(scene))
    assert result.failure_code == "CORRECTION_ID_MISMATCH"


def test_forged_plan_id_preserves_specific_mismatch_code():
    scene = _scene()
    plan = _plan(scene)
    auth = _auth(plan)
    auth["plan_id"] = "0" * 64
    result = execute_object_collection_normalization(plan, auth, extractor=_extractor(scene))
    assert result.failure_code == "PLAN_ID_MISMATCH"


def test_forged_source_binding_preserves_specific_mismatch_code():
    scene = _scene()
    plan = _plan(scene)
    auth = _auth(plan)
    auth["source_report_digest"] = "0" * 64
    result = execute_object_collection_normalization(plan, auth, extractor=_extractor(scene))
    assert result.failure_code == "SOURCE_REPORT_DIGEST_MISMATCH"


def test_forged_plan_body_fails_closed_before_extraction():
    scene = _scene()
    plan = _plan(scene)
    forged = copy.deepcopy(plan)
    forged["params"]["target_collection"] = "Goals"
    result = execute_object_collection_normalization(forged, _auth(plan), extractor=_extractor(scene))
    assert result.failure_code == "CORRECTION_ID_MISMATCH" or result.failure_code == "PLAN_ID_MISMATCH"


def test_forged_extractor_digest_is_not_trusted():
    scene = _scene()
    plan = _plan(scene)
    result = execute_object_collection_normalization(
        plan,
        _auth(plan),
        extractor=_extractor(scene, supplied_digest="0" * 64),
    )
    assert result.failure_code == "SOURCE_DIGEST_INVALID"


def test_forged_extractor_scene_cannot_pass_postcondition():
    source = _scene()
    mutated = _scene()
    mutated = SceneModel(
        scene_id=mutated.scene_id,
        unit_system=mutated.unit_system,
        objects=(
            ObjectModel(object_id="obj-1", name="pitch-renamed", collection="Offworld"),
            mutated.objects[1],
        ),
    )
    plan = _plan(source)
    result = execute_object_collection_normalization(plan, _auth(plan), extractor=lambda: (mutated, scene_digest(mutated)))
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"


def test_plan_allowlist_order_is_canonicalized():
    scene = _scene()
    p1 = plan_object_collection_normalization(
        scene,
        scene_digest(scene),
        expected_object_id="obj-1",
        current_collection="Offworld",
        target_collection="Field",
        allowed_collections=["Goals", "Field"],
    )
    p2 = _plan(scene)
    assert p1 == p2


def test_empty_allowlist_fails_closed():
    scene = _scene()
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Offworld",
            target_collection="Field",
            allowed_collections=[],
        )
    assert exc.value.code == "ALLOWED_COLLECTIONS_INVALID"


def test_duplicate_allowlist_fails_closed():
    scene = _scene()
    with pytest.raises(CollectionNormalizationError) as exc:
        plan_object_collection_normalization(
            scene,
            scene_digest(scene),
            expected_object_id="obj-1",
            current_collection="Offworld",
            target_collection="Field",
            allowed_collections=["Field", "Field"],
        )
    assert exc.value.code == "ALLOWED_COLLECTIONS_INVALID"


def test_non_collection_state_change_is_detected():
    scene = _scene()
    plan = _plan(scene)
    mutated = SceneModel(
        scene_id=scene.scene_id,
        unit_system=scene.unit_system,
        objects=(
            ObjectModel(object_id="obj-1", name="pitch", collection="Offworld", location=(1.0, 0.0, 0.0)),
            scene.objects[1],
        ),
    )
    forged_plan = copy.deepcopy(plan)
    forged_plan["source_report_digest"] = scene_digest(mutated)
    result = execute_object_collection_normalization(forged_plan, _auth(forged_plan), extractor=lambda: (mutated, scene_digest(mutated)))
    assert result.failure_code == "CORRECTION_ID_MISMATCH" or result.failure_code == "PLAN_ID_MISMATCH"
