"""Run the first controlled live Blender mutation through the Atlas boundary.

This harness is intentionally narrow: one authorized move of one object, followed
by a fresh Blender inspection of the saved file. The fixture is restored to its
original coordinates before the harness exits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from planning.action_plan import ActionPlan, ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_persistence_evidence import BlenderPersistenceEvidence
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS


def _object_location(result: Any, object_name: str) -> List[float]:
    details: Dict[str, Any] = result.details
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            location = obj.get("location")
            if isinstance(location, list) and len(location) == 3:
                return [float(value) for value in location]
    raise RuntimeError(f"Independent inspection could not find '{object_name}'")


def _persistence_state(object_name: str, location: List[float]) -> Dict[str, List[float]]:
    return {object_name: list(location)}


def run_live_move(
    blend_path: str,
    blender_command: str,
    object_name: str,
    delta_x: float,
    authorization_id: str,
) -> None:
    path = Path(blend_path)
    if not path.is_file():
        raise FileNotFoundError(f"Blender fixture not found: {path}")

    executor = BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command=blender_command,
    )
    boundary = BlenderExecutionBoundary(executor)

    inspect_args = {"file_name": str(path)}
    pre_result = boundary.execute_verified("inspect_scene", inspect_args)
    original = _object_location(pre_result, object_name)
    target = [original[0] + delta_x, original[1], original[2]]

    action = ActionSpec(
        tool="move_object",
        arguments={
            "file_name": str(path),
            "object_name": object_name,
            "location": target,
        },
        name="controlled_goalpost_move",
        requires_success=True,
    )
    plan = ActionPlan([action])
    plan.authorize_with_id(authorization_id)

    mutation_error = None
    try:
        if not plan.authorized:
            raise RuntimeError("live mutation plan failed authorization")
        result, receipt = boundary.execute_with_receipt(action.tool, action.arguments)
        plan.record_result(result.__dict__, result.ok)
        if not result.ok or not isinstance(receipt, BlenderExecutionReceipt):
            raise RuntimeError("live mutation did not produce a valid execution receipt")
        if not receipt.matches(action.tool, action.arguments, result):
            raise RuntimeError("live mutation execution receipt did not match the request/result")

        # This is deliberately a second Blender process. The write response above
        # is not treated as persistence evidence.
        post_result = boundary.execute_verified("inspect_scene", inspect_args)
        persisted = _object_location(post_result, object_name)
        expected_state = _persistence_state(object_name, target)
        observed_state = _persistence_state(object_name, persisted)
        persistence_evidence = BlenderPersistenceEvidence.create(
            action.tool,
            action.arguments,
            "inspect_scene",
            expected_state,
            observed_state,
            post_result,
        )
        if not persistence_evidence.matches(
            action.tool,
            action.arguments,
            expected_state,
            observed_state,
            post_result,
        ) or persisted != target:
            raise RuntimeError(
                f"independent persistence verification failed: expected {target}, got {persisted}"
            )

        print("LIVE MUTATION VERIFIED")
        print(f"object={object_name}")
        print(f"before={original}")
        print(f"after={persisted}")
        print(f"authorization={authorization_id}")
        print("persistence_evidence=verified")
    except Exception as exc:
        mutation_error = exc
    finally:
        # Always attempt deterministic fixture restoration after a successful
        # pre-inspection. Restoration itself uses the same controlled write path.
        try:
            restore_args = {
                "file_name": str(path),
                "object_name": object_name,
                "location": original,
            }
            restore_result, restore_receipt = boundary.execute_with_receipt("move_object", restore_args)
            if not restore_result.ok or not isinstance(restore_receipt, BlenderExecutionReceipt):
                raise RuntimeError("fixture restoration returned unsuccessful result")
            restored = _object_location(
                boundary.execute_verified("inspect_scene", inspect_args), object_name
            )
            if restored != original:
                raise RuntimeError(
                    f"fixture restoration verification failed: expected {original}, got {restored}"
                )
            print(f"fixture_restored={restored}")
        except Exception as restore_error:
            raise RuntimeError(
                f"LIVE MUTATION FAILED and fixture restoration failed: {restore_error}"
            ) from restore_error

    if mutation_error is not None:
        raise mutation_error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--delta-x", type=float, default=0.25)
    parser.add_argument("--authorization-id", default="atlas-stage11-live-mutation")
    args = parser.parse_args()

    try:
        run_live_move(
            args.blend,
            args.blender,
            args.object,
            args.delta_x,
            args.authorization_id,
        )
    except Exception as exc:
        print(f"LIVE MUTATION FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
