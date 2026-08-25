"""Live Blender probe for production-facing multi-operation corrective composition.

The probe composes two already-proven production Blender mutations in one
scene, injects a real world-state interruption between them, proves the
pre-interruption corrective authorization is rejected before the executor can
write, then allows the generalized runtime to observe fresh state and issue a
replacement authorization.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Tuple

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.replan_authorization import ReplanAuthorization
from planning.production_multi_operation_corrective_task import ProductionMultiOperationCorrectiveTask
from tools.blender import move_object
from tools.blender_transform import inspect_object_transform, set_object_rotation


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _move_action(file_name: str, object_name: str, location: list[float]) -> ActionSpec:
    return ActionSpec(
        tool="move_object",
        arguments={
            "file_name": file_name,
            "object_name": object_name,
            "location": list(location),
        },
    )


def _rotation_action(file_name: str, object_name: str, rotation: list[float]) -> ActionSpec:
    return ActionSpec(
        tool="set_object_rotation",
        arguments={
            "file_name": file_name,
            "object_name": object_name,
            "rotation_degrees": list(rotation),
        },
    )


def _execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool == "move_object":
        raw = move_object(**arguments)
    elif tool == "set_object_rotation":
        raw = set_object_rotation(**arguments)
    else:
        raise RuntimeError(f"live composition probe does not permit {tool}")
    status = raw.get("status")
    return {
        "ok": status in {"moved", "already_moved", "ok", "already_rotated"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _observe(file_name: str, object_name: str) -> Dict[str, Any]:
    observed = inspect_object_transform(file_name=file_name, object_name=object_name)
    if observed.get("status") != "ok":
        raise RuntimeError(f"authoritative observation failed: {observed}")
    return {
        "location": list(observed["location"]),
        "rotation_degrees": list(observed["rotation_degrees"]),
    }


def _verify(action: ActionSpec, _receipt: Any) -> Tuple[bool, Dict[str, Any]]:
    observed = inspect_object_transform(
        file_name=action.arguments["file_name"],
        object_name=action.arguments["object_name"],
    )
    if observed.get("status") != "ok":
        return False, {"authoritative": observed}
    if action.tool == "move_object":
        expected = [float(value) for value in action.arguments["location"]]
        actual = observed.get("location")
        key = "location"
    elif action.tool == "set_object_rotation":
        expected = [float(value) for value in action.arguments["rotation_degrees"]]
        actual = observed.get("rotation_degrees")
        key = "rotation_degrees"
    else:
        return False, {"unsupported_tool": action.tool}
    matches = isinstance(actual, list) and len(actual) == 3 and all(
        abs(float(actual[i]) - expected[i]) <= 1e-5 for i in range(3)
    )
    return matches, {"authoritative": observed, f"{key}_matches": matches}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="atlas_live_mutation.blend")
    parser.add_argument("--object", default="Cube")
    parser.add_argument("--location", nargs=3, type=float, default=[1.0, 2.0, 3.0])
    parser.add_argument("--rotation", nargs=3, type=float, default=[10.0, 20.0, 30.0])
    parser.add_argument("--interrupted-rotation", nargs=3, type=float, default=[91.0, 92.0, 93.0])
    args = parser.parse_args()

    file_name = args.file
    object_name = args.object
    target_location = list(args.location)
    target_rotation = list(args.rotation)
    interrupted_rotation = list(args.interrupted_rotation)

    state = _observe(file_name, object_name)
    move = _move_action(file_name, object_name, target_location)
    rotate = _rotation_action(file_name, object_name, target_rotation)
    pre_interruption_evidence = dict(state)
    stale_replan = ReplanAuthorization.issue(
        pre_interruption_evidence,
        [rotate],
        "live:multi-operation:stale",
    )

    stale_write_count = {"writes": 0}

    def counting_executor(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        stale_write_count["writes"] += 1
        return _execute(tool, arguments)

    stale_boundary = BlenderExecutionBoundary(counting_executor)
    stale_replan_request = type("StaleReplan", (), {"actions": [rotate], "authorization": stale_replan})()

    # Operation 1: execute through the protected production boundary.
    first_authorization = BlenderWriteAuthorization.issue(move, "live:multi-operation:first")
    first_boundary = BlenderExecutionBoundary(_execute)
    first_result, first_receipt = first_boundary.execute_authorized_write(move, first_authorization)

    # Real external interruption: mutate the same Blender scene outside the
    # corrective task so the next observation is genuinely different.
    interruption_raw = set_object_rotation(
        file_name=file_name,
        object_name=object_name,
        rotation_degrees=interrupted_rotation,
    )

    interrupted_evidence = _observe(file_name, object_name)
    stale_rejected = False
    stale_error = None
    try:
        stale_boundary.execute_authorized_replan(stale_replan_request, interrupted_evidence)
    except RuntimeError as exc:
        stale_rejected = True
        stale_error = str(exc)

    # Fresh production composition: the generalized runtime observes the
    # interrupted world and authorizes the replacement operation against it.
    def observe() -> Dict[str, Any]:
        return _observe(file_name, object_name)

    def plan(evidence: Dict[str, Any]):
        actions = []
        if evidence["location"] != target_location:
            actions.append(move)
        if evidence["rotation_degrees"] != target_rotation:
            actions.append(rotate)
        return actions

    task = ProductionMultiOperationCorrectiveTask(
        observe,
        plan,
        "live:multi-operation:fresh",
        executor=BlenderExecutionBoundary(_execute),
    )
    result = task.run(max_steps=4)
    final_state = _observe(file_name, object_name)

    output = {
        "file": file_name,
        "object": object_name,
        "first_operation": _json_safe(first_result),
        "first_receipt_present": first_receipt is not None,
        "external_interruption": _json_safe(interruption_raw),
        "pre_interruption_evidence": pre_interruption_evidence,
        "interrupted_evidence": interrupted_evidence,
        "stale_authorization_rejected": stale_rejected,
        "stale_authorization_error": stale_error,
        "stale_executor_writes": stale_write_count["writes"],
        "fresh_runtime_converged": bool(result.converged),
        "fresh_runtime_receipts": len(result.receipts),
        "final_state": final_state,
        "target_location": target_location,
        "target_rotation": target_rotation,
    }

    print("ATLAS BLENDER LIVE MULTI-OPERATION CORRECTIVE COMPOSITION")
    print(json.dumps(output, indent=2))

    if not stale_rejected or stale_write_count["writes"] != 0:
        raise SystemExit("LIVE COMPOSITION FAILED: stale authorization was not blocked with zero writes")
    if not result.converged:
        raise SystemExit("LIVE COMPOSITION FAILED: fresh corrective runtime did not converge")
    if final_state["location"] != target_location or final_state["rotation_degrees"] != target_rotation:
        raise SystemExit("LIVE COMPOSITION FAILED: final authoritative state is incorrect")
    if len(result.receipts) < 1:
        raise SystemExit("LIVE COMPOSITION FAILED: fresh corrective execution produced no receipt")

    print("ATLAS BLENDER LIVE MULTI-OPERATION COMPOSITION: PASS")
    print("ATLAS BLENDER LIVE STALE AUTHORIZATION ZERO-WRITE GATE: PASS")


if __name__ == "__main__":
    main()
