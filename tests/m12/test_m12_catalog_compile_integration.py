"""M12.2 deterministic tests — catalog→composition→compile integration + authority."""

import pytest

from planning.m12 import (
    DEFAULT_UNREAL_CATALOG,
    UnsupportedCompileMappingError,
    compile_unreal_semantic_task,
)
from planning.task_definition import AtlasTaskDefinition


def _resolve(name, params, twin="twin-1", **kw):
    return DEFAULT_UNREAL_CATALOG.resolve(name, params, digital_twin_id=twin, **kw)


def test_composed_non_render_task_compiles():
    task = _resolve(
        "unreal.sequence-configure",
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
    )
    compiled = compile_unreal_semantic_task(task)
    assert isinstance(compiled, AtlasTaskDefinition)
    assert compiled.metadata["unreal_semantic_task_class"] == "sequence-configure"
    assert compiled.metadata["unreal_semantic_task_id"] == "unreal.sequence-configure"
    # Catalog/fragment provenance survives into the compiled metadata.
    assert "unreal_target_state" in compiled.metadata
    assert "catalog_version" in compiled.metadata["unreal_provenance"] or "catalog_version" in str(compiled.metadata)


def test_render_task_resolution_compiles_fails_closed():
    task = _resolve(
        "unreal.render-execute",
        {"twin_id": "twin-1", "sequence_name": "main"},
    )
    assert task.render_task
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


def test_artifact_validate_render_compile_fails_closed():
    task = _resolve(
        "unreal.artifact-validate",
        {"twin_id": "twin-1", "artifact_ref": "art-1"},
    )
    with pytest.raises(UnsupportedCompileMappingError):
        compile_unreal_semantic_task(task)


def test_composed_task_has_no_authority_material():
    task = _resolve(
        "unreal.camera-configure",
        {"twin_id": "twin-1", "camera_slots": [1]},
    )
    compiled = compile_unreal_semantic_task(task)
    text = str(compiled.snapshot()).lower()
    for token in ("receipt", "authorization_id", "manifest_id", "hmac", "nonce"):
        assert token not in text, f"authority token leaked: {token}"


def test_composed_task_does_not_collapse_identity():
    task = _resolve(
        "unreal.scene-prepare",
        {"twin_id": "twin-stadium-01"},
        twin="twin-stadium-01",
    )
    assert task.digital_twin_id == "twin-stadium-01"
    assert "artifact_id" not in task.to_json_compatible()


def test_composition_dependencies_preserved_in_compile():
    task = _resolve(
        "unreal.sequence-configure",
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
    )
    compiled = compile_unreal_semantic_task(task)
    assert compiled.metadata["unreal_semantic_dependencies"] == [
        "scene_setup",
        "camera_setup",
        "sequence_setup",
    ]