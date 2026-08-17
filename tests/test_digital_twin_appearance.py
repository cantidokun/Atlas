import pytest

from planning.digital_twin_appearance import AppearanceKind, AppearanceReference


def test_canonical_appearance_is_not_variant_bound():
    appearance = AppearanceReference("field-surface", "grass-canonical", AppearanceKind.CANONICAL, "grass")
    assert appearance.kind is AppearanceKind.CANONICAL
    assert appearance.variant_id is None


def test_canonical_appearance_cannot_reference_variant():
    with pytest.raises(ValueError):
        AppearanceReference(
            "field-surface",
            "grass-liquid",
            AppearanceKind.CANONICAL,
            "grass",
            variant_id="liquid-shot",
        )


def test_production_appearance_can_reference_variant():
    appearance = AppearanceReference(
        "field-surface",
        "liquid-look",
        AppearanceKind.PRODUCTION,
        "liquid-metal",
        variant_id="liquid-shot",
    )
    assert appearance.variant_id == "liquid-shot"
