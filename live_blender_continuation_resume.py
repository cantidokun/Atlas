"""Live Blender interruption/resume proof for corrective continuation."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from action_plan import ActionSpec
from planning.blender_result_contract import normalize_blender_result
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.continuation_resume import ContinuationState
from planning.replan_authorization import ReplanAuthorization
from planning.blender_execution_boundary import BlenderExecutionBoundary
from tools.blender import move_object
from tools.blender_transform import inspect_object_transform, set_object_rotation


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _observe(file_name: str, object_name: str):
    observed = inspect_object_transform(file_name=file_name, object_name=object_name)
    if observed.get("status") != "ok":
        raise RuntimeError(f"authoritative observation failed: {observed}")
    return {
        "file_name": file_name,
        "object_name": object_name,
        "location": list(observed["location"]),
        "rotation_degrees": list(observed["rotation_degrees"]),
    }


def _execute(tool: str, arguments: dict):
    if tool == "move_object":
        raw = move_object(**arguments)
    elif tool == "set_object_rotation":
        raw = set_object_rotation(**arguments)
    else:
        raise RuntimeError(f"unsupported live continuation tool: {tool}")
    status = raw.get("status")
    return {
        "ok": status in {"moved", "already_moved", "ok", "already_rotated", "rotated"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="object_move_INCORRECT.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--location", nargs=3, type=float, default=[1.0, 2.0, 3.0])
    parser.add_argument("--interrupted-rotation", nargs=3, type=float, default=[91.0, 92.0, 93.0])
    parser.add_argument("--final-rotation", nargs=3, type=float, default=[10.0, 20.0, 30.0])
    args = parser.parse_args()

    file_name = args.file
    object_name = args.object
    target_location = list(args.location)
    interrupted_rotation = list(args.interrupted_rotation)
    final_rotation = list(args.final_rotation)

    # V1: observe and execute the first production mutation.
    evidence_v1 = _observe(file_name, object_name)
    move = ActionSpec(
        tool="move_object",
        arguments={
            "file_name": file_name,
            "object_name": object_name,
            "location": target_location,
        },
    )
    rotation = ActionSpec(
        tool="set_object_rotation",
        arguments={
            "file_name": file_name,
            "object_name": object_name,
            "rotation_degrees": final_rotation,
        },
    )
    first_authorization = BlenderWriteAuthorization.issue(move, "live-resume:first")
    boundary = BlenderExecutionBoundary(_execute)
    first_result, first_receipt = boundary.execute_authorized_write(move, first_authorization)
    if not first_result.ok or not first_receipt.matches_authorization(first_authorization.authorization_id):
        raise SystemExit("LIVE CONTINUATION FAILED: first authorized write was not receipt-bound")

    # Save the checkpoint immediately after operation 1.
    checkpoint_evidence = _observe(file_name, object_name)
    checkpoint = ContinuationState.create(
        "live:blender-resume",
        [move],
        checkpoint_evidence,
        "live-resume",
    )

    # Real interruption: mutate the same Blender file externally.
    interruption_raw = set_object_rotation(
        file_name=file_name,
        object_name=object_name,
        rotation_degrees=interrupted_rotation,
    )
    interrupted_evidence = _observe(file_name, object_name)

    stale_writes = {"count": 0}

    def stale_executor(tool: str, arguments: dict):
        stale_writes["count"] += 1
        return _execute(tool, arguments)

    stale_boundary = BlenderExecutionBoundary(stale_executor)
    stale_replan = type(
        "StaleReplan",
        (),
        {
            "actions": [rotation],
            "authorization": ReplanAuthorization.issue(
                checkpoint_evidence,
                [rotation],
                "live-resume:stale",
            ),
        },
    )()

    stale_rejected = False
    stale_error = None
    try:
        stale_boundary.execute_authorized_replan(stale_replan, interrupted_evidence)
    except RuntimeError as exc:
        stale_rejected = True
        stale_error = str(exc)

    # Resume only from fresh evidence. The saved authorization is never reused.
    fresh_authorization = checkpoint.authorize_remaining(interrupted_evidence, [rotation])
    resume_result, resume_receipt = boundary.execute_authorized_replan(
        type("ResumeReplan", (), {"actions": [rotation], "authorization": fresh_authorization})(),
        interrupted_evidence,
    )
    final_evidence = _observe(file_name, object_name)

    target_matches = (
        final_evidence["location"] == target_location
        and all(abs(float(final_evidence["rotation_degrees"][i]) - final_rotation[i]) <= 1e-5 for i in range(3))
    )

    output = {
        "file": file_name,
        "object": object_name,
        "first_result": _json_safe(first_result),
        "first_receipt_bound": first_receipt.matches_authorization(first_authorization.authorization_id),
        "checkpoint_evidence": checkpoint_evidence,
        "interruption": _json_safe(interruption_raw),
        "interrupted_evidence": interrupted_evidence,
        "stale_authorization_rejected": stale_rejected,
        "stale_authorization_error": stale_error,
        "stale_executor_writes": stale_writes["count"],
        "fresh_authorization": fresh_authorization.snapshot(),
        "resume_result": _json_safe(resume_result),
        "resume_receipt_bound": resume_receipt.matches_authorization(fresh_authorization.authorization_id),
        "final_evidence": final_evidence,
        "target_matches": target_matches,
    }

    print("ATLAS BLENDER LIVE CONTINUATION / RESUME")
    print(json.dumps(output, indent=2))

    if not stale_rejected or stale_writes["count"] != 0:
        raise SystemExit("LIVE CONTINUATION FAILED: stale continuation was not blocked with zero writes")
    if not resume_result.ok or not target_matches:
        raise SystemExit("LIVE CONTINUATION FAILED: fresh resume did not reach authoritative target state")
    if not resume_receipt.matches_authorization(fresh_authorization.authorization_id):
        raise SystemExit("LIVE CONTINUATION FAILED: resumed write receipt is not authorization-bound")

    print("ATLAS BLENDER LIVE CONTINUATION STALE-STATE ZERO-WRITE GATE: PASS")
    print("ATLAS BLENDER LIVE CONTINUATION RESUME: PASS")


if __name__ == "__main__":
    main()
