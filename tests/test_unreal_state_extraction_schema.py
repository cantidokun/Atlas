"""Closed-schema validation, markers, canonical order and derived-field consistency.

Contract obligations exercised here: Revision 3.1 §4 (boundary, closed schema, marker
derivation), §3.4–§3.9 (record shapes), §7.1/§7.3 (ordering is validated, never
repaired) and D7.
"""

from __future__ import annotations

import copy

import pytest

from planning.unreal_state_extraction import UnrealStateExtractionError, validate_value_tree
from planning.unreal_state_extraction.errors import (
    ERR_EXTRACTION_NON_CANONICAL_ORDER,
    ERR_EXTRACTION_SCHEMA,
)
from tests.extraction_payload_fixtures import (
    WORLD_PACKAGE_PATH,
    actor,
    actor_state_tree,
    editor_visibility,
    level_scope,
    material_component,
    sequencer_state_tree,
    slot,
    transform,
    vector3,
    world,
)


def _expect(tree, code: str) -> str:
    with pytest.raises(UnrealStateExtractionError) as excinfo:
        validate_value_tree(tree)
    assert excinfo.value.code == code, excinfo.value
    return str(excinfo.value)


# ---------------------------------------------------------------------------
# Top-level closedness
# ---------------------------------------------------------------------------

def test_conforming_actor_state_tree_validates() -> None:
    validated = validate_value_tree(actor_state_tree())
    assert validated["extraction_kind"] == "actor_state"
    assert validated["extraction_schema_version"] == 1
    assert validated["sequences"] == []
    assert validated["actors"][0]["entity_id"] == "FIELD_SURFACE"


def test_conforming_sequencer_state_tree_validates() -> None:
    validated = validate_value_tree(sequencer_state_tree())
    assert validated["extraction_kind"] == "sequencer_state"
    assert validated["actors"] == []


@pytest.mark.parametrize("key", sorted(("world", "actors", "sequences", "extraction_kind")))
def test_top_level_missing_key_is_rejected(key: str) -> None:
    tree = actor_state_tree()
    del tree[key]
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_top_level_extra_key_is_rejected() -> None:
    tree = actor_state_tree()
    tree["session_identity"] = {"process_id": 1}
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_schema_version_must_be_the_integer_one() -> None:
    for bad in (True, 2, 1.0, "1", None):
        tree = actor_state_tree()
        tree["extraction_schema_version"] = bad
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_extraction_kind_must_be_derived_from_content() -> None:
    tree = actor_state_tree()
    tree["extraction_kind"] = "sequencer_state"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_both_collections_populated_is_rejected() -> None:
    tree = actor_state_tree()
    tree["sequences"] = sequencer_state_tree()["sequences"]
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_both_collections_empty_is_rejected() -> None:
    tree = actor_state_tree(actors=[])
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_sequencer_state_carries_exactly_one_record() -> None:
    tree = sequencer_state_tree()
    tree["sequences"] = tree["sequences"] * 2
    _expect(tree, ERR_EXTRACTION_SCHEMA)


# ---------------------------------------------------------------------------
# Reserved keys at any depth, and the un-augmented boundary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key",
    [
        "_session_identity",
        "session_identity",
        "engine_session_identity",
        "process_id",
        "editor_session_id",
        "server_start_time_utc",
        "process_creation_time_utc",
        "_anything",
    ],
)
def test_reserved_keys_are_rejected_wherever_they_appear(key: str) -> None:
    tree = actor_state_tree()
    tree["actors"][0][key] = "x"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_reserved_key_inside_a_nested_structure_is_rejected() -> None:
    tree = actor_state_tree()
    tree["world"]["level_scope"]["levels"][0]["_session_identity"] = {}
    _expect(tree, ERR_EXTRACTION_SCHEMA)


# ---------------------------------------------------------------------------
# World record
# ---------------------------------------------------------------------------

