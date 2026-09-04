"""Prove explicit action dependencies on a real Blender fixture."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.evidence_plan import EvidenceRequest
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


def _location(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            return [float(value) for value in obj["location"]]
    raise RuntimeError(f"Object not found: {object_name}")


def _rotation(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    if details.get("object_name") != object_name:
        raise RuntimeError("Unexpected transform inspection object")
    return [float(value) for value in details["rotation_degrees"]]


class BlenderExecutor:
    def __init__(self, boundary: BlenderExecutionBoundary) -> None:
        self.boundary = boundary

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool in {"inspect_scene", "inspect_object_transform"}:
            return dict(self.boundary.execute_verified(tool, arguments).details)
        if tool == "move_object":
            object_name = arguments["object_name"]
            result = self.boundary.execute_with_persistence(
                tool,
                arguments,
                "inspect_scene",
                {"file_name": arguments["file_name"]},
                {object_name: {"location": [float(v) for v in arguments["location"]]}},
                lambda inspection: {object_name: {"location": _location(inspection, object_name)}},
            )
            return dict(result.operation_result.details)
        if tool == "set_object_rotation":
            object_name = arguments["object_name"]
            result = self.boundary.execute_with_persistence(
                tool,
                arguments,
                "inspect_object_transform",
                {"file_name": arguments["file_name"], "object_name": object_name},
                {"object_name": object_name, "rotation_degrees": [float(v) for v in arguments["rotation_degrees"]]},
                lambda inspection: {"object_name": object_name, "rotation_degrees": _rotation(inspection, object_name)},
            )
            return dict(result.operation_result.details)
        raise RuntimeError(f"Unsupported tool: {tool}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--delta-x", type=float, default=0.25)
    parser.add_argument("--state-file", default="Saved/atlas-live-dependency-task.json")
    args = parser.parse_args()

    path = Path(args.blend)
    if not path.is_file():
        print(f"LIVE DEPENDENCY TASK FAILED: fixture not found: {path}")
        return 1

    executor_transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=args.blender)
    boundary = BlenderExecutionBoundary(executor_transport)
    execute = BlenderExecutor(boundary)
    inspect_args = {"file_name": str(path)}
    transform_args = {"file_name": str(path), "object_name": args.object}
    original_location = _location(boundary.execute_verified("inspect_scene", inspect_args), args.object)
    original_rotation = _rotation(boundary.execute_verified("inspect_object_transform", transform_args), args.object)
    target_location = [original_location[0] + args.delta_x, original_location[1], original_location[2]]
    target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + 15.0]

    evaluator = TargetStateEvaluator([
        StateInvariant("location_target", lambda e: e["scene"]["objects"] and _location(e["scene"], args.object) == target_location),
        StateInvariant("rotation_target", lambda e: _rotation(e["transform"], args.object) == target_rotation),
    ])
    task = AtlasTaskDefinition(
        name="live-dependency-task",
        evidence=(
            EvidenceRequest("inspect_scene", inspect_args, "scene"),
            EvidenceRequest("inspect_object_transform", transform_args, "transform"),
        ),
        actions=(
            ActionSpec(
                "move_object",
                {"file_name": str(path), "object_name": args.object, "location": target_location},
                "prepare_location",
            ),
            ActionSpec(
                "set_object_rotation",
                {"file_name": str(path), "object_name": args.object, "rotation_degrees": target_rotation},
                "prepare_rotation",
                depends_on=("prepare_location",),
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools={"move_object", "set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
    )

    state_file = Path(args.state_file)
    state_file.unlink(missing_ok=True)
    runtime = AutonomousTaskRuntime.start(
        task,
        FutureRuntimeStateStore(state_file),
        RuntimeContext(
            "Execute a dependency-aware soccer-field Blender preparation task.",
            {"environment": "local-blender", "file": str(path), "task": task.name},
        ),
        execute,
        authorization_id="atlas-stage14-dependency-live",
    )
    result = runtime.run_until_pause()
    if result.get("complete") is not True:
        raise RuntimeError(f"dependency-aware task did not complete: {result}")

    final_scene = boundary.execute_verified("inspect_scene", inspect_args)
    final_transform = boundary.execute_verified("inspect_object_transform", transform_args)
    final_location = _location(final_scene, args.object)
    final_rotation = _rotation(final_transform, args.object)
    if final_location != target_location or final_rotation != target_rotation:
        raise RuntimeError("final independent verification did not match dependency task targets")

    boundary.execute_with_persistence(
        "move_object",
        {"file_name": str(path), "object_name": args.object, "location": original_location},
        "inspect_scene",
        inspect_args,
        {args.object: {"location": original_location}},
        lambda inspection: {args.object: {"location": _location(inspection, args.object)}},
    )
    boundary.execute_with_persistence(
        "set_object_rotation",
        {"file_name": str(path), "object_name": args.object, "rotation_degrees": original_rotation},
        "inspect_object_transform",
        transform_args,
        {"object_name": args.object, "rotation_degrees": original_rotation},
        lambda inspection: {"object_name": args.object, "rotation_degrees": _rotation(inspection, args.object)},
    )
    state_file.unlink(missing_ok=True)

    print("LIVE AUTONOMOUS DEPENDENCY TASK VERIFIED")
    print(f"object={args.object}")
    print(f"original_location={original_location}")
    print(f"target_location={target_location}")
    print(f"target_rotation={target_rotation}")
    print("explicit_dependency=prepare_rotation->prepare_location")
    print("dependency_validation=verified")
    print("dependency_authorization=verified")
    print("dependency_execution_order=verified")
    print("fresh_final_verification=verified")
    print(f"fixture_restored_location={original_location}")
    print(f"fixture_restored_rotation={original_rotation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
