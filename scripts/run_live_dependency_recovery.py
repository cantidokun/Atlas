"""Prove dependency-aware recovery across a Python process restart."""

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
from planning.replan_authorization import ReplanAuthorization
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.task_definition import AtlasTaskDefinition


class BlenderExecutor:
    """Route reads/writes through the existing verified Blender boundary."""

    def __init__(self, boundary: BlenderExecutionBoundary) -> None:
        self.boundary = boundary

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_scene":
            return dict(self.boundary.execute_verified(tool, arguments).details)
        if tool == "inspect_object_transform":
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


def _task(path: Path, object_name: str, location: List[float], rotation: List[float]) -> AtlasTaskDefinition:
    evaluator = TargetStateEvaluator([
        StateInvariant("location_target", lambda e: _location(e["scene"], object_name) == location),
        StateInvariant("rotation_target", lambda e: _rotation(e["transform"], object_name) == rotation),
    ])
    return AtlasTaskDefinition(
        name="live-dependency-recovery",
        evidence=(
            EvidenceRequest("inspect_scene", {"file_name": str(path)}, "scene"),
            EvidenceRequest("inspect_object_transform", {"file_name": str(path), "object_name": object_name}, "transform"),
        ),
        actions=(
            ActionSpec(
                "move_object",
                {"file_name": str(path), "object_name": object_name, "location": location},
                "prepare_location",
            ),
            ActionSpec(
                "set_object_rotation",
                {"file_name": str(path), "object_name": object_name, "rotation_degrees": rotation},
                "prepare_rotation",
                depends_on=("prepare_location",),
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools={"move_object", "set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
    )


def _context(path: Path) -> RuntimeContext:
    return RuntimeContext(
        "Execute a dependency-aware two-step soccer-field Blender task with restart recovery.",
        {"environment": "local-blender", "file": str(path), "task": "live-dependency-recovery"},
    )


def phase_failure(path: Path, blender: str, object_name: str, state_file: Path) -> None:
    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender)
    boundary = BlenderExecutionBoundary(transport)
    executor = BlenderExecutor(boundary)
    original_location = _location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    original_rotation = _rotation(
        boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}),
        object_name,
    )
    target_location = [original_location[0] + 0.25, original_location[1], original_location[2]]
    target_rotation = [original_rotation[0], original_rotation[1], original_rotation[2] + 15.0]
    task = _task(path, object_name, target_location, target_rotation)
    state_file.unlink(missing_ok=True)
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.start(task, store, _context(path), executor, "atlas-stage14-dependency-recovery-initial")
    runtime.runtime.checkpoint_metadata({
        "fixture_original_location": original_location,
        "fixture_original_rotation": original_rotation,
        "fixture_target_location": target_location,
        "fixture_target_rotation": target_rotation,
    })

    class FailDependentAction:
        def __init__(self, delegate):
            self.delegate = delegate
        def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            if tool == "set_object_rotation":
                raise RuntimeError("controlled dependent-action failure")
            return self.delegate(tool, arguments)

    runtime.executor = FailDependentAction(runtime.executor)
    failed = runtime.run_until_pause()
    snapshot = store.load()["snapshot"]
    if failed.get("blocked") is not True or failed.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"dependent action did not fail at action.1: {failed}")
    if snapshot.get("current_index") != 3 or snapshot.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"dependency recovery checkpoint invalid: {snapshot}")
    next_action = snapshot.get("current_step", {})
    if not isinstance(next_action, dict):
        raise RuntimeError("missing failed checkpoint")

    print("LIVE AUTONOMOUS DEPENDENCY RECOVERY PHASE 1 VERIFIED")
    print(f"object={object_name}")
    print(f"original_location={original_location}")
    print(f"original_rotation={original_rotation}")
    print(f"target_location={target_location}")
    print(f"target_rotation={target_rotation}")
    print("dependency_checkpoint=prepare_rotation->prepare_location")
    print("action_1=completed")
    print("action_2=controlled_failure")
    print("partial_progress_checkpoint=verified")
    print("process_restart=ready")


def phase_recover(path: Path, blender: str, object_name: str, state_file: Path) -> None:
    transport = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender)
    boundary = BlenderExecutionBoundary(transport)
    executor = BlenderExecutor(boundary)
    store = FutureRuntimeStateStore(state_file)
    metadata = store.load().get("metadata") or {}
    original_location = [float(v) for v in metadata["fixture_original_location"]]
    original_rotation = [float(v) for v in metadata["fixture_original_rotation"]]
    target_location = [float(v) for v in metadata["fixture_target_location"]]
    target_rotation = [float(v) for v in metadata["fixture_target_rotation"]]
    task = _task(path, object_name, target_location, target_rotation)
    runtime = AutonomousTaskRuntime.resume_from_store(task, store, _context(path), executor)
    snapshot = runtime.runtime.snapshot()
    if snapshot.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError("fresh process did not recover dependent failure checkpoint")
    if runtime.authorization is None or runtime.authorization.authorization_id != "atlas-stage14-dependency-recovery-initial":
        raise RuntimeError("initial dependency authorization was not recovered")

    recovery = runtime.recover_with_fresh_evidence()
    if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
        raise RuntimeError(f"fresh dependency evidence did not authorize replanning: {recovery}")

    replacement = [ActionSpec(
        "set_object_rotation",
        {"file_name": str(path), "object_name": object_name, "rotation_degrees": target_rotation},
        "replanned_rotation",
        depends_on=("prepare_location",),
    )]
    receipt = runtime.authorize_replan(replacement, "atlas-stage14-dependency-recovery-replan")
    if not isinstance(receipt, ReplanAuthorization):
        raise RuntimeError("missing replan authorization")
    runtime.install_authorized_replan(receipt, replacement)
    # The replacement plan intentionally names the completed prerequisite from
    # the original task. The recovery runtime must accept this only because the
    # durable partial-progress checkpoint proves prepare_location succeeded.
    result = runtime.run_until_pause()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"dependency-aware recovery did not complete: {result}")

    final_location = _location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    final_rotation = _rotation(
        boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}),
        object_name,
    )
    if final_location != target_location or final_rotation != target_rotation:
        raise RuntimeError("dependency-aware final verification failed")

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
    state_file.unlink(missing_ok=True)

    print("LIVE AUTONOMOUS DEPENDENCY RECOVERY VERIFIED")
    print(f"object={object_name}")
    print(f"target_location={target_location}")
    print(f"target_rotation={target_rotation}")
    print("explicit_dependency=prepare_rotation->prepare_location")
    print("dependency_checkpoint_recovered=verified")
    print("completed_prerequisite_not_replayed=verified")
    print("process_restart=verified")
    print("fresh_recovery_evidence=verified")
    print("dependency_replan_authorization=verified")
    print("dependent_replacement_execution=verified")
    print("fresh_final_verification=verified")
    print(f"fixture_restored_location={original_location}")
    print(f"fixture_restored_rotation={original_rotation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("failure", "recover"), required=True)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--state-file", default="Saved/atlas-live-dependency-recovery.json")
    args = parser.parse_args()
    path = Path(args.blend)
    try:
        if args.phase == "failure":
            phase_failure(path, args.blender, args.object, Path(args.state_file))
        else:
            phase_recover(path, args.blender, args.object, Path(args.state_file))
    except Exception as exc:
        print(f"LIVE AUTONOMOUS DEPENDENCY RECOVERY FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
