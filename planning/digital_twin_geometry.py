"""Engine-independent geometry primitives for Atlas Digital Twins."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from planning.digital_twin_spatial import Vector3


class GeometryKind(str, Enum):
    MESH = "mesh"
    POINT = "point"
    CURVE = "curve"
    VOLUME = "volume"
    OTHER = "other"


@dataclass(frozen=True)
class BoundingBox:
    minimum: Vector3
    maximum: Vector3

    def __post_init__(self) -> None:
        if self.minimum.x > self.maximum.x or self.minimum.y > self.maximum.y or self.minimum.z > self.maximum.z:
            raise ValueError("bounding box minimum must not exceed maximum")


@dataclass(frozen=True)
class GeometryReference:
    entity_id: str
    geometry_id: str
    kind: GeometryKind
    representation_id: str
    bounds: Optional[BoundingBox] = None

    def __post_init__(self) -> None:
        for name, value in (("entity_id", self.entity_id), ("geometry_id", self.geometry_id), ("representation_id", self.representation_id)):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
