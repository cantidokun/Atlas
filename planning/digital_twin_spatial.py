"""Atlas-owned spatial primitives for the canonical Digital Twin.

These primitives deliberately describe Atlas space, not Blender or Unreal space.
Engine-specific coordinate conversion belongs at the tool-adapter boundary.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional


class DistanceUnit(str, Enum):
    METER = "m"
    CENTIMETER = "cm"
    MILLIMETER = "mm"


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.x, self.y, self.z)):
            raise ValueError("Vector3 components must be finite")


@dataclass(frozen=True)
class Quaternion:
    x: float
    y: float
    z: float
    w: float = 1.0

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.z, self.w)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Quaternion components must be finite")
        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude <= 0.0:
            raise ValueError("Quaternion must have non-zero magnitude")


@dataclass(frozen=True)
class CoordinateFrame:
    """Canonical Atlas coordinate frame metadata."""

    frame_id: str
    unit: DistanceUnit
    up_axis: str
    handedness: str
    origin: Vector3 = Vector3(0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise ValueError("frame_id must not be empty")
        if self.up_axis not in ("x", "y", "z"):
            raise ValueError("up_axis must be x, y, or z")
        if self.handedness not in ("left", "right"):
            raise ValueError("handedness must be left or right")


@dataclass(frozen=True)
class SpatialPose:
    """Atlas-space position and orientation for a Digital Twin entity."""

    frame_id: str
    position: Vector3
    rotation: Quaternion = Quaternion(0.0, 0.0, 0.0, 1.0)
    parent_entity_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise ValueError("frame_id must not be empty")
        if self.parent_entity_id is not None and not self.parent_entity_id.strip():
            raise ValueError("parent_entity_id must be non-empty when provided")
