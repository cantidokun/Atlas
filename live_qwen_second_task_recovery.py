"""Live Blender proof: recover Task 2 from the last known-good Task 1 checkpoint."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import marker_task_definition
from planning.object_move_task import object_move_task_definition
from planning.task_checkpoint_store import TaskCheckpointStore
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from tools.blender import create_empty_marker, inspect_object_collections, inspect_scene, move_object
from tools.blender_transform import inspect_object_transform

FILE_NAME = "second_task_recovery.blend"
CHECKPOINT = "second_task_recovery_checkpoint.json"


def move_reduce(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence[-1])


def marker_reduce(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence:
        state.update(result)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("prepare-and-interrupt", "recover"), required=True)
    parser.add_argument("--checkpoint", default=CHECKPOINT)
    args = parser.parse_args()

    move_task = object_move_task_definition(FILE_NAME)
    marker_task = marker_task_definition(FILE_NAME)
    definition = TaskSequenceDefinition((move_task, marker_task))
    store = TaskCheckpointStore(Path(args.checkpoint))
    writes = {"move_object": 0, "create_empty_marker": 0}

    def action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "move_object":
            writes[tool] += 1
            result = move_object(**arguments)
        elif tool == "create_empty_marker":
            writes[tool] += 1
            result = create_empty_marker(**arguments)
        else:
            raise RuntimeError(f"unexpected action: {tool}")
        return {"ok": result.get("status") in {"moved", "already_moved", "created", "already_exists"}, "state": result.get("status", "unknown"), "details": result}

    boundary = BlenderExecutionBoundary(action)

    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_object_transform":
            return inspect_object_transform(**arguments)
        if tool == "inspect_scene":
            return inspect_scene(**arguments)
        if tool == "inspect_object_collections":
            return inspect_object_collections(**arguments)
        normalized, receipt = boundary.execute_with_receipt(tool, arguments)
        return {"ok": normalized.ok, "state": normalized.state, "details": {**normalized.details, "receipt": receipt}}

    if args.case == "prepare-and-interrupt":
        session = TaskSequenceSession(definition, execute, (move_reduce, marker_reduce))
        first_checkpoint = session.run_current(authorization_id="live:second-task:move")
        store.save(first_checkpoint)
        resumed = TaskSequenceSession.resume_from_checkpoint(
            definition, execute, (move_reduce, marker_reduce), store.load()
        )
        resumed.start_current().acquire_initial_evidence()
        target = resumed.start_current().evaluate_target()
        if target.satisfied:
            raise RuntimeError("marker fixture was unexpectedly already correct")
        resumed.authorize("live:second-task:marker")
        resumed.execute_authorized_action()
        print("ATLAS SECOND-TASK INTERRUPTION POINT: MARKER MUTATED BEFORE CHECKPOINT")
        print("EXPECTED PROCESS BOUNDARY: PASS")
        return

    recovered = TaskSequenceSession.resume_from_checkpoint(
        definition, execute, (move_reduce, marker_reduce), store.load()
    )
    checkpoint = recovered.recover_current(authorization_id="must-not-be-needed")
    if writes["create_empty_marker"] != 0:
        raise RuntimeError("recovery repeated marker creation")
    store.save(checkpoint)
    final = TaskSequenceSession.resume_from_checkpoint(
        definition, execute, (move_reduce, marker_reduce), store.load()
    )
    if not final.complete:
        raise RuntimeError("second-task recovery did not reach completion")
    print("ATLAS SECOND-TASK RECOVERY: PASS")
    print("TASK 1 CHECKPOINT -> TASK 2 INTERRUPTION -> RESTART -> FRESH INSPECTION -> NO DUPLICATE WRITE -> COMPLETE")


if __name__ == "__main__":
    main()
