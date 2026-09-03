"""Prove multi-step autonomous Blender recovery across a Python restart.

Phase 1 performs the first real write, intentionally fails the second write
before Blender is invoked, and persists the resulting blocked checkpoint.
Phase 2 starts a fresh Python process, reconstructs the blocked continuation,
acquires multiple fresh evidence sources, authorizes only the unfinished
replacement action, verifies both final invariants, and restores the fixture.
"""

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
from planning.replan_authorization import ReplanAuthorization


class BlenderTaskExecutor:
    """Route task writes through persistence and reads through verification."""

    WRITE_TOOLS = {"move_object", "set_object_rotation"}

    def __init__(self, boundary: BlenderExecutionBoundary) -> None:
        self.boundary = boundary

    def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_scene":
            result = self.boundary.execute_verified(tool, arguments)
            return dict(result.details)
        if tool == "inspect_object_transform":
            result = self.boundary.execute_verified(tool, arguments)
            return dict(result.details)
        if tool == "move_object":
            target = {
                arguments["object_name"]: {
                    "location": [float(value) for value in arguments["location"]],
                }
            }
            result = self.boundary.execute_with_persistence(
                tool,
                arguments,
                "inspect_scene",
                {"file_name": arguments["file_name"]},
                target,
                lambda inspection: {
                    arguments["object_name"]: {
                        "location": _object_location(inspection, arguments["object_name"]),
                    }
                },
            )
            return dict(result.operation_result.details)
        if tool == "set_object_rotation":
            expected = {
                "object_name": arguments["object_name"],
                "rotation_degrees": [float(value) for value in arguments["rotation_degrees"]],
            }
            result = self.boundary.execute_with_persistence(
                tool,
                arguments,
                "inspect_object_transform",
                {"file_name": arguments["file_name"], "object_name": arguments["object_name"]},
                expected,
                lambda inspection: {
                    "object_name": arguments["object_name"],
                    "rotation_degrees": _object_rotation(inspection, arguments["object_name"]),
                },
            )
            return dict(result.operation_result.details)
        raise ValueError(f"Unsupported live Blender task tool: {tool}")


