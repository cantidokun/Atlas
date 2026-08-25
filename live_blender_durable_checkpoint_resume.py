"""Live Blender proof of durable checkpoint reload and safe resume."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.continuation_resume import ContinuationState
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.replan_authorization import ReplanAuthorization
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
        raise RuntimeError(f"unsupported live checkpoint tool: {tool}")
    status = raw.get("status")
    return {
        "ok": status in {"moved", "already_moved", "ok", "already_rotated", "rotated"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _revision(twin_id: str):
    identity = DigitalTwinIdentity(
        twin_id=twin_id,
        entity_type="soccer_field",
        anchors=(IdentityAnchor("venue", "field", twin_id),),
    )
    return create_revision(identity, "rev:live-001", 1, RevisionKind.CORRECTION)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="object_move_INCORRECT.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    parser.add_argument("--location", nargs=3, type=float, default=[1.0, 2.0, 3.0])
    parser.add_argument("--interrupted-rotation", nargs=3, type=float, default=[91.0, 92.0, 93.0])
    parser.add_argument("--final-rotation", nargs=3, type=float, default=[10.0, 20.0, 30.0])
    args = parser.parse_args()

    if not Path(args.file).exists():
        raise SystemExit(f"missing Blender fixture: {args.file}")

    revision = _revision("twin:live-soccer-field")
    first = ActionSpec(
        tool="move_object",
        arguments={"file_name": args.file, "object_name": args.object, "location": list(args.location)},
    )
    remaining = ActionSpec(
        tool="set_object_rotation",
        arguments={"file_name": args.file, "object_name": args.object, "rotation_degrees": list(args.final_rotation)},
    )

    evidence_v1 = _observe(args.file, args.object)
    first_auth = BlenderWriteAuthorization.issue(first, "live-durable:first")
    boundary = BlenderExecutionBoundary(_execute)
    first_result, first_receipt = boundary.execute_authorized_write(first, first_auth)
    if not first_result.ok or not first_receipt.matches_authorization(first_auth.authorization_id):
        raise SystemExit("LIVE DURABLE CHECKPOINT FAILED: first write was not authorization-bound")

    checkpoint_evidence = _observe(args.file, args.object)
    checkpoint = ProductionTaskCheckpoint.create(
        "task:live-durable-resume",
        revision,
        (first,),
        checkpoint_evidence,
        "live-durable-lineage",
    )
    persisted = checkpoint.snapshot()
    reloaded = ProductionTaskCheckpoint.from_snapshot(persisted, revision)

    interruption = set_object_rotation(
        file_name=args.file,
        object_name=args.object,
        rotation_degrees=list(args.interrupted_rotation),
    )
    fresh_evidence = _observe(args.file, args.object)

    stale_writes = {"count": 0}

    def stale_executor(tool: str, arguments: dict):
        stale_writes["count"] += 1
        return _execute(tool, arguments)

    stale_boundary = BlenderExecutionBoundary(stale_executor)
    stale_auth = ReplanAuthorization.issue(checkpoint_evidence, [remaining], "live-durable-stale")
    stale_replan = type("StaleReplan", (), {"actions": [remaining], "authorization": stale_auth})()
    stale_rejected = False
    try:
        stale_boundary.execute_authorized_replan(stale_replan, fresh_evidence)
    except RuntimeError:
        stale_rejected = True

    fresh_auth = ReplanAuthorization.issue(fresh_evidence, [remaining], "live-durable-resume")
    fresh_replan = type("FreshReplan", (), {"actions": [remaining], "authorization": fresh_auth})()
    resume_result, resume_receipt = boundary.execute_authorized_replan(fresh_replan, fresh_evidence)
    final_evidence = _observe(args.file, args.object)

    target_matches = (
        final_evidence["location"] == list(args.location)
        and all(abs(float(final_evidence["rotation_degrees"][i]) - list(args.final_rotation)[i]) <= 1e-5 for i in range(3))
    )
    checkpoint_integrity = reloaded.snapshot() == persisted
    resume_receipt_bound = resume_receipt.matches_authorization(fresh_auth.authorization_id)

    output = {
        "file": args.file,
        "object": args.object,
        "checkpoint_integrity": checkpoint_integrity,
        "interruption": _json_safe(interruption),
        "stale_authorization_rejected": stale_rejected,
        "stale_writes": stale_writes["count"],
        "resume_result": _json_safe(resume_result),
        "resume_receipt_bound": resume_receipt_bound,
        "final_evidence": final_evidence,
        "target_matches": target_matches,
    }
    print("ATLAS BLENDER LIVE DURABLE CHECKPOINT / RESUME")
    print(json.dumps(output, indent=2))

    if not checkpoint_integrity:
        raise SystemExit("LIVE DURABLE CHECKPOINT FAILED: checkpoint did not survive reload intact")
    if not stale_rejected or stale_writes["count"] != 0:
        raise SystemExit("LIVE DURABLE CHECKPOINT FAILED: stale checkpoint path was not zero-write")
    if not resume_result.ok or not target_matches:
        raise SystemExit("LIVE DURABLE CHECKPOINT FAILED: resumed task did not reach target state")
    if not resume_receipt_bound:
        raise SystemExit("LIVE DURABLE CHECKPOINT FAILED: resumed receipt is not authorization-bound")

    print("ATLAS BLENDER LIVE DURABLE CHECKPOINT STALE-STATE ZERO-WRITE GATE: PASS")
    print("ATLAS BLENDER LIVE DURABLE CHECKPOINT RESUME: PASS")


if __name__ == "__main__":
    main()
