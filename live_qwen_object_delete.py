"""Live generic Blender task: conditionally delete an explicit cleanup candidate."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from audit_trail import AuditTrail
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.object_delete_task import TARGET_OBJECT, object_delete_task_definition
from planning.task_runtime import prepare_task_runtime
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_scene
from tools.blender_delete import delete_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "object_delete_CORRECT.blend"
INCORRECT_FILE = "object_delete_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_scene", "delete_object"}


def prompt(file_name: str) -> str:
    return f"""You are the Atlas Blender planning assistant.
Ensure cleanup candidate {TARGET_OBJECT} is absent from {file_name}.
Return exactly one JSON OBJECT with exactly two top-level fields: evidence and actions.
Evidence: exactly one inspect_scene request with file_name="{file_name}".
Actions: exactly one delete_object action with file_name="{file_name}", object_name="{TARGET_OBJECT}".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations."""


def correction(file_name: str) -> str:
    return f"""Return ONLY this JSON OBJECT and nothing else:
{{
  "evidence": [{{"tool":"inspect_scene","arguments":{{"file_name":"{file_name}"}},"name":"inspect_scene"}}],
  "actions": [{{"tool":"delete_object","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}"}},"name":"delete_object"}}]
}}"""


def ask(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False, "format": TASK_PLAN_JSON_SCHEMA},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def build_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    messages = [
        {"role": "system", "content": prompt(file_name)},
        {"role": "user", "content": "Create the structured Atlas task plan."},
    ]
    last: Optional[Exception] = None
    for attempt in range(1, 4):
        raw = ask(messages)
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
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": correction(file_name)},
        ]
    raise RuntimeError(f"Qwen plan rejected: {last}")


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_scene":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    scene = inspect_scene(**arguments)
    scene["object_names"] = [obj["name"] for obj in scene.get("objects", [])]
    return scene


def boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "delete_object":
            raise RuntimeError(f"Unexpected object delete action: {tool}")
        raw = delete_object(**arguments)
        status = raw.get("status")
        return {"ok": status in {"ok", "already_absent"}, "state": str(status or "unknown"), "details": dict(raw)}
    return BlenderExecutionBoundary(execute)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    definition = object_delete_task_definition(file_name)

    if tuple(proposal.evidence) != definition.evidence:
        raise RuntimeError("Qwen evidence plan does not match object delete task definition")
    if tuple(proposal.actions) != definition.actions:
        raise RuntimeError("Qwen action plan does not match object delete task definition")

    orchestrator = prepare_task_runtime(definition)
    initial = orchestrator.acquire_next_evidence(evidence)
    audit.record_evidence({"tool": definition.evidence[0].tool, "arguments": dict(definition.evidence[0].arguments), "name": definition.evidence[0].name}, initial)
    state = orchestrator.evaluate_target_state(initial)
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools=definition.allowed_action_tools,
            allow_writes=definition.allow_writes,
        )
        authorization = orchestrator.authorize_execution(f"live:object-delete:{args.case}")
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        action = definition.actions[0]

        execution = boundary()
        capture: Dict[str, Any] = {}

        def execute_once(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            normalized, receipt = execution.execute_with_receipt(tool, arguments)
            capture["normalized"] = normalized
            capture["receipt"] = receipt
            return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

        result = orchestrator.execute_next_action(execute_once)
        normalized = capture["normalized"]
        receipt = capture["receipt"]
        if not receipt.matches(action.tool, action.arguments, normalized):
            raise RuntimeError("Object delete execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized object delete action failed: {result}")
        audit.record_action(0, {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}, result, True)

    final = evidence("inspect_scene", {"file_name": file_name})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent object delete verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Object delete task did not complete: {orchestrator.snapshot()}")

    print("ATLAS OBJECT DELETE TASK: PASS")
    print("TARGET ALREADY ABSENT" if state.satisfied else "TARGET DELETED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
