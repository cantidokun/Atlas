"""Declarative capability and argument-schema registry for the Atlas Unreal Agent.

Capabilities describe what the Unreal domain can propose. They do not grant
execution authority; Atlas authorization and the adapter remain authoritative.
"""

from dataclasses import dataclass
from typing import FrozenSet, Mapping, Tuple

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind


@dataclass(frozen=True)
class UnrealCapabilitySpec:
    capability: UnrealCapability
    allowed_kinds: FrozenSet[UnrealOperationKind]
    required_evidence: Tuple[str, ...]
    description: str
    argument_keys: FrozenSet[str] = frozenset({"entity_ids"})


DEFAULT_UNREAL_CAPABILITIES = (
    UnrealCapabilitySpec(
        UnrealCapability.INSPECT_WORLD,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}),
        ("world_state",),
        "Inspect or verify Unreal world/level state.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.INSPECT_ACTOR,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}),
        ("actor_state",),
        "Inspect or verify an Unreal Actor representation.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.MODIFY_ACTOR,
        frozenset({UnrealOperationKind.WRITE}),
        ("actor_state",),
        "Modify an already-authorized Unreal Actor representation.",
        argument_keys=frozenset({"entity_ids", "location"}),
    ),
    UnrealCapabilitySpec(
        UnrealCapability.INSPECT_ASSET,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}),
        ("asset_state",),
        "Inspect or verify an Unreal asset representation.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.MODIFY_ASSET,
        frozenset({UnrealOperationKind.WRITE}),
        ("asset_state",),
        "Modify an already-authorized Unreal asset representation.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.MATERIAL,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}),
        ("material_state",),
        "Inspect, modify, or verify material state.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.NIAGARA,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}),
        ("niagara_state",),
        "Inspect, modify, or verify Niagara VFX state.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.BLUEPRINT,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}),
        ("blueprint_state",),
        "Inspect, modify, or verify Blueprint state.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.SEQUENCER,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}),
        ("sequencer_state",),
        "Inspect, modify, or verify cinematic Sequencer state.",
    ),
    UnrealCapabilitySpec(
        UnrealCapability.RENDER,
        frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}),
        ("render_state",),
        "Configure or verify controlled Unreal rendering operations.",
    ),
)


class UnrealCapabilityRegistry:
    def __init__(self, specs=DEFAULT_UNREAL_CAPABILITIES):
        self._specs = {spec.capability: spec for spec in specs}

    def get(self, capability: UnrealCapability) -> UnrealCapabilitySpec:
        try:
            return self._specs[capability]
        except KeyError:
            raise KeyError("unknown Unreal capability")

    def validate(self, capability: UnrealCapability, kind: UnrealOperationKind) -> UnrealCapabilitySpec:
        spec = self.get(capability)
        if kind not in spec.allowed_kinds:
            raise ValueError(
                "operation kind is not permitted for capability " + capability.value
            )
        return spec

    def validate_operation(self, operation: UnrealOperation) -> UnrealOperation:
        """Fail closed unless a proposed operation matches its argument schema."""
        spec = self.validate(operation.capability, operation.kind)
        arguments = operation.arguments
        if not isinstance(arguments, Mapping):
            raise ValueError("Unreal operation arguments must be a mapping")
        if frozenset(arguments.keys()) != spec.argument_keys:
            raise ValueError(
                "Unreal operation arguments do not match the capability schema"
            )

        argument_entity_ids = arguments.get("entity_ids")
        if not isinstance(argument_entity_ids, (tuple, list)) or not argument_entity_ids:
            raise ValueError("Unreal operation requires non-empty entity_ids arguments")
        normalized = tuple(argument_entity_ids)
        if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in normalized):
            raise ValueError("Unreal operation entity_ids must contain non-empty strings")
        if normalized != tuple(operation.entity_ids):
            raise ValueError("Unreal operation entity_ids must match its argument payload")
        return operation

    def all(self):
        return tuple(self._specs.values())