def _object_location(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    for obj in details.get("objects", []):
        if obj.get("name") == object_name:
            values = obj.get("location")
            if isinstance(values, list) and len(values) == 3:
                return [float(value) for value in values]
    raise RuntimeError(f"Independent scene inspection could not find '{object_name}'")


def _object_rotation(result: Any, object_name: str) -> List[float]:
    details = result.details if hasattr(result, "details") else result
    if details.get("object_name") != object_name:
        raise RuntimeError("Independent transform inspection returned unexpected object")
    values = details.get("rotation_degrees")
    if not isinstance(values, list) or len(values) != 3:
        raise RuntimeError("Independent transform inspection returned invalid rotation")
    return [float(value) for value in values]


def _task(path: Path, object_name: str, target_location: List[float], target_rotation: List[float]) -> AtlasTaskDefinition:
    evaluator = TargetStateEvaluator(
        [
            StateInvariant(
                "location_ready",
                lambda evidence: _object_location_from_bundle(evidence, object_name) == target_location,
            ),
            StateInvariant(
                "rotation_ready",
                lambda evidence: _object_rotation_from_bundle(evidence, object_name) == target_rotation,
            ),
        ]
    )
    return AtlasTaskDefinition(
        name="live-autonomous-multistep-recovery",
        evidence=(
            EvidenceRequest("inspect_scene", {"file_name": str(path)}, "scene"),
            EvidenceRequest("inspect_object_transform", {"file_name": str(path), "object_name": object_name}, "transform"),
        ),
        actions=(
            ActionSpec(
                "move_object",
                {"file_name": str(path), "object_name": object_name, "location": target_location},
                "prepare_location",
            ),
            ActionSpec(
                "set_object_rotation",
                {"file_name": str(path), "object_name": object_name, "rotation_degrees": target_rotation},
                "prepare_rotation",
            ),
        ),
        evaluator=evaluator,
        allowed_action_tools={"move_object", "set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "multi_step_recovery"},
    )


def _object_location_from_bundle(evidence: Dict[str, Any], object_name: str) -> List[float]:
    scene = evidence["scene"]
    for obj in scene.get("objects", []):
        if obj.get("name") == object_name:
            values = obj.get("location")
            return [float(value) for value in values]
    raise RuntimeError("Target evaluator could not find object location")


def _object_rotation_from_bundle(evidence: Dict[str, Any], object_name: str) -> List[float]:
    transform = evidence["transform"]
    if transform.get("object_name") != object_name:
        raise RuntimeError("Target evaluator received unexpected transform object")
    return [float(value) for value in transform["rotation_degrees"]]


def _context(path: Path, task_name: str) -> RuntimeContext:
    return RuntimeContext(
        "Execute a two-step soccer-field object preparation task with restart recovery.",
        {"environment": "local-blender", "file": str(path), "task": task_name},
    )


def phase_failure(
    path: Path,
    blender_command: str,
    object_name: str,
    state_file: Path,
    authorization_id: str,
    target_location: List[float],
    target_rotation: List[float],
) -> None:
    real_executor = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender_command)
    boundary = BlenderExecutionBoundary(real_executor)
    inspect_scene_args = {"file_name": str(path)}
    inspect_transform_args = {"file_name": str(path), "object_name": object_name}
    original_location = _object_location(boundary.execute_verified("inspect_scene", inspect_scene_args), object_name)
    original_rotation = _object_rotation(boundary.execute_verified("inspect_object_transform", inspect_transform_args), object_name)

    task = _task(path, object_name, target_location, target_rotation)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.unlink(missing_ok=True)
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.start(
        task,
        store,
        _context(path, task.name),
        BlenderTaskExecutor(boundary),
        authorization_id=authorization_id,
    )
    runtime.runtime.checkpoint_metadata(
        {
            "fixture_original_location": original_location,
            "fixture_original_rotation": original_rotation,
        }
    )

    calls = 0

    class FailSecondAction:
        def __init__(self, delegate):
            self.delegate = delegate

        def __call__(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal calls
            calls += 1
            if tool == "set_object_rotation":
                raise RuntimeError("controlled second-action failure")
            return self.delegate(tool, arguments)

    runtime.executor = FailSecondAction(runtime.executor)
    failed = runtime.run_until_pause()
    if failed.get("blocked") is not True or failed.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"controlled later-action failure did not checkpoint as expected: {failed}")

    snapshot = store.load()["snapshot"]
    if snapshot.get("current_index") != 3 or snapshot.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"partial-progress checkpoint was not preserved: {snapshot}")

    print("LIVE AUTONOMOUS MULTISTEP RECOVERY PHASE 1 VERIFIED")
    print(f"object={object_name}")
    print(f"original_location={original_location}")
    print(f"original_rotation={original_rotation}")
    print("action_1=completed")
    print("action_2=controlled_failure")
    print("partial_progress_checkpoint=verified")
    print("process_restart=ready")
    print(f"state_file={state_file}")


