"""M12.2 deterministic tests — fragments + composition."""

from copy import deepcopy

import pytest

from planning.m12 import (
    FragmentCompositionError,
    UnrealProductionFragment,
    compose_fragments,
)
from planning.m12.fragments_registry import (
    CANONICAL_UNREAL_FRAGMENTS,
    canonical_fragment,
    canonical_fragment_ids,
)


def make_fragment(
    fid="a",
    *,
    requires=(),
    produces=None,
    contributes_invariants=(),
    idempotent=True,
) -> UnrealProductionFragment:
    produced = tuple(produces) if produces is not None else (f"produced_{fid}",)
    return UnrealProductionFragment(
        canonical_id=fid,
        version=1,
        label=f"fragment {fid}",
        produces=produced,
        requires=tuple(requires),
        contributes_invariants=tuple(contributes_invariants),
        idempotent=idempotent,
    )


# ---------------------------------------------------------------------------
# Fragment validation
# ---------------------------------------------------------------------------


def test_fragment_canonical_id_no_whitespace():
    with pytest.raises(ValueError):
        UnrealProductionFragment(
            canonical_id="bad id", version=1, label="x", produces=("r",)
        )


def test_fragment_version_positive():
    with pytest.raises(ValueError):
        UnrealProductionFragment(
            canonical_id="a", version=0, label="x", produces=("r",)
        )


def test_fragment_must_produce_or_contribute():
    with pytest.raises(ValueError):
        UnrealProductionFragment(
            canonical_id="a", version=1, label="x"  # neither produces nor contributes
        )


def test_fragment_no_duplicate_tokens_in_tuple():
    with pytest.raises(ValueError):
        UnrealProductionFragment(
            canonical_id="a", version=1, label="x", produces=("r", "r")
        )


def test_canonical_fragment_resolution_and_ids():
    frag = canonical_fragment("scene_setup")
    assert frag.canonical_id == "scene_setup"
    with pytest.raises(KeyError):
        canonical_fragment("nope")
    assert "camera_setup" in canonical_fragment_ids()
    assert len(CANONICAL_UNREAL_FRAGMENTS) >= 6


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------


def test_composition_orders_by_dependency():
    # camera depends on scene -> scene first.
    plan = compose_fragments(
        [canonical_fragment("camera_setup"), canonical_fragment("scene_setup")]
    )
    assert plan.fragment_ids == ("scene_setup", "camera_setup")


def test_deterministic_order_for_independents():
    a = compose_fragments(
        [canonical_fragment("scene_setup"), canonical_fragment("lighting_setup")]
    )
    b = compose_fragments(
        [canonical_fragment("scene_setup"), canonical_fragment("lighting_setup")]
    )
    assert a.fragment_ids == b.fragment_ids
    assert a.to_json_compatible() == b.to_json_compatible()


def test_missing_dependency_fails_closed():
    with pytest.raises(FragmentCompositionError):
        compose_fragments([canonical_fragment("camera_setup")])  # requires scene_ready


def test_cycle_fails_closed():
    f1 = make_fragment("x", requires=("r_y",), produces=("r_x",))
    f2 = make_fragment("y", requires=("r_x",), produces=("r_y",))
    with pytest.raises(FragmentCompositionError):
        compose_fragments([f1, f2])


# ---------------------------------------------------------------------------
# Duplicate / conflict behavior
# ---------------------------------------------------------------------------


def test_duplicate_fragment_id_fails_closed():
    scene = canonical_fragment("scene_setup")
    with pytest.raises(FragmentCompositionError):
        compose_fragments([scene, deepcopy(scene)])


def test_conflicting_invariant_contribution_fails_closed():
    f1 = make_fragment("x", contributes_invariants=("cameras_configured",), idempotent=True)
    f2 = make_fragment(
        "y", contributes_invariants=("cameras_configured",), idempotent=False
    )
    with pytest.raises(FragmentCompositionError):
        compose_fragments([f1, f2])


def test_idempotent_shared_invariant_is_deduplicated():
    f1 = make_fragment("x", produces=("r1",), contributes_invariants=("inv",))
    f2 = make_fragment("y", produces=("r2",), contributes_invariants=("inv",))
    plan = compose_fragments([f1, f2])
    assert "inv" in plan.target_state.invariant_names
    assert sum(1 for n in plan.target_state.invariant_names if n == "inv") == 1


# ---------------------------------------------------------------------------
# Target-state merge
# ---------------------------------------------------------------------------


def test_target_state_invariants_merged_deterministically():
    plan = compose_fragments(
        [
            canonical_fragment("scene_setup"),
            canonical_fragment("camera_setup"),
            canonical_fragment("sequence_setup"),
        ],
        requested_invariants=("requested_extra",),
    )
    assert plan.target_state.invariant_names == frozenset(
        {
            "scene_initialized",
            "cameras_configured",
            "sequence_configured",
            "requested_extra",
        }
    )
    assert plan.target_state.expects_render is False


# ---------------------------------------------------------------------------
# Serialization determinism
# ---------------------------------------------------------------------------


def test_planned_composition_serialization_is_stable():
    plan = compose_fragments(
        [canonical_fragment("scene_setup"), canonical_fragment("camera_setup")]
    )
    j1 = plan.to_json_compatible()
    j2 = plan.to_json_compatible()
    assert j1 == j2


def test_requires_at_least_one_fragment():
    with pytest.raises(FragmentCompositionError):
        compose_fragments([])