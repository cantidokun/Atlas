"""Closed finding → correction mapping for the Cleanup/Correction planner.

Every current ``FindingCode`` (from :mod:`planning.blender.finding_codes`) has an EXPLICIT,
deterministic classification. No code falls through to an accidental generic proposal: the table
below is exhaustive and the planner\'s dispatch looks up every finding by code — an unknown code is
a ``PLANNING_ERROR`` (never silently mapped).

The classification follows the approved design (section 11 of
``BLENDER_CLEANUP_CORRECTION_PLANNER_DESIGN.md``) EXACTLY — it was reviewed and must not be
silently changed:

- DETERMINISTIC      : MESH_DUPLICATE_FACE, MESH_DEGENERATE_FACE
- HEURISTIC          : MESH_WINDING_INCONSISTENT, SCENE_UNIT_INVALID, OBJECT_NAME_INVALID
- REQUIRES_REVIEW    : MESH_INVALID_INDEX, MESH_DUPLICATE_VERTEX, MESH_NON_MANIFOLD_EDGE,
                       MESH_SCALE_OUT_OF_RANGE, MESH_NORMAL_INCONSISTENT, SCENE_ORIGIN_INVALID,
                       SCENE_BOUNDS_EMPTY, OBJECT_HIERARCHY_INVALID (dangling),
                       OBJECT_BOUNDS_OVERLAP, OBJECT_COLLECTION_INVALID
- UNSAFE_TO_AUTOMATE : OBJECT_ID_DUPLICATE, OBJECT_HIERARCHY_INVALID (cycle),
                       OBJECT_TRANSFORM_INVALID
- OUT_OF_SCOPE       : DIGITAL_TWIN_READINESS_FAILED

Each row also fixes: the proposed ``correction_type`` (or None where no auto action exists),
the source-fidelity risk class, the reversibility, and whether the proposal is automatically
generated or gated behind human review.
"""
from __future__ import annotations

from typing import Optional

from planning.blender.correction_codes import (
    CorrectionDeterminism,
    CorrectionReversibility,
    CorrectionRiskClass,
)
from planning.blender.finding_codes import FindingCode


class _Row:
    __slots__ = ("determinism", "correction_type", "risk", "reversibility", "auto_propose")

    def __init__(self, determinism: CorrectionDeterminism, *, correction_type: Optional[str],
                 risk: CorrectionRiskClass, reversibility: CorrectionReversibility,
                 auto_propose: bool):
        self.determinism = determinism
        self.correction_type = correction_type
        self.risk = risk
        self.reversibility = reversibility
        self.auto_propose = auto_propose


# --------------------------------------------------------------------------- mapping rows
# `auto_propose` = the planner emits a proposal for this finding automatically (a *proposal*, never
# an execution). REVIEW findings still get a review proposal (flagged), UNSAFE/OUT_OF_SCOPE get no
# auto proposal (they surface as state/planning_errors, never a hidden generic fix).

