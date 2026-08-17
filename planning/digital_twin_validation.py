"""Attribute-level validation state for Atlas Digital Twin entities."""

from dataclasses import dataclass
from enum import Enum


class ValidationState(str, Enum):
    RAW = "raw"
    INGESTED = "ingested"
    ANALYZED = "analyzed"
    CORRECTED = "corrected"
    VALIDATED = "validated"
    PRODUCTION_READY = "production_ready"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True)
class ValidationRecord:
    entity_id: str
    attribute: str
    state: ValidationState
    evidence_id: str

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.attribute.strip() or not self.evidence_id.strip():
            raise ValueError("validation identity fields must not be empty")
