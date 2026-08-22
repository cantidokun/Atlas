"""Live recovery proof: survive an interruption after Blender mutation but before task checkpoint."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import marker_task_definition
from planning.object_move_task import object_move_task_definition
from planning.task_checkpoint_store import TaskCheckpointStore
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.evidence_plan import EvidenceRequest
from planning.task_definition import AtlasTaskDefinition
from tools.blender import create_empty_marker, inspect_object_collections, inspect_scene, move_object
from tools.blender_transform import inspect_object_transform

FILE_NAME = "interrupted_sequence.blend"
CHECKPOINT = "interrupted_sequence_checkpoint.json"


def _move_reducer(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence[-1])


def _marker_reducer(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence:
        state.update(result)
    return state


def _initial_checkpoint(definition: TaskSequenceDefinition) -> Dict[str, Any]:
    return TaskSequenceSession(definition, lambda *_: {}, (_move_reducer, _marker_reducer)).checkpoint()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("interrupt-after-move", "resume"), required=True)
    parser.add_argument("--checkpoint", default=CHECKPOINT)
    args = parser.parse_args()

    move_task = object_move_task_definition(FILE_NAME)
    marker_task = marker_task_definition(FILE_NAME)
    definition = TaskSequenceDefinition((move_task, marker_task))
    store = TaskCheckpointStore(Path(args.checkpoint))

    def action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "move_object":
            result = move_object(**arguments)
        elif tool == "create_empty_marker":
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

    if args.case == "interrupt-after-move":
        store.save(_initial_checkpoint(definition))
        session = TaskSequenceSession.resume_from_checkpoint(definition, execute, (_move_reducer, _marker_reducer), store.load())
        task = session.current_task
        session.start_current().acquire_initial_evidence()
        target = session.start_current().evaluate_target()
        if target.satisfied:
            raise RuntimeError("fixture was unexpectedly already correct")
        session.authorize("live:interruption:movement")
        session.execute_authorized_action()
        print("ATLAS INTERRUPTION POINT: MOVE COMPLETED BEFORE TASK CHECKPOINT")
        raise SystemExit(17)

    resumed = TaskSequenceSession.resume_from_checkpoint(definition, execute, (_move_reducer, _marker_reducer), store.load())
    checkpoint = resumed.run_current(authorization_id="live:recovery:movement")
    store.save(checkpoint)
    final = TaskSequenceSession.resume_from_checkpoint(definition, execute, (_move_reducer, _marker_reducer), store.load())
    final.run_current(authorization_id="live:recovery:marker")
    if not final.complete:
        raise RuntimeError("recovery sequence did not complete")
    print("ATLAS INTERRUPTED MULTI-TASK RECOVERY: PASS")
    print("MUTATE -> PROCESS INTERRUPTION -> RELOAD BOUNDARY -> FRESH INSPECTION -> NO REPEAT WRITE -> MARKER -> COMPLETE")


if __name__ == "__main__":
    main()
