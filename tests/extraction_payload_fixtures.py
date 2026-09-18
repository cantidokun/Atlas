"""Builders for conforming extraction payloads used by the contract-boundary tests.

These builders produce the *shape a compliant C++ producer must emit* (Revision 3.1
§4.4–§4.9). They are test-only: nothing here is production code, and every value is a
literal a producer could have derived from an engine object.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

WORLD_OBJECT_PATH = (
    "/Game/AtlasTest/AtlasRenderFixture.AtlasRenderFixture:PersistentLevel"
)
WORLD_PACKAGE_PATH = "/Game/AtlasTest/AtlasRenderFixture"
WORLD_NAME = "AtlasRenderFixture"
ENGINE_VERSION = "5.6.1-44394996+++UE5+Release-5.6"
ENGINE_BUILD_VERSION = "++UE5+Release-5.6-CL-44394996"

#: Canonical binary64 patterns used by the builders (see binary64.BINARY64_VECTORS).
IDENTITY = "3ff0000000000000"
ZERO = "0000000000000000"
NEGATIVE_ZERO = "8000000000000000"


def level_scope(levels: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if levels is None:
        levels = [
            {
                "level_package_path": WORLD_PACKAGE_PATH,
                "level_kind": "persistent",
                "loaded": True,
                "visible": True,
            }
        ]
    return {"levels": levels}


def world(**overrides: Any) -> Dict[str, Any]:
    material = {
        "world_object_path": WORLD_OBJECT_PATH,
        "world_package_path": WORLD_PACKAGE_PATH,
        "world_name": WORLD_NAME,
        "world_type": "editor",
        "engine_version": ENGINE_VERSION,
        "engine_build_version": ENGINE_BUILD_VERSION,
        "selection_provenance": "g_editor_editor_world_context",
        "is_partitioned_world": False,
        "level_scope": level_scope(),
    }
    material.update(overrides)
    return material


def vector3(x: str = IDENTITY, y: str = IDENTITY, z: str = IDENTITY) -> Dict[str, str]:
    return {"x": x, "y": y, "z": z}


def transform(**overrides: Any) -> Dict[str, Any]:
    material = {
        "source_component_type": "binary64",
        "location_cm": vector3(ZERO, ZERO, ZERO),
        "rotation": {
            "coordinate_frame": {
                "handedness": "left",
                "up_axis": "Z",
                "positive_x": "forward",
                "positive_y": "right",
                "positive_z": "up",
            },
            "representation": "quaternion",
            "component_order": "x,y,z,w",
            "unit": "unitless",
            "source": "actor_world_quaternion",
            "x": ZERO,
            "y": ZERO,
            "z": ZERO,
            "w": IDENTITY,
        },
        "scale": vector3(IDENTITY, IDENTITY, IDENTITY),
    }
    material.update(overrides)
    return material


def editor_visibility(**overrides: Any) -> Dict[str, Any]:
    material = {
        "hidden_in_editor": False,
        "derived_from_gis_editor": True,
        "hidden_ed_at_startup": False,
        "temporarily_hidden_in_editor": False,
        "hidden_ed_layer": False,
        "hidden_ed_level": False,
        "unrecorded_hidden_inputs": ["bEditable"],
    }
    material.update(overrides)
    return material


def slot(
    slot_index: int,
    *,
    asset_slot: Optional[str] = "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial",
    override: Optional[str] = None,
    resolved: Optional[str] = "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial",
) -> Dict[str, Any]:
    return {
        "slot_index": slot_index,
        "asset_slot_material_asset_path": asset_slot,
        "override_material_asset_path": override,
        "resolved_material_asset_path": resolved,
    }


def material_component(**overrides: Any) -> Dict[str, Any]:
    material = {
        "component_object_path": (
            f"{WORLD_OBJECT_PATH}.AtlasSurfaceFixture.StaticMeshComponent0"
        ),
        "component_class": "StaticMeshComponent",
        "mesh_asset_path": "/Engine/BasicShapes/Cube.Cube",
        "mesh_state": "mesh_asset_present",
        "slot_count": 1,
        "slots": [slot(0)],
    }
    material.update(overrides)
    return material


def actor(**overrides: Any) -> Dict[str, Any]:
    material = {
        "entity_id": "FIELD_SURFACE",
        "actor_name": "AtlasSurfaceFixture",
        "actor_object_path": f"{WORLD_OBJECT_PATH}.AtlasSurfaceFixture",
        "actor_class": "StaticMeshActor",
        "level_package_path": WORLD_PACKAGE_PATH,
        "parent": {"binding": "none", "entity_id": None, "actor_object_path": None},
        "editor_visibility": editor_visibility(),
        "transform": transform(),
        "materials": [material_component()],
        "omitted_material_components": {"count": 0, "classes": []},
    }
    material.update(overrides)
    return material


def sequence(**overrides: Any) -> Dict[str, Any]:
    material = {
        "entity_id": "SEQUENCE_FIXTURE",
        "sequence_actor_object_path": f"{WORLD_OBJECT_PATH}.AtlasSequencerFixtureActor",
        "sequence_asset_object_path": (
            "/Game/AtlasTest/AtlasSequencerFixtureSequence.AtlasSequencerFixtureSequence"
        ),
        "playback_range": {
            "lower_frame": 0,
            "lower_bound": "inclusive",
            "upper_frame": 100,
            "upper_bound": "exclusive",
        },
        "tick_resolution": {"numerator": 24000, "denominator": 1},
        "display_rate": {"numerator": 30, "denominator": 1},
    }
    material.update(overrides)
    return material


def actor_state_tree(actors: Optional[List[Dict[str, Any]]] = None, **overrides: Any) -> Dict[str, Any]:
    material = {
        "extraction_schema_version": 1,
        "extraction_kind": "actor_state",
        "world": world(),
        "actors": [actor()] if actors is None else actors,
        "sequences": [],
    }
    material.update(overrides)
    return material


def sequencer_state_tree(sequences: Optional[List[Dict[str, Any]]] = None, **overrides: Any) -> Dict[str, Any]:
    material = {
        "extraction_schema_version": 1,
        "extraction_kind": "sequencer_state",
        "world": world(),
        "actors": [],
        "sequences": [sequence()] if sequences is None else sequences,
    }
    material.update(overrides)
    return material


def response(
    tree: Optional[Dict[str, Any]] = None,
    *,
    session_identity: Optional[Dict[str, Any]] = None,
    **overrides: Any,
) -> Dict[str, Any]:
    """A conforming transport response envelope around ``tree``.

    ``session_identity`` is envelope metadata (never extracted); when supplied it stays
    at the envelope level, which is exactly how the contract distinguishes it from the
    augmented ``_session_identity`` inside ``observed_state``.
    """
    material: Dict[str, Any] = {
        "request_id": "req-fixture-1",
        "operation_name": "extract_actor_state",
        "success": True,
        "error": "",
        "error_code": "",
        "source": "unreal",
        "schema_version": 1,
        "entity_ids": ["FIELD_SURFACE"],
        "observed_state": {"unreal_state_extraction": actor_state_tree() if tree is None else tree},
    }
    if session_identity is not None:
        material["session_identity"] = session_identity
    material.update(overrides)
    return material
