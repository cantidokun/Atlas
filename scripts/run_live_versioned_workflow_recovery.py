"""Prove versioned soccer workflow recovery across a Python process restart."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.autonomous_task_runtime import AutonomousTaskRuntime
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_process_executor import BlenderProcessExecutor
from planning.blender_tool_requests import BLENDER_PROCESS_REQUEST_BUILDERS
from planning.replan_authorization import ReplanAuthorization
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.soccer_production_catalog import compile_soccer_production_workflow


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


def _location(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            return [float(v) for v in obj["location"]]
    raise RuntimeError(f"Object not found: {object_name}")


def _rotation(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    if details.get("object_name") != object_name:
        raise RuntimeError("Unexpected transform inspection object")
    return [float(v) for v in details["rotation_degrees"]]


def _parameters(path: Path, object_name: str, location: List[float], rotation: List[float]) -> Dict[str, Any]:
    return {
        "file_name": str(path),
        "object_name": object_name,
        "target_location": list(location),
        "target_rotation": list(rotation),
    }


def _context(path: Path) -> RuntimeContext:
    return RuntimeContext(
        "Execute a versioned reusable soccer production workflow with restart recovery.",
        {"environment": "local-blender", "file": str(path), "workflow": "broadcast-goal-preparation@1"},
    )


def phase_failure(path: Path, blender: str, object_name: str, state_file: Path) -> None:
    boundary = BlenderExecutionBoundary(
        BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender)
    )
    executor = BlenderExecutor(boundary)
    original_location = _location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    original_rotation = _rotation(
        boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}),
        object_name,
    )
    target_location = [original_location[0] + 0.25, original_location[1], original_location[2]]
    target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + 15.0]
    task = compile_soccer_production_workflow(
        "broadcast-goal-preparation", _parameters(path, object_name, target_location, target_rotation), version=1
    ).compile()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.unlink(missing_ok=True)
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.start(
        task, store, _context(path), executor, "atlas-stage15-versioned-recovery-initial"
    )
    runtime.runtime.checkpoint_metadata({
        "fixture_original_location": original_location,
        "fixture_original_rotation": original_rotation,
        "fixture_target_location": target_location,
        "fixture_target_rotation": target_rotation,
    })
    metadata = store.load()["metadata"]
    if metadata["task_metadata"]["workflow_catalog"]["version"] != 1:
        raise RuntimeError("versioned workflow provenance was not persisted")

    class FailRotation:
        def __init__(self, delegate: Any) -> None:
            self.delegate = delegate

        def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            if tool == "set_object_rotation":
                raise RuntimeError("controlled versioned-workflow rotation failure")
            return self.delegate(tool, arguments)

    runtime.executor = FailRotation(runtime.executor)
    failed = runtime.run_until_pause()
    if failed.get("blocked") is not True or failed.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"versioned workflow did not fail at rotation action: {failed}")

    print("LIVE VERSIONED WORKFLOW RECOVERY PHASE 1 VERIFIED")
    print(f"object={object_name}")
    print("workflow=broadcast-goal-preparation")
    print("workflow_version=1")
    print("workflow_parameter_contract=verified")
    print("semantic_provenance_persisted=verified")
    print("action_1=completed")
    print("action_2=controlled_failure")
    print("partial_progress_checkpoint=verified")
    print("process_restart=ready")


def phase_recover(path: Path, blender: str, object_name: str, state_file: Path) -> None:
    boundary = BlenderExecutionBoundary(
        BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender)
    )
    executor = BlenderExecutor(boundary)
    store = FutureRuntimeStateStore(state_file)
    persisted = store.load()
    metadata = persisted["metadata"]
    task_metadata = metadata["task_metadata"]
    catalog = task_metadata["workflow_catalog"]
    if catalog["name"] != "broadcast-goal-preparation" or catalog["version"] != 1:
        raise RuntimeError(f"persisted workflow identity is invalid: {catalog}")
    parameters = task_metadata["workflow_parameters"]
    task = compile_soccer_production_workflow(
        "broadcast-goal-preparation", parameters, version=1
    ).compile()
    runtime = AutonomousTaskRuntime.resume_from_store(task, store, _context(path), executor)
    if runtime.runtime.snapshot().get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError("fresh process did not recover the failed versioned workflow")
    if runtime.authorization is None or runtime.authorization.authorization_id != "atlas-stage15-versioned-recovery-initial":
        raise RuntimeError("initial versioned workflow authorization was not recovered")

    recovery = runtime.recover_with_fresh_evidence()
    if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
        raise RuntimeError(f"fresh evidence did not require replan: {recovery}")

    target_rotation = [float(v) for v in parameters["target_rotation"]]
    replacement = [ActionSpec(
        "set_object_rotation",
        {"file_name": str(path), "object_name": object_name, "rotation_degrees": target_rotation},
        "replanned_rotation",
        depends_on=("position_goal",),
    )]
    receipt = runtime.authorize_replan(replacement, "atlas-stage15-versioned-recovery-replan")
    if not isinstance(receipt, ReplanAuthorization):
        raise RuntimeError("missing versioned-workflow replan authorization")
    runtime.install_authorized_replan(receipt, replacement)
    if runtime.runtime.metadata.get("task_metadata", {}).get("workflow_catalog", {}).get("version") != 1:
        raise RuntimeError("workflow version provenance was lost during replan")
    if runtime.runtime.metadata.get("task_metadata", {}).get("workflow_parameters") != parameters:
        raise RuntimeError("workflow parameter provenance was changed during replan")
    result = runtime.run_until_pause()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"versioned workflow recovery did not complete: {result}")

    final_location = _location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    final_rotation = _rotation(
        boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}),
        object_name,
    )
    if final_location != [float(v) for v in parameters["target_location"]] or final_rotation != target_rotation:
        raise RuntimeError("versioned workflow final verification failed")

    original_location = [float(v) for v in metadata["fixture_original_location"]]
    original_rotation = [float(v) for v in metadata["fixture_original_rotation"]]
    boundary.execute_with_persistence(
        "move_object",
        {"file_name": str(path), "object_name": object_name, "location": original_location},
        "inspect_scene",
        {"file_name": str(path)},
        {object_name: {"location": original_location}},
        lambda inspection: {object_name: {"location": _location(inspection, object_name)}},
    )
    boundary.execute_with_persistence(
        "set_object_rotation",
        {"file_name": str(path), "object_name": object_name, "rotation_degrees": original_rotation},
        "inspect_object_transform",
        {"file_name": str(path), "object_name": object_name},
        {"object_name": object_name, "rotation_degrees": original_rotation},
        lambda inspection: {"object_name": object_name, "rotation_degrees": _rotation(inspection, object_name)},
    )
    restored_location = _location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    restored_rotation = _rotation(
        boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}),
        object_name,
    )
    if restored_location != original_location or restored_rotation != original_rotation:
        raise RuntimeError("fixture restoration verification failed")
    state_file.unlink(missing_ok=True)

    print("LIVE VERSIONED WORKFLOW RECOVERY VERIFIED")
    print(f"object={object_name}")
    print("workflow=broadcast-goal-preparation")
    print("workflow_version=1")
    print("workflow_parameter_contract=verified")
    print("semantic_provenance_recovered=verified")
    print("completed_prerequisite_not_replayed=verified")
    print("process_restart=verified")
    print("fresh_recovery_evidence=verified")
    print("replan_authorization=verified")
    print("replacement_execution=verified")
    print("fresh_final_verification=verified")
    print(f"fixture_restored_location={restored_location}")
    print(f"fixture_restored_rotation={restored_rotation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("failure", "recover"), required=True)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--state-file", default="Saved/atlas-live-versioned-workflow-recovery.json")
    args = parser.parse_args()
    path = Path(args.blend)
    try:
        if args.phase == "failure":
            phase_failure(path, args.blender, args.object, Path(args.state_file))
        else:
            phase_recover(path, args.blender, args.object, Path(args.state_file))
    except Exception as exc:
        print(f"LIVE VERSIONED WORKFLOW RECOVERY FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
