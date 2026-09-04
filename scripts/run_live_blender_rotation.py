"""Run one authorized live Blender rotation with independent persistence verification.

The harness reads the original rotation, applies one controlled rotation, reopens the
saved file through a fresh Blender inspection, and restores the original rotation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS


def _object_rotation(result: Any, object_name: str) -> List[float]:
    details: Dict[str, Any] = result.details
    if details.get("object_name") != object_name:
        raise RuntimeError(f"Independent transform inspection returned unexpected object '{details.get('object_name')}'")
    rotation = details.get("rotation_degrees")
    if not isinstance(rotation, list) or len(rotation) != 3:
        raise RuntimeError(f"Independent transform inspection returned invalid rotation for '{object_name}'")
    return [float(value) for value in rotation]


def run_live_rotation(
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
    pre_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    original = _object_rotation(pre_result, object_name)

    action = ActionSpec(
        tool="set_object_rotation",
        arguments={
            "file_name": str(path),
            "object_name": object_name,
            "rotation_degrees": list(rotation_degrees),
        },
        name="controlled_goalpost_rotation",
        requires_success=True,
    )
    plan = ActionPlan([action])
    plan.authorize_with_id(authorization_id)

    mutation_error = None
    try:
        if not plan.authorized:
            raise RuntimeError("live rotation plan failed authorization")

        target = list(rotation_degrees)
        closed_loop = boundary.execute_with_persistence(
            action.tool,
            action.arguments,
            "inspect_object_transform",
            inspect_args,
            {"object_name": object_name, "rotation_degrees": target},
            lambda inspection: {
                "object_name": object_name,
                "rotation_degrees": _object_rotation(inspection, object_name),
            },
        )
        plan.record_result(closed_loop.operation_result.__dict__, True)

        print("LIVE ROTATION VERIFIED")
        print(f"object={object_name}")
        print(f"before={original}")
        print(f"after={_object_rotation(closed_loop.inspection_result, object_name)}")
        print(f"authorization={authorization_id}")
        print("execution_receipt=verified")
        print("persistence_evidence=verified")
    except Exception as exc:
        mutation_error = exc
    finally:
        try:
            restore_args = {
                "file_name": str(path),
                "object_name": object_name,
                "rotation_degrees": original,
            }
            restore_result, restore_receipt = boundary.execute_with_receipt(
                "set_object_rotation", restore_args
            )
            if not restore_result.ok or not isinstance(restore_receipt, BlenderExecutionReceipt):
                raise RuntimeError("fixture restoration returned unsuccessful result")
            if not restore_receipt.matches("set_object_rotation", restore_args, restore_result):
                raise RuntimeError("fixture restoration receipt did not match the request/result")
            restored_result = boundary.execute_verified("inspect_object_transform", inspect_args)
            restored = _object_rotation(restored_result, object_name)
            if restored != original:
                raise RuntimeError(
                    f"fixture restoration verification failed: expected {original}, got {restored}"
                )
            print(f"fixture_restored={restored}")
        except Exception as restore_error:
            raise RuntimeError(
                f"LIVE ROTATION FAILED and fixture restoration failed: {restore_error}"
            ) from restore_error

    if mutation_error is not None:
        raise mutation_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--authorization-id", default="atlas-stage12-live-rotation")
    args = parser.parse_args()

    try:
        run_live_rotation(
            args.blend,
            args.blender,
            args.object,
            args.rotation,
            args.authorization_id,
        )
    except Exception as exc:
        print(f"LIVE ROTATION FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
