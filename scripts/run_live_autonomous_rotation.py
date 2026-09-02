"""Prove the task-aware autonomous Blender runtime against a real Blender process.

The script uses the declarative object-rotation task, the generic autonomous future
runtime, and the production Blender process executor. The fixture is restored through
the existing closed-loop boundary after the autonomous task completes.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.object_rotation_task import object_rotation_task_definition
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _rotation(result: Dict[str, Any], object_name: str) -> List[float]:
    details = result.get("details", result)
    if not isinstance(details, dict) or details.get("object_name") != object_name:
        raise RuntimeError("inspection returned unexpected object data")
    values = details.get("rotation_degrees")
    if not isinstance(values, list) or len(values) != 3:
        raise RuntimeError("inspection returned invalid rotation data")
    return [float(value) for value in values]


def run_live_autonomous_rotation(
    blend_path: str,
    blender_command: str,
    object_name: str,
    rotation_degrees: List[float],
    authorization_id: str,
) -> None:
    path = Path(blend_path)
    if not path.is_file():
        raise FileNotFoundError(f"Blender fixture not found: {path}")
    if len(rotation_degrees) != 3:
        raise ValueError("rotation_degrees must contain exactly three values")

    executor = BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command=blender_command,
    )
    boundary = BlenderExecutionBoundary(executor)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    original_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    original = _rotation({"details": dict(original_result.details)}, object_name)

    task = object_rotation_task_definition(
        str(path),
        target_object=object_name,
        target_rotation=list(rotation_degrees),
    )
    context = RuntimeContext(
        f"Rotate Blender object {object_name} to the requested orientation.",
        {"environment": "local-blender", "file": str(path), "task": task.name},
    )

    with tempfile.TemporaryDirectory(prefix="atlas-autonomous-rotation-") as directory:
        store = FutureRuntimeStateStore(Path(directory) / "runtime.json")
        runtime = AutonomousTaskRuntime.start(
            task,
            store,
            context,
            executor,
            authorization_id=authorization_id,
        )
        result = runtime.run_until_pause()

    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"autonomous task did not complete successfully: {result}")

    history = result.get("history", [])
    action_entries = [entry for entry in history if entry.get("phase") == "ACTION"]
    verification_entries = [entry for entry in history if entry.get("phase") == "VERIFICATION"]
    if len(action_entries) != 1 or action_entries[0].get("status") != "succeeded":
        raise RuntimeError("autonomous action was not recorded as successful")
    if len(verification_entries) != 1 or verification_entries[0].get("status") != "succeeded":
        raise RuntimeError("autonomous verification was not recorded as successful")

    final_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    final_rotation = _rotation({"details": dict(final_result.details)}, object_name)
    expected = [float(value) for value in rotation_degrees]
    if final_rotation != expected:
        raise RuntimeError(f"autonomous live mutation did not persist: expected {expected}, got {final_rotation}")

    restore_args = {
        "file_name": str(path),
        "object_name": object_name,
        "rotation_degrees": original,
    }
    restored = boundary.execute_with_persistence(
        "set_object_rotation",
        restore_args,
        "inspect_object_transform",
        inspect_args,
        {"object_name": object_name, "rotation_degrees": original},
        lambda inspection: {
            "object_name": object_name,
            "rotation_degrees": _rotation(
                {"details": dict(inspection.details)},
                object_name,
            ),
        },
    )
    restored_rotation = _rotation(
        {"details": dict(restored.inspection_result.details)},
        object_name,
    )
    if restored_rotation != original:
        raise RuntimeError(
            f"fixture restoration verification failed: expected {original}, got {restored_rotation}"
        )

    print("LIVE AUTONOMOUS ROTATION VERIFIED")
    print(f"object={object_name}")
    print(f"before={original}")
    print(f"after={final_rotation}")
    print(f"authorization={authorization_id}")
    print("task_contract=verified")
    print("autonomous_runtime=verified")
    print("fresh_verification=verified")
    print(f"fixture_restored={restored_rotation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--authorization-id", default="atlas-stage12-autonomous-rotation")
    args = parser.parse_args()

    try:
        run_live_autonomous_rotation(
            args.blend,
            args.blender,
            args.object,
            args.rotation,
            args.authorization_id,
        )
    except Exception as exc:
        print(f"LIVE AUTONOMOUS ROTATION FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
