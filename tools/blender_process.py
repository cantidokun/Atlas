"""Fail-closed subprocess boundary for controlled Blender execution."""

import json
import subprocess
from typing import Any, Dict


class BlenderProcessError(RuntimeError):
    """Raised when Blender cannot produce trustworthy execution evidence."""


def run_checked_blender(
    blender_executable: str,
    blend_path: str,
    script: str,
    start_marker: str,
    end_marker: str,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Run Blender and require a successful process and valid evidence payload."""
    try:
        result = subprocess.run(
            [blender_executable, "--background", blend_path, "--python-expr", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BlenderProcessError("Blender process timed out.") from exc
    except OSError as exc:
        raise BlenderProcessError(f"Unable to start Blender: {exc}") from exc

    output = result.stdout or ""
    if result.returncode != 0:
        diagnostics = (result.stderr or output)[-3000:]
        raise BlenderProcessError(
            f"Blender process failed with exit code {result.returncode}.\n{diagnostics}"
        )

    start = output.find(start_marker)
    end = output.find(end_marker, start + len(start_marker)) if start != -1 else -1
    if start == -1 or end == -1 or end < start:
        raise BlenderProcessError(
            "Blender did not return a valid result.\n" + output[-3000:]
        )

    payload = output[start + len(start_marker):end].strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BlenderProcessError("Blender returned an invalid JSON result.") from exc

    if not isinstance(parsed, dict):
        raise BlenderProcessError("Blender result must be a JSON object.")
    return parsed
