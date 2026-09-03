"""Prove a higher-level reusable soccer production workflow through Atlas."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.production_task import ProductionTaskDefinition
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.soccer_production_templates import BroadcastGoalPreparationTemplate


def _object_location(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            return [float(value) for value in obj["location"]]
    raise RuntimeError(f"Object not found: {object_name}")


def _object_rotation(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    if details.get("object_name") != object_name:
        raise RuntimeError("Unexpected transform object")
    return [float(value) for value in details["rotation_degrees"]]


class BlenderProductionExecutor:
    """Use the proven Blender adapter and persistence boundary."""

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
                {object_name: {"location": [float(value) for value in arguments["location"]]}},
                lambda inspection: {object_name: {"location": _object_location(inspection, object_name)}},
            )
            return dict(result.operation_result.details)
        if tool == "set_object_rotation":
            object_name = arguments["object_name"]
            result = self.boundary.execute_with_persistence(
                tool,
                arguments,
                "inspect_object_transform",
                {"file_name": arguments["file_name"], "object_name": object_name},
                {"object_name": object_name, "rotation_degrees": [float(value) for value in arguments["rotation_degrees"]]},
                lambda inspection: {"object_name": object_name, "rotation_degrees": _object_rotation(inspection, object_name)},
            )
            return dict(result.operation_result.details)
        raise RuntimeError(f"Unsupported production task tool: {tool}")


def _production_task(
    path: Path,
    object_name: str,
    target_location: List[float],
    target_rotation: List[float],
) -> ProductionTaskDefinition:
    template = BroadcastGoalPreparationTemplate(
        file_name=str(path),
        object_name=object_name,
        target_location=tuple(target_location),
        target_rotation=tuple(target_rotation),
    )
    return template.production_task()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--state-file", default="Saved/atlas-live-composed-production-task.json")
    args = parser.parse_args()

    path = Path(args.blend)
    state_file = Path(args.state_file)
    if not path.is_file():
        print(f"LIVE COMPOSED PRODUCTION TASK FAILED: Blender fixture not found: {path}")
        return 1

    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=args.blender)
    boundary = BlenderExecutionBoundary(transport)
    executor = BlenderProductionExecutor(boundary)

    try:
        original_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object)
        original_rotation = _object_rotation(
            boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": args.object}),
            args.object,
        )
        target_location = [original_location[0] + 0.25, original_location[1], original_location[2]]
        target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + 15.0]
        production = _production_task(path, args.object, target_location, target_rotation)
        task = production.compile()
        state_file.unlink(missing_ok=True)
        runtime = AutonomousTaskRuntime.start(
            task,
            FutureRuntimeStateStore(state_file),
            RuntimeContext(
                "Execute a reusable soccer production workflow through Atlas.",
                {"environment": "local-blender", "file": str(path), "task": production.name},
            ),
            executor,
            "atlas-stage15-soccer-workflow-template",
        )
        runtime.runtime.checkpoint_metadata({"production_task": production.snapshot()})
        result = runtime.run_until_pause()
        if result.get("complete") is not True or result.get("blocked") is True:
            raise RuntimeError(f"reusable production workflow did not complete: {result}")

        final_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object)
        final_rotation = _object_rotation(
            boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": args.object}),
            args.object,
        )
        if final_location != target_location or final_rotation != target_rotation:
            raise RuntimeError("final independent reusable-workflow verification failed")

        boundary.execute_with_persistence(
            "move_object",
            {"file_name": str(path), "object_name": args.object, "location": original_location},
            "inspect_scene",
            {"file_name": str(path)},
            {args.object: {"location": original_location}},
            lambda inspection: {args.object: {"location": _object_location(inspection, args.object)}},
        )
        boundary.execute_with_persistence(
            "set_object_rotation",
            {"file_name": str(path), "object_name": args.object, "rotation_degrees": original_rotation},
            "inspect_object_transform",
            {"file_name": str(path), "object_name": args.object},
            {"object_name": args.object, "rotation_degrees": original_rotation},
            lambda inspection: {"object_name": args.object, "rotation_degrees": _object_rotation(inspection, args.object)},
        )
        restored_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object)
        restored_rotation = _object_rotation(
            boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": args.object}),
            args.object,
        )
        if restored_location != original_location or restored_rotation != original_rotation:
            raise RuntimeError("reusable-workflow fixture restoration verification failed")

        state_file.unlink(missing_ok=True)
        print("LIVE REUSABLE SOCCER PRODUCTION WORKFLOW VERIFIED")
        print(f"object={args.object}")
        print(f"workflow={production.name}")
        print(f"objective={production.objective}")
        print(f"target_location={target_location}")
        print(f"target_rotation={target_rotation}")
        print(f"domain={production.domain}")
        print("workflow_template=verified")
        print("fragment_composition=verified")
        print("fragment_dependencies=verified")
        print("multi_operation_composition=verified")
        print("dependency_validation=verified")
        print("existing_task_runtime=verified")
        print("independent_final_verification=verified")
        print(f"fixture_restored_location={restored_location}")
        print(f"fixture_restored_rotation={restored_rotation}")
    except Exception as exc:
        state_file.unlink(missing_ok=True)
        print(f"LIVE REUSABLE SOCCER PRODUCTION WORKFLOW FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
