"""Live conditional Atlas harness for a controlled Blender task.

Qwen proposes the plan. Python validates it, acquires read-only evidence, and
makes the target-state decision from that evidence. A satisfied target skips
all writes. An unsatisfied target enters the existing Python authorization gate,
executes the already-validated actions, and independently verifies the result.

Usage:
    python live_qwen_conditional_loop.py --case already-correct
    python live_qwen_conditional_loop.py --case incorrect
"""

import argparse
import json
import shutil
from typing import Any, Dict, List

import requests

from audit_trail import AuditTrail
from conditional_action import ConditionalActionPlan, TargetCondition
from qwen_planning_executor import execute_read_only_plan
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
CORRECT_FILE = "goalpost_test.blend"
WORKING_INCORRECT_FILE = "goalpost_test_CONDITIONAL_INCORRECT.blend"
MAX_PLAN_ATTEMPTS = 3

ALLOWED_TOOLS = {"inspect_object_relationship", "move_object"}
TARGET_LEFT = [0.0, 5.233, 0.0]
TARGET_RIGHT = [0.0, -5.233, 0.0]
TARGET_MIDPOINT = [0.0, 0.0, 0.0]
TARGET_DISTANCE = 10.466


def build_system_prompt(file_name: str) -> str:
    return f"""You are the Atlas planning assistant.

Create a structured plan for {file_name} whose requested final state is:
- Goal_Left_post = [0.0, 5.233, 0.0]
- Goal_Right_Post = [0.0, -5.233, 0.0]
- midpoint = [0.0, 0.0, 0.0]

Return ONLY valid JSON with exactly two top-level fields: evidence and actions.
Both fields MUST be arrays.
Evidence MUST contain exactly one inspect_object_relationship request for the two goalposts.
Actions MUST contain exactly two move_object actions in left-then-right order.
Every item must contain tool, arguments, and name.
Do not add tools, fields, coordinates, markdown, or explanations.
Do not execute tools yourself."""


def build_correction_prompt(file_name: str) -> str:
    return f"""Return ONLY corrected Atlas JSON for {file_name}.
Evidence: inspect_object_relationship(file_name=\"{file_name}\", object1_name=\"Goal_Left_post\", object2_name=\"Goal_Right_Post\")
Action 1: move_object(file_name=\"{file_name}\", object_name=\"Goal_Left_post\", location=[0.0,5.233,0.0])
Action 2: move_object(file_name=\"{file_name}\", object_name=\"Goal_Right_Post\", location=[0.0,-5.233,0.0])
Use only tool, arguments, name. Both evidence and actions must be arrays."""


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

        audit.record_qwen_proposal(
            raw,
            attempt,
            False,
            str(last_error) if last_error else "schema validation failed",
        )
        if attempt < MAX_PLAN_ATTEMPTS:
            messages.extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": build_correction_prompt(file_name)},
            ])

    raise RuntimeError(f"Qwen plan rejected after {MAX_PLAN_ATTEMPTS} attempts: {last_error}")


def target_is_satisfied(relationship: Dict[str, Any]) -> bool:
    """Require every authoritative target invariant, not just the midpoint."""
    try:
        return (
            relationship["object_a"]["location"] == TARGET_LEFT
            and relationship["object_b"]["location"] == TARGET_RIGHT
            and relationship["midpoint"] == TARGET_MIDPOINT
            and relationship["symmetric_about_origin"] is True
            and relationship["distance"] == TARGET_DISTANCE
        )
    except (KeyError, TypeError):
        return False


def action_payload(action: Any) -> Dict[str, Any]:
    return {
        "tool": action.tool,
        "arguments": dict(action.arguments),
        "name": action.name,
    }


def prepare_case(case: str) -> str:
    if case == "already-correct":
        return CORRECT_FILE

    # The fixture setup is isolated to a disposable copy. It deliberately does
    # not use the conditional planner; it creates the known-incorrect starting
    # state that the conditional planner must then repair.
    shutil.copy2(CORRECT_FILE, WORKING_INCORRECT_FILE)
    setup_result = move_object(
        WORKING_INCORRECT_FILE,
        "Goal_Left_post",
        [0.0, 5.000, 0.0],
    )
    if setup_result.get("status") != "moved":
        raise RuntimeError(f"Could not prepare incorrect fixture: {setup_result}")
    return WORKING_INCORRECT_FILE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()

    file_name = prepare_case(args.case)
    audit = AuditTrail()
    proposal = get_validated_plan(file_name, audit)

    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise RuntimeError("Unexpected conditional plan shape")
    if any(action.tool != "move_object" for action in proposal.actions):
        raise RuntimeError("Conditional plan contains a non-write action")

    evidence_only = TaskPlanProposal(evidence=proposal.evidence, actions=[])
    evidence_execution = execute_read_only_plan(evidence_only)
    if not evidence_execution.get("read_only") or evidence_execution.get("execution_authorized"):
        raise RuntimeError("Evidence executor crossed the write boundary")

    relationship = evidence_execution["results"][0]["result"]
    audit.record_evidence(action_payload(proposal.evidence[0]), relationship)

    satisfied = target_is_satisfied(relationship)
    condition = TargetCondition(path=("target_satisfied",), expected=True)
    conditional = ConditionalActionPlan(
        action_plan=__import__("action_plan").ActionPlan(list(proposal.actions)),
        condition=condition,
    )
    conditional.evaluate({"target_satisfied": satisfied})

    audit.record(
        "conditional_decision",
        "skip" if satisfied else "execute",
        target_satisfied=satisfied,
        case=args.case,
    )

    print("--- CONDITIONAL DECISION ---")
    print(json.dumps(conditional.snapshot(), indent=2))

    if satisfied:
        if conditional.next_action is not None or conditional.action_plan.completed:
            raise RuntimeError("Satisfied target exposed or executed a write")
        final = inspect_object_relationship(file_name, "Goal_Left_post", "Goal_Right_Post")
        if not target_is_satisfied(final):
            raise RuntimeError("Independent no-op verification failed")
        audit.record_verification(final, True)
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
            result = move_object(**action.arguments)
            success = result.get("status") == "moved"
            audit.record_action(index, payload, result, success)
            conditional.action_plan.record_result(result, success)
            if not success:
                raise RuntimeError(f"Authorized action failed: {result}")

        final = inspect_object_relationship(file_name, "Goal_Left_post", "Goal_Right_Post")
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
