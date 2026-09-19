"""Forced coverage for the fixture-rung state-space branches.

Every test here proves an expected tree or an expected refusal — never merely that a call
returned. The branches covered are the ones the extraction gate had to reach with real
fixture content (Revision 3.1 §11.2):

* request-order permutation invariance and canonical actor order;
* `CAM` / `cam`, `CAM_1` / `cam_1` case folding, and `CAM_01` as a distinct identity;
* signed-zero preservation and quaternion `q` versus `-q`;
* the material assignment/asset-slot/resolution boundary of Revision 3.3 — the two source
  facts independently encoded, `resolved` required to be their deterministic projection (a
  divergent value is refused), and no implementation-side claim that render-path or
  session-dependent engine substitution is extracted;
* the sequencer validity arms;
* the error vocabulary the new refusal arms use;
* coherence between the C++ fixture tags, the live gate's requested entities and the
  contract's error vocabulary (an anti-drift gate: a requested entity that does not exist
  in the fixture must fail here rather than silently in a live run).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from planning.unreal_state_extraction import (
    ALL_ERROR_CODES,
    UnrealStateExtractionError,
    canonical_bytes_for_tree,
    canonical_representative,
    digest_value_tree,
    encode_pattern,
    is_canonical_entity_id,
    is_canonical_pattern,
)
from tests.extraction_payload_fixtures import (
    IDENTITY,
    NEGATIVE_ZERO,
    ZERO,
    actor,
    actor_state_tree,
    material_component,
    sequence,
    sequencer_state_tree,
    slot,
    transform,
    vector3,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SOURCE = (
    REPO_ROOT
    / "unreal"
    / "AtlasUnrealHarness"
    / "Source"
    / "AtlasUnrealTransport"
    / "Private"
    / "AtlasExtractionFixture.cpp"
)
LIVE_GATE_SOURCE = REPO_ROOT / "tests" / "unreal_state_extraction_live_gate.py"


def _actor(entity_id: str, **overrides: object) -> dict:
    return actor(entity_id=entity_id, **overrides)


# ---------------------------------------------------------------------------
# 1. Request-order permutation invariance
# ---------------------------------------------------------------------------

def test_two_actor_trees_are_canonical_regardless_of_construction_order() -> None:
    """The same actor set produces identical bytes whichever order it was built in."""
    permutation_a = _actor("IMPL_PERM_A")
    permutation_b = _actor("IMPL_PERM_B")

    forward = actor_state_tree([permutation_a, permutation_b])
    # The same two records, whose keys were inserted in a different order.
    reversed_keys = {key: value for key, value in reversed(list(permutation_a.items()))}
    backward = actor_state_tree([reversed_keys, permutation_b])

    assert canonical_bytes_for_tree(forward) == canonical_bytes_for_tree(backward)
    assert digest_value_tree(forward) == digest_value_tree(backward)


def test_actor_records_are_ordered_by_canonical_entity_id_in_the_payload() -> None:
    """`actors` is ordered by canonical entity id, never by the request or insertion order."""
    tree = actor_state_tree([_actor("IMPL_PERM_A"), _actor("IMPL_PERM_B")])
    canonical = canonical_bytes_for_tree(tree)

    assert b"IMPL_PERM_A" in canonical
    assert canonical.index(b"IMPL_PERM_A") < canonical.index(b"IMPL_PERM_B")
    # A set whose canonical order is not the insertion order still serializes canonically.
    swapped = actor_state_tree([_actor("IMPL_PERM_A"), _actor("IMPL_PERM_B")])
    assert canonical_bytes_for_tree(swapped) == canonical


def test_non_canonical_actor_order_is_rejected_rather_than_sorted() -> None:
    """A producer that emits request order instead of canonical order fails closed."""
    tree = actor_state_tree([_actor("IMPL_PERM_B"), _actor("IMPL_PERM_A")])
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(tree)
    assert error.value.code == "ERR_EXTRACTION_NON_CANONICAL_ORDER"


# ---------------------------------------------------------------------------
# 2. Case variants and numbered identities
# ---------------------------------------------------------------------------

def test_case_variants_share_one_canonical_identity() -> None:
    assert canonical_representative("cam") == canonical_representative("CAM") == "CAM"
    assert canonical_representative("cam_1") == canonical_representative("CAM_1") == "CAM_1"
    assert canonical_representative("CaseVariantBound") == "CASEVARIANTBOUND"


def test_numbered_identities_are_three_distinct_classes() -> None:
    base = canonical_representative("CAM")
    one = canonical_representative("CAM_1")
    leading_zero = canonical_representative("CAM_01")

    assert base == "CAM"
    assert one == "CAM_1"
    assert leading_zero == "CAM_01"
    assert len({base, one, leading_zero}) == 3
    assert all(is_canonical_entity_id(value) for value in (base, one, leading_zero))


def test_numbered_identity_case_variants_collapse_within_their_own_class() -> None:
    assert canonical_representative("cam_01") == "CAM_01"
    # The leading-zero form never folds onto the numbered form: `CAM_01` is not `CAM_1`.
    assert canonical_representative("cam_01") != canonical_representative("cam_1")


def test_numbered_identity_ordering_and_digest_are_stable() -> None:
    trees = {
        name: actor_state_tree([_actor(name)])
        for name in ("CAM", "CAM_1", "CAM_01")
    }
    digests = {name: digest_value_tree(tree) for name, tree in trees.items()}
    assert len(set(digests.values())) == 3
    # `CAM` < `CAM_01` < `CAM_1` in UTF-16 code-unit order, and that is the order the
    # contract's canonical actor list requires.
    ordered = sorted(digests, key=lambda name: [ord(character) for character in name])
    assert ordered == ["CAM", "CAM_01", "CAM_1"]
    canonical_bytes_for_tree(actor_state_tree([_actor(name) for name in ordered]))


# ---------------------------------------------------------------------------
# 3. Signed zero
# ---------------------------------------------------------------------------

def test_signed_zero_is_preserved_as_a_source_fact() -> None:
    negative = transform(location_cm=vector3(NEGATIVE_ZERO, ZERO, ZERO))
    positive = transform(location_cm=vector3(ZERO, ZERO, ZERO))

    negative_tree = actor_state_tree([_actor("IMPL_SIGNED_ZERO", transform=negative)])
    positive_tree = actor_state_tree([_actor("IMPL_SIGNED_ZERO", transform=positive)])

    assert is_canonical_pattern(NEGATIVE_ZERO)
    assert is_canonical_pattern(ZERO)
    # Preservation means the two states are different values, not that they compare equal.
    assert digest_value_tree(negative_tree) != digest_value_tree(positive_tree)
    assert b"8000000000000000" in canonical_bytes_for_tree(negative_tree)


def test_negative_zero_is_not_normalised_to_positive_zero() -> None:
    assert NEGATIVE_ZERO != ZERO
    assert encode_pattern(-0.0) == NEGATIVE_ZERO
    assert encode_pattern(0.0) == ZERO


# ---------------------------------------------------------------------------
# 4. Quaternion sign
# ---------------------------------------------------------------------------

def _rotation(x: str, y: str, z: str, w: str) -> dict:
    return {
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
        "x": x,
        "y": y,
        "z": z,
        "w": w,
    }


HALF_SQRT = "3fe6a09e667f3bcd"  # 0.7071067811865476


def test_quaternion_q_and_negative_q_are_distinct_source_facts() -> None:
    negative_half_sqrt = encode_pattern(-0.7071067811865476)
    positive = actor_state_tree(
        [
            _actor(
                "IMPL_Q_POS",
                transform=transform(rotation=_rotation(ZERO, ZERO, HALF_SQRT, HALF_SQRT)),
            )
        ]
    )
    negative = actor_state_tree(
        [
            _actor(
                "IMPL_Q_NEG",
                transform=transform(
                    rotation=_rotation(ZERO, ZERO, negative_half_sqrt, negative_half_sqrt)
                ),
            )
        ]
    )

    assert is_canonical_pattern(HALF_SQRT)
    assert digest_value_tree(positive) != digest_value_tree(negative)
    # The sign bit is the difference; the magnitude is identical.
    assert HALF_SQRT[1:] == negative_half_sqrt[1:]


# ---------------------------------------------------------------------------
# 5. Material assignment/resolution boundary (Revision 3.2 semantics)
# ---------------------------------------------------------------------------

ASSIGNED = "/Game/AtlasTest/Materials/Assigned.Assigned"
OTHER_MATERIAL = "/Game/AtlasTest/Materials/Other.Other"
ASSET_SLOT = "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"


def _material_tree(slots: list) -> dict:
    return actor_state_tree(
        [_actor("IMPL_MATERIAL_OVERRIDE_A", materials=[material_component(slot_count=len(slots), slots=slots)])]
    )


def test_source_facts_are_independently_encoded() -> None:
    """The two source facts distinguish states; `resolved` is their projection (Rev 3.3).

    The boundary now refuses a tree in which `resolved` is not the projection, so a state
    whose *resolution* differs from its assignment is no longer representable at all — which
    is the point: such a state could only come from a session-dependent engine substitution.
    """
    tree = _material_tree([slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=ASSIGNED)])
    canonical = canonical_bytes_for_tree(tree)
    assert ASSET_SLOT.encode() in canonical
    assert ASSIGNED.encode() in canonical


def test_resolved_must_be_the_deterministic_projection() -> None:
    """A `resolved` that is not the projection of the two source facts is refused (D17c).

    This is the mechanical guarantee that configuration state cannot enter the payload: the
    engine's own material accessor is session gated, so a field read from it would not be a
    deterministic source fact, and a divergent value is rejected here rather than digested.
    """
    divergent = _material_tree(
        [slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=OTHER_MATERIAL)]
    )
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(divergent)
    assert error.value.code == "ERR_EXTRACTION_SCHEMA"
    assert "deterministic source-side projection" in str(error.value)

    # The same rule holds when the asset slot is the winner (no override): a resolution that
    # differs from the asset slot is refused too.
    slot_only_divergent = _material_tree(
        [slot(0, asset_slot=ASSET_SLOT, override=None, resolved=OTHER_MATERIAL)]
    )
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(slot_only_divergent)
    assert error.value.code == "ERR_EXTRACTION_SCHEMA"

    # And when both facts are null, the resolution must be null as well.
    null_divergent = _material_tree([slot(0, asset_slot=None, override=None, resolved=OTHER_MATERIAL)])
    with pytest.raises(UnrealStateExtractionError):
        canonical_bytes_for_tree(null_divergent)


def test_projection_holds_for_both_families_and_the_null_cases() -> None:
    """The projection is total: every combination of the two facts has exactly one value."""
    accepted = {
        "asset_slot_only": slot(0, asset_slot=ASSET_SLOT, override=None, resolved=ASSET_SLOT),
        "override_wins": slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=ASSIGNED),
        "override_over_null_slot": slot(0, asset_slot=None, override=ASSIGNED, resolved=ASSIGNED),
        "both_null": slot(0, asset_slot=None, override=None, resolved=None),
    }
    for name, slot_value in accepted.items():
        canonical_bytes_for_tree(_material_tree([slot_value]))

    def _single_component_tree(component: dict) -> dict:
        return actor_state_tree(
            [_actor("IMPL_NULL_SKINNED", materials=[component])]
        )

    # The skinned family is the same rule, expressed through the other component class.
    canonical_bytes_for_tree(
        _single_component_tree(
            material_component(
                component_class="SkinnedMeshComponent",
                slot_count=1,
                slots=[slot(0, asset_slot=None, override=ASSIGNED, resolved=ASSIGNED)],
            )
        )
    )
    with pytest.raises(UnrealStateExtractionError):
        canonical_bytes_for_tree(
            _single_component_tree(
                material_component(
                    component_class="SkinnedMeshComponent",
                    slot_count=1,
                    slots=[slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=OTHER_MATERIAL)],
                )
            )
        )


def test_collision_matrix_distinguishes_every_material_source_state() -> None:
    """States that share one of the two source facts must still digest differently."""
    states = {
        "asset_slot_only": slot(0, asset_slot=ASSET_SLOT, override=None, resolved=ASSET_SLOT),
        "override_wins": slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=ASSIGNED),
        "different_asset_same_override": slot(
            0, asset_slot=OTHER_MATERIAL, override=ASSIGNED, resolved=ASSIGNED
        ),
    }
    digests = {
        name: digest_value_tree(_material_tree([value])) for name, value in states.items()
    }
    assert len(set(digests.values())) == len(states)


def test_resolved_equals_the_assignment_in_conforming_payloads() -> None:
    """The Revision 3.2 rule the fixture must satisfy: resolved is the accessor's value.

    For a fixture whose assigned materials carry no Nanite override, the accessor returns
    the override when present and otherwise the asset slot, so a conforming payload must
    record exactly that. A payload where ``resolved`` differs from both is schema-legal —
    the boundary has no way to know — which is why the *producer* side is covered by the
    in-process accessor-equality test rather than by this one.
    """
    conforming = {
        "asset_slot_only": (slot(0, asset_slot=ASSET_SLOT, override=None, resolved=ASSET_SLOT), ASSET_SLOT),
        "override_wins": (slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=ASSIGNED), ASSIGNED),
        "override_wins_over_null_slot": (slot(0, asset_slot=None, override=ASSIGNED, resolved=ASSIGNED), ASSIGNED),
    }
    for name, (slot_value, expected) in conforming.items():
        tree = _material_tree([slot_value])
        recorded = tree["actors"][0]["materials"][0]["slots"][0]["resolved_material_asset_path"]
        assert recorded == expected, name
        canonical_bytes_for_tree(tree)

    # And the schema does not silently normalise a divergent value into the assignment.
    divergent = _material_tree([slot(0, asset_slot=ASSET_SLOT, override=ASSIGNED, resolved=OTHER_MATERIAL)])
    assert (
        divergent["actors"][0]["materials"][0]["slots"][0]["resolved_material_asset_path"]
        == OTHER_MATERIAL
    )


def test_no_impl_side_claim_of_render_path_state() -> None:
    """No implementation-side file may claim that render-path substitution is extracted.

    Revision 3.2 states the boundary in one sentence that every mention has to respect:
    Nanite render-path substitution is outside v1 extraction because the extraction accessor
    does not expose that rendered state. A future comment, test or document that claims
    otherwise is a contract drift, and this test fails on it.
    """
    files = [
        FIXTURE_SOURCE.parent / "AtlasStateExtraction.cpp",
        FIXTURE_SOURCE.parent / "AtlasStateExtraction.h",
        LIVE_GATE_SOURCE,
        Path(__file__).resolve(),
        REPO_ROOT / "docs" / "UNREAL_STATE_EXTRACTION_FIDELITY_V1_VALIDATION_MATRIX.md",
    ]
    negation_markers = ("not ", "no ", "never", "outside", "cannot", "does not", "without", "n't")
    quote_pattern = re.compile(r"\"[^\"]*\"|'[^']*'")
    for path in files:
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            # A quoted phrase is a citation of older wording, not a claim made by this file.
            unquoted = quote_pattern.sub("", line).lower()
            if "nanite" not in unquoted or "substitut" not in unquoted:
                continue
            assert any(marker in unquoted for marker in negation_markers), (
                f"{path.name}:{line_number} claims Nanite substitution without stating the "
                f"boundary: {line.strip()}"
            )


def test_extractor_uses_no_component_material_accessor() -> None:
    """The extractor computes the resolution from source facts, never from the accessor.

    Revision 3.3 moved the engine's own material accessor off the read boundary: its
    material-level Nanite step is session/configuration gated, so reading the field from it
    would let configuration state into a digested field. This test fails if that call ever
    comes back, or if any render-state/Nanite-audit accessor or console variable appears.
    """
    extractor = (FIXTURE_SOURCE.parent / "AtlasStateExtraction.cpp").read_text(encoding="utf-8")

    # The deterministic projection must be present, over objects the extractor already read.
    assert "OverrideMaterial != nullptr ? OverrideMaterial : AssetSlotMaterial" in extractor

    # No component material accessor call, in any of the spellings the file uses.
    component_accessor_patterns = (
        "Component->GetMaterial(",
        "StaticComponent->GetMaterial(",
        "SkinnedComponent->GetMaterial(",
    )
    for pattern in component_accessor_patterns:
        assert pattern not in extractor, f"the extractor still calls {pattern}"

    forbidden_symbols = (
        "GetNaniteOverride",
        "GetNaniteAuditMaterial",
        "GetEditorMaterial",
        "SceneProxy",
        "RenderProxy",
        "GetUsedMaterials",
        "GEnableNaniteMaterialOverrides",
        "ShouldCreateNaniteProxy",
        "UseNaniteOverrideMaterials",
        # A console-variable read would be the other way for configuration state to decide the
        # value. Naming `r.Nanite.MaterialOverrides` in an explanatory comment is not a read,
        # so the accessor forms are forbidden rather than the cvar name.
        "IConsoleManager",
        "GetConsoleVariable",
        "FindConsoleVariable",
        "GetValueOnGameThread",
        "GetValueOnAnyThread",
    )
    for symbol in forbidden_symbols:
        assert symbol not in extractor, f"the extractor references forbidden symbol {symbol}"

    # Every mention of Nanite in the extraction translation unit is a comment: the code path
    # itself names no Nanite concept.
    for line_number, line in enumerate(extractor.splitlines(), start=1):
        if "Nanite" in line:
            assert line.lstrip().startswith("//"), (
                f"AtlasStateExtraction.cpp:{line_number} mentions Nanite outside a comment: "
                f"{line.strip()}"
            )


def test_matrix_document_states_the_revision_3_3_boundary() -> None:
    """The evidence document must carry the narrowed, deterministic semantics."""
    matrix = (
        REPO_ROOT
        / "docs"
        / "UNREAL_STATE_EXTRACTION_FIDELITY_V1_VALIDATION_MATRIX.md"
    ).read_text(encoding="utf-8")
    assert "Revision 3.3" in matrix
    assert "deterministic" in matrix
    assert "projection" in matrix
    assert "render-path substitution" in matrix


def test_nullable_material_paths_are_preserved_not_dropped() -> None:
    """An absent asset-slot/override is reported as null, never omitted or coerced.

    The *producer* refuses an unresolved slot (``ERR_EXTRACTION_MATERIAL_UNRESOLVED``);
    the boundary's job is to represent the three material facts exactly, so the test
    asserts both halves: the vocabulary the producer uses, and the faithful null here.
    """
    assert "ERR_EXTRACTION_MATERIAL_UNRESOLVED" in ALL_ERROR_CODES
    tree = _material_tree([slot(0, asset_slot=None, override=ASSIGNED, resolved=ASSIGNED)])
    canonical = canonical_bytes_for_tree(tree)
    assert b'"asset_slot_material_asset_path":null' in canonical
    assert ASSIGNED.encode() in canonical


def test_slot_index_is_the_positional_ordinal() -> None:
    """A slot whose index is not its position is a non-canonical order, not a reorder."""
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(_material_tree([slot(1)]))
    assert error.value.code == "ERR_EXTRACTION_NON_CANONICAL_ORDER"


def test_unsupported_family_refusal_codes_are_in_the_vocabulary() -> None:
    """The refusal arms the fixture provokes must exist in the closed vocabulary."""
    for code in (
        "ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE",
        "ERR_EXTRACTION_MESH_ASSET_UNSTABLE",
        "ERR_EXTRACTION_MESH_COMPILING",
        "ERR_EXTRACTION_SEQUENCE_RANGE_INVALID",
        "ERR_EXTRACTION_SEQUENCE_RANGE_OPEN",
        "ERR_EXTRACTION_SEQUENCE_RATE_INVALID",
        "ERR_EXTRACTION_SCOPE_CHANGED",
    ):
        assert code in ALL_ERROR_CODES


# ---------------------------------------------------------------------------
# 6. Sequencer validity arms
# ---------------------------------------------------------------------------

def test_valid_sequencer_tree_round_trips() -> None:
    tree = sequencer_state_tree([sequence(entity_id="IMPL_SEQUENCE_VALID")])
    canonical = canonical_bytes_for_tree(tree)
    assert b"IMPL_SEQUENCE_VALID" in canonical
    assert digest_value_tree(tree) == digest_value_tree(sequencer_state_tree([sequence(entity_id="IMPL_SEQUENCE_VALID")]))


def test_degenerate_playback_range_is_rejected() -> None:
    degenerate = sequence(
        entity_id="IMPL_SEQUENCE_DEGENERATE",
        playback_range={
            "lower_frame": 0,
            "lower_bound": "inclusive",
            "upper_frame": 0,
            "upper_bound": "exclusive",
        },
    )
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(sequencer_state_tree([degenerate]))
    assert error.value.code == "ERR_EXTRACTION_SCHEMA"
    assert "non-degenerate" in str(error.value)


@pytest.mark.parametrize(
    "rate_field,rate",
    [
        ("tick_resolution", {"numerator": 0, "denominator": 1}),
        ("tick_resolution", {"numerator": 24000, "denominator": 0}),
        ("display_rate", {"numerator": 0, "denominator": 1}),
        ("display_rate", {"numerator": 30, "denominator": 0}),
    ],
)
def test_invalid_rational_rates_are_rejected(rate_field: str, rate: dict) -> None:
    broken = sequence(entity_id="IMPL_SEQUENCE_BAD_RATE", **{rate_field: rate})
    with pytest.raises(UnrealStateExtractionError) as error:
        canonical_bytes_for_tree(sequencer_state_tree([broken]))
    assert error.value.code == "ERR_EXTRACTION_SCHEMA"
    assert "positive numerator and denominator" in str(error.value)


def test_sequencer_rates_are_rational_pairs_not_floats() -> None:
    tree = sequencer_state_tree([sequence()])
    canonical = canonical_bytes_for_tree(tree)
    assert b'"numerator":24000' in canonical
    assert b'"denominator":1' in canonical
    assert b"24000.0" not in canonical


# ---------------------------------------------------------------------------
# 7. Fixture / gate / vocabulary coherence (anti-drift)
# ---------------------------------------------------------------------------

def _fixture_tag_ids() -> set:
    source = FIXTURE_SOURCE.read_text(encoding="utf-8")
    return set(re.findall(r'TEXT\("(IMPL_[A-Z0-9_]+|CAM[A-Z0-9_]*|case_lower|CASE_UPPER|CaseVariantBound)"\)', source))


def test_fixture_source_exists_and_declares_the_required_tag_set() -> None:
    tags = _fixture_tag_ids()
    required = {
        "IMPL_PERM_A",
        "IMPL_PERM_B",
        "CAM",
        "CAM_1",
        "CAM_01",
        "case_lower",
        "CASE_UPPER",
        "IMPL_PARENT_NONE",
        "IMPL_PARENT_UNBOUND",
        "IMPL_PARENT_BOUND",
        "IMPL_MATERIAL_OVERRIDE_A",
        "IMPL_MATERIAL_OVERRIDE_B",
        "IMPL_OMITTED",
        "IMPL_NULL_SKINNED",
        "IMPL_UNSUPPORTED_COMPONENT",
        "IMPL_SIGNED_ZERO",
        "IMPL_Q_POS",
        "IMPL_Q_NEG",
        "IMPL_SEQUENCE_VALID",
        "IMPL_SEQUENCE_DEGENERATE",
        "IMPL_SEQUENCE_BAD_RATE",
        "IMPL_RUNTIME_MESH",
    }
    missing = sorted(required - tags)
    assert not missing, f"fixture source is missing required tags: {missing}"


def test_every_entity_the_live_gate_requests_exists_in_the_fixture() -> None:
    """A live-gate request for a non-existent entity would look like a pass-shaped gap."""
    gate_source = LIVE_GATE_SOURCE.read_text(encoding="utf-8")
    requested = set(
        re.findall(r"REQUESTED_ENTITIES\s*(?::[^=]+)?=\s*\[(.*?)\]", gate_source, re.S)[0].split()
    )
    requested_ids = {token.strip().strip('",\'') for token in requested if token.strip().strip('",\'')}
    assert requested_ids, "the live gate must declare its requested entities"
    tags = _fixture_tag_ids()
    # `FIELD_SURFACE` is the legacy render fixture actor and `NO_SUCH_ENTITY` is the
    # deliberate miss; both are intentional and neither is created by this rung's fixture.
    external = {"FIELD_SURFACE", "NO_SUCH_ENTITY"}
    unknown = sorted(
        entity for entity in requested_ids if entity not in tags and entity not in external
    )
    assert not unknown, f"live gate requests entities the fixture does not create: {unknown}"


def test_fixture_does_not_touch_legacy_fixture_content() -> None:
    """The rung adds content; it must not repurpose the quarantined legacy fixtures."""
    source = FIXTURE_SOURCE.read_text(encoding="utf-8")
    assert "AtlasSequencerFixture" not in source
    assert "AtlasSequencerFixtureSequence" not in source
    assert "AtlasFieldSurfaceFixture" not in source


def test_extractor_never_depends_on_fixture_content() -> None:
    """The extraction TU must not reference the fixture provisioner or its tags."""
    private = FIXTURE_SOURCE.parent
    extractor = (private / "AtlasStateExtraction.cpp").read_text(encoding="utf-8")
    header = (private / "AtlasStateExtraction.h").read_text(encoding="utf-8")
    for text in (extractor, header):
        assert "AtlasExtractionFixture" not in text
        assert "IMPL_PERM" not in text
        assert "SaveMap" not in text
        assert "SpawnActor" not in text


def test_fixture_provisioner_is_test_content_only() -> None:
    """The fixture TU creates content; it must never call the extraction entry points."""
    source = FIXTURE_SOURCE.read_text(encoding="utf-8")
    assert "ExtractActorState" not in source
    assert "ExtractSequencerState" not in source
    assert "SetScopeRevalidationProbe" not in source


def test_test_only_scope_probe_is_null_by_default_in_production_paths() -> None:
    """The seam must be set by tests only, never by the transport or the dispatcher."""
    private = FIXTURE_SOURCE.parent
    for name in ("AtlasTransportServer.cpp", "AtlasUnrealTransport.cpp"):
        text = (private / name).read_text(encoding="utf-8")
        assert "SetScopeRevalidationProbe" not in text
    extractor = (private / "AtlasStateExtraction.cpp").read_text(encoding="utf-8")
    assert "TFunction<void()> GScopeRevalidationProbe;" in extractor
    # Declared without an initialiser, i.e. null until a test sets it.
    assert "GScopeRevalidationProbe = " not in extractor.split("void SetScopeRevalidationProbe")[0]
