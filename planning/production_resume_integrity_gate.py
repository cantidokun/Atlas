"""Fail-closed integrity gate for durable production resume.

A persisted production checkpoint is only resumable when its plan identity and
Digital Twin revision still match the currently requested production state.
This module performs validation only; it does not execute or authorize work.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionResumeCheckpoint:
    sequence_id: str
    plan_id: str
    digital_twin_revision: str
    completed_operation_index: int

    def __post_init__(self) -> None:
        if not self.sequence_id.strip():
            raise ValueError("sequence_id must not be empty")
        if not self.plan_id.strip():
            raise ValueError("plan_id must not be empty")
        if not self.digital_twin_revision.strip():
            raise ValueError("digital_twin_revision must not be empty")
        if isinstance(self.completed_operation_index, bool) or not isinstance(
            self.completed_operation_index, int
        ):
            raise TypeError("completed_operation_index must be an integer")
        if self.completed_operation_index < -1:
            raise ValueError("completed_operation_index must be >= -1")


@dataclass(frozen=True)
class ProductionResumeRequest:
    sequence_id: str
    plan_id: str
    digital_twin_revision: str

    def __post_init__(self) -> None:
        if not self.sequence_id.strip():
            raise ValueError("sequence_id must not be empty")
        if not self.plan_id.strip():
            raise ValueError("plan_id must not be empty")
        if not self.digital_twin_revision.strip():
            raise ValueError("digital_twin_revision must not be empty")


def validate_production_resume(
    checkpoint: ProductionResumeCheckpoint,
    request: ProductionResumeRequest,
) -> None:
    """Raise when a durable checkpoint cannot safely resume.

    All identity dimensions are checked before execution can be considered.
    """
    if not isinstance(checkpoint, ProductionResumeCheckpoint):
        raise TypeError("checkpoint must be a ProductionResumeCheckpoint")
    if not isinstance(request, ProductionResumeRequest):
        raise TypeError("request must be a ProductionResumeRequest")

    if checkpoint.sequence_id != request.sequence_id:
        raise ValueError("checkpoint sequence_id does not match resume request")
    if checkpoint.plan_id != request.plan_id:
        raise ValueError("checkpoint plan_id does not match resume request")
    if checkpoint.digital_twin_revision != request.digital_twin_revision:
        raise ValueError("checkpoint Digital Twin revision does not match resume request")
