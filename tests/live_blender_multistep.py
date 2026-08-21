"""Approved live test for Atlas multi-step Blender execution and verification."""
from __future__ import annotations

import shutil
from pathlib import Path

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_executor import BlenderToolExecutor
from planning.blender_verification_resolver import object_locations_resolver
from planning.future_generator import FutureStep
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "goalpost_test.blend"
WORKING_FILE = ROOT / "atlas_live_multistep.blend"
STATE_FILE = ROOT / "atlas_live_multistep_runtime.json"
BLENDER_FILE = WORKING_FILE.name

LEFT = "Goal_Left_post"
RIGHT = "Goal_Right_Post"


def _location(result, object_name):
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise AssertionError(f"Initial Blender inspection failed for {object_name}: {result}")
    details = result.get("details", {})
    if details.get("object_name") != object_name:
        raise AssertionError(f"Unexpected inspected object: {details}")
    location = details.get("location")
    if not isinstance(location, list) or len(location) != 3:
        raise AssertionError(f"Initial Blender inspection has no valid location: {details}")
    return [float(value) for value in location]


def _steps(left_target, right_target):
    return [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "Use fresh Blender evidence."),
        FutureStep(1, "target.evaluated", "TARGET", "Use the resolved multi-step target."),
        FutureStep(
            2,
            "action.0",
            "ACTION",
            "Move the left goalpost to its authorized target location.",
            {"tool": "move_object", "arguments": {"file_name": BLENDER_FILE, "object_name": LEFT, "location": left_target}},
        ),
        FutureStep(
            3,
            "action.1",
            "ACTION",
            "Move the right goalpost to its authorized target location.",
            {"tool": "move_object", "arguments": {"file_name": BLENDER_FILE, "object_name": RIGHT, "location": right_target}},
        ),
        FutureStep(4, "verification.pending", "VERIFICATION", "Independently inspect and verify both goalposts."),
        FutureStep(5, "complete", "COMPLETE", "Declare completion only after both postconditions pass."),
    ]


def main():
    if not SOURCE_FILE.is_file():
        raise FileNotFoundError(f"Missing live fixture: {SOURCE_FILE}")

    shutil.copy2(SOURCE_FILE, WORKING_FILE)
    if STATE_FILE.exists():
        STATE_FILE.unlink()

    boundary = BlenderExecutionBoundary(BlenderToolExecutor().execute)
    acknowledgements = {
        "evidence.authoritative": {"source": "fresh_blender_evidence"},
        "target.evaluated": {"satisfied": False, "reason": "controlled mutation requested"},
    }

    try:
        before_left = boundary.execute("inspect_object_transform", {"file_name": BLENDER_FILE, "object_name": LEFT})
        before_right = boundary.execute("inspect_object_transform", {"file_name": BLENDER_FILE, "object_name": RIGHT})
        left = _location(before_left, LEFT)
        right = _location(before_right, RIGHT)

        left_target = [left[0] + 0.25, left[1], left[2]]
        right_target = [right[0] - 0.25, right[1], right[2]]
        steps = _steps(left_target, right_target)
        context = RuntimeContext(
            "Move both authorized goalposts inward by 0.25m on X and verify both final locations.",
            {"environment": "local-blender", "file": BLENDER_FILE},
        )
        runtime = AutonomousFutureRuntime(steps, FutureRuntimeStateStore(STATE_FILE), context)
        verifier = object_locations_resolver(
            file_name=BLENDER_FILE,
            expected_locations={LEFT: tuple(left_target), RIGHT: tuple(right_target)},
        )

        result = runtime.run_until_pause(
            boundary.execute,
            acknowledgements=acknowledgements,
            verification_resolver=verifier,
        )
        if result.get("complete") is not True:
            raise AssertionError(f"Multi-step runtime did not complete: {result}")

        print("ATLAS_LIVE_BLENDER_MULTISTEP_PASS")
        print(f"before_left={left}")
        print(f"target_left={left_target}")
        print(f"before_right={right}")
        print(f"target_right={right_target}")
        print(f"history_entries={len(result.get('history', []))}")
        return 0
    finally:
        if WORKING_FILE.exists():
            WORKING_FILE.unlink()
        if STATE_FILE.exists():
            STATE_FILE.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
