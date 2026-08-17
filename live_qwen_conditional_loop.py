"""Live conditional Atlas task harness with constrained Qwen planning."""

import argparse
import json
from typing import Any, Dict, List, Optional

import requests

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.target_state import StateInvariant, TargetStateEvaluator
from planning.verification_plan import VerificationPlan
from qwen.structured_plan import TASK_PLAN_JSON_SCHEMA
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "goalpost_test_CONDITIONAL_CORRECT.blend"
INCORRECT_FILE = "goalpost_test_CONDITIONAL_INCORRECT.blend"
MAX_PLAN_ATTEMPTS = 3

ALLOWED_TOOLS = {"inspect_object_relationship", "move_object"}
TARGET_LEFT = [0.0, 5.233, 0.0]
TARGET_RIGHT = [0.0, -5.233, 0.0]
TARGET_MIDPOINT = [0.0, 0.0, 0.0]
TARGET_DISTANCE = 10.466


def build_system_prompt(file_name: str) -> str:
    return f"""You are the Atlas planning assistant.

The user has authorized this specific Blender task for {file_name}:
- Goal_Left_post target = [0.0, 5.233, 0.0]
- Goal_Right_Post target = [0.0, -5.233, 0.0]
- midpoint target = [0.0, 0.0, 0.0]

Return exactly one JSON OBJECT with exactly these top-level fields:
{{"evidence": [...], "actions": [...]}}

Evidence MUST contain exactly one inspect_object_relationship request with:
file_name="{file_name}"
object1_name="Goal_Left_post"
object2_name="Goal_Right_Post"

Actions MUST contain exactly these two move_object actions in this order:
1. Goal_Left_post -> [0.0, 5.233, 0.0]
2. Goal_Right_Post -> [0.0, -5.233, 0.0]

Every item must contain exactly tool, arguments, and name. Use exact argument
names: file_name, object_name, location for move_object. Do not return a list.
Do not add fields, tools, actions, coordinates, markdown, or explanations.
Do not execute tools yourself."""


def build_correction_prompt(file_name: str) -> str:
    return f"""Return ONLY one JSON OBJECT, never a JSON array.
The object MUST have exactly two fields: evidence and actions.
Evidence is an array. Actions is an array.
Use this exact structure and arguments:
{{
  "evidence": [{{"tool": "inspect_object_relationship", "arguments": {{"file_name": "{file_name}", "object1_name": "Goal_Left_post", "object2_name": "Goal_Right_Post"}}, "name": "inspect_object_relationship"}}],
  "actions": [
    {{"tool": "move_object", "arguments": {{"file_name": "{file_name}", "object_name": "Goal_Left_post", "location": [0.0, 5.233, 0.0]}}, "name": "move_object"}},
    {{"tool": "move_object", "arguments": {{"file_name": "{file_name}", "object_name": "Goal_Right_Post", "location": [0.0, -5.233, 0.0]}}, "name": "move_object"}}
  ]
}}
No other fields or tools."""


def ask_qwen(messages: List[Dict[str, str]]) -> str:
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


def get_validated_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(file_name)},
        {"role": "user", "content": "Create the structured Atlas task plan."},
    ]
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
        raw = ask_qwen(messages)
        print(f"--- QWEN PLAN ATTEMPT {attempt} ---")
        print(raw)
        try:
            proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
        except (TaskPlanValidationError, TypeError, ValueError) as exc:
            proposal = None
            last_error = exc
        if proposal is not None:
            audit.record_qwen_proposal(raw, attempt, True)
            return proposal
        reason = str(last_error) if last_error else "schema validation failed"
        audit.record_qwen_proposal(raw, attempt, False, reason)
        if attempt < MAX_PLAN_ATTEMPTS:
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": build_correction_prompt(file_name)},
            ])
    raise RuntimeError(f"Qwen plan rejected after {MAX_PLAN_ATTEMPTS} attempts: {last_error}")


def target_state_evaluator() -> TargetStateEvaluator:
    return TargetStateEvaluator([
        StateInvariant("left_post_location", lambda e: e["object_a"]["location"] == TARGET_LEFT),
        StateInvariant("right_post_location", lambda e: e["object_b"]["location"] == TARGET_RIGHT),
        StateInvariant("midpoint", lambda e: e["midpoint"] == TARGET_MIDPOINT),
        StateInvariant("symmetric_about_origin", lambda e: e["symmetric_about_origin"] is True),
        StateInvariant("distance", lambda e: e["distance"] == TARGET_DISTANCE),
    ])


