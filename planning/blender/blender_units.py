"""Canonical Blender unit-system -> SceneModel mapping (language-neutral).

Blender's ``bpy.types.UnitSettings`` exposes two relevant fields:
  - ``system``      : a coarse enum — ``NONE`` / ``METRIC`` / ``IMPERIAL``.
  - ``length_unit`` : the precise length-unit string, e.g. ``"METERS"``, ``"CENTIMETERS"``,
                      ``"INCHES"``, ``"FEET"``.

Canonical contract (deterministic, no loss, no silent scale assumption):

  length_unit present (non-empty)
      -> canonical SceneModel token = the normalized ``length_unit`` string.
         (e.g. ``"METERS"`` -> ``"METERS"``; ``"CENTIMETERS"`` -> ``"CENTIMETERS"``. We do NOT
          fold centimeters->meters: that would silently assume a scale factor. Atlas's soccer
          profile only accepts the meters family, so a centimeters scene legitimately yields
          ``SCENE_UNIT_INVALID`` rather than a wrong scale.)
  else ``system``
      -> canonical representative for the coarse system:
           METRIC    -> "METERS"       (metric system's representative length unit)
           IMPERIAL  -> "INCHES"       (imperial system's representative length unit)
           NONE      -> "UNSPECIFIED"
           <other>   -> the normalized system token (kernel/profile ultimately judges it)

``map_unit_system`` NEVER fails merely because the unit is unusual — an unusual unit is a
*validation* signal (the profile rejects it as ``SCENE_UNIT_INVALID``), not an extraction crash.
What IS fail-closed is undecidable input: a unit_settings object with neither a usable
``length_unit`` nor a ``system`` is a mapping error (raises ``UnitMappingError``).

The canonical SceneModel vocabulary is the returned token. Blender is NOT the semantic authority:
this mapping is one deterministic source of a language-neutral value the kernel consumes; a C++ or
other producer can supply the same canonical token directly.
"""

from typing import Optional, Union

# Blender's canonical coarse-system enum values -> representative canonical unit token.
_SYSTEM_REPRESENTATIVE = {
    "METRIC": "METERS",
    "IMPERIAL": "INCHES",
    "NONE": "UNSPECIFIED",
    "": "UNSPECIFIED",
    "UNSPECIFIED": "UNSPECIFIED",
}


class UnitMappingError(ValueError):
    """Declared error: the source unit settings cannot be mapped to a canonical unit token."""


def _normalize_token(value: str) -> str:
    return value.strip().upper()


def map_unit_system(unit_settings: object) -> str:
    """Return the canonical SceneModel ``unit_system`` token for a Blender ``unit_settings``.

    Prefers ``length_unit`` (precise) over ``system`` (coarse). Raises ``UnitMappingError`` when
    neither yields a usable token (undecidable input -> fail closed, never fabricate the unit).
    """
    length_unit = getattr(unit_settings, "length_unit", None)
    if length_unit is not None:
        token = _normalize_token(str(length_unit))
        if token and token != "NONE":
            return token

    system = getattr(unit_settings, "system", None)
    if system is not None:
        sys_tok = _normalize_token(str(system))
        if any(k == sys_tok for k in ("METRIC", "IMPERIAL", "NONE", "")):
            return _SYSTEM_REPRESENTATIVE[sys_tok]
        if sys_tok:  # already a canonical token (e.g. a producer or test supplies "METERS")
            return sys_tok

    raise UnitMappingError(
        "cannot map Blender unit_settings to a canonical unit token "
        "(no usable length_unit and no usable system)"
    )


def is_meters_like(token: str) -> bool:
    """True when a canonical token is meters-family (an alias the soccer profile accepts)."""
    return _normalize_token(token) in _METERS_ALIASES


_METERS_ALIASES = {"METERS", "METER", "METRES", "METRE", "M"}