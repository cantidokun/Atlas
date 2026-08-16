"""Live Stage 8 harness: conditionally execute an authorized Blender plan.

The model proposes a structured evidence/action plan. Python validates exact
argument schemas, executes read-only evidence, evaluates the target state from
authoritative evidence, and then either skips all writes or executes the
already-authorized action sequence. Final state is independently verified.

Usage:
    python live_qwen_conditional_loop.py --case already-correct
    python live_qwen_conditional_loop.py --case incorrect

The two cases use deterministic fixture files provisioned in the Atlas project
folder. The original goalpost_test.blend is never used as a write target.
"""

import argparse
import json
from typing import Any, Dict, List

import requests

from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from qwen_planning_executor import execute_read_only_plan
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

Return ONLY valid JSON with exactly two top-level fields: evidence and actions.
Both fields MUST be arrays.

Evidence MUST contain exactly one inspect_object_relationship request with:
file_name="{file_name}"
object1_name="Goal_Left_post"
object2_name="Goal_Right_Post"

Actions MUST contain exactly these two move_object actions in this order:
1. Goal_Left_post -> [0.0, 5.233, 0.0]
2. Goal_Right_Post -> [0.0, -5.233, 0.0]

Every item must contain tool, arguments, and name. Use exact parameter names.
Do not add fields, tools, actions, coordinates, markdown, or explanations.
Do not execute tools yourself."""


def build_correction_prompt(file_name: str) -> str:
    return f"""Return ONLY the corrected Atlas JSON task plan for {file_name}.
Use exactly tool/arguments/name and these exact arguments:
Evidence: inspect_object_relationship(file_name="{file_name}", object1_name="Goal_Left_post", object2_name="Goal_Right_Post")
Action 1: move_object(file_name="{file_name}", object_name="Goal_Left_post", location=[0.0,5.233,0.0])
Action 2: move_object(file_name="{file_name}", object_name="Goal_Right_Post", location=[0.0,-5.233,0.0])
Both evidence and actions must be arrays. No other fields or tools."""


def ask_qwen(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def get_validated_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(file_name)},
        {"role": "user", "content": "Create the structured Atlas task plan."},
    ]
    last_error: Exception | None = None

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


def target_is_satisfied(relationship: Dict[str, Any]) -> bool:
    """Return true only when every independent target invariant is satisfied."""
    return (
        relationship["object_a"]["location"] == TARGET_LEFT
        and relationship["object_b"]["location"] == TARGET_RIGHT
        and relationship["midpoint"] == TARGET_MIDPOINT
        and relationship["symmetric_about_origin"] is True
        and relationship["distance"] == TARGET_DISTANCE
    )


def execute_move_action(action: Any) -> Dict[str, Any]:
    if action.tool != "move_object":
        raise RuntimeError(f"Unexpected action tool: {action.tool}")
    return move_object(**action.arguments)


def action_payload(action: Any) -> Dict[str, Any]:
    return {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}


def prepare_case(case: str) -> str:
    if case == "already-correct":
        return CORRECT_FILE
    return INCORRECT_FILE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()

    file_name = prepare_case(args.case)
    audit = AuditTrail()
    proposal = get_validated_plan(file_name, audit)

    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise RuntimeError("Unexpected conditional plan shape")

    evidence_only = TaskPlanProposal(evidence=proposal.evidence, actions=[])
    evidence_execution = execute_read_only_plan(evidence_only)
    relationship = evidence_execution["results"][0]["result"]
    audit.record_evidence(action_payload(proposal.evidence[0]), relationship)

    satisfied = target_is_satisfied(relationship)
    conditional = ConditionalActionPlan(proposal.actions)
    conditional.evaluate(satisfied)
    audit.record(
        "conditional_decision",
        "skip" if satisfied else "execute",
        target_satisfied=satisfied,
        case=args.case,
    )

    print("--- CONDITIONAL DECISION ---")
    print(json.dumps(conditional.snapshot(), indent=2))

    if satisfied:
        if conditional.next_action is not None:
            raise RuntimeError("Satisfied target exposed an action")
        if conditional.action_plan.completed:
            raise RuntimeError("Satisfied target executed an action")
        print("TARGET ALREADY SATISFIED")
        print("WRITE EXECUTION SKIPPED")
        print("ATLAS CONDITIONAL ALREADY-CORRECT TEST: PASS")
    else:
        authorize_task_plan(
            proposal,
            evidence_complete=True,
            allowed_action_tools={"move_object"},
            allow_writes=True,
        )
        audit.record_authorization(True, action_count=len(proposal.actions))

        while not conditional.complete:
            action = conditional.next_action
            if action is None:
                raise RuntimeError("Conditional plan has no executable next action")
            index = conditional.action_plan.current_index
            payload = action_payload(action)
            try:
                result = execute_move_action(action)
            except Exception as exc:
                result = {"error": str(exc)}
                audit.record_action(index, payload, result, False)
                conditional.record_result(result, False)
                raise

            success = result.get("status") == "moved"
            audit.record_action(index, payload, result, success)
            conditional.record_result(result, success)
            if not success:
                raise RuntimeError(f"Authorized action failed: {result}")

        final = inspect_object_relationship(
            file_name,
            "Goal_Left_post",
            "Goal_Right_Post",
        )
        verification_ok = target_is_satisfied(final)
        audit.record_verification(final, verification_ok)
        if not verification_ok:
            raise RuntimeError("Independent final verification failed")

        print("FINAL STATE INDEPENDENTLY VERIFIED")
        print("ATLAS CONDITIONAL INCORRECT-STATE TEST: PASS")

    print("--- AUDIT TRAIL ---")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
