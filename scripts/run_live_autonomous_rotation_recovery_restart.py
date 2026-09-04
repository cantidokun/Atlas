"""Prove autonomous Blender recovery across a Python process restart."""

from __future__ import annotations

import argparse
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
            raise RuntimeError("controlled live recovery restart failure")
        return self._real_executor(tool, arguments)


def _rotation(result: Dict[str, Any], object_name: str) -> List[float]:
    details = result.get("details", result)
    if not isinstance(details, dict) or details.get("object_name") != object_name:
        raise RuntimeError("inspection returned unexpected object data")
    values = details.get("rotation_degrees")
    if not isinstance(values, list) or len(values) != 3:
        raise RuntimeError("inspection returned invalid rotation data")
    return [float(value) for value in values]


def _set_rotation(boundary: BlenderExecutionBoundary, path: Path, object_name: str, rotation: List[float]) -> List[float]:
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


def _task(path: Path, object_name: str, expected: List[float]):
    return object_rotation_task_definition(str(path), target_object=object_name, target_rotation=expected)


def _context(task_name: str, path: Path) -> RuntimeContext:
    """Keep the continuation identity stable across both processes."""
    return RuntimeContext(
        "Recover a failed Blender rotation operation across a Python restart.",
        {"environment": "local-blender", "file": str(path), "task": task_name},
    )


def phase_failure(path: Path, blender_command: str, object_name: str, expected: List[float], authorization_id: str, state_file: Path) -> None:
    real_executor = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender_command)
    boundary = BlenderExecutionBoundary(real_executor)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    original_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    original = _rotation({"details": dict(original_result.details)}, object_name)

    neutral = list(original)
    if neutral == expected:
        neutral[2] = expected[2] - 15.0
        if neutral == expected:
            neutral[2] -= 1.0
        normalized = _set_rotation(boundary, path, object_name, neutral)
        if normalized != neutral:
            raise RuntimeError(f"failed to normalize fixture: expected {neutral}, got {normalized}")

    task = _task(path, object_name, expected)
    context = _context(task.name, path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    if state_file.exists():
        state_file.unlink()
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.start(task, store, context, FailOnceExecutor(real_executor, "set_object_rotation"), authorization_id=authorization_id)
    runtime.runtime.checkpoint_metadata({"fixture_original_rotation": original})

    failed = runtime.run_until_pause()
    if failed.get("blocked") is not True:
        raise RuntimeError(f"controlled failure did not produce BLOCKED state: {failed}")
    persisted = store.load()
    snapshot = persisted["snapshot"]
    if snapshot.get("failure", {}).get("phase") != "ACTION":
        raise RuntimeError("failed action was not persisted as an ACTION failure")
    if snapshot.get("blocked") is not True:
        raise RuntimeError("failed action checkpoint is not blocked")

    print("LIVE AUTONOMOUS RECOVERY RESTART PHASE 1 VERIFIED")
    print(f"object={object_name}")
    print(f"original={original}")
    print(f"checkpoint={snapshot.get('current_step', {})}")
    print(f"authorization={authorization_id}")
    print("controlled_failure=checkpointed")
    print("process_restart=ready")
    print(f"state_file={state_file}")


def phase_recover(path: Path, blender_command: str, object_name: str, expected: List[float], authorization_id: str, replan_authorization_id: str, state_file: Path) -> None:
    real_executor = BlenderProcessExecutor(BLENDER_PROCESS_REQUEST_BUILDERS, blender_command=blender_command)
    boundary = BlenderExecutionBoundary(real_executor)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    task = _task(path, object_name, expected)
    context = _context(task.name, path)
    store = FutureRuntimeStateStore(state_file)
    runtime = AutonomousTaskRuntime.resume_from_store(task, store, context, real_executor)

    persisted = store.load()
    original_raw = (persisted.get("metadata") or {}).get("fixture_original_rotation")
    if not isinstance(original_raw, list) or len(original_raw) != 3:
        raise RuntimeError("persisted fixture restoration state is missing")
    original = [float(value) for value in original_raw]

    resumed = runtime.runtime.snapshot()
    if resumed.get("blocked") is not True or resumed.get("failure", {}).get("phase") != "ACTION":
        raise RuntimeError(f"fresh process did not recover the blocked ACTION checkpoint: {resumed}")
    if runtime.recovery_gate is None:
        raise RuntimeError("fresh process did not reconstruct the recovery gate")
    if runtime.authorization is None or runtime.authorization.authorization_id != authorization_id:
        raise RuntimeError("initial action authorization was not recovered")

    recovery = runtime.recover_with_fresh_evidence()
    if recovery["decision"]["disposition"] != "REPLAN_REQUIRED":
        raise RuntimeError(f"fresh process recovery did not reach REPLAN_REQUIRED: {recovery}")

    replacement = [ActionSpec("set_object_rotation", {"file_name": str(path), "object_name": object_name, "rotation_degrees": expected}, "restart_replanned_set_object_rotation")]
    receipt = runtime.authorize_replan(replacement, replan_authorization_id)
    runtime.install_authorized_replan(receipt, replacement)
    result = runtime.run_until_pause()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"cross-process authorized recovery did not complete: {result}")

    verified = boundary.execute_verified("inspect_object_transform", inspect_args)
    final_rotation = _rotation({"details": dict(verified.details)}, object_name)
    if final_rotation != expected:
        raise RuntimeError(f"recovered mutation did not persist: expected {expected}, got {final_rotation}")

    restored = _set_rotation(boundary, path, object_name, original)
    if restored != original:
        raise RuntimeError(f"fixture restoration failed: expected {original}, got {restored}")

    state_file.unlink(missing_ok=True)
    print("LIVE AUTONOMOUS RECOVERY RESTART VERIFIED")
    print(f"object={object_name}")
    print(f"original={original}")
    print(f"recovered={final_rotation}")
    print(f"initial_authorization={authorization_id}")
    print(f"replan_authorization={replan_authorization_id}")
    print("durable_failure_checkpoint=verified")
    print("process_restart=verified")
    print("authorization_recovered=verified")
    print("fresh_recovery_evidence=verified")
    print("replan_authorization=verified")
    print("replacement_execution=verified")
    print("fresh_final_verification=verified")
    print(f"fixture_restored={restored}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("failure", "recover"), required=True)
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--authorization-id", default="atlas-stage12-autonomous-recovery-restart-initial")
    parser.add_argument("--replan-authorization-id", default="atlas-stage12-autonomous-recovery-restart-replan")
    parser.add_argument("--state-file", default="Saved/atlas-autonomous-recovery-restart.json")
    args = parser.parse_args()
    blend_path = Path(args.blend)
    state_file = Path(args.state_file)
    expected = [float(value) for value in args.rotation]
    try:
        if not blend_path.is_file():
            raise FileNotFoundError(f"Blender fixture not found: {blend_path}")
        if args.phase == "failure":
            phase_failure(blend_path, args.blender, args.object, expected, args.authorization_id, state_file)
        else:
            phase_recover(blend_path, args.blender, args.object, expected, args.authorization_id, args.replan_authorization_id, state_file)
    except Exception as exc:
        print(f"LIVE AUTONOMOUS RECOVERY RESTART FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
