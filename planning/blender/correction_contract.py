"""Canonical ``CorrectionProposal`` + ``CorrectionPlan`` value contracts (immutable, deterministic).

These are the language-neutral output of the cleanup/correction planner. They are consumed only by
a FUTURE controlled executor (never imported here) and re-serializable by a non-Python (C++)
consumer from their canonical JSON.

Invariants enforced at construction:

- All nested data is PASSED THROUGH the canonical-value grammar
  (:mod:`planning.blender.correction_values`): exact built-in scalars, ``tuple``/``dict`` with
  exact-``str`` keys, JSON-native. bpy objects, Python identities, callables, and arbitrary
  containers are structurally rejected.
- ``CorrectionProposal`` is frozen and sealed (``@dataclass(frozen=True, slots=True)``) so no
  caller can mutate it or sub-class it.
- ``CorrectionPlan.plan_id`` is the SHA-256 of the canonical plan JSON — the plan identity is
  derived from its own deterministic contents (self-committing), NOT from execution.
- The plan binds to its source: ``source_report_digest`` is mandatory and the proposal/plan
  constructors fail closed on unknown/missing report identity.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from planning.blender.correction_codes import (
    CorrectionDeterminism,
    CorrectionReversibility,
    CorrectionRiskClass,
    PlannerState,
)
from planning.blender.correction_values import (
    CorrectionInputError,
    _canonical_scalar,
    canonical_json_bytes,
    freeze_canonical,
    thaw_jsonable,
)
from planning.blender.finding_codes import FindingCode, FindingSeverity, severity_of


def _canon(obj: Any, label: str) -> Any:
    return _canonical_scalar(obj, label=label)


def _require_exact_str(value: Any, label: str) -> str:
    if type(value) is not str:
        raise CorrectionInputError(f"{label} must be an exact built-in str")
    return value


def _require_optional_str(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _require_exact_str(value, label)


def _resolve_finding_code(value: Any) -> FindingCode:
    """Resolve a finding code token, failing closed on unknown values."""
    if type(value) is FindingCode:
        return value
    if type(value) is not str:
        raise CorrectionInputError("finding_code must be a FindingCode or exact built-in str")
    try:
        return FindingCode(value)
    except ValueError:
        raise CorrectionInputError(f"unknown finding code: {value!r}") from None


def _resolve_determinism(value: Any) -> str:
    if type(value) is CorrectionDeterminism:
        return value.value
    if type(value) is not str:
        raise CorrectionInputError("determinism must be a CorrectionDeterminism or exact str")
    try:
        return CorrectionDeterminism(value).value
    except ValueError:
        raise CorrectionInputError(f"unknown determinism classification: {value!r}") from None


def _resolve_risk(value: Any) -> str:
    if type(value) is CorrectionRiskClass:
        return value.value
    if type(value) is not str:
        raise CorrectionInputError("risk must be a CorrectionRiskClass or exact str")
    try:
        return CorrectionRiskClass(value).value
    except ValueError:
        raise CorrectionInputError(f"unknown risk class: {value!r}") from None


def _resolve_reversibility(value: Any) -> str:
    if type(value) is CorrectionReversibility:
        return value.value
    if type(value) is not str:
        raise CorrectionInputError("reversibility must be a CorrectionReversibility or exact str")
    try:
        return CorrectionReversibility(value).value
    except ValueError:
        raise CorrectionInputError(f"unknown reversibility: {value!r}") from None


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    """One immutable, self-contained, deterministic correction proposal (proposal ONLY)."""

    correction_id: str
    finding_code: str
    object_id: Optional[str]
    mesh_id: Optional[str]
    correction_type: str
    parameters: Mapping[str, Any]
    rationale: str
    preconditions: Tuple[Any, ...]
    expected_postcondition: Mapping[str, Any]
    risk: str
    severity: str
    reversibility: str
    dependencies: Tuple[str, ...]
    determinism: str
    requires_human_review: bool
    out_of_scope: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "correction_id", _require_exact_str(self.correction_id, "correction_id"))
        object.__setattr__(self, "finding_code", _resolve_finding_code(self.finding_code).value)
        object.__setattr__(self, "object_id", _require_optional_str(self.object_id, "object_id"))
        object.__setattr__(self, "mesh_id", _require_optional_str(self.mesh_id, "mesh_id"))
        object.__setattr__(self, "correction_type", _require_exact_str(self.correction_type, "correction_type"))
        object.__setattr__(self, "rationale", _require_exact_str(self.rationale, "rationale"))
        object.__setattr__(self, "risk", _resolve_risk(self.risk))
        object.__setattr__(self, "severity", severity_of(_resolve_finding_code(self.finding_code)).value)
        object.__setattr__(self, "reversibility", _resolve_reversibility(self.reversibility))
        object.__setattr__(self, "determinism", _resolve_determinism(self.determinism))
        if type(self.requires_human_review) is not bool:
            raise CorrectionInputError("requires_human_review must be an exact built-in bool")
        if type(self.out_of_scope) is not bool:
            raise CorrectionInputError("out_of_scope must be an exact built-in bool")
        # Canonicalize nested data (parameters/preconditions/postcondition), EXACT-TYPE guarded,
        # then DEEP-FREEZE so no caller-held mapping/list can mutate canonical content after
        # construction (D1: plan.plan_id must stay == digest of the current canonical content).
        object.__setattr__(
            self, "parameters",
            freeze_canonical(_canon(self.parameters, "parameters"), label="parameters"),
        )
        object.__setattr__(
            self, "preconditions",
            freeze_canonical(_canon(self.preconditions, "preconditions"), label="preconditions"),
        )
        object.__setattr__(
            self, "expected_postcondition",
            freeze_canonical(
                _canon(self.expected_postcondition, "expected_postcondition"),
                label="expected_postcondition",
            ),
        )
        # Dependencies are a deterministic ordered tuple of exact correction_ids (no self-dep).
        deps = _canon(self.dependencies, "dependencies")
        object.__setattr__(self, "dependencies", tuple(_require_exact_str(d, "dependency") for d in deps))
        if self.correction_id in self.dependencies:
            raise CorrectionInputError(f"correction {self.correction_id!r} must not depend on itself")

    def to_json_compatible(self) -> dict:
        return {
            "correction_id": self.correction_id,
            "finding_code": self.finding_code,
            "object_id": self.object_id,
            "mesh_id": self.mesh_id,
            "correction_type": self.correction_type,
            "parameters": thaw_jsonable(self.parameters),
            "rationale": self.rationale,
            "preconditions": thaw_jsonable(self.preconditions),
            "expected_postcondition": thaw_jsonable(self.expected_postcondition),
            "risk": self.risk,
            "severity": self.severity,
            "reversibility": self.reversibility,
            "dependencies": list(self.dependencies),
            "determinism": self.determinism,
            "requires_human_review": self.requires_human_review,
            "out_of_scope": self.out_of_scope,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_json_compatible(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def preview(self) -> dict:
        """Deterministic conceptual preview (informational only; never executes anything)."""
        return {
            "correction_id": self.correction_id,
            "correction_type": self.correction_type,
            "object_id": self.object_id,
            "mesh_id": self.mesh_id,
            "finding_code": self.finding_code,
            "rationale": self.rationale,
            "risk": self.risk,
            "determinism": self.determinism,
            "expected_postcondition": thaw_jsonable(self.expected_postcondition),
        }


@dataclass(frozen=True, slots=True)
class CorrectionPlan:
    """Deterministic plan produced by the cleanup/correction planner (proposal ONLY)."""

    plan_id: str
    source_report_digest: str
    source_revision_id: Optional[str]
    planner_version: str
    profile: Mapping[str, Any]
    corrections: Tuple[CorrectionProposal, ...]
    dependencies: Tuple[Tuple[str, str], ...]
    summary_metrics: Mapping[str, Any]
    state: str
    planning_errors: Tuple[Any, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_report_digest", _require_exact_str(self.source_report_digest, "source_report_digest"))
        object.__setattr__(self, "source_revision_id", _require_optional_str(self.source_revision_id, "source_revision_id"))
        object.__setattr__(self, "planner_version", _require_exact_str(self.planner_version, "planner_version"))
        object.__setattr__(self, "state", _resolve_state(self.state))
        object.__setattr__(self, "profile", freeze_canonical(_canon(self.profile, "profile"), label="profile"))
        object.__setattr__(self, "summary_metrics", freeze_canonical(_canon(self.summary_metrics, "summary_metrics"), label="summary_metrics"))
        object.__setattr__(self, "planning_errors", freeze_canonical(_canon(self.planning_errors, "planning_errors"), label="planning_errors"))
        # corrections must be CorrectionProposal instances (already canonical) in a stable tuple
        if not isinstance(self.corrections, tuple) or not all(
            type(c) is CorrectionProposal for c in self.corrections
        ):
            raise CorrectionInputError("corrections must be a tuple of CorrectionProposal")
        # dependency edges: tuple of exact (from, to) correction_id pairs
        edges = _canon(self.dependencies, "dependencies")
        object.__setattr__(self, "dependencies", tuple(
            (_require_exact_str(f, "dependency.from"), _require_exact_str(t, "dependency.to"))
            for (f, t) in edges
        ))
        ids = {c.correction_id for c in self.corrections}
        for (f, t) in self.dependencies:
            if f not in ids or t not in ids:
                raise CorrectionInputError(f"dependency edge references unknown correction: {f!r}->{t!r}")
        # plan_id must equal the digest of the canonical plan contents (self-committing).
        object.__setattr__(
            self, "plan_id",
            _require_exact_str(self.plan_id, "plan_id") if self.plan_id else self._compute_plan_id(),
        )
        if self.plan_id != self._compute_plan_id():
            raise CorrectionInputError("plan_id does not match the canonical plan contents")

    def _compute_plan_id(self) -> str:
        body = {
            "source_report_digest": self.source_report_digest,
            "source_revision_id": self.source_revision_id,
            "planner_version": self.planner_version,
            "profile": thaw_jsonable(self.profile),
            "state": self.state,
            "corrections": [c.to_json_compatible() for c in self.corrections],
            "dependencies": [list(e) for e in self.dependencies],
            "summary_metrics": thaw_jsonable(self.summary_metrics),
            "planning_errors": thaw_jsonable(self.planning_errors),
        }
        return hashlib.sha256(canonical_json_bytes(body)).hexdigest()

    def to_json_compatible(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "source_report_digest": self.source_report_digest,
            "source_revision_id": self.source_revision_id,
            "planner_version": self.planner_version,
            "profile": thaw_jsonable(self.profile),
            "state": self.state,
            "corrections": [c.to_json_compatible() for c in self.corrections],
            "dependencies": [list(e) for e in self.dependencies],
            "summary_metrics": thaw_jsonable(self.summary_metrics),
            "planning_errors": thaw_jsonable(self.planning_errors),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_json_compatible(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def preview(self) -> dict:
        """Deterministic plan-level conceptual preview (informational only)."""
        return {
            "plan_id": self.plan_id,
            "state": self.state,
            "source_report_digest": self.source_report_digest,
            "proposals": [c.preview() for c in self.corrections],
            "dependencies": [list(e) for e in self.dependencies],
        }


def _resolve_state(value: Any) -> str:
    if type(value) is PlannerState:
        return value.value
    if type(value) is not str:
        raise CorrectionInputError("state must be a PlannerState or exact built-in str")
    try:
        return PlannerState(value).value
    except ValueError:
        raise CorrectionInputError(f"unknown planner state: {value!r}") from None