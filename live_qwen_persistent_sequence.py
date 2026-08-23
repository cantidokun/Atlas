"""Live multi-task Blender sequence with a real persisted checkpoint boundary."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import marker_task_definition
from planning.object_move_task import object_move_task_definition
from planning.task_checkpoint_store import TaskCheckpointStore
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from task_plan_authorization import authorize_task_plan
from tools.blender import create_empty_marker, inspect_object_collections, inspect_scene, move_object
from tools.blender_transform import inspect_object_transform
from live_qwen_marker_task import build_plan as build_marker_plan
from live_qwen_object_move import build_plan as build_move_plan

INCORRECT_FILE = "persistent_sequence_INCORRECT.blend"
CORRECT_FILE = "persistent_sequence_CORRECT.blend"
CHECKPOINT_FILE = "atlas_sequence_checkpoint.json"


def reduce_move(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence[-1])


def reduce_marker(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence:
        state.update(result)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect", "tampered-checkpoint"), required=True)
    parser.add_argument("--checkpoint", default=CHECKPOINT_FILE)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE
    store = TaskCheckpointStore(Path(args.checkpoint))

    from audit_trail import AuditTrail
    audit = AuditTrail()
    move_proposal = build_move_plan(file_name, audit)
    marker_proposal = build_marker_plan(file_name, audit)
    move_definition = object_move_task_definition(file_name)
    marker_definition = marker_task_definition(file_name)
    if tuple(move_proposal.evidence) != move_definition.evidence or tuple(move_proposal.actions) != move_definition.actions:
        raise RuntimeError("Qwen movement proposal does not match authorized task definition")
    if tuple(marker_proposal.evidence) != marker_definition.evidence or tuple(marker_proposal.actions) != marker_definition.actions:
        raise RuntimeError("Qwen marker proposal does not match authorized task definition")

    definitions = TaskSequenceDefinition((move_definition, marker_definition))
    proposals = {move_definition.name: move_proposal, marker_definition.name: marker_proposal}
    captures: Dict[str, Any] = {}

    def action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "move_object":
            raw = move_object(**arguments)
        elif tool == "create_empty_marker":
            raw = create_empty_marker(**arguments)
        else:
            raise RuntimeError(f"Unexpected sequence action: {tool}")
        status = raw.get("status")
        return {"ok": status in {"moved", "already_moved", "created", "already_exists"}, "state": str(status or "unknown"), "details": dict(raw)}

    boundary = BlenderExecutionBoundary(action)

    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_object_transform":
            return inspect_object_transform(**arguments)
        if tool == "inspect_scene":
            return inspect_scene(**arguments)
        if tool == "inspect_object_collections":
            return inspect_object_collections(**arguments)
        normalized, receipt = boundary.execute_with_receipt(tool, arguments)
        captures[tool] = {"normalized": normalized, "receipt": receipt}
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    def authorize(task) -> None:
        authorize_task_plan(proposals[task.name], evidence_complete=True, allowed_action_tools=task.allowed_action_tools, allow_writes=task.allow_writes)

    # Phase 1: execute movement and persist the exact checkpoint to disk.
    sequence = TaskSequenceSession(definitions, execute, (reduce_move, reduce_marker))
    first_checkpoint = sequence.run_current(
        authorization_id=f"live:persistent-sequence:{args.case}:movement",
        authorization_callback=authorize,
    )
    store.save(first_checkpoint)
    loaded = store.load()
    if loaded != first_checkpoint:
        raise RuntimeError("Persisted checkpoint did not round-trip exactly")

    if args.case == "tampered-checkpoint":
        tampered = dict(loaded)
        tampered["current_task"] = "TAMPERED"
        store.save(tampered)
        try:
            store.load_session(definitions, execute, (reduce_move, reduce_marker))
        except ValueError as exc:
            print("ATLAS PERSISTENT CHECKPOINT INTEGRITY: PASS")
            print(f"TAMPERED DISK CHECKPOINT REJECTED: {exc}")
            return
        raise RuntimeError("Tampered persisted checkpoint was accepted")

    # Phase 2: reconstruct the sequence from disk, simulating a process/session boundary.
    resumed = TaskSequenceSession.resume_from_checkpoint(
        definitions, execute, (reduce_move, reduce_marker), loaded
    )
    # Ensure the persisted state, not the original in-memory session, is the resume authority.
    if resumed.index != 1 or resumed.current_task is None:
        raise RuntimeError("Persisted checkpoint did not restore the expected task boundary")
    second_checkpoint = resumed.run_current(
        authorization_id=f"live:persistent-sequence:{args.case}:marker",
        authorization_callback=authorize,
    )
    if not resumed.complete or second_checkpoint["next_task_index"] != 2:
        raise RuntimeError("Persisted sequence did not complete after resume")

    print("ATLAS PERSISTENT MULTI-TASK SEQUENCE: PASS")
    print("DISK CHECKPOINT -> NEW SESSION -> RESUME -> MARKER -> VERIFY -> COMPLETE")


if __name__ == "__main__":
    main()
