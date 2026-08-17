"""Engine-neutral Unreal Agent capability declarations.

This module contains no Unreal Engine dependency. It defines the structured
capability vocabulary that the eventual Unreal adapter will implement behind
Atlas's existing authorization and verification boundaries.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class UnrealCapability(str, Enum):
    WORLD_INSPECTION = "world_inspection"
    ENTITY_INSPECTION = "entity_inspection"
    ASSET_INSPECTION = "asset_inspection"
    ACTOR_MODIFICATION = "actor_modification"
    MATERIAL_MODIFICATION = "material_modification"
    NIAGARA_MODIFICATION = "niagara_modification"
    BLUEPRINT_MODIFICATION = "blueprint_modification"
    SEQUENCER_MODIFICATION = "sequencer_modification"
    RENDER_TEST = "render_test"


@dataclass(frozen=True)
class UnrealCapabilitySpec:
    capability: UnrealCapability
    read_only: bool
    requires_authorization: bool
    requires_independent_verification: bool


DEFAULT_CAPABILITIES: Tuple[UnrealCapabilitySpec, ...] = tuple(
    UnrealCapabilitySpec(
        capability=capability,
        read_only=capability in {
            UnrealCapability.WORLD_INSPECTION,
            UnrealCapability.ENTITY_INSPECTION,
            UnrealCapability.ASSET_INSPECTION,
        },
        requires_authorization=capability not in {
            UnrealCapability.WORLD_INSPECTION,
            UnrealCapability.ENTITY_INSPECTION,
            UnrealCapability.ASSET_INSPECTION,
        },
        requires_independent_verification=True,
    )
    for capability in UnrealCapability
)


def capability_spec(capability: UnrealCapability) -> UnrealCapabilitySpec:
    """Return the immutable policy metadata for one Unreal capability."""
    for spec in DEFAULT_CAPABILITIES:
        if spec.capability is capability:
            return spec
    raise ValueError(f"unknown Unreal capability: {capability}")
