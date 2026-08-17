"""Fail-closed parsing of structured Unreal Agent operations.

This is the boundary for AI-produced operation objects. Parsing normalizes only
well-typed data; capability authorization remains the responsibility of the
Unreal capability registry and the generic Atlas authorization layer.
"""

from typing import Any, Mapping, Tuple

from planning.unreal_agent import (
    UnrealCapability,
    UnrealOperation,
    UnrealOperationKind,
)
from planning.unreal_capability_registry import UnrealCapabilityRegistry


_REQUIRED_KEYS = frozenset({"capability", "kind", "name", "arguments", "entity_ids"})


def parse_unreal_operation(
    payload: Mapping[str, Any],
    capabilities=None,
) -> UnrealOperation:
    """Parse and validate one AI-produced Unreal operation.

    The input must be an object with exactly the contract keys. Enum values are
    accepted only as their canonical string values; no fuzzy matching or
    coercion is performed.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("Unreal operation must be an object")

    if frozenset(payload.keys()) != _REQUIRED_KEYS:
        raise ValueError("Unreal operation does not match the required contract schema")

    capability_value = payload["capability"]
    kind_value = payload["kind"]
    name = payload["name"]
    arguments = payload["arguments"]
    entity_ids = payload["entity_ids"]

    if not isinstance(capability_value, str):
        raise TypeError("capability must be a string")
    if not isinstance(kind_value, str):
        raise TypeError("kind must be a string")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(arguments, Mapping):
        raise TypeError("arguments must be an object")
    if not isinstance(entity_ids, (list, tuple)) or not entity_ids:
        raise ValueError("entity_ids must be a non-empty array")

    try:
        capability = UnrealCapability(capability_value)
    except ValueError as exc:
        raise ValueError("unsupported Unreal capability") from exc

    try:
        kind = UnrealOperationKind(kind_value)
    except ValueError as exc:
        raise ValueError("unsupported Unreal operation kind") from exc

    normalized_entity_ids: Tuple[str, ...] = tuple(entity_ids)
    if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in normalized_entity_ids):
        raise ValueError("entity_ids must contain only non-empty strings")

    operation = UnrealOperation(
        capability=capability,
        kind=kind,
        name=name,
        arguments=dict(arguments),
        entity_ids=normalized_entity_ids,
    )

    registry = capabilities or UnrealCapabilityRegistry()
    return registry.validate_operation(operation)
