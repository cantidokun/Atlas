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

    if not result.ok:
        raise AssertionError(f"Live Blender execution was not successful: {result}")
    if result.state != "completed":
        raise AssertionError(f"Unexpected Blender execution state: {result}")
    if "scene" not in result.details:
        raise AssertionError(
            f"Live Blender result is missing scene identity: {result.details}"
        )
    if "total_objects" not in result.details:
        raise AssertionError(
            f"Live Blender result is missing object count: {result.details}"
        )

    print("ATLAS_LIVE_BLENDER_SMOKE_PASS")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
