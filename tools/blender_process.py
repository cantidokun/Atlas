"""Fail-closed subprocess boundary for controlled Blender execution."""
import json
import subprocess
from typing import Any, Dict


def run_checked_blender(blender_executable: str, blend_path: str, script: str, start_marker: str, end_marker: str, timeout: int = 60) -> Dict[str, Any]:
    """Run Blender and require both a successful process and a valid payload."""
    result = subprocess.run(
        [blender_executable, "--background", blend_path, "--python-expr", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    output = result.stdout
    if result.returncode != 0:
        diagnostics = (result.stderr or output)[-3000:]
        raise RuntimeError(
            f"Blender process failed with exit code {result.returncode}.\n{diagnostics}"
        )

    start = output.find(start_marker)
    end = output.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            "Blender did not return a valid result.\n" + output[-3000:]
        )

    payload = output[start + len(start_marker):end].strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Blender returned an invalid JSON result.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Blender result must be a JSON object.")
    return parsed
