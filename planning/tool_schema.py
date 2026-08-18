"""Strict argument schemas for tools that may enter Atlas task plans."""
from math import isfinite
from typing import Any, Dict, Iterable


# This registry covers tools currently admitted by the structured planning
# bridge. Tool-specific safety restrictions remain in the executor layer.
TOOL_SCHEMAS = {
    "inspect_scene": {
        "required": {"file_name"},
        "properties": {"file_name": "string"},
    },
    "inspect_object_relationship": {
        "required": {"file_name", "object1_name", "object2_name"},
        "properties": {
            "file_name": "string",
            "object1_name": "string",
            "object2_name": "string",
        },
    },
    "inspect_object_parent": {
        "required": {"file_name", "object_name"},
        "properties": {
            "file_name": "string",
            "object_name": "string",
        },
    },
    "move_object": {
        "required": {"file_name", "object_name", "location"},
        "properties": {
            "file_name": "string",
            "object_name": "string",
            "location": "location3",
        },
    },
    "create_collection": {
        "required": {"file_name", "collection_name"},
        "properties": {
            "file_name": "string",
            "collection_name": "string",
        },
    },
    "parent_object": {
        "required": {"file_name", "child_name", "parent_name"},
        "properties": {
            "file_name": "string",
            "child_name": "string",
            "parent_name": "string",
        },
    },
    "inspect_object_collections": {
        "required": {"file_name", "object_name"},
        "properties": {
            "file_name": "string",
            "object_name": "string",
        },
    },
    "move_object_to_collection": {
        "required": {"file_name", "object_name", "collection_name"},
        "properties": {
            "file_name": "string",
            "object_name": "string",
            "collection_name": "string",
        },
    },
}


def _error(message: str):
    from task_planner import TaskPlanValidationError
    return TaskPlanValidationError(message)


def _validate_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise _error(f"{field} must be a non-empty string.")


def _validate_location(value: Any, field: str) -> None:
    if not isinstance(value, list) or len(value) != 3:
        raise _error(f"{field} must contain exactly 3 numbers.")
    for number in value:
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise _error(f"{field} must contain only numbers.")
        if not isfinite(float(number)):
            raise _error(f"{field} must contain only finite numbers.")


def validate_tool_arguments(tool: str, arguments: Dict[str, Any]) -> None:
    """Validate arguments against the exact schema for an admitted tool."""
    schema = TOOL_SCHEMAS.get(tool)
    if schema is None:
        raise _error(f"No argument schema registered for tool: {tool}")

    expected = set(schema["properties"])
    actual = set(arguments)
    unknown = actual - expected
    if unknown:
        names = ", ".join(sorted(unknown))
        raise _error(f"Unknown argument(s) for {tool}: {names}")

    missing = set(schema["required"]) - actual
    if missing:
        names = ", ".join(sorted(missing))
        raise _error(f"Missing argument(s) for {tool}: {names}")

    for field, kind in schema["properties"].items():
        if field not in arguments:
            continue
        value = arguments[field]
        if kind == "string":
            _validate_string(value, field)
        elif kind == "location3":
            _validate_location(value, field)
        else:
            raise _error(f"Unsupported schema kind: {kind}")


def validate_plan_arguments(items: Iterable[Any]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        tool = item.get("tool")
        arguments = item.get("arguments", {})
        if isinstance(tool, str) and isinstance(arguments, dict):
            validate_tool_arguments(tool, arguments)
