"""Canonical and production appearance metadata for Atlas entities."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AppearanceKind(str, Enum):
    CANONICAL = "canonical"
    PRODUCTION = "production"


@dataclass(frozen=True)
class AppearanceReference:
    entity_id: str
    appearance_id: str
    kind: AppearanceKind
    material_id: Optional[str] = None
    texture_set_id: Optional[str] = None
    variant_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.appearance_id.strip():
            raise ValueError("appearance identity fields must not be empty")
        if self.kind is AppearanceKind.CANONICAL and self.variant_id is not None:
            raise ValueError("canonical appearance cannot reference a production variant")
