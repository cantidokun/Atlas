"""Canonical M12.2 Unreal semantic production fragments registry.

A separate module holding the canonical immutable fragment set so the catalog
and composition layers share one source of truth without circular imports.
"""

from __future__ import annotations

from typing import FrozenSet, Tuple

from planning.m12.fragments import UnrealProductionFragment


def _f(
    canonical_id: str,
    version: int,
    label: str,
    *,
    inputs=(),
    produces=(),
    requires=(),
    contributes_invariants=(),
    idempotent=True,
    expandable=True,
    detail=None,
) -> UnrealProductionFragment:
    return UnrealProductionFragment(
        canonical_id=canonical_id,
        version=version,
        label=label,
        inputs=tuple(inputs),
        produces=tuple(produces),
        requires=tuple(requires),
        contributes_invariants=tuple(contributes_invariants),
        idempotent=idempotent,
        expandable=expandable,
        detail=dict(detail or {}),
    )


CANONICAL_UNREAL_FRAGMENTS: Tuple[UnrealProductionFragment, ...] = (
    _f(
        "scene_setup",
        1,
        "Prepare the soccer digital-twin scene.",
        produces=("scene_ready",),
        contributes_invariants=("scene_initialized",),
        detail={"kind": "scene"},
    ),
    _f(
        "environment_setup",
        1,
        "Configure the field/environment representation.",
        produces=("environment_ready",),
        contributes_invariants=("environment_configured",),
        detail={"kind": "environment"},
    ),
    _f(
        "camera_setup",
        1,
        "Configure camera placement/framing for production shots.",
        requires=("scene_ready",),
        produces=("cameras_ready",),
        contributes_invariants=("cameras_configured",),
        detail={"kind": "camera"},
    ),
    _f(
        "lighting_setup",
        1,
        "Configure lighting for the scene.",
        requires=("scene_ready",),
        produces=("lighting_ready",),
        contributes_invariants=("lighting_configured",),
        detail={"kind": "lighting"},
    ),
    _f(
        "sequence_setup",
        1,
        "Configure the cinematic sequence / playback range.",
        requires=("scene_ready", "cameras_ready"),
        produces=("sequence_ready",),
        contributes_invariants=("sequence_configured",),
        detail={"kind": "sequence"},
    ),
    _f(
        "render_setup",
        1,
        "Configure render job parameters for an authorized render.",
        requires=("sequence_ready",),
        produces=("render_ready",),
        contributes_invariants=("render_configured",),
        idempotent=False,
        expandable=False,
        detail={"kind": "render", "render_execution_constrained": True},
    ),
)


def canonical_fragment(fragment_id: str) -> UnrealProductionFragment:
    """Resolve a canonical fragment by exact id; fail closed on unknown."""
    if not isinstance(fragment_id, str) or not fragment_id.strip():
        raise ValueError("fragment id must be a non-empty string")
    for fragment in CANONICAL_UNREAL_FRAGMENTS:
        if fragment.canonical_id == fragment_id:
            return fragment
    known = ", ".join(f.canonical_id for f in CANONICAL_UNREAL_FRAGMENTS)
    raise KeyError(f"unknown Unreal semantic fragment: {fragment_id!r} (known: {known})")


def available_canonical_fragments() -> Tuple[UnrealProductionFragment, ...]:
    """Return the canonical fragment set in stable definition order."""
    return CANONICAL_UNREAL_FRAGMENTS


def canonical_fragment_ids() -> FrozenSet[str]:
    return frozenset(f.canonical_id for f in CANONICAL_UNREAL_FRAGMENTS)


__all__ = [
    "CANONICAL_UNREAL_FRAGMENTS",
    "canonical_fragment",
    "available_canonical_fragments",
    "canonical_fragment_ids",
]