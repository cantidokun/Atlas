"""Live Qwen Blender task: conditionally rotate an explicit cleanup candidate."""
import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from evidence_plan import EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.object_rotation_task import TARGET_OBJECT, TARGET_ROTATION, object_rotation_target_evaluator
from planning.task_definition import AtlasTaskDefinition
from planning.task_runtime import prepare_task_runtime
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


def rotation_boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "set_object_rotation":
            raise RuntimeError(f"Unexpected rotation action: {tool}")
        raw = set_object_rotation(**arguments)
        status = raw.get("status")
        return {"ok": status in {"ok", "already_rotated"}, "state": str(status or "unknown"), "details": dict(raw)}
    return BlenderExecutionBoundary(execute)


def task_definition(file_name: str) -> AtlasTaskDefinition:
    return AtlasTaskDefinition(
        name="object_rotation",
        evidence=(EvidenceRequest("inspect_object_transform", {"file_name": file_name, "object_name": TARGET_OBJECT}, "inspect_object_transform"),),
        actions=(ActionSpec("set_object_rotation", {"file_name": file_name, "object_name": TARGET_OBJECT, "rotation_degrees": TARGET_ROTATION}, "set_object_rotation"),),
        evaluator=object_rotation_target_evaluator(),
        allowed_action_tools={"set_object_rotation"},
        allow_writes=True,
        verify_after_action=True,
        metadata={"domain": "blender", "operation": "rotation"},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE

    audit = AuditTrail()
    proposal = build_plan(file_name, audit)
    definition = task_definition(file_name)
    if tuple(proposal.evidence) != definition.evidence or tuple(proposal.actions) != definition.actions:
        raise RuntimeError("Qwen plan does not match declarative task definition")
    orchestrator = prepare_task_runtime(definition)

    initial = orchestrator.acquire_next_evidence(read_evidence)
    audit.record_evidence({"tool": definition.evidence[0].tool, "arguments": dict(definition.evidence[0].arguments), "name": definition.evidence[0].name}, initial)
    state = orchestrator.evaluate_target_state(initial)
    audit.record("conditional_decision", "skip" if state.satisfied else "execute", target_satisfied=state.satisfied, failed_invariants=state.failed, case=args.case)

    if not state.satisfied:
        authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools=definition.allowed_action_tools, allow_writes=definition.allow_writes)
        authorization = orchestrator.authorize_execution(f"live:object-rotation:{args.case}")
        audit.record_authorization(True, action_count=len(definition.actions), authorization_id=authorization.authorization_id)
        action = definition.actions[0]
        execution = rotation_boundary()
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
            raise RuntimeError("Rotation execution receipt mismatch")
        if not result.get("ok"):
            raise RuntimeError(f"Authorized rotation action failed: {result}")
        audit.record_action(0, {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}, result, True)

    final = read_evidence("inspect_object_transform", {"file_name": file_name, "object_name": TARGET_OBJECT})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if definition.verify_after_action and not final_state.satisfied:
        raise RuntimeError(f"Independent rotation verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Object rotation task did not complete: {orchestrator.snapshot()}")

    print("ATLAS OBJECT ROTATION TASK: PASS")
    print("TARGET ALREADY CORRECT" if state.satisfied else "TARGET ROTATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
