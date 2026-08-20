"""Live Qwen Blender task: conditionally create an explicit Atlas marker."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from audit_trail import AuditTrail
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.marker_task import (
    MARKER_OBJECT,
    marker_task_definition,
)
from planning.task_runtime import prepare_task_runtime
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_scene, create_empty_marker

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "marker_task_CORRECT.blend"
INCORRECT_FILE = "marker_task_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_scene", "create_empty_marker"}


def prompt(file_name: str) -> str:
    definition = marker_task_definition(file_name)
    action = definition.actions[0]
    return f'''You are the Atlas Blender planning assistant.
Ensure Blender object {MARKER_OBJECT} exists as an EMPTY in the Atlas_Test collection in {file_name}.
Return exactly one JSON object with exactly two top-level fields: evidence and actions.
Evidence: exactly one item with tool="inspect_scene", arguments containing file_name="{file_name}", and name="inspect_scene".
Actions: exactly one item with tool="create_empty_marker", arguments containing file_name="{file_name}", collection_name="Atlas_Test", object_name="{MARKER_OBJECT}", and name="create Atlas_Marker".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY this JSON object:
{{
  "evidence": [{{"tool":"inspect_scene","arguments":{{"file_name":"{file_name}"}},"name":"inspect_scene"}}],
  "actions": [{{"tool":"create_empty_marker","arguments":{{"file_name":"{file_name}","collection_name":"Atlas_Test","object_name":"{MARKER_OBJECT}"}},"name":"create Atlas_Marker"}}]
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


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_scene":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    return inspect_scene(**arguments)


def boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "create_empty_marker":
            raise RuntimeError(f"Unexpected marker action: {tool}")
        raw = create_empty_marker(**arguments)
        status = raw.get("status")
        return {"ok": status in {"created", "already_exists"}, "state": str(status or "unknown"), "details": dict(raw)}
    return BlenderExecutionBoundary(execute)


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

    orchestrator = prepare_task_runtime(definition)
    initial = orchestrator.acquire_next_evidence(evidence)
    audit.record_evidence({"tool": definition.evidence[0].tool, "arguments": dict(definition.evidence[0].arguments), "name": definition.evidence[0].name}, initial)
    state = orchestrator.evaluate_target_state(initial)
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    execution_count = 0
    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools=definition.allowed_action_tools, allow_writes=definition.allow_writes)
        authorization = orchestrator.authorize_execution(f"live:marker-creation:{args.case}")
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        action = definition.actions[0]
        execution = boundary()
        capture: Dict[str, Any] = {}

        def execute_once(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal execution_count
            execution_count += 1
            normalized, receipt = execution.execute_with_receipt(tool, arguments)
            capture["normalized"] = normalized
            capture["receipt"] = receipt
            return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

        result = orchestrator.execute_next_action(execute_once)
        normalized = capture["normalized"]
        receipt = capture["receipt"]
        if not receipt.matches(action.tool, action.arguments, normalized):
            raise RuntimeError("Marker execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized marker action failed: {result}")
        audit.record_action(0, {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}, result, True)

    expected_execution_count = 0 if state.satisfied else 1
    if execution_count != expected_execution_count:
        raise RuntimeError(
            f"Marker execution count mismatch: expected {expected_execution_count}, got {execution_count}"
        )

    final = evidence("inspect_scene", {"file_name": file_name})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent marker verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Marker task did not complete: {orchestrator.snapshot()}")

    print("ATLAS MARKER TASK: PASS")
    print("TARGET ALREADY SATISFIED" if state.satisfied else "MARKER CREATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
