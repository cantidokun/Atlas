"""Deterministic classification vocabulary for the Cleanup/Correction planner.

These are **deterministic classifications**, NOT an ML confidence score. Each is a stable,
language-neutral enum token derived from (finding code + available data + profile), never a model
opinion. The tokens are serialized by their ``value`` string.

- ``CorrectionRiskClass`` — source-fidelity risk of a proposed correction (section 8 of the
  design).
- ``CorrectionDeterminism`` — how the proposal is classified for automatic-vs-review dispatch.
- ``CorrectionReversibility`` — declared reversibility for human/executor awareness (NOT an
  undo/rollback authority).
- ``PlannerState`` — the overall deterministic planner state (section 15 of the design).
"""
from __future__ import annotations

from enum import Enum, unique


@unique
class CorrectionRiskClass(str, Enum):
    """Deterministic source-fidelity risk of a proposed correction (closed set)."""

    FIDELITY_SAFE = "FIDELITY_SAFE"
    FIDELITY_TRANSFORM = "FIDELITY_TRANSFORM"
    FIDELITY_GEOMETRY = "FIDELITY_GEOMETRY"
    FIDELITY_RECONSTRUCTION = "FIDELITY_RECONSTRUCTION"


@unique
class CorrectionDeterminism(str, Enum):
    """How a proposal is dispatched: automatic vs review vs unsafe (closed, deterministic)."""

    DETERMINISTIC = "DETERMINISTIC"
    HEURISTIC = "HEURISTIC"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    UNSAFE_TO_AUTOMATE = "UNSAFE_TO_AUTOMATE"


@unique
class CorrectionReversibility(str, Enum):
    """Declared reversibility of a proposed correction (informational; not a rollback
    authority — the future executor owns any undo/rollback, which is OUT OF SCOPE here)."""

    REVERSIBLE = "reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    NOT_REVERSIBLE = "not_reversible"


@unique
class PlannerState(str, Enum):
    """Overall deterministic planner state (distinct from the kernel ``ValidationState``)."""

    NO_CORRECTIONS = "NO_CORRECTIONS"
    AUTO_PROPOSALS_AVAILABLE = "AUTO_PROPOSALS_AVAILABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSAFE_TO_AUTOMATE = "UNSAFE_TO_AUTOMATE"
    PLANNING_ERROR = "PLANNING_ERROR"