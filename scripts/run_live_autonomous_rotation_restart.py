"""Prove task-aware autonomous Blender recovery across a Python process restart.

Phase 1 performs the real Blender mutation and stops at the persisted verification
checkpoint. Phase 2 starts a fresh Python process, reconstructs the task runtime
from durable state, recovers the exact authorization, performs fresh verification,
and restores the Blender fixture to its recorded pre-mutation rotation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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


def _executor(blender_command: str) -> BlenderProcessExecutor:
    return BlenderProcessExecutor(
        BLENDER_PROCESS_REQUEST_BUILDERS,
        blender_command=blender_command,
    )


def _boundary(blender_command: str) -> BlenderExecutionBoundary:
    return BlenderExecutionBoundary(_executor(blender_command))


def _rotation(result: Dict[str, Any], object_name: str) -> List[float]:
    details = result.get("details", result)
    if not isinstance(details, dict) or details.get("object_name") != object_name:
        raise RuntimeError("inspection returned unexpected object data")
    values = details.get("rotation_degrees")
    if not isinstance(values, list) or len(values) != 3:
        raise RuntimeError("inspection returned invalid rotation data")
    return [float(value) for value in values]


def _context(path: Path, task_name: str, object_name: str) -> RuntimeContext:
    return RuntimeContext(
        f"Rotate Blender object {object_name} to the requested orientation.",
        {"environment": "local-blender", "file": str(path), "task": task_name},
    )


def _task(path: Path, object_name: str, rotation_degrees: List[float]):
    return object_rotation_task_definition(
        str(path),
        target_object=object_name,
        target_rotation=list(rotation_degrees),
    )


def _sidecar_path(state_path: str) -> Path:
    return Path(f"{state_path}.fixture.json")


def _phase_start(
    blend_path: str,
    blender_command: str,
    object_name: str,
    rotation_degrees: List[float],
    authorization_id: str,
    state_path: str,
) -> None:
    path = Path(blend_path)
    state_store = FutureRuntimeStateStore(state_path)
    boundary = _boundary(blender_command)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    before_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    before = _rotation({"details": dict(before_result.details)}, object_name)

    task = _task(path, object_name, rotation_degrees)
    context = _context(path, task.name, object_name)
    runtime = AutonomousTaskRuntime.start(
        task,
        state_store,
        context,
        _executor(blender_command),
        authorization_id=authorization_id,
    )

    metadata = state_store.load().get("metadata") or {}
    if metadata.get("target_satisfied") is not False:
        raise RuntimeError(f"phase 1 preflight target decision is not unsatisfied: {metadata}")
    if runtime.authorization is None or runtime.authorization.authorization_id != authorization_id:
        raise RuntimeError("phase 1 did not establish the expected action authorization")

    paused = runtime.runtime.run_until_pause(
        runtime._run_executor(),
        acknowledgements={
            "evidence.authoritative": {"source": "live-restart-harness", "task": task.name},
            "target.evaluated": {"satisfied": False},
        },
    )
    if paused.get("current_step", {}).get("phase") != "VERIFICATION":
        raise RuntimeError(f"phase 1 did not stop at verification: {paused}")
    if len([entry for entry in paused.get("history", []) if entry.get("phase") == "ACTION"]) != 1:
        raise RuntimeError("phase 1 did not execute exactly one authorized action")

    expected = [float(value) for value in rotation_degrees]
    inspect_after = boundary.execute_verified("inspect_object_transform", inspect_args)
    after = _rotation({"details": dict(inspect_after.details)}, object_name)
    if after != expected:
        raise RuntimeError(f"phase 1 mutation did not persist: expected {expected}, got {after}")

    _sidecar_path(state_path).write_text(
        json.dumps({"object_name": object_name, "original_rotation": before}, sort_keys=True),
        encoding="utf-8",
    )

    print("LIVE AUTONOMOUS RESTART PHASE 1 VERIFIED")
    print(f"object={object_name}")
    print(f"before={before}")
    print(f"after={after}")
    print(f"authorization={authorization_id}")
    print("checkpoint=verification")
    print("process_restart=ready")


def _phase_resume(
    blend_path: str,
    blender_command: str,
    object_name: str,
    rotation_degrees: List[float],
    authorization_id: str,
    state_path: str,
) -> None:
    path = Path(blend_path)
    state_store = FutureRuntimeStateStore(state_path)
    sidecar = _sidecar_path(state_path)
    if not sidecar.is_file():
        raise RuntimeError("pre-mutation fixture state sidecar is missing")
    recorded = json.loads(sidecar.read_text(encoding="utf-8"))
    original = recorded.get("original_rotation")
    if recorded.get("object_name") != object_name or not isinstance(original, list) or len(original) != 3:
        raise RuntimeError("pre-mutation fixture state sidecar is invalid")
    original = [float(value) for value in original]

    task = _task(path, object_name, rotation_degrees)
    context = _context(path, task.name, object_name)
    resumed = AutonomousTaskRuntime.resume_from_store(
        task,
        state_store,
        context,
        _executor(blender_command),
    )
    if resumed.authorization is None:
        raise RuntimeError("phase 2 could not recover the persisted action authorization")
    if resumed.authorization.authorization_id != authorization_id:
        raise RuntimeError("phase 2 recovered the wrong authorization identity")

    result = resumed.resume_and_run()
    if result.get("complete") is not True or result.get("blocked") is True:
        raise RuntimeError(f"resumed autonomous task did not complete: {result}")

    boundary = _boundary(blender_command)
    inspect_args = {"file_name": str(path), "object_name": object_name}
    expected = [float(value) for value in rotation_degrees]
    final_result = boundary.execute_verified("inspect_object_transform", inspect_args)
    final_rotation = _rotation({"details": dict(final_result.details)}, object_name)
    if final_rotation != expected:
        raise RuntimeError(f"resumed mutation verification failed: expected {expected}, got {final_rotation}")

    restored = boundary.execute_with_persistence(
        "set_object_rotation",
        {
            "file_name": str(path),
            "object_name": object_name,
            "rotation_degrees": original,
        },
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
        raise RuntimeError(f"fixture restoration failed: expected {original}, got {restored_rotation}")

    print("LIVE AUTONOMOUS RESTART VERIFIED")
    print(f"object={object_name}")
    print(f"after_restart={final_rotation}")
    print(f"authorization={resumed.authorization.authorization_id}")
    print("durable_checkpoint=verified")
    print("authorization_recovered=verified")
    print("fresh_verification=verified")
    print(f"fixture_restored={restored_rotation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("start", "resume"))
    parser.add_argument("--blend", default="atlas_live_mutation.blend")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--rotation", nargs=3, type=float, default=[0.0, 0.0, 15.0])
    parser.add_argument("--authorization-id", default="atlas-stage12-autonomous-restart")
    parser.add_argument("--state", required=False)
    args = parser.parse_args()

    if args.phase:
        if not args.state:
            raise SystemExit("--state is required with --phase")
        if args.phase == "start":
            _phase_start(args.blend, args.blender, args.object, list(args.rotation), args.authorization_id, args.state)
        else:
            _phase_resume(args.blend, args.blender, args.object, list(args.rotation), args.authorization_id, args.state)
        return 0

    with tempfile.TemporaryDirectory(prefix="atlas-autonomous-restart-") as directory:
        state_path = str(Path(directory) / "runtime.json")
        common = [
            "--blend", args.blend,
            "--blender", args.blender,
            "--object", args.object,
            "--rotation", *[str(value) for value in args.rotation],
            "--authorization-id", args.authorization_id,
            "--state", state_path,
        ]
        for phase in ("start", "resume"):
            completed = subprocess.run(
                [sys.executable, "-m", "scripts.run_live_autonomous_rotation_restart", "--phase", phase, *common],
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
