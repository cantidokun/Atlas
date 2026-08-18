"""Live Qwen Blender task: conditionally rotate an explicit cleanup candidate."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.object_rotation_task import TARGET_OBJECT, TARGET_ROTATION, object_rotation_target_evaluator
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan
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
Evidence: exactly one inspect_object_transform request with file_name="{file_name}" and object_name="{TARGET_OBJECT}".
Actions: exactly one set_object_rotation action with file_name="{file_name}", object_name="{TARGET_OBJECT}", rotation_degrees={TARGET_ROTATION}.
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


def read_evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_object_transform":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    return inspect_object_transform(**arguments)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    evaluator = object_rotation_target_evaluator()
    orchestrator = ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([EvidenceRequest(r.tool, dict(r.arguments), r.name) for r in proposal.evidence]),
        conditional_plan=ConditionalActionPlan([ActionSpec(a.tool, dict(a.arguments), a.name, a.requires_success) for a in proposal.actions]),
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )

    initial = orchestrator.acquire_next_evidence(read_evidence)
    audit.record_evidence({"tool": proposal.evidence[0].tool, "arguments": dict(proposal.evidence[0].arguments), "name": proposal.evidence[0].name}, initial)
    state = orchestrator.evaluate_target_state(initial)
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools={"set_object_rotation"}, allow_writes=True)
        authorization = orchestrator.authorize_execution(f"live:object-rotation:{args.case}")
        audit.record_authorization(True, action_count=1, authorization_id=authorization.authorization_id)
        receipt_holder: Dict[str, Any] = {}

        def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            if tool != "set_object_rotation":
                raise RuntimeError(f"Unexpected rotation action: {tool}")
            raw = set_object_rotation(**arguments)
            receipt_holder["normalized"], receipt_holder["receipt"] = BlenderExecutionBoundary(lambda _tool, _args: raw).execute_with_receipt(tool, arguments)
            normalized = receipt_holder["normalized"]
            return {"ok": normalized.ok, "state": normalized.state, "details": dict(normalized.details)}

        result = orchestrator.execute_next_action(execute)
        receipt = receipt_holder.get("receipt")
        action = proposal.actions[0]
        if receipt is None or not receipt.matches(action.tool, action.arguments, receipt_holder["normalized"]):
            raise RuntimeError("Rotation execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized rotation action failed: {result}")
        audit.record_action(0, {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}, result, True)

    final = read_evidence("inspect_object_transform", {"file_name": file_name, "object_name": TARGET_OBJECT})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if not final_state.satisfied:
        raise RuntimeError(f"Independent rotation verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Object rotation task did not complete: {orchestrator.snapshot()}")

    print("ATLAS OBJECT ROTATION TASK: PASS")
    print("TARGET ALREADY CORRECT" if state.satisfied else "TARGET ROTATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