def test_world_type_marker_is_enforced() -> None:
    tree = actor_state_tree()
    tree["world"]["world_type"] = "pie"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_partitioned_world_is_refused_not_extracted() -> None:
    tree = actor_state_tree()
    tree["world"]["is_partitioned_world"] = True
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_selection_provenance_marker_is_enforced() -> None:
    tree = actor_state_tree()
    tree["world"]["selection_provenance"] = "g_engine_world_contexts_0"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_engine_identity_must_be_present_and_non_empty() -> None:
    for field in ("engine_version", "engine_build_version"):
        tree = actor_state_tree()
        tree["world"][field] = ""
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_level_scope_must_not_be_empty() -> None:
    tree = actor_state_tree()
    tree["world"]["level_scope"]["levels"] = []
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_scope_must_contain_exactly_one_persistent_level() -> None:
    tree = actor_state_tree()
    tree["world"]["level_scope"]["levels"] = [
        {"level_package_path": "/Game/A", "level_kind": "persistent", "loaded": True, "visible": True},
        {"level_package_path": "/Game/B", "level_kind": "persistent", "loaded": True, "visible": True},
    ]
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_streaming_levels_are_accepted_and_duplicates_are_permitted() -> None:
    tree = actor_state_tree()
    tree["world"]["level_scope"] = level_scope(
        [
            {"level_package_path": WORLD_PACKAGE_PATH, "level_kind": "persistent", "loaded": True, "visible": True},
            {"level_package_path": "/Game/B", "level_kind": "streaming", "loaded": True, "visible": True},
            {"level_package_path": "/Game/B", "level_kind": "streaming", "loaded": True, "visible": True},
        ]
    )
    validated = validate_value_tree(tree)
    levels = validated["world"]["level_scope"]["levels"]
    assert [level["level_package_path"] for level in levels] == [
        WORLD_PACKAGE_PATH,
        "/Game/B",
        "/Game/B",
    ]


def test_loaded_and_visible_markers_must_be_true() -> None:
    for field in ("loaded", "visible"):
        tree = actor_state_tree()
        tree["world"]["level_scope"]["levels"][0][field] = False
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_scope_order_is_validated_not_repaired() -> None:
    tree = actor_state_tree()
    tree["world"]["level_scope"] = level_scope(
        [
            {"level_package_path": "/Game/B", "level_kind": "streaming", "loaded": True, "visible": True},
            {"level_package_path": "/Game/A", "level_kind": "streaming", "loaded": True, "visible": True},
            {"level_package_path": WORLD_PACKAGE_PATH, "level_kind": "persistent", "loaded": True, "visible": True},
        ]
    )
    _expect(tree, ERR_EXTRACTION_NON_CANONICAL_ORDER)


# ---------------------------------------------------------------------------
# Actor record
# ---------------------------------------------------------------------------

def test_reported_entity_id_must_be_canonical() -> None:
    tree = actor_state_tree(actors=[actor(entity_id="field_surface")])
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_actor_entity_ids_must_be_ordered_and_unique() -> None:
    unordered = actor_state_tree(
        actors=[actor(entity_id="FIELD_SURFACE"), actor(entity_id="CAM01", actor_name="Second")]
    )
    _expect(unordered, ERR_EXTRACTION_NON_CANONICAL_ORDER)
    duplicated = actor_state_tree(actors=[actor(), actor()])
    _expect(duplicated, ERR_EXTRACTION_SCHEMA)


