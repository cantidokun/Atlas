"""Serializable escalation packet for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §10.

The packet carries everything a higher-tier model needs to continue without
reconstructing the investigation from scratch — but it MUST NOT carry any
credential-bearing data. Raw prompts are not stored unless they pass the same
privacy allow-list as telemetry.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from planning.m11_router.evidence_gate import EvidenceGateResult
from planning.m11_router.model_profile import ModelTier
from planning.m11_router.risk import RiskAssessment
from planning.m11_router.routing import ModelSelection


@dataclass(frozen=True)
class EscalationPacket:
    """Immutable, serializable escalation packet (design §10)."""

    task_id: str
    task_statement: str
    risk: Optional[RiskAssessment] = None
    current_tier: Optional[ModelTier] = None
    selection: Optional[ModelSelection] = None
    prior_result: Optional[str] = None
    evidence: List[EvidenceGateResult] = field(default_factory=list)
    failures: Tuple[str, ...] = ()
    corrections: Tuple[str, ...] = ()
    contract_references: Tuple[str, ...] = ()
    unresolved_questions: Tuple[str, ...] = ()
    attempt_ids: Tuple[str, ...] = ()
    escalation_ids: Tuple[str, ...] = ()

    @property
    def from_attempt(self) -> Optional[str]:
        return self.attempt_ids[-1] if self.attempt_ids else None

    @property
    def human_summary(self) -> str:
        lines = [
            f"task_id={self.task_id}",
            f"current_tier={self.current_tier.value if self.current_tier else None}",
            f"failures={len(self.failures)} corrections={len(self.corrections)}",
            f"evidence_records={len(self.evidence)}",
        ]
        if self.risk is not None:
            lines.append(f"risk.final_tier={self.risk.final_tier.value}")
        return "; ".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EscalationPacket":
        # Rebuild the structured sub-objects from serialized dicts (best-effort;
        # a lossy serialization of a nested dataclass is acceptable: the packet
        # is a summary, not the authoritative record).
        risk = raw.get("risk")
        if isinstance(risk, dict):
            risk = RiskAssessment(
                task_id=risk.get("task_id") or "",
                task_classes=frozenset(risk.get("task_classes") or ()),
                dimension_scores=dict(risk.get("dimension_scores") or {}),
                unknown_signals=frozenset(risk.get("unknown_signals") or ()),
                data_complete=bool(risk.get("data_complete", True)),
                max_dim=int(risk.get("max_dim", 0)),
                raw_tier=risk.get("raw_tier") or ModelTier.L0,
                hard_tier=risk.get("hard_tier") or ModelTier.L0,
                final_tier=risk.get("final_tier") or ModelTier.L0,
                reasons=tuple(risk.get("reasons") or ()),
            )
        evidence = []
        for g in raw.get("evidence") or ():
            if isinstance(g, dict):
                evidence.append(EvidenceGateResult(outcome=g.get("outcome", "FAILED")))
            else:
                evidence.append(g)
        return cls(
            task_id=raw.get("task_id"),
            task_statement=raw.get("task_statement") or "",
            risk=risk,
            current_tier=raw.get("current_tier"),
            selection=raw.get("selection"),
            prior_result=raw.get("prior_result"),
            evidence=evidence,
            failures=tuple(raw.get("failures") or ()),
            corrections=tuple(raw.get("corrections") or ()),
            contract_references=tuple(raw.get("contract_references") or ()),
            unresolved_questions=tuple(raw.get("unresolved_questions") or ()),
            attempt_ids=tuple(raw.get("attempt_ids") or ()),
            escalation_ids=tuple(raw.get("escalation_ids") or ()),
        )

    @classmethod
    def build(
        cls,
        *,
        task_id: str,
        task_statement: str,
        risk: Optional[RiskAssessment] = None,
        current_tier: Optional[ModelTier] = None,
        selection: Optional[ModelSelection] = None,
        prior_result: Optional[str] = None,
        evidence: Optional[List[EvidenceGateResult]] = None,
        failures: Optional[List[str]] = None,
        corrections: Optional[List[str]] = None,
        contract_references: Optional[List[str]] = None,
        unresolved_questions: Optional[List[str]] = None,
        attempt_ids: Optional[List[str]] = None,
        escalation_ids: Optional[List[str]] = None,
    ) -> "EscalationPacket":
        return cls(
            task_id=task_id,
            task_statement=task_statement,
            risk=risk,
            current_tier=current_tier,
            selection=selection,
            prior_result=prior_result,
            evidence=list(evidence or ()),
            failures=tuple(failures or ()),
            corrections=tuple(corrections or ()),
            contract_references=tuple(contract_references or ()),
            unresolved_questions=tuple(unresolved_questions or ()),
            attempt_ids=tuple(attempt_ids or ()),
            escalation_ids=tuple(escalation_ids or ()),
        )


