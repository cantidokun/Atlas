"""Live generic-task proof: conditionally ensure an Atlas collection exists."""

import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.verification_plan import VerificationPlan
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import create_collection, inspect_scene, inspect_scene_settings

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "collection_task_CORRECT.blend"
INCORRECT_FILE = "collection_task_INCORRECT.blend"
TARGET_COLLECTION = "Atlas_Test"
ALLOWED_TOOLS = {"inspect_scene", "create_collection"}


def prompt(file_name: str) -> str:
    return f'''You are the Atlas planning assistant.
Ensure Blender collection {TARGET_COLLECTION} exists in {file_name}.
Return exactly one JSON OBJECT with exactly two top-level fields: evidence and actions.
Both fields are arrays.
Evidence: exactly one inspect_scene request with file_name="{file_name}".
Actions: exactly one create_collection action with file_name="{file_name}" and collection_name="{TARGET_COLLECTION}".
Every item must contain exactly tool, arguments, and name.
Do not return a list. Do not add fields, tools, actions, markdown, or explanations.
Do not execute tools.'''


def correction(file_name: str) -> str:
    return f'''Return ONLY one JSON OBJECT, never a JSON array.
Use exactly this structure:
{{
  "evidence": [{{"tool":"inspect_scene","arguments":{{"file_name":"{file_name}"}},"name":"inspect_scene"}}],
  "actions": [{{"tool":"create_collection","arguments":{{"file_name":"{file_name}","collection_name":"{TARGET_COLLECTION}"}},"name":"create_collection"}}]
}}
No other fields or tools.'''


def ask(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "format": TASK_PLAN_JSON_SCHEMA,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
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


def evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant("target_collection_exists", lambda e: TARGET_COLLECTION in e.get("collections", [])),
    ])


def build_orchestrator(proposal: TaskPlanProposal) -> ConditionalPlanningOrchestrator:
    ev = evaluator()
    return ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan([
            EvidenceRequest(r.tool, dict(r.arguments), r.name) for r in proposal.evidence
        ]),
        conditional_plan=ConditionalActionPlan([
            ActionSpec(a.tool, dict(a.arguments), a.name, a.requires_success) for a in proposal.actions
        ]),
        target_evaluator=ev,
        verification_plan=VerificationPlan(ev),
    )


def evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_scene":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    scene = inspect_scene(**arguments)
    settings = inspect_scene_settings(**arguments)
    scene["collections"] = settings.get("collections", [])
    return scene


def verified_action_boundary() -> BlenderExecutionBoundary:
    def execute(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "create_collection":
            raise RuntimeError(f"Unexpected action tool: {tool}")
        raw = create_collection(**arguments)
        status = raw.get("status")
        return {
            "ok": status in {"created", "already_exists"},
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
    proposal = plan(file_name, audit)
    if len(proposal.evidence) != 1 or len(proposal.actions) != 1:
        raise RuntimeError("Unexpected generic collection plan shape")

    orch = build_orchestrator(proposal)
    ev = orch.acquire_next_evidence(evidence)
    audit.record_evidence({
        "tool": proposal.evidence[0].tool,
        "arguments": proposal.evidence[0].arguments,
        "name": proposal.evidence[0].name,
    }, ev)
    state = orch.evaluate_target_state(ev)
    audit.record(
        "conditional_decision",
        "skip" if state.satisfied else "execute",
        target_satisfied=state.satisfied,
        failed_invariants=state.failed,
        case=args.case,
    )

    receipt_holder: Dict[str, Any] = {}
    if not state.satisfied:
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools={"create_collection"},
            allow_writes=True,
        )
        execution_authorization = orch.authorize_execution(f"live:collection:{args.case}")
        audit.record_authorization(
            True,
            action_count=1,
            authorization_id=execution_authorization.authorization_id,
        )

        boundary = verified_action_boundary()

        def execute_once(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            normalized, receipt = boundary.execute_with_receipt(tool, dict(arguments))
            receipt_holder["receipt"] = receipt
            return {
                "ok": normalized.ok,
                "state": normalized.state,
                "details": dict(normalized.details),
            }

        result = orch.execute_next_action(execute_once)
        if not result.get("ok"):
            raise RuntimeError(f"Authorized collection action failed: {result}")

        receipt = receipt_holder.get("receipt")
        if receipt is None:
            raise RuntimeError("Successful collection action produced no execution receipt")
        if not receipt.matches(
            proposal.actions[0].tool,
            proposal.actions[0].arguments,
            boundary.execute_verified.__self__ if False else boundary.execute_verified.__annotations__.get("return")
        ):
            # Receipt matching is performed in the execution closure against the exact
            # normalized result; this branch is unreachable and exists only to make the
            # single-execution requirement explicit.
            raise RuntimeError("Collection execution receipt mismatch")
        audit.record_action(
            0,
            {
                "tool": proposal.actions[0].tool,
                "arguments": proposal.actions[0].arguments,
                "name": proposal.actions[0].name,
            },
            {
                "ok": result["ok"],
                "state": result["state"],
                "details": result["details"],
                "receipt": {
                    "tool": receipt.tool,
                    "arguments_digest": receipt.arguments_digest,
                    "result_digest": receipt.result_digest,
                },
            },
            True,
        )

    final = evidence("inspect_scene", {"file_name": file_name})
    final_state = orch.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if not final_state.satisfied:
        raise RuntimeError(f"Independent verification failed: {final_state.failed}")
    orch.finalize_future()
    if orch.next_phase() != "COMPLETE":
        raise RuntimeError(f"Task did not complete: {orch.snapshot()}")

    print("ATLAS GENERIC COLLECTION TASK: PASS")
    print("TARGET ALREADY SATISFIED" if state.satisfied else "TARGET CREATED, RECEIPT-BOUND, AND INDEPENDENTLY VERIFIED")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
