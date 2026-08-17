"""Provenance primitives for tracing Atlas Digital Twin state."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProvenanceSource(str, Enum):
    PHOTOGRAMMETRY = "photogrammetry"
    FIELD_MEASUREMENT = "field_measurement"
    ATLAS_INFERENCE = "atlas_inference"
    BLENDER = "blender"
    UNREAL = "unreal"
    HUMAN = "human"
    OTHER = "other"


@dataclass(frozen=True)
class ProvenanceRecord:
    entity_id: str
    source: ProvenanceSource
    source_id: str
    operation: str
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.source_id.strip() or not self.operation.strip():
            raise ValueError("provenance identity fields must not be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("provenance confidence must be between 0 and 1")
