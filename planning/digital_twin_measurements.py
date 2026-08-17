"""Physical measurements and tolerance-aware requirements for Atlas."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MeasurementStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Measurement:
    entity_id: str
    key: str
    value: float
    unit: str
    expected: Optional[float] = None
    tolerance: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.key.strip() or not self.unit.strip():
            raise ValueError("measurement identity fields must not be empty")
        if self.tolerance is not None and self.tolerance < 0:
            raise ValueError("measurement tolerance must be non-negative")

    def status(self) -> MeasurementStatus:
        if self.expected is None or self.tolerance is None:
            return MeasurementStatus.UNVERIFIED
        return (
            MeasurementStatus.PASS
            if abs(self.value - self.expected) <= self.tolerance
            else MeasurementStatus.FAIL
        )