def test_transform_markers_are_enforced() -> None:
    for field, bad in (
        ("source_component_type", "binary32"),
        ("source_component_type", "float32"),
    ):
        tree = actor_state_tree(actors=[actor(transform=transform(**{field: bad}))])
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_rotation_encoding_labels_are_enforced() -> None:
    for field, bad in (
        ("representation", "euler"),
        ("component_order", "w,x,y,z"),
        ("unit", "radians"),
        ("source", "actor_rotation"),
    ):
        rotation = transform()["rotation"] | {field: bad}
        tree = actor_state_tree(actors=[actor(transform=transform(rotation=rotation))])
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_coordinate_frame_is_enforced() -> None:
    rotation = transform()["rotation"]
    rotation["coordinate_frame"] = rotation["coordinate_frame"] | {"up_axis": "Y"}
    tree = actor_state_tree(actors=[actor(transform=transform(rotation=rotation))])
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_unrecorded_hidden_inputs_is_a_frozen_literal() -> None:
    tree = actor_state_tree(
        actors=[actor(editor_visibility=editor_visibility(unrecorded_hidden_inputs=[]))]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_visibility_flags_must_be_booleans() -> None:
    tree = actor_state_tree(
        actors=[actor(editor_visibility=editor_visibility(hidden_ed_layer="false"))]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


# ---------------------------------------------------------------------------
# Parent binding — three states, no collapse
# ---------------------------------------------------------------------------

def test_parent_none_requires_nulls() -> None:
    tree = actor_state_tree(
        actors=[
            actor(parent={"binding": "none", "entity_id": None, "actor_object_path": "/Game/A.A"})
        ]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_parent_unbound_requires_the_locator_and_no_identity() -> None:
    tree = actor_state_tree(
        actors=[
            actor(
                parent={
                    "binding": "unbound",
                    "entity_id": None,
                    "actor_object_path": "/Game/A.Level:A.ParentActor",
                }
            )
        ]
    )
    validated = validate_value_tree(tree)
    assert validated["actors"][0]["parent"] == {
        "binding": "unbound",
        "entity_id": None,
        "actor_object_path": "/Game/A.Level:A.ParentActor",
    }


def test_parent_unbound_without_a_locator_is_rejected() -> None:
    tree = actor_state_tree(
        actors=[actor(parent={"binding": "unbound", "entity_id": None, "actor_object_path": None})]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_parent_bound_requires_a_canonical_identity() -> None:
    good = actor_state_tree(
        actors=[
            actor(
                parent={
                    "binding": "bound",
                    "entity_id": "CAM01",
                    "actor_object_path": "/Game/A.Level:A.ParentActor",
                }
            )
        ]
    )
    assert validate_value_tree(good)["actors"][0]["parent"]["entity_id"] == "CAM01"
    for bad_entity in ("cam01", None, ""):
        tree = actor_state_tree(
            actors=[
                actor(
                    parent={
                        "binding": "bound",
                        "entity_id": bad_entity,
                        "actor_object_path": "/Game/A.Level:A.ParentActor",
                    }
                )
            ]
        )
        _expect(tree, ERR_EXTRACTION_SCHEMA)


@pytest.mark.parametrize("binding", ["unknown", "", "NONE", None])
def test_unknown_parent_binding_is_rejected(binding) -> None:
    tree = actor_state_tree(
        actors=[
            actor(parent={"binding": binding, "entity_id": None, "actor_object_path": None})
        ]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_two_unbound_parents_are_distinguishable() -> None:
    def with_parent(path: str) -> dict:
        return actor_state_tree(
            actors=[
                actor(parent={"binding": "unbound", "entity_id": None, "actor_object_path": path})
            ]
        )

    from planning.unreal_state_extraction import digest_value_tree

    left = with_parent("/Game/A.Level:A.ParentOne")
    right = with_parent("/Game/A.Level:A.ParentTwo")
    assert digest_value_tree(left) != digest_value_tree(right)
    assert digest_value_tree(left) != digest_value_tree(actor_state_tree())


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def test_no_mesh_asset_requires_null_path_and_no_slots() -> None:
    tree = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(
                        mesh_state="no_mesh_asset", mesh_asset_path=None, slot_count=0, slots=[]
                    )
                ]
            )
        ]
    )
    validated = validate_value_tree(tree)
    assert validated["actors"][0]["materials"][0]["mesh_state"] == "no_mesh_asset"
    for bad in (
        {"mesh_state": "no_mesh_asset", "mesh_asset_path": "/Engine/Cube.Cube", "slot_count": 0, "slots": []},
        {"mesh_state": "no_mesh_asset", "mesh_asset_path": None, "slot_count": 1, "slots": [slot(0)]},
        {"mesh_state": "mesh_asset_present", "mesh_asset_path": None, "slot_count": 0, "slots": []},
    ):
        tree = actor_state_tree(actors=[actor(materials=[material_component(**bad)])])
        _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_slot_count_must_equal_the_slot_records() -> None:
    tree = actor_state_tree(
        actors=[actor(materials=[material_component(slot_count=3, slots=[slot(0)])])]
    )
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_slot_index_must_be_the_positional_ordinal() -> None:
    tree = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(slot_count=1, slots=[slot(5)])
                ]
            )
        ]
    )
    _expect(tree, ERR_EXTRACTION_NON_CANONICAL_ORDER)


def test_component_paths_must_be_ordered_and_unique() -> None:
    unordered = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(component_object_path="/Game/A.Level:A.Mesh1"),
                    material_component(component_object_path="/Game/A.Level:A.Mesh0"),
                ]
            )
        ]
    )
    _expect(unordered, ERR_EXTRACTION_NON_CANONICAL_ORDER)
    duplicated = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(component_object_path="/Game/A.Level:A.Mesh0"),
                    material_component(component_object_path="/Game/A.Level:A.Mesh0"),
                ]
            )
        ]
    )
    _expect(duplicated, ERR_EXTRACTION_SCHEMA)


def test_override_and_resolved_are_independent_facts() -> None:
    """The Revision-2 collision pair: (override A, asset B) vs (override A, asset C)."""
    from planning.unreal_state_extraction import digest_value_tree

    def component(asset_slot: str, override: str, resolved: str) -> dict:
        return material_component(
            slot_count=1,
            slots=[slot(0, asset_slot=asset_slot, override=override, resolved=resolved)],
        )

    asset_b = actor_state_tree(
        actors=[actor(materials=[component("/Game/B.B", "/Game/A.A", "/Game/A.A")])]
    )
    asset_c = actor_state_tree(
        actors=[actor(materials=[component("/Game/C.C", "/Game/A.A", "/Game/A.A")])]
    )
    assert digest_value_tree(asset_b) != digest_value_tree(asset_c)


