"""Canonical, production-variant, and shot-state boundaries."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VariantKind(str, Enum):
    CANONICAL = "canonical"
    PRODUCTION = "production"
    SHOT = "shot"
    RENDER = "render"


@dataclass(frozen=True)
class DigitalTwinVariant:
    twin_id: str
    variant_id: str
    kind: VariantKind
    source_revision_id: str
    parent_variant_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (("twin_id", self.twin_id), ("variant_id", self.variant_id), ("source_revision_id", self.source_revision_id)):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.kind is VariantKind.CANONICAL and self.parent_variant_id is not None:
            raise ValueError("canonical variant cannot have a parent variant")
        if self.parent_variant_id == self.variant_id:
            raise ValueError("variant cannot parent itself")


def create_production_variant(
    twin_id: str,
    variant_id: str,
    source_revision_id: str,
    kind: VariantKind = VariantKind.PRODUCTION,
    parent_variant_id: Optional[str] = None,
) -> DigitalTwinVariant:
    if kind is VariantKind.CANONICAL:
        raise ValueError("use canonical revisions for canonical state")
    return DigitalTwinVariant(twin_id, variant_id, kind, source_revision_id, parent_variant_id)
