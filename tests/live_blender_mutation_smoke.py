"""Explicitly opt-in live Blender mutation smoke test.

This test is intentionally gated by ATLAS_APPROVE_LIVE_MUTATION=1. It uses a
copy of a dedicated goalpost scene, moves one authorized goalpost by a small
known delta, verifies the persisted result through a second Blender read, and
restores the original file even when verification fails.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor


TARGET_FILE = "atlas_live_mutation.blend"
OBJECT_NAME = "Goal_Left_post"
DELTA_X = 0.25
TOLERANCE = 0.001


def _scene_object(result, object_name):
    for obj in result.details["objects"]:
        if obj["name"] == object_name:
            return obj
    raise AssertionError(f"Object not found in live scene: {object_name}")


def main() -> int:
    if os.environ.get("ATLAS_APPROVE_LIVE_MUTATION") != "1":
        raise SystemExit(
            "Live mutation test is gated. Set ATLAS_APPROVE_LIVE_MUTATION=1 "
            "only when you explicitly approve the test."
        )

    project_dir = Path(__file__).resolve().parents[1]
    target_path = project_dir / TARGET_FILE
    backup_path = project_dir / f".{TARGET_FILE}.backup"

    if not target_path.is_file():
        raise FileNotFoundError(
            f"Dedicated mutation scene not found: {target_path}"
        )

    shutil.copy2(target_path, backup_path)

    try:
        executor = BlenderToolExecutor()
        boundary = BlenderExecutionBoundary(executor.execute)

        before = boundary.execute_verified(
            "inspect_scene", {"file_name": TARGET_FILE}
        )
        before_obj = _scene_object(before, OBJECT_NAME)
        before_location = list(before_obj["location"])
        target_location = [before_location[0] + DELTA_X, before_location[1], before_location[2]]

        moved = boundary.execute_verified(
            "move_object",
            {
                "file_name": TARGET_FILE,
                "object_name": OBJECT_NAME,
                "location": target_location,
            },
        )

        if moved.details.get("status") != "moved":
            raise AssertionError(f"Unexpected mutation result: {moved}")

        after = boundary.execute_verified(
            "inspect_scene", {"file_name": TARGET_FILE}
        )
        after_obj = _scene_object(after, OBJECT_NAME)
        after_location = list(after_obj["location"])

        if any(
            abs(after_location[index] - target_location[index]) > TOLERANCE
            for index in range(3)
        ):
            raise AssertionError(
                f"Persisted location mismatch: expected={target_location} "
                f"actual={after_location}"
            )

        print("ATLAS_LIVE_BLENDER_MUTATION_PASS")
        print(f"before={before_location}")
        print(f"target={target_location}")
        print(f"after={after_location}")
        return 0
    finally:
        shutil.copy2(backup_path, target_path)
        backup_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
