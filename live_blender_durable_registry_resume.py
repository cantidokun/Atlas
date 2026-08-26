"""Live proof of durable resume bound to a persisted canonical Digital Twin registry."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.digital_twin_identity import DigitalTwinIdentity, IdentityAnchor
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import RevisionKind, create_revision
from planning.production_task_checkpoint import ProductionTaskCheckpoint
from planning.durable_resumable_corrective_task import DurableResumableCorrectiveTask
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
        raise RuntimeError(f"unsupported live registry-resume tool: {tool}")
    status = raw.get("status")
    return {
        "ok": status in {"moved", "already_moved", "ok", "already_rotated", "rotated"},
        "state": str(status or "unknown"),
        "details": dict(raw),
    }


def _identity() -> DigitalTwinIdentity:
    return DigitalTwinIdentity(
        twin_id="twin:live-soccer-field",
        entity_type="soccer_field",
        anchors=(IdentityAnchor("venue", "field", "live-soccer-field"),),
    )


def _plan(file_name: str, object_name: str, rotation: list[float]):
    """Plan only when authoritative state is not already at the requested target."""
    def plan(evidence: dict[str, Any]):
        current = list(evidence.get("rotation_degrees", ()))
        if len(current) == 3 and all(abs(float(current[i]) - rotation[i]) <= 1e-5 for i in range(3)):
            return []
        return [
            ActionSpec(
                tool="set_object_rotation",
                arguments={
                    "file_name": file_name,
                    "object_name": object_name,
                    "rotation_degrees": list(rotation),
                },
            )
        ]
    return plan


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

    identity = _identity()
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision_v1 = create_revision(identity, "rev:live-001", 1, RevisionKind.RECONSTRUCTION)
    registry.register_revision(revision_v1)

    move = ActionSpec(
        tool="move_object",
        arguments={"file_name": args.file, "object_name": args.object, "location": list(args.location)},
    )
    boundary = BlenderExecutionBoundary(_execute)
    authorization = BlenderWriteAuthorization.issue(move, "live-registry:move")
    move_result, move_receipt = boundary.execute_authorized_write(move, authorization)
    if not move_result.ok or not move_receipt.matches_authorization(authorization.authorization_id):
        raise SystemExit("LIVE REGISTRY RESUME FAILED: initial mutation was not authorization-bound")

    checkpoint_evidence = _observe(args.file, args.object)
    checkpoint_v1 = ProductionTaskCheckpoint.create(
        "task:live-registry-resume-v1",
        revision_v1,
        (move,),
        checkpoint_evidence,
        "live-registry-lineage",
    )
    persisted_registry = registry.snapshot()
    reloaded_registry = DigitalTwinRegistry.from_snapshot(persisted_registry)

    revision_v2 = create_revision(
        identity, "rev:live-002", 2, RevisionKind.CORRECTION, source_revision=revision_v1
    )
    reloaded_registry.register_revision(revision_v2)

    stale_writes = {"count": 0}

    def stale_executor(tool: str, arguments: dict):
        stale_writes["count"] += 1
        return _execute(tool, arguments)

    stale_rejected = False
    try:
        DurableResumableCorrectiveTask(
            checkpoint_v1,
            revision_v1,
            lambda: _observe(args.file, args.object),
            _plan(args.file, args.object, list(args.final_rotation)),
            executor=stale_executor,
            registry=reloaded_registry,
        )
    except ValueError as exc:
        stale_rejected = "current canonical" in str(exc) or "canonical Digital Twin revision" in str(exc)

    checkpoint_v2 = ProductionTaskCheckpoint.create(
        "task:live-registry-resume-v2",
        revision_v2,
        (move,),
        _observe(args.file, args.object),
        "live-registry-lineage-v2",
    )
    interruption = set_object_rotation(
        file_name=args.file,
        object_name=args.object,
        rotation_degrees=list(args.interrupted_rotation),
    )
    interrupted_evidence = _observe(args.file, args.object)

    task = DurableResumableCorrectiveTask(
        checkpoint_v2,
        revision_v2,
        lambda: _observe(args.file, args.object),
        _plan(args.file, args.object, list(args.final_rotation)),
        executor=_execute,
        registry=reloaded_registry,
    )
    resume_result = task.resume(max_steps=4)
    final_evidence = _observe(args.file, args.object)

    checkpoint_integrity = (
        DigitalTwinRegistry.from_snapshot(persisted_registry).snapshot() == persisted_registry
    )
    target_matches = all(
        abs(float(final_evidence["rotation_degrees"][i]) - list(args.final_rotation)[i]) <= 1e-5
        for i in range(3)
    )

    output = {
        "file": args.file,
        "object": args.object,
        "registry_snapshot_integrity": checkpoint_integrity,
        "canonical_revision_before_advance": revision_v1.revision_id,
        "canonical_revision_after_advance": reloaded_registry.canonical_revision(revision_v2.twin_id).revision_id,
        "stale_checkpoint_rejected": stale_rejected,
        "stale_writes": stale_writes["count"],
        "interruption": _json_safe(interruption),
        "interrupted_evidence": interrupted_evidence,
        "resume_result": _json_safe(resume_result),
        "final_evidence": final_evidence,
        "target_matches": target_matches,
    }
    print("ATLAS BLENDER LIVE DURABLE REGISTRY RESUME")
    print(json.dumps(output, indent=2))

    if not checkpoint_integrity:
        raise SystemExit("LIVE REGISTRY RESUME FAILED: persisted registry did not survive reload intact")
    if not stale_rejected or stale_writes["count"] != 0:
        raise SystemExit("LIVE REGISTRY RESUME FAILED: stale canonical revision crossed the write boundary")
    if not resume_result.converged or not target_matches:
        raise SystemExit("LIVE REGISTRY RESUME FAILED: current-revision resume did not converge")

    print("ATLAS BLENDER LIVE REGISTRY STALE-REVISION ZERO-WRITE GATE: PASS")
    print("ATLAS BLENDER LIVE REGISTRY DURABLE RESUME: PASS")


if __name__ == "__main__":
    main()
