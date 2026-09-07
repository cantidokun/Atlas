"""M12.2 deterministic tests — Unreal semantic production catalog."""

import json

import pytest

from planning.m12 import (
    DEFAULT_UNREAL_CATALOG,
    UnrealCatalogError,
    UnrealProductionTaskDefinition,
    UnsupportedCatalogVersionError,
    UnknownCatalogTaskError,
    InvalidCatalogParametersError,
)


def test_catalog_has_explicit_version():
    assert DEFAULT_UNREAL_CATALOG.version >= 1
    assert "catalog_version" in DEFAULT_UNREAL_CATALOG.to_json_compatible()


def test_available_task_names_is_stable():
    names = DEFAULT_UNREAL_CATALOG.available_task_names()
    assert names == tuple(sorted(names))
    assert "unreal.camera-configure" in names
    assert "unreal.render-execute" in names


def test_resolve_camera_configure_returns_valid_task():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.camera-configure",
        {"twin_id": "twin-1", "camera_slots": [1, 2, 3]},
        digital_twin_id="twin-1",
        provenance={"proposal_source": "qwen-proposal-v1"},
    )
    assert isinstance(task, UnrealProductionTaskDefinition)
    assert task.task_class == "camera-configure"
    assert task.digital_twin_id == "twin-1"
    assert task.canonical_task_id == "unreal.camera-configure"


def test_resolution_is_deterministic():
    a = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.lighting-configure",
        {"twin_id": "twin-1", "lighting_rig": {"rig": "A"}},
        digital_twin_id="twin-1",
    )
    b = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.lighting-configure",
        {"twin_id": "twin-1", "lighting_rig": {"rig": "A"}},
        digital_twin_id="twin-1",
    )
    assert a == b
    assert a.canonical_json() == b.canonical_json()


def test_canonical_json_is_stable():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.scene-prepare",
        {"twin_id": "twin-1"},
        digital_twin_id="twin-1",
    )
    j1 = task.canonical_json()
    j2 = task.canonical_json()
    assert j1 == j2
    assert json.loads(j1)["task_class"] == "scene-prepare"


def test_unknown_task_fails_closed():
    with pytest.raises(UnknownCatalogTaskError):
        DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.does-not-exist",
            {"twin_id": "twin-1"},
            digital_twin_id="twin-1",
        )


def test_unsupported_version_fails_closed():
    with pytest.raises(UnsupportedCatalogVersionError):
        DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.camera-configure",
            {"twin_id": "twin-1", "camera_slots": []},
            digital_twin_id="twin-1",
            version=999,
        )


def test_missing_parameter_fails_closed():
    with pytest.raises(InvalidCatalogParametersError):
        DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.camera-configure",
            {"twin_id": "twin-1"},  # missing camera_slots
            digital_twin_id="twin-1",
        )


def test_unexpected_parameter_fails_closed():
    with pytest.raises(InvalidCatalogParametersError):
        DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.scene-prepare",
            {"twin_id": "twin-1", "bogus": 1},
            digital_twin_id="twin-1",
        )


def test_wrong_parameter_type_fails_closed():
    # scene-prepare requires int frame params for sequence-configure; for
    # camera-configure camera_slots must be JSON-serializable.
    with pytest.raises((InvalidCatalogParametersError, UnrealCatalogError)):
        DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.camera-configure",
            {"twin_id": "twin-1", "camera_slots": object()},
            digital_twin_id="twin-1",
        )


def test_render_execute_has_render_expectant_target():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.render-execute",
        {"twin_id": "twin-1", "sequence_name": "seq"},
        digital_twin_id="twin-1",
    )
    assert task.render_task is True
    assert task.target_state.expects_render is True


def test_catalog_serialization_is_canonical():
    j = DEFAULT_UNREAL_CATALOG.to_json_compatible()
    assert set(j) == {"catalog_version", "entries"}
    assert len(j["entries"]) == len(
        DEFAULT_UNREAL_CATALOG.available_task_names()
    )


def test_resolution_preserves_provenance():
    task = DEFAULT_UNREAL_CATALOG.resolve(
        "unreal.sequence-configure",
        {
            "twin_id": "twin-1",
            "sequence_name": "main",
            "frame_start": 1,
            "frame_end": 24,
        },
        digital_twin_id="twin-1",
        provenance={"proposal_source": "qwen-proposal-v1", "proposal_id": "p-1"},
    )
    prov = task.to_json_compatible()["provenance"]
    assert prov["proposal_source"] == "qwen-proposal-v1"
    assert prov["proposal_id"] == "p-1"
    assert prov["canonical_digital_twin_id"] == "twin-1"