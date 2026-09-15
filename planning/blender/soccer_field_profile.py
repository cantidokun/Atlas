"""Configurable Atlas-specific validation profile for soccer-field digital-twin scenes.

The generic mesh/scene health kernel is deliberately profile-agnostic: it only tells you WHAT a
geometric/organizational rule is violated, never WHICH production is plausible. Atlas-specific
rules (dimensional envelope, required units, naming, required object roles, permitted hierarchy
and collections, tolerances) live here so the generic kernel stays reusable and C++-replacable.

A ``SoccerFieldValidationProfile`` is an immutable value object of plain primitives; it carries no
behavior beyond attribute lookup, so it can be serialized to a language-neutral configuration
document and (later) driven by a C++ geometry engine without Python semantics.
"""

import re
from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Pattern, Sequence, Tuple

from planning.blender.finding_codes import FindingCode, DEFAULT_READY_BLOCKING_CODES


@dataclass(frozen=True)
class SoccerFieldValidationProfile:
    """Immutable, configurable validation profile for one production domain (default: soccer)."""

    name: str = "soccer-field"
    # Dimensional envelope (meters) the scene/assets are expected to fall within.
    # None disables the envelope check.
    envelope_min: Tuple[float, float, float] = (-50.0, -40.0, 0.0)   # X, Y, Z min (meters)
    envelope_max: Tuple[float, float, float] = (50.0, 40.0, 12.0)    # X, Y, Z max (meters)
    # Canonical unit tokens the Atlas pipeline accepts. The extraction adapter maps Blender's
    # unit_settings to these tokens (`planning.blender.blender_units.map_unit_system`): a length_unit
    # of "METERS" (or a METRIC system) yields the canonical "METERS"; IMPERIAL -> "INCHES";
    # NONE -> "UNSPECIFIED". Tokens outside this set are a deterministic SCENE_UNIT_INVALID signal
    # (an unusual unit is a validation finding, not an extraction crash).
    allowed_units: FrozenSet[str] = frozenset({"METERS", "meters", "m"})
    # Naming convention: a compiled pattern (None disables). Default: dotted kebab/snake.
    name_pattern: Optional[Pattern[str]] = None
    allowed_collections: Optional[FrozenSet[str]] = None
    required_object_roles: Tuple[str, ...] = ()  # semantic roles that must be present
    permitted_hierarchy_depth: int = 4
    # Codes that, if present at any severity, make a scene NOT_READY.
    ready_blocking_codes: Tuple[FindingCode, ...] = DEFAULT_READY_BLOCKING_CODES
    # Expected production frame (documented; generic kernel does NOT assume it).
    expected_up_axis: str = "z"
    expected_ground_level: float = 0.0
    tolerance_bounds_metres: float = 0.05

    def __post_init__(self) -> None:
        if not self.name.strip():
            object.__setattr__(self, "name", "soccer-field")
        if type(self.allowed_units) is not frozenset:
            raise TypeError("allowed_units must be a frozen set")
        if not isinstance(self.permitted_hierarchy_depth, int) or self.permitted_hierarchy_depth < 1:
            raise ValueError("permitted_hierarchy_depth must be a positive int")
        if any(not isinstance(c, FindingCode) for c in self.ready_blocking_codes):
            raise TypeError("ready_blocking_codes must be FindingCode values")
        if self.tolerance_bounds_metres < 0.0:
            raise ValueError("tolerance_bounds_metres must be >= 0")


def soccer_field_profile(**overrides) -> SoccerFieldValidationProfile:
    """Return the default soccer-field profile, optionally overriding fields.

    The default naming pattern accepts dotted/space-separated token names (e.g. ``pitch.main``,
    ``goal.left.post``) of lowercase alphanumerics and the separators ``.-_``.
    """
    base = SoccerFieldValidationProfile(
        name="soccer-field",
        name_pattern=re.compile(r"^[a-z0-9][a-z0-9._-]*$"),
        allowed_collections=frozenset({"Field", "Sidelines", "Goals", "Players", "Structure"}),
        required_object_roles=("pitch", "goal_left", "goal_right"),
        permitted_hierarchy_depth=4,
    )
    if not overrides:
        return base
    data = {
        "name": base.name,
        "envelope_min": base.envelope_min,
        "envelope_max": base.envelope_max,
        "allowed_units": base.allowed_units,
        "name_pattern": base.name_pattern,
        "allowed_collections": base.allowed_collections,
        "required_object_roles": base.required_object_roles,
        "permitted_hierarchy_depth": base.permitted_hierarchy_depth,
        "ready_blocking_codes": base.ready_blocking_codes,
        "expected_up_axis": base.expected_up_axis,
        "expected_ground_level": base.expected_ground_level,
        "tolerance_bounds_metres": base.tolerance_bounds_metres,
    }
    data.update(overrides)
    return SoccerFieldValidationProfile(**data)