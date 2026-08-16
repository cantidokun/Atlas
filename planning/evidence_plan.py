"""Generic evidence-plan primitives for Atlas."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class EvidenceRequest:
    tool: str
    arguments: Dict[str, Any]
    name: str = ""

@dataclass
class EvidencePlan:
    requests: List[EvidenceRequest]
    completed: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    failed: Optional[Dict[str, Any]] = None
    current_index: int = 0

    @property
    def complete(self) -> bool:
        return self.failed is None and self.current_index >= len(self.requests)

    @property
    def blocked(self) -> bool:
        return self.failed is not None

    @property
    def next_request(self) -> Optional[EvidenceRequest]:
        if self.complete or self.blocked:
            return None
        return self.requests[self.current_index]

    def record_result(self, result: Dict[str, Any], success: bool, reused: bool = False) -> None:
        if self.complete:
            raise RuntimeError("Evidence plan is already complete.")
        if self.blocked:
            raise RuntimeError("Evidence plan is blocked by a previous failure.")
        request = self.requests[self.current_index]
        entry = {"index": self.current_index, "name": request.name or request.tool, "tool": request.tool, "arguments": request.arguments, "result": result, "success": bool(success), "reused": bool(reused)}
        if reused:
            self.skipped.append(entry)
        if success:
            self.completed.append(entry)
            self.current_index += 1
        else:
            self.failed = entry

    def snapshot(self) -> Dict[str, Any]:
        next_request = self.next_request
        return {
            "current_index": self.current_index,
            "total_requests": len(self.requests),
            "complete": self.complete,
            "blocked": self.blocked,
            "next_request": ({"name": next_request.name or next_request.tool, "tool": next_request.tool, "arguments": next_request.arguments} if next_request is not None else None),
            "completed": list(self.completed),
            "skipped": list(self.skipped),
            "failure": self.failed,
        }
