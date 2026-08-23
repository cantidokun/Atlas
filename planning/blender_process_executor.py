"""Process-backed Blender executor for the controlled execution boundary.

This module is deliberately transport-focused. It does not validate tool
capabilities or decide whether an action is authorized; those decisions remain
owned by BlenderExecutionBoundary and the planning/authorization layers above it.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping

from tools.blender_process import run_checked_blender


@dataclass(frozen=True)
class BlenderProcessRequest:
    """Validated inputs required to invoke one Blender subprocess."""

    blend_path: str
    script: str
    start_marker: str
    end_marker: str
    timeout: int = 60


RequestBuilder = Callable[[str, Dict[str, Any]], BlenderProcessRequest]


class BlenderProcessExecutor:
    """Adapt named Atlas tools to the fail-closed Blender process transport."""

    def __init__(
        self,
        request_builders: Mapping[str, RequestBuilder],
        *,
        blender_command: str,
    ) -> None:
        self._request_builders = dict(request_builders)
        self._blender_command = blender_command

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            builder = self._request_builders[tool]
        except KeyError as exc:
            raise ValueError(f"No Blender process request builder for tool '{tool}'") from exc

        request = builder(tool, dict(arguments))
        if not isinstance(request, BlenderProcessRequest):
            raise TypeError("Blender process request builder must return BlenderProcessRequest")

        return run_checked_blender(
            self._blender_command,
            request.blend_path,
            request.script,
            request.start_marker,
            request.end_marker,
            timeout=request.timeout,
        )
