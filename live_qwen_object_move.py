"""Live Qwen Blender task: conditionally move an explicit object."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from audit_trail import AuditTrail
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_tool_adapter import BlenderToolAdapter
from planning.object_move_task import TARGET_LOCATION, TARGET_OBJECT, object_move_task_definition
from planning.task_runtime import TaskRuntimeSession
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "object_move_CORRECT.blend"
INCORRECT_FILE = "object_move_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_object_transform", "move_object"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas Blender planning assistant.
Ensure {TARGET_OBJECT} in {file_name} has location {TARGET_LOCATION}.
Return exactly one JSON object with exactly two top-level fields: evidence and actions.
Evidence: exactly one item with tool="inspect_object_transform", arguments containing file_name="{file_name}" and object_name="{TARGET_OBJECT}", and name="inspect_object_transform".
Actions: exactly one item with tool="move_object", arguments containing file_name="{file_name}", object_name="{TARGET_OBJECT}", location={TARGET_LOCATION}, and name="move_object".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY this JSON object:
{{
  "evidence": [{{"tool":"inspect_object_transform","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}"}},"name":"inspect_object_transform"}}],
  "actions": [{{"tool":"move_object","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}","location":{TARGET_LOCATION}}},"name":"move_object"}}]
}}'''


def ask(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False, "format": TASK_PLAN_JSON_SCHEMA},
        timeout=120,
    )
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


def _reduce_move_evidence(evidence_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(evidence_results[-1])


def _as_runtime_result(result: Any) -> Dict[str, Any]:
    return {"ok": result.ok, "state": result.state, "details": dict(result.details)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    definition = object_move_task_definition(file_name)
    if tuple(proposal.evidence) != definition.evidence:
        raise RuntimeError("Qwen evidence plan does not match object movement task definition")
    if tuple(proposal.actions) != definition.actions:
        raise RuntimeError("Qwen action plan does not match object movement task definition")

    adapter = BlenderToolAdapter()

    def blender_action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "move_object":
            raise RuntimeError(f"Unexpected movement action: {tool}")
        return _as_runtime_result(adapter(tool, arguments))

    action_boundary = BlenderExecutionBoundary(blender_action)
    capture: Dict[str, Any] = {}

    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "inspect_object_transform":
            # Preserve the existing evidence shape consumed by the generic
            # TaskRuntimeSession; the adapter's canonical envelope is only an
            # internal normalization boundary here.
            normalized = adapter(tool, arguments)
            if not isinstance(normalized.state, dict):
                raise RuntimeError("Object transform evidence must be an object")
            return dict(normalized.state)
        normalized, receipt = action_boundary.execute_with_receipt(tool, arguments)
        capture["normalized"] = normalized
        capture["receipt"] = receipt
        return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

    session = TaskRuntimeSession(definition, execute, _reduce_move_evidence)
    initial = session.acquire_initial_evidence()
    audit.record("evidence_batch", "initial", state=initial)
    state = session.evaluate_target()
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools=definition.allowed_action_tools, allow_writes=definition.allow_writes)
        authorization = session.authorize(f"live:object-move:{args.case}")
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        result = session.execute_authorized_action()
        action = definition.actions[0]
        if not capture["receipt"].matches(action.tool, action.arguments, capture["normalized"]):
            raise RuntimeError("Movement execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized movement action failed: {result}")

    final = session.acquire_post_action_evidence()
    final_state = session.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent movement verification failed: {final_state.failed}")
    session.finalize()
    if not session.complete:
        raise RuntimeError(f"Object movement task did not complete: {session.snapshot()}")

    print("ATLAS OBJECT MOVEMENT TASK: PASS")
    print("TARGET ALREADY CORRECT" if state.satisfied else "TARGET MOVED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
