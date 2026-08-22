"""Live Qwen Blender task: conditionally create an explicit Atlas marker."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from audit_trail import AuditTrail
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import MARKER_COLLECTION, MARKER_OBJECT, marker_task_definition
from planning.task_runtime import TaskRuntimeSession
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_scene, create_empty_marker
from tools.blender_collection import inspect_object_collections

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "marker_task_CORRECT.blend"
INCORRECT_FILE = "marker_task_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_scene", "inspect_object_collections", "create_empty_marker"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas Blender planning assistant.
Ensure Blender object {MARKER_OBJECT} exists as an EMPTY in the {MARKER_COLLECTION} collection in {file_name}.
Return exactly one JSON object with exactly two top-level fields: evidence and actions.
Evidence must contain exactly two items, in this order:
1. tool="inspect_scene", arguments={{"file_name":"{file_name}"}}, name="inspect_scene"
2. tool="inspect_object_collections", arguments={{"file_name":"{file_name}","object_name":"{MARKER_OBJECT}"}}, name="inspect marker collection membership"
Actions must contain exactly one item with tool="create_empty_marker", arguments containing file_name="{file_name}", collection_name="{MARKER_COLLECTION}", object_name="{MARKER_OBJECT}", and name="create Atlas_Marker".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY this JSON object:
{{
  "evidence": [
    {{"tool":"inspect_scene","arguments":{{"file_name":"{file_name}"}},"name":"inspect_scene"}},
    {{"tool":"inspect_object_collections","arguments":{{"file_name":"{file_name}","object_name":"{MARKER_OBJECT}"}},"name":"inspect marker collection membership"}}
  ],
  "actions": [{{"tool":"create_empty_marker","arguments":{{"file_name":"{file_name}","collection_name":"{MARKER_COLLECTION}","object_name":"{MARKER_OBJECT}"}},"name":"create Atlas_Marker"}}]
}}'''


def ask(messages: List[Dict[str, str]]) -> str:
    response = requests.post(OLLAMA_URL, json={"model": MODEL, "messages": messages, "stream": False, "format": TASK_PLAN_JSON_SCHEMA}, timeout=120)
    response.raise_for_status()
    return response.json()["message"]["content"]


def build_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    messages = [{"role": "system", "content": prompt(file_name)}, {"role": "user", "content": "Create the structured Atlas task plan."}]
    last: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            raw = ask(messages)
        except requests.exceptions.ReadTimeout as exc:
            last = exc
            audit.record_qwen_proposal("", attempt, False, f"ReadTimeout: {exc}")
            if attempt < 3:
                continue
            raise RuntimeError(f"Qwen plan timed out after {attempt} attempts: {last}") from exc
        print(f"--- QWEN PLAN ATTEMPT {attempt} ---")
        print(raw)
        try:
            proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
        except (TaskPlanValidationError, TypeError, ValueError) as exc:
            proposal = None
            last = exc
        audit.record_qwen_proposal(raw, attempt, proposal is not None, None if proposal is not None else str(last))
        if proposal is not None:
            return proposal
        messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": correction(file_name)}]
    raise RuntimeError(f"Qwen plan rejected: {last}")


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool == "inspect_scene":
        return inspect_scene(**arguments)
    if tool == "inspect_object_collections":
        return inspect_object_collections(**arguments)
    raise RuntimeError(f"Unexpected evidence tool: {tool}")


def boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "create_empty_marker":
            raise RuntimeError(f"Unexpected marker action: {tool}")
        raw = create_empty_marker(**arguments)
        status = raw.get("status")
        return {"ok": status in {"created", "already_exists"}, "state": str(status or "unknown"), "details": dict(raw)}
    return BlenderExecutionBoundary(execute)


def _reduce_marker_evidence(evidence_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence_results:
        state.update(result)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    definition = marker_task_definition(file_name)
    if tuple(proposal.evidence) != definition.evidence:
        raise RuntimeError("Qwen evidence plan does not match marker task definition")
    if tuple(proposal.actions) != definition.actions:
        raise RuntimeError("Qwen action plan does not match marker task definition")

    execution_boundary = boundary()
    capture: Dict[str, Any] = {}

    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool in {request.tool for request in definition.evidence}:
            return evidence(tool, arguments)
        normalized, receipt = execution_boundary.execute_with_receipt(tool, arguments)
        capture["receipt"] = receipt
        capture["normalized"] = normalized
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    session = TaskRuntimeSession(definition, execute, _reduce_marker_evidence)
    initial = session.acquire_initial_evidence()
    audit.record("evidence_batch", "initial", state=initial)
    state = session.evaluate_target()
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools=definition.allowed_action_tools, allow_writes=definition.allow_writes)
        authorization = session.authorize(f"live:marker-creation:{args.case}")
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        result = session.execute_authorized_action()
        action = definition.actions[0]
        if not capture["receipt"].matches(action.tool, action.arguments, capture["normalized"]):
            raise RuntimeError("Marker execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized marker action failed: {result}")

    final = session.acquire_post_action_evidence()
    final_state = session.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent marker verification failed: {final_state.failed}")
    session.finalize()
    if not session.complete:
        raise RuntimeError(f"Marker task did not complete: {session.snapshot()}")

    print("ATLAS MARKER TASK: PASS")
    print("TARGET ALREADY SATISFIED" if state.satisfied else "MARKER CREATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
