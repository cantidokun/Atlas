"""Gated live Blender mutation test.

This test is intentionally explicit: it requires a dedicated fixture named
atlas_live_mutation.blend and performs one authorized goalpost move. It backs
up the fixture and restores it in a finally block.
"""
from pathlib import Path
import shutil

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor

TARGET_FILE = "atlas_live_mutation.blend"
OBJECT_NAME = "Goal_Left_post"
TARGET_LOCATION = [0.25, 0.0, 0.0]


def main() -> int:
    target = Path(TARGET_FILE)
    backup = Path(f"{TARGET_FILE}.atlas-backup")
    if not target.exists():
        raise SystemExit(f"Missing required fixture: {TARGET_FILE}")
    shutil.copy2(target, backup)
    try:
        executor = BlenderToolExecutor()
        boundary = BlenderExecutionBoundary(executor.execute)

        before = boundary.execute_verified(
            "inspect_object_transform",
            {"file_name": TARGET_FILE, "object_name": OBJECT_NAME},
        )
        if not before.ok:
            raise AssertionError(f"Pre-mutation inspection failed: {before}")

        moved = boundary.execute_verified(
            "move_object",
            {"file_name": TARGET_FILE, "object_name": OBJECT_NAME, "location": TARGET_LOCATION},
        )
        if not moved.ok:
            raise AssertionError(f"Mutation failed: {moved}")

        after = boundary.execute_verified(
            "inspect_object_transform",
            {"file_name": TARGET_FILE, "object_name": OBJECT_NAME},
        )
        if not after.ok:
            raise AssertionError(f"Post-mutation inspection failed: {after}")

        actual = after.details.get("location")
        if actual is None:
            raise AssertionError(f"Post-mutation result missing location: {after}")
        if any(abs(float(actual[i]) - TARGET_LOCATION[i]) > 1e-5 for i in range(3)):
            raise AssertionError(f"Persisted location mismatch: expected {TARGET_LOCATION}, got {actual}")

        print("ATLAS_LIVE_BLENDER_MUTATION_PASS")
        print(f"before={before}")
        print(f"moved={moved}")
        print(f"after={after}")
        return 0
    finally:
        shutil.copy2(backup, target)
        backup.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