def test_null_override_entry_is_equivalent_to_no_override_entry() -> None:
    from planning.unreal_state_extraction import digest_value_tree

    explicit_null = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(
                        slot_count=1,
                        slots=[
                            slot(0, asset_slot="/Game/M.M", override=None, resolved="/Game/M.M")
                        ],
                    )
                ]
            )
        ]
    )
    absent = actor_state_tree(
        actors=[
            actor(
                materials=[
                    material_component(
                        slot_count=1,
                        slots=[slot(0, asset_slot="/Game/M.M", resolved="/Game/M.M")],
                    )
                ]
            )
        ]
    )
    assert digest_value_tree(explicit_null) == digest_value_tree(absent)


def test_unknown_mesh_state_is_rejected() -> None:
    tree = actor_state_tree(actors=[actor(materials=[material_component(mesh_state="unknown")])])
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_omitted_inventory_consistency() -> None:
    ok = actor_state_tree(
        actors=[actor(omitted_material_components={"count": 2, "classes": ["ADecalActor"]})]
    )
    assert validate_value_tree(ok)["actors"][0]["omitted_material_components"]["count"] == 2
    for bad in (
        {"count": 0, "classes": ["ADecalActor"]},
        {"count": 1, "classes": []},
        {"count": 1, "classes": ["B", "A"]},
        {"count": 2, "classes": ["A", "A"]},
        {"count": -1, "classes": []},
    ):
        tree = actor_state_tree(actors=[actor(omitted_material_components=bad)])
        _expect(
            tree,
            ERR_EXTRACTION_NON_CANONICAL_ORDER
            if bad.get("classes") == ["B", "A"]
            else ERR_EXTRACTION_SCHEMA,
        )


def test_materials_may_be_empty_when_the_actor_has_no_mesh_component() -> None:
    tree = actor_state_tree(actors=[actor(materials=[])])
    assert validate_value_tree(tree)["actors"][0]["materials"] == []


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

def test_playback_bounds_are_marked_inclusive_exclusive() -> None:
    tree = sequencer_state_tree()
    tree["sequences"][0]["playback_range"]["upper_bound"] = "inclusive"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


@pytest.mark.parametrize(
    ("lower", "upper"), [(0, 0), (10, 5), (-5, -10)]
)
def test_degenerate_or_inverted_ranges_are_refused(lower: int, upper: int) -> None:
    tree = sequencer_state_tree()
    tree["sequences"][0]["playback_range"]["lower_frame"] = lower
    tree["sequences"][0]["playback_range"]["upper_frame"] = upper
    _expect(tree, ERR_EXTRACTION_SCHEMA)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tick_resolution", {"numerator": 0, "denominator": 1}),
        ("tick_resolution", {"numerator": 24000, "denominator": 0}),
        ("tick_resolution", {"numerator": -24000, "denominator": 1}),
        ("display_rate", {"numerator": 30, "denominator": -1}),
    ],
)
def test_rate_pairs_must_be_positive(field: str, value: dict) -> None:
    tree = sequencer_state_tree()
    tree["sequences"][0][field] = value
    _expect(tree, ERR_EXTRACTION_SCHEMA)


def test_rate_pairs_are_recorded_verbatim_never_reduced() -> None:
    tree = sequencer_state_tree()
    tree["sequences"][0]["tick_resolution"] = {"numerator": 60, "denominator": 2}
    validated = validate_value_tree(tree)
    assert validated["sequences"][0]["tick_resolution"] == {"numerator": 60, "denominator": 2}


def test_sequence_entity_id_must_be_canonical() -> None:
    tree = sequencer_state_tree()
    tree["sequences"][0]["entity_id"] = "sequence_fixture"
    _expect(tree, ERR_EXTRACTION_SCHEMA)


# ---------------------------------------------------------------------------
# §4.2.5 — the digest input is reconstructed, not copied
# ---------------------------------------------------------------------------

def test_validation_returns_a_fresh_structure() -> None:
    tree = actor_state_tree()
    validated = validate_value_tree(tree)
    assert validated is not tree
    assert validated["world"] is not tree["world"]
    assert validated["actors"][0] is not tree["actors"][0]
    snapshot = copy.deepcopy(validated)
    tree["world"]["world_name"] = "Mutated"
    tree["actors"][0]["actor_name"] = "Mutated"
    assert validated == snapshot


def test_validation_returns_only_declared_fields() -> None:
    validated = validate_value_tree(actor_state_tree())
    assert set(validated) == {
        "extraction_schema_version",
        "extraction_kind",
        "world",
        "actors",
        "sequences",
    }
    assert set(validated["world"]) == {
        "world_object_path",
        "world_package_path",
        "world_name",
        "world_type",
        "engine_version",
        "engine_build_version",
        "selection_provenance",
        "is_partitioned_world",
        "level_scope",
    }
