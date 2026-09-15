"""Deterministic digital-twin readiness gate for a scene report.

The readiness result is DERIVED FROM the kernel's findings — it is NOT a separate set of hidden
checks. The state vocabulary reuses the project's existing
:class:`planning.digital_twin_validation.ValidationState` terms (PRODUCTION_READY / ANALYZED /
NEEDS_REVIEW) rather than inventing a competing state system.

Mapping (documented, deterministic):
- READY                      -> ValidationState.PRODUCTION_READY
- READY_WITH_WARNINGS        -> ValidationState.ANALYZED   (valid geometry, non-blocking warnings)
- NOT_READY                  -> ValidationState.NEEDS_REVIEW

A scene is NOT automatically "production-ready" merely because geometry passes: readiness reflects
the CURRENT documented gate (no ready-blocking findings AND required roles present). Future
criteria can be added to this gate ONLY by extending the profile's ``required_object_roles`` or
``ready_blocking_codes`` — never by injecting engine-side checks.
"""

from typing import Iterable, Sequence, Tuple

from planning.blender.finding_codes import FindingCode, FindingSeverity, DEFAULT_READY_BLOCKING_CODES
from planning.blender.scene_report import Finding
from planning.blender.scene_model import SceneModel
from planning.blender.soccer_field_profile import SoccerFieldValidationProfile
from planning.digital_twin_validation import ValidationState


def evaluate_readiness(
    scene: SceneModel,
    findings: Iterable[Finding],
    profile: SoccerFieldValidationProfile,
) -> Tuple[str, str]:
    """Return ``(ValidationState.value, reason)`` derived deterministically from findings.

    ``ValidationState.value`` is the canonical serialized term (e.g. ``"production_ready"``).
    The reason string is informational only; the state is the semantic signal.
    """
    findings = tuple(findings)
    blocking = {
        f.code for f in findings if f.code in set(profile.ready_blocking_codes)
    }
    errors = {f.code for f in findings if f.severity is FindingSeverity.ERROR}
    warnings = [f for f in findings if f.severity is FindingSeverity.WARNING]

    missing_roles = _missing_roles(scene, profile)

    if blocking or errors or missing_roles:
        reasons = []
        if errors:
            reasons.append("geometry/scene errors present")
        if blocking - errors:
            reasons.append("ready-blocking finding present")
        if missing_roles:
            reasons.append(f"missing required roles: {', '.join(sorted(missing_roles))}")
        return ValidationState.NEEDS_REVIEW.value, "; ".join(reasons) or "not ready"

    if warnings:
        return ValidationState.ANALYZED.value, f"{len(warnings)} non-blocking warning(s)"

    return ValidationState.PRODUCTION_READY.value, "ready"


def _missing_roles(scene: SceneModel, profile: SoccerFieldValidationProfile) -> Tuple[str, ...]:
    if not profile.required_object_roles:
        return ()
    names = {o.object_id for o in scene.objects} | {o.name for o in scene.objects}
    return tuple(role for role in profile.required_object_roles if role not in names)


def is_ready(state: str) -> bool:
    return state == ValidationState.PRODUCTION_READY.value


def is_ready_with_warnings(state: str) -> bool:
    return state == ValidationState.ANALYZED.value


def is_not_ready(state: str) -> bool:
    return state == ValidationState.NEEDS_REVIEW.value