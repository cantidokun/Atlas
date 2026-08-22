import pytest

from planning.blender_evidence import BlenderEvidenceError, normalize_blender_result


def test_normalize_successful_blender_result():
    observation = normalize_blender_result(
        "inspect_scene_health",
        {"status": "ok", "warnings": ["unapplied_transform"], "healthy": False},
    )
    assert observation.verified is True
    assert observation.source == "inspect_scene_health"
    assert observation.facts == {"warnings": ["unapplied_transform"], "healthy": False}


def test_normalize_rejects_failed_result():
    with pytest.raises(BlenderEvidenceError, match="only successful"):
        normalize_blender_result("inspect_scene", {"status": "error", "error": "bad file"})


def test_normalize_rejects_non_object_result():
    with pytest.raises(BlenderEvidenceError, match="must be an object"):
        normalize_blender_result("inspect_scene", ["ok"])
