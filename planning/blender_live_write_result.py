"""Explicit outcome for the final controlled Blender write gate."""
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from planning.blender_execution_receipt import BlenderExecutionReceipt


@dataclass(frozen=True)
class BlenderLiveWriteOutcome:
    status: str
    receipt: Optional[BlenderExecutionReceipt]
    verification: Mapping[str, Any]
    reason: Optional[str] = None

    @classmethod
    def verified(cls, receipt: BlenderExecutionReceipt, verification: Mapping[str, Any]):
        if not isinstance(receipt, BlenderExecutionReceipt):
            raise TypeError("verified outcome requires a BlenderExecutionReceipt")
        return cls("VERIFIED", receipt, dict(verification), None)

    @classmethod
    def blocked(cls, verification: Mapping[str, Any], reason: str):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("blocked outcome requires a reason")
        return cls("BLOCKED", None, dict(verification), reason)

    @property
    def is_verified(self) -> bool:
        return self.status == "VERIFIED" and self.receipt is not None