_TABLE: dict[FindingCode, _Row] = {
    # --- DETERMINISTIC (lossless topological garbage removal) ---
    FindingCode.MESH_DUPLICATE_FACE: _Row(
        CorrectionDeterminism.DETERMINISTIC,
        correction_type="REMOVE_DUPLICATE_FACE",
        risk=CorrectionRiskClass.FIDELITY_SAFE,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=True,
    ),
    FindingCode.MESH_DEGENERATE_FACE: _Row(
        CorrectionDeterminism.DETERMINISTIC,
        correction_type="REMOVE_DEGENERATE_FACE",
        risk=CorrectionRiskClass.FIDELITY_SAFE,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=True,
    ),
    # --- HEURISTIC (stable rule, small documented parametric/policy freedom) ---
    FindingCode.MESH_WINDING_INCONSISTENT: _Row(
        CorrectionDeterminism.HEURISTIC,
        correction_type="REPAIR_FACE_WINDING",
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.PARTIALLY_REVERSIBLE,
        auto_propose=True,  # deterministic, but fidelity GEOMETRY -> surfaces as review by design
    ),
    FindingCode.SCENE_UNIT_INVALID: _Row(
        CorrectionDeterminism.HEURISTIC,
        correction_type="NORMALIZE_UNIT_METADATA",
        risk=CorrectionRiskClass.FIDELITY_TRANSFORM,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=True,
    ),
    FindingCode.OBJECT_NAME_INVALID: _Row(
        CorrectionDeterminism.HEURISTIC,
        correction_type="RENAME_OBJECT",
        risk=CorrectionRiskClass.FIDELITY_TRANSFORM,
        reversibility=CorrectionReversibility.PARTIALLY_REVERSIBLE,
        auto_propose=True,  # naming is organizational -> review-flagged
    ),
    # --- REQUIRES_REVIEW (do NOT auto-execute; surface with a review boundary) ---
    FindingCode.MESH_INVALID_INDEX: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type=None,
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.PARTIALLY_REVERSIBLE,
        auto_propose=False,  # out-of-range/non-finite index -> human decision on the datum
    ),
    FindingCode.MESH_DUPLICATE_VERTEX: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="REPAIR_MERGE_VERTEX",
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.PARTIALLY_REVERSIBLE,
        auto_propose=False,  # merging vertices collapses real coincident geometry
    ),
    FindingCode.MESH_NON_MANIFOLD_EDGE: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="FLAG_NON_MANIFOLD_FOR_REVIEW",
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,
    ),
    FindingCode.MESH_SCALE_OUT_OF_RANGE: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="FLAG_SCALE_FOR_REVIEW",
        risk=CorrectionRiskClass.FIDELITY_RECONSTRUCTION,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,  # going out-of-envelope is real geometry; never auto-remap
    ),
    FindingCode.MESH_NORMAL_INCONSISTENT: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="REPAIR_NORMAL_CONSISTENCY",
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.PARTIALLY_REVERSIBLE,
        auto_propose=False,  # blocked: kernel defers per-face normals (adapter emits None)
    ),
    FindingCode.SCENE_ORIGIN_INVALID: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="FLAG_ORIGIN_FOR_REVIEW",
        risk=CorrectionRiskClass.FIDELITY_TRANSFORM,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,
    ),
    FindingCode.SCENE_BOUNDS_EMPTY: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type=None,
        risk=CorrectionRiskClass.FIDELITY_SAFE,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,  # empty scene has no geometry to fix
    ),
    FindingCode.OBJECT_HIERARCHY_INVALID: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="REPAIR_PARENT_REFERENCE",
        risk=CorrectionRiskClass.FIDELITY_TRANSFORM,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,  # dangling parent -> needs an intended target; cycles are unsafe
    ),
    FindingCode.OBJECT_BOUNDS_OVERLAP: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="FLAG_BOUNDS_OVERLAP_FOR_REVIEW",
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,
    ),
    FindingCode.OBJECT_COLLECTION_INVALID: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type="RESTRUCTURE_COLLECTION",
        risk=CorrectionRiskClass.FIDELITY_TRANSFORM,
        reversibility=CorrectionReversibility.REVERSIBLE,
        auto_propose=False,  # which allowed collection? -> ambiguous
    ),
    # --- UNSAFE_TO_AUTOMATE (never auto-propose; human decision required) ---
    FindingCode.OBJECT_ID_DUPLICATE: _Row(
        CorrectionDeterminism.UNSAFE_TO_AUTOMATE,
        correction_type=None,
        risk=CorrectionRiskClass.FIDELITY_RECONSTRUCTION,
        reversibility=CorrectionReversibility.NOT_REVERSIBLE,
        auto_propose=False,
    ),
    FindingCode.OBJECT_TRANSFORM_INVALID: _Row(
        CorrectionDeterminism.UNSAFE_TO_AUTOMATE,
        correction_type=None,
        risk=CorrectionRiskClass.FIDELITY_GEOMETRY,
        reversibility=CorrectionReversibility.NOT_REVERSIBLE,
        auto_propose=False,
    ),
    # --- OUT_OF_SCOPE (derived aggregate; the underlying findings are the real triggers) ---
    FindingCode.DIGITAL_TWIN_READINESS_FAILED: _Row(
        CorrectionDeterminism.REQUIRES_REVIEW,
        correction_type=None,
        risk=CorrectionRiskClass.FIDELITY_RECONSTRUCTION,
        reversibility=CorrectionReversibility.NOT_REVERSIBLE,
        auto_propose=False,
    ),
}


def _is_hierarchy_cycle(measured: object) -> bool:
    """Deterministically decide dangling-parent (REQUIRES_REVIEW) vs cycle (UNSAFE_TO_AUTOMATE).

    The kernel emits ``OBJECT_HIERARCHY_INVALID`` for BOTH a dangling parent and a cycle. The two
    are distinguished by the finding's ``measured`` payload:
    - dangling : ``measured = {"parent": <missing_parent_id>}``  (a dict with a ``parent`` key)
    - cycle    : everything else — a dict WITHOUT a ``parent`` key OR ``measured`` absent (the
                 kernel emits cycle findings with ``measured=None``; see
                 ``scene_health._collect_hierarchy_validity``).

    We detect a cycle by the ABSENCE of a ``parent`` key, so we never require a fabricated
    ``parent`` structure to recognize a cycle.
    """
    if type(measured) is not dict:
        return True  # measured=None (real kernel cycle shape) or any non-dict -> cycle
    return "parent" not in measured


def _row_for(finding_code: FindingCode, measured: object) -> _Row:
    """Deterministic row for a finding, dispatching the OBJECT_HIERARCHY_INVALID sub-cases."""
    if finding_code is FindingCode.OBJECT_HIERARCHY_INVALID:
        if not _is_hierarchy_cycle(measured):
            return _TABLE[FindingCode.OBJECT_HIERARCHY_INVALID]
        # cycle -> UNSAFE_TO_AUTOMATE
        return _Row(
            CorrectionDeterminism.UNSAFE_TO_AUTOMATE,
            correction_type=None,
            risk=CorrectionRiskClass.FIDELITY_RECONSTRUCTION,
            reversibility=CorrectionReversibility.NOT_REVERSIBLE,
            auto_propose=False,
        )
    try:
        return _TABLE[finding_code]
    except KeyError:
        raise KeyError(f"no correction mapping for finding code {finding_code!r}") from None


def classify(code: FindingCode, measured: object) -> tuple[str, Optional[str], str, str, bool]:
    """Return ``(determinism, correction_type, risk, reversibility, auto_propose)`` deterministically.

    ``measured`` is the finding's canonical ``measured`` value (a dict for hierarchy dispatch).
    """
    row = _row_for(code, measured)
    return (row.determinism.value, row.correction_type, row.risk.value,
            row.reversibility.value, row.auto_propose)