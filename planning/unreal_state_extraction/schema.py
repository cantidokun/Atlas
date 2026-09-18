"""Closed-schema validation of the extraction value tree.

Design source: Revision 3.1 §4 (boundary and closed schema), §7 (ordering), §8 (errors).

Two properties are load-bearing here:

1. **The schema is closed at every level.** Every object has an exact key set, so there
   is no open bag of keys a transient metadata field could be added to. Any key equal
   to, or beginning with, ``_`` is rejected at any depth, as are the named session and
   timestamp keys, so an unrecognised session-like field cannot slip through under a new
   name.
2. **The digest input is reconstructed, not copied.** :func:`validate_value_tree`
   returns a *fresh* structure assembled field by field from validated values. It never
   returns (or aliases) the parsed payload, so no parser artefact that is not a declared
   field can reach canonicalization. This is the mechanical answer to "how is
   canonicalization prevented from seeing session/timestamp fields".

Array order is *validated*, never silently repaired: a non-canonical order fails closed
with :data:`ERR_EXTRACTION_NON_CANONICAL_ORDER`, because silent sorting would hide a
producer defect and make the digest depend on the validator's tolerance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from planning.unreal_state_extraction.binary64 import (
    is_int32,
    require_canonical_pattern,
)
from planning.unreal_state_extraction.entity_id import require_canonical_entity_id
from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_NON_CANONICAL_ORDER,
    ERR_EXTRACTION_SCHEMA,
    UnrealStateExtractionError,
)
from planning.unreal_state_extraction.strict_json import find_lone_surrogates

EXTRACTION_NODE_KEY = "unreal_state_extraction"
EXTRACTION_SCHEMA_VERSION = 1

#: Keys that are never part of an extraction value tree, wherever they appear.
RESERVED_KEYS = frozenset(
    {
        "session_identity",
        "engine_session_identity",
        "process_id",
        "editor_session_id",
        "server_start_time_utc",
        "process_creation_time_utc",
    }
)

WORLD_KEYS = (
    "world_object_path",
    "world_package_path",
    "world_name",
    "world_type",
    "engine_version",
    "engine_build_version",
    "selection_provenance",
    "is_partitioned_world",
    "level_scope",
)
LEVEL_KEYS = ("level_package_path", "level_kind", "loaded", "visible")
ACTOR_KEYS = (
    "entity_id",
    "actor_name",
    "actor_object_path",
    "actor_class",
    "level_package_path",
    "parent",
    "editor_visibility",
    "transform",
    "materials",
    "omitted_material_components",
)
PARENT_KEYS = ("binding", "entity_id", "actor_object_path")
VISIBILITY_KEYS = (
    "hidden_in_editor",
    "derived_from_gis_editor",
    "hidden_ed_at_startup",
    "temporarily_hidden_in_editor",
    "hidden_ed_layer",
    "hidden_ed_level",
    "unrecorded_hidden_inputs",
)
TRANSFORM_KEYS = ("source_component_type", "location_cm", "rotation", "scale")
ROTATION_KEYS = (
    "coordinate_frame",
    "representation",
    "component_order",
    "unit",
    "source",
    "x",
    "y",
    "z",
    "w",
)
COORDINATE_FRAME_KEYS = ("handedness", "up_axis", "positive_x", "positive_y", "positive_z")
VECTOR3_KEYS = ("x", "y", "z")
MATERIAL_KEYS = (
    "component_object_path",
    "component_class",
    "mesh_asset_path",
    "mesh_state",
    "slot_count",
    "slots",
)
SLOT_KEYS = (
    "slot_index",
    "asset_slot_material_asset_path",
    "override_material_asset_path",
    "resolved_material_asset_path",
)
OMITTED_KEYS = ("count", "classes")
SEQUENCE_KEYS = (
    "entity_id",
    "sequence_actor_object_path",
    "sequence_asset_object_path",
    "playback_range",
    "tick_resolution",
    "display_rate",
)
PLAYBACK_RANGE_KEYS = ("lower_frame", "lower_bound", "upper_frame", "upper_bound")
RATE_KEYS = ("numerator", "denominator")

SEQUENCE_ACTOR_BOUND_LOWER = "inclusive"
SEQUENCE_ACTOR_BOUND_UPPER = "exclusive"

SELECTION_PROVENANCE = "g_editor_editor_world_context"
WORLD_TYPE_EDITOR = "editor"
SOURCE_COMPONENT_TYPE = "binary64"
UNRECORDED_HIDDEN_INPUTS = ["bEditable"]


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------

def _reject_reserved_keys(value: Any, *, where: str = "$") -> None:
    """Reject reserved/session-like keys at any depth, before structural validation."""
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and (key.startswith("_") or key in RESERVED_KEYS):
                raise UnrealStateExtractionError(
                    ERR_EXTRACTION_SCHEMA,
                    f"{where}: reserved key {key!r} is never part of an extraction value tree",
                )
            _reject_reserved_keys(item, where=f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_reserved_keys(item, where=f"{where}[{index}]")


def _require_object(value: Any, where: str, keys: Sequence[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where} must be an object, got {type(value).__name__}"
        )
    expected = set(keys)
    actual = set(value.keys())
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} violates the closed schema (missing={missing}, unexpected={unexpected})",
        )
    return value


def _require_array(value: Any, where: str) -> List[Any]:
    if not isinstance(value, list):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where} must be an array, got {type(value).__name__}"
        )
    return value


def _require_string(value: Any, where: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where} must be a string, got {type(value).__name__}"
        )
    if non_empty and not value:
        raise UnrealStateExtractionError(ERR_EXTRACTION_SCHEMA, f"{where} must not be empty")
    return value


def _require_nullable_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, where)


def _require_bool(value: Any, where: str) -> bool:
    if type(value) is not bool:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where} must be a boolean, got {type(value).__name__}"
        )
    return value


def _require_int32(value: Any, where: str) -> int:
    if not is_int32(value):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must be an exact int32 integer (got {value!r}); booleans and "
            "floats are not integers",
        )
    return value


def _require_marker(value: Any, where: str, expected: Any) -> Any:
    if value != expected or type(value) is not type(expected):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must be the contracted marker {expected!r}, got {value!r}",
        )
    return expected


def _utf16_sort_key(name: str) -> bytes:
    return name.encode("utf-16-be")


def _require_ascending(values: Sequence[str], where: str) -> None:
    keys = [_utf16_sort_key(value) for value in values]
    if keys != sorted(keys):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_NON_CANONICAL_ORDER,
            f"{where} is not in canonical UTF-16 code-unit order: {list(values)!r}",
        )


def _require_unique(values: Sequence[str], where: str) -> None:
    if len(set(values)) != len(values):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where} contains duplicate identities: {list(values)!r}"
        )


# ---------------------------------------------------------------------------
# Compound validators
# ---------------------------------------------------------------------------

def _validate_visibility(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, VISIBILITY_KEYS)
    return {
        "hidden_in_editor": _require_bool(obj["hidden_in_editor"], f"{where}.hidden_in_editor"),
        "derived_from_gis_editor": _require_bool(
            obj["derived_from_gis_editor"], f"{where}.derived_from_gis_editor"
        ),
        "hidden_ed_at_startup": _require_bool(
            obj["hidden_ed_at_startup"], f"{where}.hidden_ed_at_startup"
        ),
        "temporarily_hidden_in_editor": _require_bool(
            obj["temporarily_hidden_in_editor"], f"{where}.temporarily_hidden_in_editor"
        ),
        "hidden_ed_layer": _require_bool(obj["hidden_ed_layer"], f"{where}.hidden_ed_layer"),
        "hidden_ed_level": _require_bool(obj["hidden_ed_level"], f"{where}.hidden_ed_level"),
        "unrecorded_hidden_inputs": _validate_unrecorded_hidden_inputs(
            obj["unrecorded_hidden_inputs"], f"{where}.unrecorded_hidden_inputs"
        ),
    }


def _validate_unrecorded_hidden_inputs(value: Any, where: str) -> List[str]:
    array = _require_array(value, where)
    items = [_require_string(item, f"{where}[{index}]") for index, item in enumerate(array)]
    if items != UNRECORDED_HIDDEN_INPUTS:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must be the frozen literal {UNRECORDED_HIDDEN_INPUTS!r}, got {items!r}",
        )
    return list(UNRECORDED_HIDDEN_INPUTS)


def _validate_vector3(value: Any, where: str) -> Dict[str, str]:
    obj = _require_object(value, where, VECTOR3_KEYS)
    return {
        axis: require_canonical_pattern(obj[axis], where=f"{where}.{axis}")
        for axis in VECTOR3_KEYS
    }


def _validate_transform(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, TRANSFORM_KEYS)
    _require_marker(
        obj["source_component_type"], f"{where}.source_component_type", SOURCE_COMPONENT_TYPE
    )
    rotation = _require_object(obj["rotation"], f"{where}.rotation", ROTATION_KEYS)
    frame = _require_object(
        rotation["coordinate_frame"], f"{where}.rotation.coordinate_frame", COORDINATE_FRAME_KEYS
    )
    for key, expected in (
        ("handedness", "left"),
        ("up_axis", "Z"),
        ("positive_x", "forward"),
        ("positive_y", "right"),
        ("positive_z", "up"),
    ):
        _require_marker(frame[key], f"{where}.rotation.coordinate_frame.{key}", expected)
    for key, expected in (
        ("representation", "quaternion"),
        ("component_order", "x,y,z,w"),
        ("unit", "unitless"),
        ("source", "actor_world_quaternion"),
    ):
        _require_marker(rotation[key], f"{where}.rotation.{key}", expected)
    return {
        "source_component_type": SOURCE_COMPONENT_TYPE,
        "location_cm": _validate_vector3(obj["location_cm"], f"{where}.location_cm"),
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
            **{
                axis: require_canonical_pattern(rotation[axis], where=f"{where}.rotation.{axis}")
                for axis in ("x", "y", "z", "w")
            },
        },
        "scale": _validate_vector3(obj["scale"], f"{where}.scale"),
    }


def _validate_slot(value: Any, where: str, expected_index: int) -> Dict[str, Any]:
    obj = _require_object(value, where, SLOT_KEYS)
    slot_index = _require_int32(obj["slot_index"], f"{where}.slot_index")
    if slot_index != expected_index:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_NON_CANONICAL_ORDER,
            f"{where}.slot_index must be the positional ordinal {expected_index}, got {slot_index}",
        )
    return {
        "slot_index": slot_index,
        "asset_slot_material_asset_path": _require_nullable_string(
            obj["asset_slot_material_asset_path"], f"{where}.asset_slot_material_asset_path"
        ),
        "override_material_asset_path": _require_nullable_string(
            obj["override_material_asset_path"], f"{where}.override_material_asset_path"
        ),
        "resolved_material_asset_path": _require_nullable_string(
            obj["resolved_material_asset_path"], f"{where}.resolved_material_asset_path"
        ),
    }


def _validate_material_component(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, MATERIAL_KEYS)
    mesh_state = obj["mesh_state"]
    if mesh_state not in ("mesh_asset_present", "no_mesh_asset"):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.mesh_state must be 'mesh_asset_present' or 'no_mesh_asset', got {mesh_state!r}",
        )
    mesh_asset_path = _require_nullable_string(obj["mesh_asset_path"], f"{where}.mesh_asset_path")
    slots = _require_array(obj["slots"], f"{where}.slots")
    slot_count = _require_int32(obj["slot_count"], f"{where}.slot_count")
    if slot_count != len(slots):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.slot_count ({slot_count}) must equal len(slots) ({len(slots)})",
        )
    if slot_count < 0:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where}.slot_count must not be negative"
        )
    if mesh_state == "no_mesh_asset":
        if mesh_asset_path is not None:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"{where}.mesh_asset_path must be null when mesh_state is 'no_mesh_asset'",
            )
        if slot_count != 0:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"{where}.slots must be empty when mesh_state is 'no_mesh_asset'",
            )
    elif mesh_asset_path is None:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.mesh_asset_path must not be null when mesh_state is 'mesh_asset_present'",
        )
    return {
        "component_object_path": _require_string(
            obj["component_object_path"], f"{where}.component_object_path"
        ),
        "component_class": _require_string(obj["component_class"], f"{where}.component_class"),
        "mesh_asset_path": mesh_asset_path,
        "mesh_state": mesh_state,
        "slot_count": slot_count,
        "slots": [
            _validate_slot(item, f"{where}.slots[{index}]", index)
            for index, item in enumerate(slots)
        ],
    }


def _validate_omitted_material_components(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, OMITTED_KEYS)
    count = _require_int32(obj["count"], f"{where}.count")
    if count < 0:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where}.count must not be negative"
        )
    classes_array = _require_array(obj["classes"], f"{where}.classes")
    classes = [
        _require_string(item, f"{where}.classes[{index}]")
        for index, item in enumerate(classes_array)
    ]
    if len(set(classes)) != len(classes):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where}.classes must be deduplicated"
        )
    _require_ascending(classes, f"{where}.classes")
    if count == 0 and classes:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where}.classes must be empty when count is 0"
        )
    if count > 0 and not classes:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA, f"{where}.classes must not be empty when count > 0"
        )
    if count < len(classes):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.count ({count}) must be at least the number of distinct classes "
            f"({len(classes)})",
        )
    return {"count": count, "classes": classes}


def _validate_parent(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, PARENT_KEYS)
    binding = obj["binding"]
    if binding not in ("none", "unbound", "bound"):
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.binding must be 'none', 'unbound' or 'bound', got {binding!r}",
        )
    entity_id = obj["entity_id"]
    object_path = obj["actor_object_path"]
    if binding == "none":
        if entity_id is not None or object_path is not None:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"{where}: binding 'none' requires null entity_id and null actor_object_path",
            )
        return {"binding": "none", "entity_id": None, "actor_object_path": None}
    if binding == "unbound":
        if entity_id is not None:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA, f"{where}: binding 'unbound' requires a null entity_id"
            )
        return {
            "binding": "unbound",
            "entity_id": None,
            "actor_object_path": _require_string(object_path, f"{where}.actor_object_path"),
        }
    return {
        "binding": "bound",
        "entity_id": require_canonical_entity_id(entity_id, where=f"{where}.entity_id"),
        "actor_object_path": _require_string(object_path, f"{where}.actor_object_path"),
    }


def _validate_actor(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, ACTOR_KEYS)
    materials_array = _require_array(obj["materials"], f"{where}.materials")
    materials = [
        _validate_material_component(item, f"{where}.materials[{index}]")
        for index, item in enumerate(materials_array)
    ]
    component_paths = [material["component_object_path"] for material in materials]
    _require_ascending(component_paths, f"{where}.materials")
    _require_unique(component_paths, f"{where}.materials")
    return {
        "entity_id": require_canonical_entity_id(obj["entity_id"], where=f"{where}.entity_id"),
        "actor_name": _require_string(obj["actor_name"], f"{where}.actor_name"),
        "actor_object_path": _require_string(
            obj["actor_object_path"], f"{where}.actor_object_path"
        ),
        "actor_class": _require_string(obj["actor_class"], f"{where}.actor_class"),
        "level_package_path": _require_string(
            obj["level_package_path"], f"{where}.level_package_path"
        ),
        "parent": _validate_parent(obj["parent"], f"{where}.parent"),
        "editor_visibility": _validate_visibility(
            obj["editor_visibility"], f"{where}.editor_visibility"
        ),
        "transform": _validate_transform(obj["transform"], f"{where}.transform"),
        "materials": materials,
        "omitted_material_components": _validate_omitted_material_components(
            obj["omitted_material_components"], f"{where}.omitted_material_components"
        ),
    }


def _validate_rate(value: Any, where: str) -> Dict[str, int]:
    obj = _require_object(value, where, RATE_KEYS)
    numerator = _require_int32(obj["numerator"], f"{where}.numerator")
    denominator = _require_int32(obj["denominator"], f"{where}.denominator")
    if numerator <= 0 or denominator <= 0:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where} must have a positive numerator and denominator, got "
            f"{numerator}/{denominator}",
        )
    return {"numerator": numerator, "denominator": denominator}


def _validate_sequence(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, SEQUENCE_KEYS)
    playback_range = _require_object(
        obj["playback_range"], f"{where}.playback_range", PLAYBACK_RANGE_KEYS
    )
    lower_frame = _require_int32(
        playback_range["lower_frame"], f"{where}.playback_range.lower_frame"
    )
    upper_frame = _require_int32(
        playback_range["upper_frame"], f"{where}.playback_range.upper_frame"
    )
    _require_marker(
        playback_range["lower_bound"],
        f"{where}.playback_range.lower_bound",
        SEQUENCE_ACTOR_BOUND_LOWER,
    )
    _require_marker(
        playback_range["upper_bound"],
        f"{where}.playback_range.upper_bound",
        SEQUENCE_ACTOR_BOUND_UPPER,
    )
    if upper_frame <= lower_frame:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.playback_range must be non-degenerate (upper > lower), got "
            f"[{lower_frame}, {upper_frame})",
        )
    return {
        "entity_id": require_canonical_entity_id(obj["entity_id"], where=f"{where}.entity_id"),
        "sequence_actor_object_path": _require_string(
            obj["sequence_actor_object_path"], f"{where}.sequence_actor_object_path"
        ),
        "sequence_asset_object_path": _require_string(
            obj["sequence_asset_object_path"], f"{where}.sequence_asset_object_path"
        ),
        "playback_range": {
            "lower_frame": lower_frame,
            "lower_bound": SEQUENCE_ACTOR_BOUND_LOWER,
            "upper_frame": upper_frame,
            "upper_bound": SEQUENCE_ACTOR_BOUND_UPPER,
        },
        "tick_resolution": _validate_rate(obj["tick_resolution"], f"{where}.tick_resolution"),
        "display_rate": _validate_rate(obj["display_rate"], f"{where}.display_rate"),
    }


def _validate_world(value: Any, where: str) -> Dict[str, Any]:
    obj = _require_object(value, where, WORLD_KEYS)
    _require_marker(obj["world_type"], f"{where}.world_type", WORLD_TYPE_EDITOR)
    _require_marker(
        obj["selection_provenance"],
        f"{where}.selection_provenance",
        SELECTION_PROVENANCE,
    )
    partitioned = obj["is_partitioned_world"]
    if type(partitioned) is not bool or partitioned is not False:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.is_partitioned_world must be the boolean false (a partitioned world "
            "is refused, not extracted)",
        )
    level_scope = _require_object(obj["level_scope"], f"{where}.level_scope", ("levels",))
    levels_array = _require_array(level_scope["levels"], f"{where}.level_scope.levels")
    levels: List[Dict[str, Any]] = []
    for index, item in enumerate(levels_array):
        level_where = f"{where}.level_scope.levels[{index}]"
        level = _require_object(item, level_where, LEVEL_KEYS)
        kind = level["level_kind"]
        if kind not in ("persistent", "streaming"):
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"{level_where}.level_kind must be 'persistent' or 'streaming', got {kind!r}",
            )
        _require_marker(level["loaded"], f"{level_where}.loaded", True)
        _require_marker(level["visible"], f"{level_where}.visible", True)
        levels.append(
            {
                "level_package_path": _require_string(
                    level["level_package_path"], f"{level_where}.level_package_path"
                ),
                "level_kind": kind,
                "loaded": True,
                "visible": True,
            }
        )
    if not levels:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.level_scope.levels must not be empty: the persistent level is always "
            "in scope",
        )
    persistent = [level for level in levels if level["level_kind"] == "persistent"]
    if len(persistent) != 1:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"{where}.level_scope.levels must contain exactly one persistent level, got "
            f"{len(persistent)}",
        )
    _require_ascending(
        [level["level_package_path"] for level in levels], f"{where}.level_scope.levels"
    )
    return {
        "world_object_path": _require_string(obj["world_object_path"], f"{where}.world_object_path"),
        "world_package_path": _require_string(
            obj["world_package_path"], f"{where}.world_package_path"
        ),
        "world_name": _require_string(obj["world_name"], f"{where}.world_name"),
        "world_type": WORLD_TYPE_EDITOR,
        "engine_version": _require_string(obj["engine_version"], f"{where}.engine_version"),
        "engine_build_version": _require_string(
            obj["engine_build_version"], f"{where}.engine_build_version"
        ),
        "selection_provenance": SELECTION_PROVENANCE,
        "is_partitioned_world": False,
        "level_scope": {"levels": levels},
    }


def validate_value_tree(tree: Any) -> Dict[str, Any]:
    """Validate the value tree under ``unreal_state_extraction`` and reconstruct it.

    The return value is a fresh structure containing only declared fields, in the
    contract's own field order. It never aliases the input.
    """
    _reject_reserved_keys(tree)
    surrogates = find_lone_surrogates(tree)
    if surrogates:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"lone surrogate code points are not representable: {surrogates[:5]}",
        )
    obj = _require_object(
        tree,
        "unreal_state_extraction",
        ("extraction_schema_version", "extraction_kind", "world", "actors", "sequences"),
    )
    version = obj["extraction_schema_version"]
    if type(version) is not int or version != EXTRACTION_SCHEMA_VERSION:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"extraction_schema_version must be the integer {EXTRACTION_SCHEMA_VERSION}, "
            f"got {version!r}",
        )
    actors_array = _require_array(obj["actors"], "unreal_state_extraction.actors")
    actors = [
        _validate_actor(item, f"unreal_state_extraction.actors[{index}]")
        for index, item in enumerate(actors_array)
    ]
    _require_ascending(
        [actor["entity_id"] for actor in actors], "unreal_state_extraction.actors"
    )
    _require_unique([actor["entity_id"] for actor in actors], "unreal_state_extraction.actors")
    sequences_array = _require_array(obj["sequences"], "unreal_state_extraction.sequences")
    sequences = [
        _validate_sequence(item, f"unreal_state_extraction.sequences[{index}]")
        for index, item in enumerate(sequences_array)
    ]
    kind = _derived_extraction_kind(actors=actors, sequences=sequences, where="unreal_state_extraction")
    if obj["extraction_kind"] != kind:
        raise UnrealStateExtractionError(
            ERR_EXTRACTION_SCHEMA,
            f"extraction_kind must be derived from the content ({kind!r}), got "
            f"{obj['extraction_kind']!r}",
        )
    return {
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION,
        "extraction_kind": kind,
        "world": _validate_world(obj["world"], "unreal_state_extraction.world"),
        "actors": actors,
        "sequences": sequences,
    }


def _derived_extraction_kind(
    *, actors: Sequence[Mapping[str, Any]], sequences: Sequence[Mapping[str, Any]], where: str
) -> str:
    if actors and not sequences:
        return "actor_state"
    if sequences and not actors:
        if len(sequences) != 1:
            raise UnrealStateExtractionError(
                ERR_EXTRACTION_SCHEMA,
                f"{where}: 'sequencer_state' carries exactly one sequence record, got "
                f"{len(sequences)}",
            )
        return "sequencer_state"
    raise UnrealStateExtractionError(
        ERR_EXTRACTION_SCHEMA,
        f"{where}: exactly one of actors/sequences must be populated "
        f"(actors={len(actors)}, sequences={len(sequences)})",
    )
