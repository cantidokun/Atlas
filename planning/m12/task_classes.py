"""Constrained M12 Unreal semantic task taxonomy.

This module defines the canonical, constrained vocabulary of Unreal
soccer-production semantic tasks. It deliberately stays narrow (soccer-field
digital-twin production representation only) and rejects out-of-vocabulary task
types rather than guessing. The taxonomy is a *classification surface only*: it
never authorizes, schedules, or executes work.
"""

from __future__ import annotations

from typing import FrozenSet, Tuple

# The canonical, constrained set of Unreal soccer-production task classes for
# M12.0. ``effect-pass-prepare`` is deliberately reserved for a post-M12 slot and
# is NOT a selectable task class yet.
UNREAL_TASK_CLASSES: FrozenSet[str] = frozenset(
    {
        "scene-prepare",
        "environment-configure",
        "camera-configure",
        "lighting-configure",
        "sequence-configure",
        "render-execute",
        "artifact-validate",
    }
)

# Task classes that do NOT culminate in an Atlas render-job submission. These are
# pure target-state / configuration tasks whose completion is verified by
# independent target-state inspection rather than by a render job.
UNREAL_NON_RENDER_TASK_CLASSES: FrozenSet[str] = frozenset(
    {
        "scene-prepare",
        "environment-configure",
        "camera-configure",
        "lighting-configure",
        "sequence-configure",
    }
)

# Task classes that MAY culminate in an Atlas render-job submission (the existing
# render-job record / submission machinery remains the sole authority for those).
UNREAL_RENDER_TASK_CLASSES: FrozenSet[str] = frozenset(
    {"render-execute", "artifact-validate"}
)

# Task classes that are currently UNSUPPORTED by the M12 semantic layer. Having
# them listed explicitly keeps the rejection surface deterministic and auditable.
_M12_RESERVED_TASK_CLASSES: FrozenSet[str] = frozenset(
    {"effect-pass-prepare"}
)

# Canonical task-class -> human-readable intent guidance. Used ONLY for
# validation error messages and deterministic snapshots; it conveys no
# execution/authority semantics.
UNREAL_TASK_CLASS_INTENT: Tuple[Tuple[str, str], ...] = (
    ("scene-prepare", "prepare/initialize the soccer digital-twin scene"),
    ("environment-configure", "configure the field/environment representation"),
    ("camera-configure", "configure camera placement/framing for production shots"),
    ("lighting-configure", "configure lighting for the scene"),
    ("sequence-configure", "configure the cinematic sequence / playback range"),
    ("render-execute", "execute an authorized render through the existing render-job path"),
    ("artifact-validate", "wrap an existing artifact validation/verification step"),
)


def is_supported_task_class(task_class: str) -> bool:
    """Return True iff `task_class` is a currently-supported M12 semantic task."""
    return task_class in UNREAL_TASK_CLASSES


def is_render_task_class(task_class: str) -> bool:
    """Return True iff `task_class` is expected to culminate in a render job."""
    return task_class in UNREAL_RENDER_TASK_CLASSES


def validate_task_class(task_class: str) -> str:
    """Validate and return a canonical task class; fail closed otherwise.

    Raises:
        ValueError: if the task class is missing, not in the supported vocabulary,
            or explicitly reserved for a future slot.
    """
    if not isinstance(task_class, str):
        raise ValueError(f"task class must be a string, got {type(task_class).__name__}")
    canonical = task_class.strip()
    if not canonical:
        raise ValueError("task class must not be empty")
    if canonical in _M12_RESERVED_TASK_CLASSES:
        raise ValueError(
            f"task class {canonical!r} is reserved for a future slot and is not "
            "supported by the M12 semantic layer"
        )
    if canonical not in UNREAL_TASK_CLASSES:
        supported = ", ".join(sorted(UNREAL_TASK_CLASSES))
        raise ValueError(
            f"unsupported task class {canonical!r}; supported classes: {supported}"
        )
    return canonical