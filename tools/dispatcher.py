"""Trusted Atlas tool dispatch boundary.

Model output may select a registered tool and provide arguments, but it may not
select arbitrary Python callables or bypass the trusted capability registry.
The dispatcher validates the tool name, capability, and function arguments
before calling the registered function.
"""

import inspect
from typing import Any, Dict, Optional, Set

from . import TOOLS


class ToolDispatchError(ValueError):
    """Raised when a requested tool cannot safely be dispatched."""


READ_ONLY_TOOLS: Set[str] = {
    "inspect_scene",
    "inspect_mesh",
    "inspect_scene_health",
    "inspect_scene_settings",
    "inspect_object_relationship",
    "inspect_soccer_components",
}

WRITE_TOOLS: Set[str] = {
    "create_collection",
    "create_empty_marker",
    "move_object",
}

ALL_TOOLS = READ_ONLY_TOOLS | WRITE_TOOLS


# Keep the capability registry independent from model-provided metadata.
for _tool in ALL_TOOLS:
    if _tool not in TOOLS:
        raise RuntimeError(f"Trusted tool registry is missing: {_tool}")


def tool_requires_write(tool: str) -> bool:
    """Return the trusted capability for a registered tool."""
    if tool in WRITE_TOOLS:
        return True
    if tool in READ_ONLY_TOOLS:
        return False
    raise ToolDispatchError(f"Unknown Atlas tool: {tool}")


def validate_tool_arguments(tool: str, arguments: Dict[str, Any]) -> None:
    """Validate a tool name and its Python function signature before dispatch."""
    if tool not in ALL_TOOLS or tool not in TOOLS:
        raise ToolDispatchError(f"Tool is not registered: {tool}")
    if not isinstance(arguments, dict):
        raise ToolDispatchError("Tool arguments must be a dictionary.")

    signature = inspect.signature(TOOLS[tool])
    parameters = signature.parameters

    unexpected = set(arguments) - set(parameters)
    if unexpected:
        raise ToolDispatchError(
            f"Unexpected arguments for {tool}: {sorted(unexpected)}"
        )

    missing = [
        name
        for name, parameter in parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        and name not in arguments
    ]
    if missing:
        raise ToolDispatchError(
            f"Missing required arguments for {tool}: {missing}"
        )


def dispatch_tool(
    tool: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    allow_writes: bool = False,
) -> Dict[str, Any]:
    """Dispatch exactly one registered Atlas tool after trusted validation."""
    arguments = {} if arguments is None else arguments
    validate_tool_arguments(tool, arguments)

    if tool_requires_write(tool) and not allow_writes:
        raise ToolDispatchError(
            f"Write tool requires explicit Python authorization: {tool}"
        )

    result = TOOLS[tool](**arguments)
    if not isinstance(result, dict):
        raise ToolDispatchError(
            f"Atlas tool {tool} returned a non-dictionary result."
        )

    return result
