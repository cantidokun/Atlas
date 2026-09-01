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
    UnrealCapabilitySpec(UnrealCapability.MODIFY_ACTOR, frozenset({UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("actor_state",), "Modify or verify an already-authorized Unreal Actor representation.", argument_keys_by_kind={
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "location"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "expected_location"}),
    }, alternative_argument_keys_by_kind={
        UnrealOperationKind.WRITE: (frozenset({"entity_ids", "rotation"}), frozenset({"entity_ids", "scale"})),
        UnrealOperationKind.VERIFY: (frozenset({"entity_ids", "expected_rotation"}), frozenset({"entity_ids", "expected_scale"})),
    }),
    UnrealCapabilitySpec(UnrealCapability.INSPECT_ASSET, frozenset({UnrealOperationKind.READ, UnrealOperationKind.VERIFY}), ("asset_state",), "Inspect or verify an Unreal asset representation."),
    UnrealCapabilitySpec(UnrealCapability.MODIFY_ASSET, frozenset({UnrealOperationKind.WRITE}), ("asset_state",), "Modify an already-authorized Unreal asset representation."),
    UnrealCapabilitySpec(UnrealCapability.MATERIAL, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("material_state",), "Inspect, modify, or verify material state.", argument_keys_by_kind={UnrealOperationKind.READ: frozenset({"entity_ids"}), UnrealOperationKind.WRITE: frozenset({"entity_ids", "material_variant"}), UnrealOperationKind.VERIFY: frozenset({"entity_ids", "material_variant"})}),
    UnrealCapabilitySpec(UnrealCapability.NIAGARA, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("niagara_state",), "Inspect, modify, or verify Niagara VFX state.", argument_keys_by_kind={UnrealOperationKind.READ: frozenset({"entity_ids"}), UnrealOperationKind.WRITE: frozenset({"entity_ids", "niagara_variant"}), UnrealOperationKind.VERIFY: frozenset({"entity_ids", "niagara_variant"})}),
    UnrealCapabilitySpec(UnrealCapability.BLUEPRINT, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("blueprint_state",), "Inspect, modify, compile, or verify an Unreal Blueprint asset.", argument_keys_by_kind={
        UnrealOperationKind.READ: frozenset({"entity_ids", "asset_path"}),
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "asset_path"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "asset_path", "expected_compile_status"}),
    }, alternative_argument_keys_by_kind={
        UnrealOperationKind.WRITE: (frozenset({"entity_ids", "asset_path", "metadata_key", "metadata_value"}),),
    }),
    UnrealCapabilitySpec(UnrealCapability.SEQUENCER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("sequencer_state",), "Inspect, modify, or verify Sequencer state.", argument_keys_by_kind={
        UnrealOperationKind.READ: frozenset({"entity_ids"}),
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "start_frame", "end_frame"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "expected_start_frame", "expected_end_frame"}),
    }),
    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state", "render_job_state"), "Configure, submit, inspect, or verify controlled Unreal rendering operations.", argument_keys_by_kind={
        UnrealOperationKind.READ: frozenset({"entity_ids"}),
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
    }, alternative_argument_keys_by_kind={
        UnrealOperationKind.READ: (
            frozenset({"entity_ids", "job_id"}),
        ),
        UnrealOperationKind.WRITE: (
            frozenset({"entity_ids", "sequence_asset_path"}),
        ),
        UnrealOperationKind.VERIFY: (
            frozenset({"entity_ids", "job_id"}),
        ),
    }),
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
            vector_key = next((key for key in ("location", "rotation", "scale", "expected_location", "expected_rotation", "expected_scale") if key in arguments), None)
            if vector_key is None:
                raise ValueError("modify_actor operation requires a transform argument")
            vector = arguments[vector_key]
            if vector_key in {"location", "scale", "expected_location", "expected_scale"}:
                axes, label, error = {"x", "y", "z"}, vector_key, "transform components must be numeric"
            else:
                axes, label, error = {"pitch", "yaw", "roll"}, vector_key, "rotation angles must be numeric"
            if not isinstance(vector, Mapping) or set(vector.keys()) != axes:
                raise ValueError(f"{label} must contain exactly {', '.join(sorted(axes))}")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector.values()):
                raise TypeError(error)
        if operation.capability in {UnrealCapability.MATERIAL, UnrealCapability.NIAGARA} and operation.kind in {UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}:
            field = "material_variant" if operation.capability is UnrealCapability.MATERIAL else "niagara_variant"
            variant = arguments.get(field)
            if not isinstance(variant, Mapping) or set(variant.keys()) != {"name"}: raise ValueError(f"{field} must contain exactly name")
            if not isinstance(variant["name"], str) or not variant["name"].strip(): raise ValueError(f"{field}.name must be a non-empty string")
        if operation.capability is UnrealCapability.RENDER:
            operation_name = operation.name
            if operation_name == "inspect_render_job":
                job_id = arguments.get("job_id")
                if not isinstance(job_id, str) or not job_id.strip():
                    raise ValueError("job_id must be a non-empty string")
            elif operation_name == "submit_render":
                sequence_asset_path = arguments.get("sequence_asset_path")
                if (
                    not isinstance(sequence_asset_path, str)
                    or not sequence_asset_path.strip()
                    or not sequence_asset_path.startswith("/")
                ):
                    raise ValueError("sequence_asset_path must be a non-empty Unreal package path")
            elif operation_name == "verify_render_job":
                job_id = arguments.get("job_id")
                if not isinstance(job_id, str) or not job_id.strip():
                    raise ValueError("job_id must be a non-empty string")
            else:
                from planning.unreal_render_contract import normalize_render_config
                config = {
                    key: arguments[key]
                    for key in (
                        "width",
                        "height",
                        "start_frame",
                        "end_frame",
                        "output_directory",
                        "output_format",
                    )
                    if key in arguments
                }
                if operation.kind is UnrealOperationKind.READ:
                    if config:
                        raise ValueError(
                            "render READ operations must not include render configuration fields"
                        )
                else:
                    normalize_render_config(config)
        if operation.capability is UnrealCapability.BLUEPRINT:
            asset_path = arguments.get("asset_path")
            if not isinstance(asset_path, str) or not asset_path.strip() or not asset_path.startswith("/"):
                raise ValueError("Blueprint asset_path must be a non-empty Unreal package path")
            if operation.kind is UnrealOperationKind.WRITE and "metadata_key" in arguments:
                for field in ("metadata_key", "metadata_value"):
                    if not isinstance(arguments.get(field), str) or not arguments[field].strip():
                        raise ValueError(f"{field} must be a non-empty string")
            if operation.kind is UnrealOperationKind.VERIFY:
                status = arguments.get("expected_compile_status")
                if not isinstance(status, str) or not status.strip():
                    raise ValueError("expected_compile_status must be a non-empty string")
        if operation.capability is UnrealCapability.SEQUENCER and operation.kind in {UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}:
            start_key = "start_frame" if operation.kind is UnrealOperationKind.WRITE else "expected_start_frame"
            end_key = "end_frame" if operation.kind is UnrealOperationKind.WRITE else "expected_end_frame"
            start_frame, end_frame = arguments[start_key], arguments[end_key]
            if isinstance(start_frame, bool) or not isinstance(start_frame, int):
                raise TypeError(f"{start_key} must be an integer")
            if isinstance(end_frame, bool) or not isinstance(end_frame, int):
                raise TypeError(f"{end_key} must be an integer")
            if start_frame > end_frame:
                raise ValueError("Sequencer start frame must not exceed end frame")
        return operation

    def all(self):
        return tuple(self._specs.values())
