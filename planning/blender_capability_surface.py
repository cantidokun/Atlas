"""Integrity checks for Atlas's public Blender capability surface."""

from __future__ import annotations

from typing import Iterable, Mapping


def validate_blender_capability_surface(
    tools: Mapping[str, object],
    capabilities: Iterable[object],
    schemas: Mapping[str, object],
) -> tuple[str, ...]:
    """Return the canonical sorted surface or fail closed on drift.

    A tool is only considered exposed when it has an executable callable, an
    explicit capability declaration, and an argument schema.  This function
    intentionally performs structural checks only; authorization remains a
    controller concern and execution remains a Blender-boundary concern.
    """
    tool_names = set(tools)
    capability_names = {capability.name for capability in capabilities}
    schema_names = set(schemas)

    if tool_names != capability_names:
        raise ValueError(
            "Blender tool/capability drift: "
            f"tools-only={sorted(tool_names - capability_names)}, "
            f"capabilities-only={sorted(capability_names - tool_names)}"
        )

    if tool_names != schema_names:
        raise ValueError(
            "Blender tool/schema drift: "
            f"tools-only={sorted(tool_names - schema_names)}, "
            f"schemas-only={sorted(schema_names - tool_names)}"
        )

    noncallable = sorted(name for name, tool in tools.items() if not callable(tool))
    if noncallable:
        raise ValueError(f"Blender tools must be callable: {noncallable}")

    return tuple(sorted(tool_names))
