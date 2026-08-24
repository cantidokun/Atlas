"""Live Qwen Blender task: conditionally rotate an explicit object."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from audit_trail import AuditTrail
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.object_rotation_task import TARGET_OBJECT, TARGET_ROTATION, object_rotation_task_definition
from planning.task_runtime import TaskRuntimeSession
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender_transform import inspect_object_transform, set_object_rotation

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "object_rotation_CORRECT.blend"
INCORRECT_FILE = "object_rotation_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_object_transform", "set_object_rotation"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas Blender planning assistant.
Ensure {TARGET_OBJECT} in {file_name} has rotation degrees {TARGET_ROTATION}.
Return exactly one JSON object with exactly two top-level fields: evidence and actions.
Evidence: exactly one item with tool="inspect_object_transform", arguments containing file_name="{file_name}" and object_name="{TARGET_OBJECT}", and name="inspect_object_transform".
Actions: exactly one item with tool="set_object_rotation", arguments containing file_name="{file_name}", object_name="{TARGET_OBJECT}", rotation_degrees={TARGET_ROTATION}, and name="set_object_rotation".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY this JSON object:
{{
  "evidence": [{{"tool":"inspect_object_transform","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}"}},"name":"inspect_object_transform"}}],
  "actions": [{{"tool":"set_object_rotation","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}","rotation_degrees":{TARGET_ROTATION}}},"name":"set_object_rotation"}}]
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


def _reduce_rotation_evidence(evidence_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence_results[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    definition = object_rotation_task_definition(file_name)
    if tuple(proposal.evidence) != definition.evidence:
        raise RuntimeError("Qwen evidence plan does not match object rotation task definition")
    if tuple(proposal.actions) != definition.actions:
        raise RuntimeError("Qwen action plan does not match object rotation task definition")

    def blender_action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "set_object_rotation":
            raise RuntimeError(f"Unexpected rotation action: {tool}")
        raw = set_object_rotation(**arguments)
        status = raw.get("status")
        return {"ok": status in {"ok", "already_rotated"}, "state": str(status or "unknown"), "details": dict(raw)}

    action_boundary = BlenderExecutionBoundary(blender_action)
    live_gate = BlenderLiveWriteGate(action_boundary)
    capture: Dict[str, Any] = {}

    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_object_transform":
            return inspect_object_transform(**arguments)
        if tool != "set_object_rotation":
            raise RuntimeError(f"Unexpected rotation action: {tool}")
        action = definition.actions[0]
        if action.tool != tool or dict(action.arguments) != dict(arguments):
            raise RuntimeError("Rotation action does not match the declarative task definition")
        blender_authorization = BlenderWriteAuthorization.issue(action, capture["authorization_id"])
        outcome = live_gate.execute(action, blender_authorization)
        capture["outcome"] = outcome
        if outcome.status == "BLOCKED":
            raise RuntimeError(outcome.reason or "Authorized Blender write was blocked")
        normalized = outcome.verification["result"]
        capture["normalized"] = normalized
        capture["receipt"] = outcome.receipt
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    session = TaskRuntimeSession(definition, execute, _reduce_rotation_evidence)
    initial = session.acquire_initial_evidence()
    audit.record("evidence_batch", "initial", state=initial)
    state = session.evaluate_target()
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools=definition.allowed_action_tools, allow_writes=definition.allow_writes)
        authorization = session.authorize(f"live:object-rotation:{args.case}")
        capture["authorization_id"] = authorization.authorization_id
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        result = session.execute_authorized_action()
        action = definition.actions[0]
        if not capture["receipt"].matches(action.tool, action.arguments, capture["normalized"]):
            raise RuntimeError("Rotation execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized rotation action failed: {result}")

    final = session.acquire_post_action_evidence()
    final_state = session.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent rotation verification failed: {final_state.failed}")
    session.finalize()
    if not session.complete:
        raise RuntimeError(f"Object rotation task did not complete: {session.snapshot()}")

    print("ATLAS OBJECT ROTATION TASK: PASS")
    print("TARGET ALREADY CORRECT" if state.satisfied else "TARGET ROTATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
