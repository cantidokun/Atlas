"""Deterministic task/risk classification for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §4.1, §4.3 (rules
R1–R7).

Rules frozen here:
- R1: each dimension scored 0–3 by the classifier; unknown/missing -> 3 and
  data_complete=False.
- R3: max_dim drives raw tier (0→L0,1→L1,2→L2,3→L3).
- R4: hard-selector dimensions at score >=2 force L2, >=3 force L3.
- R5: multiple hard selectors -> the maximum forced tier.
- R6: any unknown signal -> data_unknown=True, final tier = L3.
- R7: final tier = max(raw tier, hard floor, unknown floor).

Model self-confidence is NEVER an input.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from planning.m11_router.constants import TASK_CLASSES
from planning.m11_router.model_profile import ModelTier, tier_index, tier_max


# Hard-selector dimensions (design §4.3 R4). score>=2 -> L2, score>=3 -> L3.
HARD_SELECTOR_DIMENSIONS: frozenset[str] = frozenset({
    "security_sensitivity",
    "authorization_identity",
    "cryptography",
    "recovery_statefulness",
    "concurrency",
    "cross_process",
    "provenance_receipt",
})

# All risk dimensions with a fixed order (design §4.2).
RISK_DIMENSIONS: tuple[str, ...] = (
    "code_complexity",
    "security_sensitivity",
    "authorization_identity",
    "cryptography",
    "concurrency",
    "cross_process",
    "recovery_statefulness",
    "provenance_receipt",
    "external_side_effects",
    "production_destructive",
    "difficulty_of_verification",
)

# Task classes that carry an inherent floor tier regardless of dimension score.
TASK_CLASS_HARD_FLOOR: dict[str, ModelTier] = {
    "contract": ModelTier.L2,
    "recovery": ModelTier.L2,
    "security-crypto": ModelTier.L3,
    "concurrency": ModelTier.L2,
    "adapter": ModelTier.L1,
    "api-boundary": ModelTier.L1,
}


@dataclass(frozen=True)
class RiskAssessment:
    """Immutable result of a deterministic risk classification."""

    task_id: str
    task_classes: frozenset[str] = frozenset()
    dimension_scores: Mapping[str, int] = field(default_factory=dict)
    unknown_signals: frozenset[str] = frozenset()
    data_complete: bool = True
    max_dim: int = 0
    raw_tier: ModelTier = ModelTier.L0
    hard_tier: ModelTier = ModelTier.L0
    final_tier: ModelTier = ModelTier.L0
    reasons: tuple[str, ...] = ()

    @property
    def data_unknown(self) -> bool:
        return not self.data_complete or bool(self.unknown_signals)


_RAW_TIER_BY_MAX = {0: ModelTier.L0, 1: ModelTier.L1, 2: ModelTier.L2, 3: ModelTier.L3}
_RAW_NAME = {0: "L0", 1: "L1", 2: "L2", 3: "L3"}


class InvalidRiskInput(ValueError):
    """Raised when a required risk signal is structurally invalid."""


def _normalize_scores(dimension_scores: Optional[Mapping[str, int]]) -> tuple[dict[str, int], tuple[str, ...]]:
    dimensions = RISK_DIMENSIONS
    d: dict[str, int] = {}
    unknown: list[str] = []
    if dimension_scores is None:
        dimension_scores = {}
    if not isinstance(dimension_scores, Mapping):
        raise InvalidRiskInput("dimension_scores must be a mapping")
    for dim in dimensions:
        v = dimension_scores.get(dim)
        if v is None:
            unknown.append(dim)
            d[dim] = 3  # R1/R6 fail-closed
            continue
        if isinstance(v, bool) or not isinstance(v, int) or not (0 <= v <= 3):
            raise InvalidRiskInput(f"dimension {dim} must be an int in 0..3")
        d[dim] = v
    return d, tuple(unknown)


def classify_task(
    task_id: str,
    dimension_scores: Mapping[str, int],
    *,
    task_classes: Optional[Sequence[str]] = None,
    confidence: Optional[Any] = None,  # documented, ALWAYS ignored
    hard_file_tokens: Optional[Sequence[str]] = None,
) -> RiskAssessment:
    """Deterministically classify a task and derive its final model tier.

    ``confidence`` is accepted (and ignored) purely to document that model
    self-reported confidence can never influence the result.
    ``hard_file_tokens`` optionally lists touched hard-selector file/field
    markers (design R4 / §7): any non-empty marker raises the hard floor to at
    least L2 (L3 if the token matches a critical security marker).
    """
    scores, unknown = _normalize_scores(dimension_scores)
    if task_classes is None:
        task_classes = ("doc",)
    classes = frozenset(
        str(tc).strip() for tc in task_classes if str(tc).strip()
    ) or frozenset({"doc"})

    max_dim = max(scores.values()) if scores else 0

    # R3: raw tier from worst single dimension.
    raw_tier = _RAW_TIER_BY_MAX[max_dim]

    # R4/R5: hard-selector floors (max across active hard dimensions + class floors).
    hard_floors: list[ModelTier] = [ModelTier.L0]
    for dim in HARD_SELECTOR_DIMENSIONS:
        s = scores.get(dim)
        if s is not None:
            if s >= 3:
                hard_floors.append(ModelTier.L3)
            elif s >= 2:
                hard_floors.append(ModelTier.L2)
    for tc in classes:
        floor = TASK_CLASS_HARD_FLOOR.get(tc)
        if floor is not None:
            hard_floors.append(floor)
    # R4: touched hard-selector file/field markers raise the floor even when
    # the raw score is low. Critical security markers force L3; all hard markers
    # force at least L2.
    for tok in (hard_file_tokens or ()):
        tok_norm = str(tok).strip().lower()
        if not tok_norm:
            continue
        hard_floors.append(ModelTier.L2)
        _CRITICAL_MARKERS = ("crypto", "hmac", "nonce", "attestation", "auth", "authorization", "receipt", "key", "secret")
        if any(m in tok_norm for m in _CRITICAL_MARKERS):
            hard_floors.append(ModelTier.L3)
    hard_tier = max(hard_floors, key=tier_index)

    # R6: unknown signal -> fail closed to L3.
    data_complete = not bool(unknown)
    unknown_floor = ModelTier.L3 if not data_complete else ModelTier.L0

    # R7: final tier = max(raw, hard, unknown); monotonic (never decreases by construction).
    final_tier = max([raw_tier, hard_tier, unknown_floor], key=tier_index)

    reasons: list[str] = [f"max_dim={max_dim} (raw={_RAW_NAME[max_dim]})"]
    if hard_tier != ModelTier.L0:
        reasons.append(f"hard_selector_floor={hard_tier.value}")
    if not data_complete:
        reasons.append(f"unknown_signal={sorted(unknown)}")
    reasons.append(f"final_tier={final_tier.value}")

    return RiskAssessment(
        task_id=task_id,
        task_classes=classes,
        dimension_scores=dict(scores),
        unknown_signals=frozenset(unknown),
        data_complete=data_complete,
        max_dim=max_dim,
        raw_tier=raw_tier,
        hard_tier=hard_tier,
        final_tier=final_tier,
        reasons=tuple(reasons),
    )


def task_digest(task_text: str) -> str:
    """Return a stable SHA-256 task_id derived from canonical task text."""
    return hashlib.sha256(task_text.encode("utf-8")).hexdigest()


def tier_min(a: ModelTier, b: ModelTier) -> ModelTier:
    """Lower (less capable) of two tiers."""
    return a if tier_index(a) <= tier_index(b) else b