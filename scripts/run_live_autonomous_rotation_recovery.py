"""Prove task-aware autonomous Blender recovery after a controlled write failure.

The first authorized write is intentionally failed before Blender is invoked.
The runtime must checkpoint the failure, require fresh real-Blender evidence,
require a new replan authorization, execute the replacement action, verify the
new state independently, and restore the original fixture state.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.object_rotation_task import object_rotation_task_definition
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


class FailOnceExecutor:
    """Inject one controlled action failure, then delegate to real Blender."""

    def __init__(self, real_executor: BlenderProcessExecutor, action_tool: str) -> None:
        self._real_executor = real_executor
        self._action_tool = action_tool
        self._failed = False

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == self._action_tool and not self._failed:
            self._failed = True
            raise RuntimeError("controlled live recovery failure")
        return self._real_executor(tool, arguments)


def _rotation(result: Dict[str, Any], object_name: str) -> List[float]:
    details = result.get("details", result)
    if not isinstance(details, dict) or details.get("object_name") != object_name:
        raise RuntimeError("inspection returned unexpected object data")
    values = details.get("rotation_degrees")
    if not isinstance(values, list) or len(values) != 3:
        raise RuntimeError("inspection returned invalid rotation data")
    return [float(value) for value in values]


def _set_rotation(
    boundary: BlenderExecutionBoundary,
    path: Path,
    object_name: str,
    rotation: List[float],
) -> List[float]:
    inspect_args = {"file_name": str(path), "object_name": object_name}
    operation_args = {
        "file_name": str(path),
        "object_name": object_name,
        "rotation_degrees": [float(value) for value in rotation],
    }
    result = boundary.execute_with_persistence(
        "set_object_rotation",
        operation_args,
        "inspect_object_transform",
        inspect_args,
        {"object_name": object_name, "rotation_degrees": [float(value) for value in rotation]},
        lambda inspection: {
            "object_name": object_name,
            "rotation_degrees": _rotation({"details": dict(inspection.details)}, object_name),
        },
    )
    return _rotation({"details": dict(result.inspection_result.details)}, object_name)


def run_live_recovery(
    blend_path: str,
    blender_command: str,
    object_name: str,
    rotation_degrees: List[float],
    authorization_id: str,
    replan_authorization_id: str,
) -> None:
    path = Path(blend_path)
    if not path.is_file():
        raise FileNotFoundError(f"Blender fixture not found: {path}")
    if len(rotation_degrees) != 3:
        raise ValueError("rotation_degrees must contain exactly three values")

    real_executor = BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command=blender_command,
    )
    boundary = BlenderExecutionBoundary(real_executor)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    original_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    original = _rotation({"details": dict(original_result.details)}, object_name)

    expected = [float(value) for value in rotation_degrees]
    neutral = list(original)
    if neutral == expected:
        neutral[2] = expected[2] - 15.0
        if neutral == expected:
            neutral[2] -= 1.0
        normalized = _set_rotation(boundary, path, object_name, neutral)
        if normalized != neutral:
            raise RuntimeError(f"failed to normalize fixture: expected {neutral}, got {normalized}")

    task = object_rotation_task_definition(
        str(path),
        target_object=object_name,
        target_rotation=expected,
    )
    context = RuntimeContext(
        f"Recover a failed Blender rotation operation for {object_name}.",
        {"environment": "local-blender", "file": str(path), "task": task.name},
    )

    try:
        with tempfile.TemporaryDirectory(prefix="atlas-autonomous-recovery-") as directory:
            store = FutureRuntimeStateStore(Path(directory) / "runtime.json")
            failing_executor = FailOnceExecutor(real_executor, "set_object_rotation")
            runtime = AutonomousTaskRuntime.start(
                task,
                store,
                context,
                failing_executor,
                authorization_id=authorization_id,
            )

            failed = runtime.run_until_pause()
            if failed.get("blocked") is not True:
                raise RuntimeError(f"controlled failure did not produce BLOCKED state: {failed}")

            persisted = store.load()
            if persisted["snapshot"].get("failure", {}).get("phase") != "ACTION":
                raise RuntimeError("failed action was not persisted as an ACTION failure")

            recovery = runtime.recover_with_fresh_evidence()
            if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
                raise RuntimeError(f"recovery did not reach REPLAN_REQUIRED: {recovery}")

            replacement = [
                ActionSpec(
                    "set_object_rotation",
                    {
                        "file_name": str(path),
                        "object_name": object_name,
                        "rotation_degrees": expected,
                    },
                    "replanned_set_object_rotation",
                )
            ]
            receipt = runtime.authorize_replan(replacement, replan_authorization_id)
            runtime.install_authorized_replan(receipt, replacement)
            result = runtime.run_until_pause()
            if result.get("complete") is not True or result.get("blocked") is True:
                raise RuntimeError(f"authorized recovery did not complete: {result}")

            verified = boundary.execute_verified("inspect_object_transform", inspect_args)
            final_rotation = _rotation({"details": dict(verified.details)}, object_name)
            if final_rotation != expected:
                raise RuntimeError(f"recovered mutation did not persist: expected {expected}, got {final_rotation}")

        restored = _set_rotation(boundary, path, object_name, original)
        if restored != original:
            raise RuntimeError(f"fixture restoration failed: expected {original}, got {restored}")

        print("LIVE AUTONOMOUS RECOVERY VERIFIED")
        print(f"object={object_name}")
        print(f"original={original}")
        print(f"recovered={final_rotation}")
        print(f"initial_authorization={authorization_id}")
        print(f"replan_authorization={replan_authorization_id}")
        print("controlled_failure=checkpointed")
        print("fresh_recovery_evidence=verified")
        print("replan_authorization=verified")
        print("replacement_execution=verified")
        print("fresh_final_verification=verified")
        print(f"fixture_restored={restored}")
    except Exception:
        try:
            restored = _set_rotation(boundary, path, object_name, original)
            print(f"fixture_restored_after_failure={restored}")
        finally:
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--authorization-id", default="atlas-stage12-autonomous-recovery-initial")
    parser.add_argument("--replan-authorization-id", default="atlas-stage12-autonomous-recovery-replan")
    args = parser.parse_args()

    try:
        run_live_recovery(
            args.blend,
            args.blender,
            args.object,
            list(args.rotation),
            args.authorization_id,
            args.replan_authorization_id,
        )
    except Exception as exc:
        print(f"LIVE AUTONOMOUS RECOVERY FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