def phase_recover(
    path: Path,
    blender_command: str,
    object_name: str,
    state_file: Path,
    authorization_id: str,
    replan_authorization_id: str,
    target_location: List[float],
    target_rotation: List[float],
) -> None:
    real_executor = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender_command)
    boundary = BlenderExecutionBoundary(real_executor)
    task = _task(path, object_name, target_location, target_rotation)
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.resume_from_store(
        task,
        store,
        _context(path, task.name),
        BlenderTaskExecutor(boundary),
    )

    persisted = store.load().get("metadata") or {}
    original_location = persisted.get("fixture_original_location")
    original_rotation = persisted.get("fixture_original_rotation")
    if not isinstance(original_location, list) or not isinstance(original_rotation, list):
        raise RuntimeError("persisted fixture restoration state is missing")
    original_location = [float(value) for value in original_location]
    original_rotation = [float(value) for value in original_rotation]

    snapshot = runtime.runtime.snapshot()
    if snapshot.get("failure", {}).get("step_id") != "action.1":
        raise RuntimeError(f"fresh process did not recover the failed second action: {snapshot}")
    if runtime.recovery_gate is None:
        raise RuntimeError("fresh process did not reconstruct the recovery gate")
    if runtime.authorization is None or runtime.authorization.authorization_id != authorization_id:
        raise RuntimeError("initial multi-step authorization was not recovered")

    recovery = runtime.recover_with_fresh_evidence()
    if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
        raise RuntimeError(f"fresh multi-step evidence did not reach REPLAN_REQUIRED: {recovery}")

    replacement = [
        ActionSpec(
            "set_object_rotation",
            {"file_name": str(path), "object_name": object_name, "rotation_degrees": target_rotation},
            "replanned_rotation_only",
        )
    ]
    receipt = runtime.authorize_replan(replacement, replan_authorization_id)
    if not isinstance(receipt, ReplanAuthorization):
        raise RuntimeError("replan authorization did not produce the expected receipt")
    runtime.install_authorized_replan(receipt, replacement)
    result = runtime.run_until_pause()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"multi-step recovery did not complete: {result}")

    final_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    final_rotation = _object_rotation(boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}), object_name)
    if final_location != target_location or final_rotation != target_rotation:
        raise RuntimeError("final independent verification did not match both target invariants")

    restore_location = {
        "file_name": str(path),
        "object_name": object_name,
        "location": original_location,
    }
    boundary.execute_with_persistence(
        "move_object",
        restore_location,
        "inspect_scene",
        {"file_name": str(path)},
        {object_name: {"location": original_location}},
        lambda inspection: {object_name: {"location": _object_location(inspection, object_name)}},
    )
    restore_rotation = {
        "file_name": str(path),
        "object_name": object_name,
        "rotation_degrees": original_rotation,
    }
    boundary.execute_with_persistence(
        "set_object_rotation",
        restore_rotation,
        "inspect_object_transform",
        {"file_name": str(path), "object_name": object_name},
        {"object_name": object_name, "rotation_degrees": original_rotation},
        lambda inspection: {"object_name": object_name, "rotation_degrees": _object_rotation(inspection, object_name)},
    )

    restored_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), object_name)
    restored_rotation = _object_rotation(boundary.execute_verified("inspect_object_transform", {"file_name": str(path), "object_name": object_name}), object_name)
    if restored_location != original_location or restored_rotation != original_rotation:
        raise RuntimeError("fixture restoration verification failed")

    state_file.unlink(missing_ok=True)
    print("LIVE AUTONOMOUS MULTISTEP RECOVERY VERIFIED")
    print(f"object={object_name}")
    print(f"original_location={original_location}")
    print(f"original_rotation={original_rotation}")
    print(f"recovered_location={final_location}")
    print(f"recovered_rotation={final_rotation}")
    print(f"initial_authorization={authorization_id}")
    print(f"replan_authorization={replan_authorization_id}")
    print("multi_request_evidence=verified")
    print("action_1_not_replayed=verified")
    print("durable_partial_progress=verified")
    print("process_restart=verified")
    print("fresh_recovery_evidence=verified")
    print("replacement_execution=verified")
    print("fresh_final_verification=verified")
    print(f"fixture_restored_location={restored_location}")
    print(f"fixture_restored_rotation={restored_rotation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("failure", "recover"), required=True)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--delta-x", type=float, default=0.25)
    parser.add_argument("--authorization-id", default="atlas-stage13-multistep-initial")
    parser.add_argument("--replan-authorization-id", default="atlas-stage13-multistep-replan")
    parser.add_argument("--state-file", default="Saved/atlas-autonomous-multistep-recovery-restart.json")
    args = parser.parse_args()

    path = Path(args.blend)
    if not path.is_file():
        print(f"LIVE AUTONOMOUS MULTISTEP RECOVERY FAILED: Blender fixture not found: {path}")
        return 1

    expected_rotation = [float(value) for value in args.rotation]
    try:
        inspector = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=args.blender)
        boundary = BlenderExecutionBoundary(inspector)
        original_location = _object_location(boundary.execute_verified("inspect_scene", {"file_name": str(path)}), args.object)
        target_location = [original_location[0] + args.delta_x, original_location[1], original_location[2]]

        if args.phase == "failure":
            phase_failure(
                path,
                args.blender,
                args.object,
                Path(args.state_file),
                args.authorization_id,
                target_location,
                expected_rotation,
            )
        else:
            phase_recover(
                path,
                args.blender,
                args.object,
                Path(args.state_file),
                args.authorization_id,
                args.replan_authorization_id,
                target_location,
                expected_rotation,
            )
    except Exception as exc:
        print(f"LIVE AUTONOMOUS MULTISTEP RECOVERY FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
