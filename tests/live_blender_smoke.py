"""Minimal opt-in live Blender smoke test.

Run this only on a machine with the Atlas Blender installation available.
It intentionally exercises inspection only; no scene mutation occurs.
"""

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor


TARGET_FILE = "atlas_live_smoke.blend"


def main() -> int:
    executor = BlenderToolExecutor()
    boundary = BlenderExecutionBoundary(executor.execute)

    result = boundary.execute_verified("inspect_scene", {"file_name": TARGET_FILE})

    if not isinstance(result, dict):
        raise AssertionError("Live Blender result must be an object")
    if result.get("status") not in (None, "ok", "success"):
        raise AssertionError(f"Unexpected Blender result status: {result}")
    if "scene" not in result:
        raise AssertionError(f"Live Blender result is missing scene identity: {result}")
    if "total_objects" not in result:
        raise AssertionError(f"Live Blender result is missing object count: {result}")

    print("ATLAS_LIVE_BLENDER_SMOKE_PASS")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
