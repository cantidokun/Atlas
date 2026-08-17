"""Live generic Blender relationship task: conditionally parent Atlas_Marker."""

import argparse
import json
from typing import Any, Dict

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.parent_marker_task import MARKER_OBJECT, PARENT_OBJECT, parent_target_evaluator
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal
from tools.blender_relationship import inspect_object_parent, parent_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "parent_task_CORRECT.blend"
INCORRECT_FILE = "parent_task_INCORRECT.blend"
ALLOWED_TOOLS = {"inspect_object_parent", "parent_object"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas Blender planning assistant.
Ensure {MARKER_OBJECT} is parented to {PARENT_OBJECT} in {file_name}.
Return exactly one JSON OBJECT with exactly two top-level fields: evidence and actions.
Evidence: exactly one inspect_object_parent request with file_name="{file_name}" and object_name="{MARKER_OBJECT}".
Actions: exactly one parent_object action with file_name="{file_name}", child_name="{MARKER_OBJECT}", parent_name="{PARENT_OBJECT}".
Every item must contain exactly tool, arguments, and name.
Do not execute tools. Do not add fields, tools, markdown, or explanations.'''


def ask(content: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages":[
                {"role": "system", "content": content},
                {"role": "user", "content": "Create the structured Atlas task plan."},
            ],
            "stream": False,
            "format": TASK_PLAN_JSON_SCHEMA,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def build_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    raw = ask(prompt(file_name))
    proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
    audit.record_qwen_proposal(raw, 1, True, None)
    return proposal


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_object_parent":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    return inspect_object_parent(**arguments)


def boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raw = parent_object(**arguments)
        status = raw.get("status")
        return {
            "ok": status in {"parented", "already_parented"},
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
        raise RuntimeError("Unexpected relationship task plan shape")

    evaluator = parent_target_evaluator()
    orchestrator = ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([
            EvidenceRequest(r.tool, dict(r.arguments), r.name) for r in proposal.evidence
        ]),
        conditional_plan=ConditionalActionPlan([
            ActionSpec(a.tool, dict(a.arguments), a.name, a.requires_success) for a in proposal.actions
        ]),
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )

    initial = orchestrator.acquire_next_evidence(evidence)
    audit.record_evidence(
        {"tool": proposal.evidence[0].tool, "arguments": dict(proposal.evidence[0].arguments), "name": proposal.evidence[0].name},
        initial,
    )
    state = orchestrator.evaluate_target_state(initial)
    audit.record(
        "conditional_decision",
        "skip" if state.satisfied else "execute",
        target_satisfied=state.satisfied,
        invariants=state.invariants,
        failed_invariants=state.failed,
        case=args.case,
    )

    if not state.satisfied:
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools={"parent_object"},
            allow_writes=True,
        )
        execution_authorization = orchestrator.authorize_execution(f"live:{args.case}")
        audit.record_authorization(
            True,
            action_count=len(proposal.actions),
            authorization_id=execution_authorization.authorization_id,
        )

        action = orchestrator.conditional_plan.next_action
        if action is None:
            raise RuntimeError("Conditional orchestrator exposed no parent action")
        index = orchestrator.conditional_plan.action_plan.current_index
        payload = {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}

        try:
            result = orchestrator.execute_next_action(boundary().execute)
        except Exception as exc:
            failure = {"error": str(exc), "exception_type": type(exc).__name__}
            audit.record_action(index, payload, failure, False)
            raise

        audit.record_action(index, payload, result, result.get("ok") is True)
        if result.get("ok") is not True:
            raise RuntimeError(f"Authorized parent action failed: {result}")
        if not orchestrator.action_complete:
            raise RuntimeError(f"Parent action phase did not complete: {orchestrator.snapshot()}")

    final = evidence("inspect_object_parent", {"file_name": file_name, "object_name": MARKER_OBJECT})
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if not final_state.satisfied:
        raise RuntimeError(f"Independent relationship verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Relationship task did not complete: {orchestrator.snapshot()}")

    print("ATLAS PARENT RELATIONSHIP TASK: PASS")
    print("TARGET ALREADY SATISFIED" if state.satisfied else "TARGET PARENTED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