def target_is_satisfied(relationship: Dict[str, Any]) -> bool:
    """Compatibility helper used by the offline regression suite."""
    return target_state_evaluator().evaluate(relationship).satisfied


def build_conditional_orchestrator(proposal: TaskPlanProposal) -> ConditionalPlanningOrchestrator:
    evidence = EvidencePlan([EvidenceRequest(r.tool, dict(r.arguments), r.name) for r in proposal.evidence])
    actions = [ActionSpec(a.tool, dict(a.arguments), a.name, a.requires_success) for a in proposal.actions]
    evaluator = target_state_evaluator()
    return ConditionalPlanningOrchestrator(
        evidence_plan=evidence,
        conditional_plan=ConditionalActionPlan(actions),
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )


def execute_evidence(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "inspect_object_relationship":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    return inspect_object_relationship(**arguments)


def execute_action(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool != "move_object":
        raise RuntimeError(f"Unexpected action tool: {tool}")
    return move_object(**arguments)


def action_payload(tool: str, arguments: Dict[str, Any], name: str = "") -> Dict[str, Any]:
    return {"tool": tool, "arguments": dict(arguments), "name": name}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()
    file_name = CORRECT_FILE if args.case == "already-correct" else INCORRECT_FILE
    audit = AuditTrail()
    proposal = get_validated_plan(file_name, audit)
    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise RuntimeError("Unexpected conditional plan shape")

    orchestrator = build_conditional_orchestrator(proposal)
    relationship = orchestrator.acquire_next_evidence(execute_evidence)
    audit.record_evidence(action_payload(proposal.evidence[0].tool, proposal.evidence[0].arguments, proposal.evidence[0].name), relationship)
    state_result = orchestrator.evaluate_target_state(relationship)
    audit.record(
        "conditional_decision",
        "skip" if state_result.satisfied else "execute",
        target_satisfied=state_result.satisfied,
        invariants=state_result.invariants,
        failed_invariants=state_result.failed,
        case=args.case,
    )

    print("--- TARGET STATE ---")
    print(json.dumps(state_result.snapshot(), indent=2))
    print("--- DETERMINISTIC FUTURE ---")
    print(json.dumps(orchestrator.snapshot()["future"], indent=2))

    if not state_result.satisfied:
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools={"move_object"},
            allow_writes=True,
        )
        execution_authorization = orchestrator.authorize_execution(f"live:{args.case}")
        audit.record_authorization(
            True,
            action_count=len(proposal.actions),
            authorization_id=execution_authorization.authorization_id,
        )
        while orchestrator.next_phase() == "ACTION":
            action = orchestrator.conditional_plan.next_action
            if action is None:
                raise RuntimeError("Conditional orchestrator exposed no action")
            index = orchestrator.conditional_plan.action_plan.current_index
            payload = action_payload(action.tool, action.arguments, action.name)
            try:
                result = orchestrator.execute_next_action(execute_action)
            except Exception as exc:
                result = {"error": str(exc)}
                audit.record_action(index, payload, result, False)
                raise
            success = result.get("status") == "moved"
            audit.record_action(index, payload, result, success)
            if not success:
                raise RuntimeError(f"Authorized action failed: {result}")
        if not orchestrator.action_complete:
            raise RuntimeError(f"Conditional action phase did not complete: {orchestrator.snapshot()}")

    final = inspect_object_relationship(file_name, "Goal_Left_post", "Goal_Right_Post")
    final_state = orchestrator.verify_post_action(final)
    audit.record_verification(final, final_state.satisfied)
    if not final_state.satisfied:
        raise RuntimeError(f"Independent final verification failed: {final_state.failed}")
    orchestrator.finalize_future()
    if orchestrator.next_phase() != "COMPLETE":
        raise RuntimeError(f"Verification succeeded but orchestration did not complete: {orchestrator.snapshot()}")

    if state_result.satisfied:
        print("TARGET ALREADY SATISFIED")
        print("WRITE EXECUTION SKIPPED")
        print("ATLAS CONDITIONAL ALREADY-CORRECT TEST: PASS")
    else:
        print("FINAL STATE INDEPENDENTLY VERIFIED")
        print("ATLAS CONDITIONAL INCORRECT-STATE TEST: PASS")

    print("--- AUDIT TRAIL ---")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
