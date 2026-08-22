"""Live multi-task proof using Qwen proposals and the shared TaskSequenceSession."""
import argparse
import json
from typing import Any, Dict, List

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import marker_task_definition
from planning.object_move_task import object_move_task_definition
from planning.task_sequence import TaskSequenceDefinition, TaskSequenceSession
from task_plan_authorization import authorize_task_plan
from tools.blender import create_empty_marker, inspect_scene
from tools.blender_transform import inspect_object_transform, move_object
from live_qwen_marker_task import build_plan as build_marker_plan
from live_qwen_object_move import build_plan as build_move_plan

INCORRECT_FILE = "sequence_INCORRECT.blend"
CORRECT_FILE = "sequence_CORRECT.blend"


def reduce_move(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence[-1])


def reduce_marker(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence:
        state.update(result)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    from audit_trail import AuditTrail
    audit = AuditTrail()
    move_proposal = build_move_plan(file_name, audit)
    marker_proposal = build_marker_plan(file_name, audit)
    move_definition = object_move_task_definition(file_name)
    marker_definition = marker_task_definition(file_name)

    if tuple(move_proposal.evidence) != move_definition.evidence or tuple(move_proposal.actions) != move_definition.actions:
        raise RuntimeError("Qwen movement proposal does not match its authorized task definition")
    if tuple(marker_proposal.evidence) != marker_definition.evidence or tuple(marker_proposal.actions) != marker_definition.actions:
        raise RuntimeError("Qwen marker proposal does not match its authorized task definition")

    proposals = {move_definition.name: move_proposal, marker_definition.name: marker_proposal}
    definitions = TaskSequenceDefinition((move_definition, marker_definition))
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
            from tools.blender import inspect_object_collections
            return inspect_object_collections(**arguments)
        normalized, receipt = boundary.execute_with_receipt(tool, arguments)
        captures[tool] = {"normalized": normalized, "receipt": receipt}
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    sequence = TaskSequenceSession(
        definitions,
        execute,
        (reduce_move, reduce_marker),
    )

    def authorize(task) -> None:
        proposal = proposals[task.name]
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools=task.allowed_action_tools,
            allow_writes=task.allow_writes,
        )

    first_checkpoint = sequence.run_current(
        authorization_id=f"live:sequence:{args.case}:movement",
        authorization_callback=authorize,
    )
    if first_checkpoint["next_task_index"] != 1:
        raise RuntimeError(f"Sequence did not advance after verified movement: {first_checkpoint}")

    if args.case == "incorrect":
        capture = captures.get("move_object")
        if not capture or not capture["receipt"].matches(move_definition.actions[0].tool, move_definition.actions[0].arguments, capture["normalized"]):
            raise RuntimeError("Movement receipt was missing or mismatched")

    second_checkpoint = sequence.run_current(
        authorization_id=f"live:sequence:{args.case}:marker",
        authorization_callback=authorize,
    )
    if not sequence.complete or second_checkpoint["next_task_index"] != 2:
        raise RuntimeError(f"Sequence did not complete after independently verified tasks: {second_checkpoint}")

    if args.case == "incorrect":
        capture = captures.get("create_empty_marker")
        if not capture or not capture["receipt"].matches(marker_definition.actions[0].tool, marker_definition.actions[0].arguments, capture["normalized"]):
            raise RuntimeError("Marker receipt was missing or mismatched")

    print("ATLAS MULTI-TASK SEQUENCE: PASS")
    print("TWO TASKS VERIFIED WITH ZERO-WRITE FIRST TASK" if args.case == "already-correct" else "MOVE -> VERIFY -> MARKER CREATE -> VERIFY -> COMPLETE")
    print(json.dumps({"case": args.case, "checkpoint_after_move": first_checkpoint, "final_checkpoint": second_checkpoint}, indent=2))


if __name__ == "__main__":
    main()
