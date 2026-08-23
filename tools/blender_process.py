"""Fail-closed subprocess boundary for controlled Blender execution.

This module deliberately keeps process execution separate from higher-level
Blender tools. It accepts only a structured stdout envelope and refuses to
promote process failures or malformed responses into successful results.
"""

import json
import subprocess
from typing import Any, List


def _extract_payload(output: str, start_marker: str, end_marker: str) -> str:
    """Extract the JSON payload between the required markers."""
    start = output.find(start_marker)
    if start < 0:
        raise RuntimeError("Blender did not return a valid result: start marker missing")

    payload_start = start + len(start_marker)
    end = output.find(end_marker, payload_start)
    if end < 0:
        raise RuntimeError("Blender did not return a valid result: end marker missing")

    payload = output[payload_start:end].strip()
    if not payload:
        raise RuntimeError("Blender returned an empty result payload")
    return payload


def run_checked_blender(
    blender_command: str,
    blend_path: str,
    script: str,
    start_marker: str,
    end_marker: str,
    *,
    timeout: int = 60,
) -> dict:
    """Run Blender and return one validated JSON object.

    A non-zero process exit, missing markers, invalid JSON, or a non-object
    JSON value is always a failure. The caller therefore cannot accidentally
    treat a partial or malformed subprocess response as successful execution.
    """
    command: List[str] = [
        blender_command,
        "--background",
        blend_path,
        "--python-expr",
        script,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Blender process timed out") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to start Blender: {exc}") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        detail = stderr.strip() or stdout.strip()
        suffix = f": {detail[-1000:]}" if detail else ""
        raise RuntimeError(
            f"Blender process failed with exit code {result.returncode}{suffix}"
        )

    payload = _extract_payload(stdout, start_marker, end_marker)

    try:
        decoded: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Blender returned invalid JSON: {exc.msg}") from exc

    if not isinstance(decoded, dict):
        raise RuntimeError("Blender result must be a JSON object")

    return decoded
