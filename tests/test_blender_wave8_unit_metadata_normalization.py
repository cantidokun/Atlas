"""Wave-8 deterministic/adversarial tests for alias-only unit metadata normalization."""
from __future__ import annotations

import pytest

from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel
from planning.blender.unit_metadata_normalization import (
    CORRECTION_TYPE,
    UnitMetadataNormalizationError,
    execute_unit_metadata_normalization,
    plan_unit_metadata_normalization,
)


def _scene(unit="meters"):
    mesh = MeshModel(
        mesh_id="m1",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
        normals=((0.0, 0.0, 1.0),),
        uvs=((0.0, 0.0),),
        materials=("pitch",),
        local_frame_id="frame-1",
    )
    obj = ObjectModel(
        object_id="o1",
        name="pitch",
        collection="Field",
        location=(3.0, 4.0, 5.0),
        scale=(1.2, 0.8, 1.5),
        rotation=(0.9, 0.1, 0.2, 0.3),
        mesh=mesh,
    )
    other = ObjectModel(object_id="o2", name="camera", collection="Field")
    return SceneModel(
        scene_id="s1",
        unit_system=unit,
        objects=(obj, other),
        coordinate_frame="world",
        world_bounds=((-10.0, -10.0, -1.0), (10.0, 10.0, 5.0)),
    )


def _extractor(scene, digest):
    return lambda: (scene, digest)


def test_meters_alias_normalizes_to_canonical_meters():
    scene = _scene("meters")
    digest = "a" * 64
    plan = plan_unit_metadata_normalization(scene, digest, current_unit="meters")
    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": digest,
    }
    result = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, digest))
    assert result.ok is True
    assert result.scene.unit_system == "METERS"
    assert result.scene.objects == scene.objects
    assert result.scene.coordinate_frame == scene.coordinate_frame
    assert result.scene.world_bounds == scene.world_bounds
    assert scene.unit_system == "meters"


def test_m_alias_normalizes_deterministically():
    scene = _scene("m")
    digest = "b" * 64
    plan = plan_unit_metadata_normalization(scene, digest, current_unit="m")
    assert plan["params"] == {"current_unit": "m", "target_unit": "METERS"}


def test_physically_different_unit_is_fail_closed():
    scene = _scene("INCHES")
    digest = "c" * 64
    with pytest.raises(UnitMetadataNormalizationError) as excinfo:
        plan_unit_metadata_normalization(scene, digest, current_unit="INCHES")
    assert excinfo.value.code == "PHYSICAL_UNIT_MISMATCH"


def test_noncanonical_target_is_rejected():
    scene = _scene("m")
    with pytest.raises(UnitMetadataNormalizationError) as excinfo:
        plan_unit_metadata_normalization(scene, "d" * 64, current_unit="m", target_unit="meters")
    assert excinfo.value.code == "TARGET_UNIT_INVALID"


def test_existing_canonical_token_is_not_a_noop_correction():
    scene = _scene("METERS")
    with pytest.raises(UnitMetadataNormalizationError) as excinfo:
        plan_unit_metadata_normalization(scene, "e" * 64, current_unit="METERS")
    assert excinfo.value.code == "ALREADY_CANONICAL"


def test_tampered_authorization_is_rejected_without_mutation():
    scene = _scene("m")
    digest = "f" * 64
    plan = plan_unit_metadata_normalization(scene, digest, current_unit="m")
    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": "tampered",
        "source_report_digest": digest,
    }
    result = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, digest))
    assert result.ok is False
    assert result.outcome == "AUTHORIZATION_REFUSED"
    assert scene.unit_system == "m"


def test_stale_source_is_rejected():
    scene = _scene("m")
    digest = "1" * 64
    fresh = "2" * 64
    plan = plan_unit_metadata_normalization(scene, digest, current_unit="m")
    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": digest,
    }
    result = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, fresh))
    assert result.ok is False
    assert result.failure_code == "SOURCE_DIGEST_MISMATCH"


def test_extra_plan_parameter_is_rejected():
    scene = _scene("m")
    digest = "3" * 64
    plan = dict(plan_unit_metadata_normalization(scene, digest, current_unit="m"))
    plan["params"] = {"current_unit": "m", "target_unit": "METERS", "scale": 39.37}
    auth = {"decision": "APPROVED", "correction_type": CORRECTION_TYPE}
    result = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, digest))
    assert result.ok is False
    assert result.failure_code == "PARAMS_INVALID"


def test_repeated_execution_is_deterministic_and_does_not_mutate_source():
    scene = _scene("m")
    digest = "4" * 64
    plan = plan_unit_metadata_normalization(scene, digest, current_unit="m")
    auth = {
        "decision": "APPROVED",
        "correction_type": CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": digest,
    }
    first = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, digest))
    second = execute_unit_metadata_normalization(plan, auth, extractor=_extractor(scene, digest))
    assert first.ok and second.ok
    assert first.output_scene_digest == second.output_scene_digest
    assert scene.unit_system == "m"
