"""Auditable lifecycle records for Atlas planner/executor runs."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AuditTrail:
    """Append-only in-memory audit record for one Atlas task lifecycle."""

    events: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, stage: str, status: str, **details: Any) -> Dict[str, Any]:
        event = {"index": len(self.events), "stage": stage, "status": status}
        event.update(details)
        self.events.append(event)
        return event

    def record_qwen_proposal(self, raw: str, attempt: int, accepted: bool, reason: Optional[str] = None) -> None:
        details: Dict[str, Any] = {"attempt": attempt, "raw": raw, "accepted": accepted}
        if reason:
            details["reason"] = reason
        self.record("qwen_proposal", "accepted" if accepted else "rejected", **details)

    def record_evidence(self, request: Dict[str, Any], result: Dict[str, Any]) -> None:
        self.record("evidence", "verified", request=request, result=result)

    def record_authorization(self, authorized: bool, **details: Any) -> None:
        self.record("authorization", "authorized" if authorized else "refused", **details)

    def record_action(self, index: int, action: Dict[str, Any], result: Dict[str, Any], success: bool) -> None:
        self.record("execution", "success" if success else "failure", index=index, action=action, result=result)

    def record_verification(self, result: Dict[str, Any], success: bool) -> None:
        self.record("verification", "success" if success else "failure", result=result)

    def snapshot(self) -> Dict[str, Any]:
        return {"event_count": len(self.events), "events": list(self.events)}
