"""Declarative capability and argument-schema registry for the Atlas Unreal Agent."""

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
    argument_keys_by_kind: Mapping[UnrealOperationKind, FrozenSet[str]] = None
    alternative_argument_keys_by_kind: Mapping[UnrealOperationKind, Tuple[FrozenSet[str], ...]] = None

    def keys_for_kind(self, kind: UnrealOperationKind) -> FrozenSet[str]:
        if self.argument_keys_by_kind is not None and kind in self.argument_keys_by_kind:
            return self.argument_keys_by_kind[kind]
        return self.argument_keys

    def alternative_keys_for_kind(self, kind: UnrealOperationKind) -> Tuple[FrozenSet[str], ...]:
        if self.alternative_argument_keys_by_kind is not None:
            return self.alternative_argument_keys_by_kind.get(kind, ())
        return ()


DEFAULT_UNREAL_CAPABILITIES = (
    UnrealCapabilitySpec(UnrealCapability.INSPECT_WORLD, frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}), ("world_state",), "Inspect or verify Unreal world/level state."),
    UnrealCapabilitySpec(UnrealCapability.INSPECT_ACTOR, frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}), ("actor_state",), "Inspect or verify an Unreal Actor representation."),
    UnrealCapabilitySpec(UnrealCapability.MODIFY_ACTOR, frozenset({UnrealOperationKind.WRITE}), ("actor_state",), "Modify an already-authorized Unreal Actor representation.", argument_keys=frozenset({"entity_ids", "location"}), alternative_argument_keys_by_kind={UnrealOperationKind.WRITE: (frozenset({"entity_ids", "rotation"}), frozenset({"entity_ids", "scale"}))}),
    UnrealCapabilitySpec(UnrealCapability.INSPECT_ASSET, frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}), ("asset_state",), "Inspect or verify an Unreal asset representation."),
    UnrealCapabilitySpec(UnrealCapability.MODIFY_ASSET, frozenset({UnrealOperationKind.WRITE}), ("asset_state",), "Modify an already-authorized Unreal asset representation."),
    UnrealCapabilitySpec(UnrealCapability.MATERIAL, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("material_state",), "Inspect, modify, or verify material state.", argument_keys_by_kind={UnrealOperationKind.READ: frozenset({"entity_ids"}), UnrealOperationKind.WRITE: frozenset({"entity_ids", "material_variant"}), UnrealOperationKind.VERIFY: frozenset({"entity_ids", "material_variant"})}),
    UnrealCapabilitySpec(UnrealCapability.NIAGARA, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("niagara_state",), "Inspect, modify, or verify Niagara VFX state.", argument_keys_by_kind={UnrealOperationKind.READ: frozenset({"entity_ids"}), UnrealOperationKind.WRITE: frozenset({"entity_ids", "niagara_variant"}), UnrealOperationKind.VERIFY: frozenset({"entity_ids", "niagara_variant"})}),
    UnrealCapabilitySpec(UnrealCapability.BLUEPRINT, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("blueprint_state",), "Inspect, modify, or verify Blueprint state."),
    UnrealCapabilitySpec(UnrealCapability.SEQUENCER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("sequencer_state",), "Inspect, modify, or verify Sequencer state."),
    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state",), "Configure or verify controlled Unreal rendering operations."),
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
            raise ValueError("operation kind is not permitted for capability " + capability.value)
        return spec

    def validate_operation(self, operation: UnrealOperation) -> UnrealOperation:
        spec = self.validate(operation.capability, operation.kind)
        arguments = operation.arguments
        if not isinstance(arguments, Mapping):
            raise ValueError("Unreal operation arguments must be a mapping")
        valid_key_sets = (spec.keys_for_kind(operation.kind),) + spec.alternative_keys_for_kind(operation.kind)
        if frozenset(arguments.keys()) not in valid_key_sets:
            raise ValueError("Unreal operation arguments do not match the capability schema")
        argument_entity_ids = arguments.get("entity_ids")
        if not isinstance(argument_entity_ids, (tuple, list)) or not argument_entity_ids:
            raise ValueError("Unreal operation requires non-empty entity_ids arguments")
        normalized = tuple(argument_entity_ids)
        if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in normalized):
            raise ValueError("Unreal operation entity_ids must contain non-empty strings")
        if normalized != tuple(operation.entity_ids):
            raise ValueError("Unreal operation entity_ids must match its argument payload")
        if operation.capability is UnrealCapability.MODIFY_ACTOR:
            if "location" in arguments: vector, axes, label, error = arguments["location"], {"x", "y", "z"}, "location", "location coordinates must be numeric"
            elif "rotation" in arguments: vector, axes, label, error = arguments["rotation"], {"pitch", "yaw", "roll"}, "rotation", "rotation angles must be numeric"
            else: vector, axes, label, error = arguments["scale"], {"x", "y", "z"}, "scale", "scale components must be numeric"
            if not isinstance(vector, Mapping) or set(vector.keys()) != axes: raise ValueError(f"{label} must contain exactly {', '.join(sorted(axes))}")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector.values()): raise TypeError(error)
        if operation.capability in {UnrealCapability.MATERIAL, UnrealCapability.NIAGARA} and operation.kind in {UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}:
            field = "material_variant" if operation.capability is UnrealCapability.MATERIAL else "niagara_variant"
            variant = arguments.get(field)
            if not isinstance(variant, Mapping) or set(variant.keys()) != {"name"}: raise ValueError(f"{field} must contain exactly name")
            if not isinstance(variant["name"], str) or not variant["name"].strip(): raise ValueError(f"{field}.name must be a non-empty string")
        return operation

    def all(self):
        return tuple(self._specs.values())
