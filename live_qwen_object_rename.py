"""Live generic Blender relationship task: conditionally rename a Blender object."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.object_rename_task import TARGET_NAME, TARGET_OBJECT, object_rename_target_evaluator
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_scene
from tools.blender_object import rename_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "object_rename_CORRECT.blend"
INCORRECT_FILE = "object_rename_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_scene", "rename_object"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas Blender planning assistant.
Ensure Blender object {TARGET_OBJECT} is named {TARGET_NAME} in {file_name}.
Return exactly one JSON OBJECT with exactly two top-level fields: evidence and actions.
Evidence: exactly one inspect_scene request with file_name="{file_name}".
Actions: exactly one rename_object action with file_name="{file_name}", object_name="{TARGET_OBJECT}", new_name="{TARGET_NAME}".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY this JSON OBJECT and nothing else:
{{
  "evidence": [{{"tool":"inspect_scene","arguments":{{"file_name":"{file_name}"}},"name":"inspect_scene"}}],
  "actions": [{{"tool":"rename_object","arguments":{{"file_name":"{file_name}","object_name":"{TARGET_OBJECT}","new_name":"{TARGET_NAME}"}},"name":"rename_object"}}]
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
        messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": correction(file_name)}]
    raise RuntimeError(f"Qwen plan rejected: {last}")


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_scene":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    scene = inspect_scene(**arguments)
    scene["object_names"] = [obj["name"] for obj in scene.get("objects", [])]
    return scene


def boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "rename_object":
            raise RuntimeError(f"Unexpected object rename action: {tool}")
        raw = rename_object(**arguments)
        status = raw.get("status")
        return {
            "ok": status in {"renamed", "already_named"},
            "state": str(status or "unknown"),
            "details": dict(raw),
        }
    return BlenderExecutionBoundary(execute)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    if len(proposal.evidence) != 1 or len(proposal.actions) != 1:
        raise RuntimeError("Unexpected object rename plan shape")

    evaluator = object_rename_target_evaluator()
    orchestrator = ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([EvidenceRequest(r.tool, dict(r.arguments), r.name) for r in proposal.evidence]),
        conditional_plan=ConditionalActionPlan([ActionSpec(a.tool, dict(a.arguments), a.name, a.requires_success) for a in proposal.actions]),
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )

    initial = orchestrator.acquire_next_evidence(evidence)
    audit.record_evidence({"tool": proposal.evidence[0].tool, "arguments": dict(proposal.evidence[0].arguments), "name": proposal.evidence[0].name}, initial)
    state = orchestrator.evaluate_target_state(initial)
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools={"rename_object"}, allow_writes=True)
        authorization = orchestrator.authorize_execution(f"live:object-rename:{args.case}")
        audit.record_authorization(True, action_count=1, authorization_id=authorization.authorization_id)
        action = proposal.actions[0]
        normalized, receipt = boundary().execute_with_receipt(action.tool, dict(action.arguments))
        if not receipt.matches(action.tool, action.arguments, normalized):
            raise RuntimeError("Object rename execution receipt mismatch")
        result = orchestrator.execute_next_action(lambda tool, arguments: {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)})
        if not result.get("ok"):
            raise RuntimeError(f"Authorized object rename action failed: {result}")
        audit.record_action(0, {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}, result, True)

    final = evidence("inspect_scene", {"file_name": file_name})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if not final_state.satisfied:
        raise RuntimeError(f"Independent object rename verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Object rename task did not complete: {orchestrator.snapshot()}")

    print("ATLAS OBJECT RENAME TASK: PASS")
    print("TARGET ALREADY SATISFIED" if state.satisfied else "TARGET RENAMED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
