"""Live conditional Atlas harness for a controlled Blender task.

Qwen proposes the plan. Python validates it, acquires read-only evidence, and
makes the target-state decision from that evidence. A satisfied target skips
all conditional-plan writes. An unsatisfied target enters the existing Python
authorization gate, executes the already-validated actions, and independently
verifies the result.
"""

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

import requests

from action_plan import ActionPlan
from audit_trail import AuditTrail
from conditional_action import ConditionalActionPlan, TargetCondition
from qwen_planning_executor import execute_read_only_plan
from qwen_planning_runtime import parse_qwen_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
WORKSPACE = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd())).resolve()
SOURCE_FILE = WORKSPACE / "goalpost_test.blend"
WORKING_CORRECT_FILE = WORKSPACE / "goalpost_test_CONDITIONAL_CORRECT.blend"
WORKING_INCORRECT_FILE = WORKSPACE / "goalpost_test_CONDITIONAL_INCORRECT.blend"
MAX_PLAN_ATTEMPTS = 3

ALLOWED_TOOLS = {"inspect_object_relationship", "move_object"}
TARGET_LEFT = [0.0, 5.233, 0.0]
TARGET_RIGHT = [0.0, -5.233, 0.0]
TARGET_MIDPOINT = [0.0, 0.0, 0.0]
TARGET_DISTANCE = 10.466
EXPECTED_LEFT_OBJECT = "Goal_Left_post"
EXPECTED_RIGHT_OBJECT = "Goal_Right_Post"


def build_system_prompt(file_name: str) -> str:
    return f"""You are the Atlas planning assistant.

Create a structured plan for {file_name} whose requested final state is:
- Goal_Left_post = [0.0, 5.233, 0.0]
- Goal_Right_Post = [0.0, -5.233, 0.0]
- midpoint = [0.0, 0.0, 0.0]

IMPORTANT: The Blender fixture contains the EXACT object names
"Goal_Left_post" and "Goal_Right_Post". You MUST use those exact strings,
including capitalization and underscores. Do NOT shorten them to Left_post or
Right_post, and do NOT invent aliases.

The available tools have these EXACT Python-compatible signatures:
- inspect_object_relationship(file_name, object1_name, object2_name)
- move_object(file_name, object_name, location)

Use the exact argument names shown above. Do NOT use aliases such as object1,
object2, target_position, or position.

Return ONLY valid JSON with exactly two top-level fields: evidence and actions.
Both fields MUST be arrays.
Evidence MUST contain exactly one request for inspect_object_relationship.
Actions MUST contain exactly two move_object requests in left-then-right order.
Every item must contain tool, arguments, and name.
Do not add tools, fields, coordinates, markdown, or explanations.
Do not execute tools yourself."""


def build_correction_prompt(file_name: str) -> str:
    return f"""Return ONLY corrected Atlas JSON for {file_name}.

The fixture object names are EXACTLY:
- {EXPECTED_LEFT_OBJECT}
- {EXPECTED_RIGHT_OBJECT}

Do not use Left_post or Right_post. Do not use aliases.

Evidence: inspect_object_relationship(file_name=\"{file_name}\", object1_name=\"{EXPECTED_LEFT_OBJECT}\", object2_name=\"{EXPECTED_RIGHT_OBJECT}\")
Action 1: move_object(file_name=\"{file_name}\", object_name=\"{EXPECTED_LEFT_OBJECT}\", location=[0.0,5.233,0.0])
Action 2: move_object(file_name=\"{file_name}\", object_name=\"{EXPECTED_RIGHT_OBJECT}\", location=[0.0,-5.233,0.0])

Use only tool, arguments, name. Both evidence and actions must be arrays."""


def ask_qwen(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def validate_conditional_proposal(proposal: TaskPlanProposal, file_name: str) -> None:
    """Enforce the semantic object-name contract for this live fixture.

    Generic plan parsing proves that a proposal is structurally valid. This
    harness additionally requires the proposal to refer to the exact objects
    that exist in the deterministic fixture. A structurally valid plan that
    names different objects must not reach evidence execution.
    """
    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise TaskPlanValidationError("Conditional plan must contain 1 evidence item and 2 actions")

    evidence = proposal.evidence[0]
    if evidence.tool != "inspect_object_relationship":
        raise TaskPlanValidationError("Conditional evidence must inspect object relationship")
    evidence_args = dict(evidence.arguments)
    if evidence_args.get("file_name") != file_name:
        raise TaskPlanValidationError("Evidence file_name does not match the selected fixture")
    if evidence_args.get("object1_name") != EXPECTED_LEFT_OBJECT:
        raise TaskPlanValidationError(
            f"Evidence object1_name must be {EXPECTED_LEFT_OBJECT!r}"
        )
    if evidence_args.get("object2_name") != EXPECTED_RIGHT_OBJECT:
        raise TaskPlanValidationError(
            f"Evidence object2_name must be {EXPECTED_RIGHT_OBJECT!r}"
        )

    expected_actions = (
        (EXPECTED_LEFT_OBJECT, TARGET_LEFT),
        (EXPECTED_RIGHT_OBJECT, TARGET_RIGHT),
    )
    for index, (action, (expected_object, expected_location)) in enumerate(
        zip(proposal.actions, expected_actions), start=1
    ):
        if action.tool != "move_object":
            raise TaskPlanValidationError(f"Action {index} must use move_object")
        args = dict(action.arguments)
        if args.get("file_name") != file_name:
            raise TaskPlanValidationError(f"Action {index} file_name does not match the selected fixture")
        if args.get("object_name") != expected_object:
            raise TaskPlanValidationError(
                f"Action {index} object_name must be {expected_object!r}"
            )
        if args.get("location") != expected_location:
            raise TaskPlanValidationError(
                f"Action {index} location must be {expected_location!r}"
            )


def get_validated_plan(file_name: str, audit: AuditTrail) -> TaskPlanProposal:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(file_name)},
        {"role": "user", "content": "Create the structured Atlas task plan."},
    ]
    last_error: Exception | None = None

    for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
        raw = ask_qwen(messages)
        print(f"--- QWEN PLAN ATTEMPT {attempt} ---")
        print(raw, flush=True)
        try:
            proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
            if proposal is None:
                raise TaskPlanValidationError("Qwen output decoded to no Atlas plan proposal")
            validate_conditional_proposal(proposal, file_name)
        except (TaskPlanValidationError, TypeError, ValueError) as exc:
            proposal = None
            last_error = exc

        if proposal is not None:
            audit.record_qwen_proposal(raw, attempt, True)
            return proposal

        if last_error is None:
            last_error = TaskPlanValidationError("Unknown Qwen plan validation failure")

        print(f"QWEN PLAN REJECTED: {last_error}", flush=True)
        audit.record_qwen_proposal(raw, attempt, False, str(last_error))
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
    return {"tool": action.tool, "arguments": dict(action.arguments), "name": action.name}


def prepare_case(case: str) -> str:
    """Select the deterministic fixture from the workflow workspace."""
    print(f"HARNESS_CWD: {Path.cwd().resolve()}", flush=True)
    print(f"HARNESS_WORKSPACE: {WORKSPACE}", flush=True)
    print(f"HARNESS_SOURCE_FILE: {SOURCE_FILE}", flush=True)

    if case == "already-correct":
        target_file = WORKING_CORRECT_FILE
        print(f"HARNESS_EXPECTED_FIXTURE: {target_file}", flush=True)
        print(f"HARNESS_FIXTURE_EXISTS: {target_file.is_file()}", flush=True)
        if not target_file.is_file():
            print("Blend files under workspace:", flush=True)
            for path in sorted(WORKSPACE.rglob("*.blend")):
                print(f"  {path}", flush=True)
            raise RuntimeError(f"Provisioned correct fixture not found: {target_file}")
        return str(target_file)

    target_file = WORKING_INCORRECT_FILE
    shutil.copy2(SOURCE_FILE, target_file)
    left = move_object(str(target_file), EXPECTED_LEFT_OBJECT, TARGET_LEFT)
    right = move_object(str(target_file), EXPECTED_RIGHT_OBJECT, TARGET_RIGHT)
    if left.get("status") != "moved" or right.get("status") != "moved":
        raise RuntimeError(f"Could not normalize conditional fixture: {left}; {right}")
    incorrect = move_object(str(target_file), EXPECTED_LEFT_OBJECT, [0.0, 5.000, 0.0])
    if incorrect.get("status") != "moved":
        raise RuntimeError(f"Could not prepare incorrect fixture: {incorrect}")
    return str(target_file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()

    file_name = prepare_case(args.case)
    audit = AuditTrail()
    proposal = get_validated_plan(file_name, audit)

    evidence_only = TaskPlanProposal(evidence=proposal.evidence, actions=[])
    evidence_execution = execute_read_only_plan(evidence_only)
    if not evidence_execution.get("read_only") or evidence_execution.get("execution_authorized"):
        raise RuntimeError("Evidence executor crossed the write boundary")

    relationship = evidence_execution["results"][0]["result"]
    audit.record_evidence(action_payload(proposal.evidence[0]), relationship)

    satisfied = target_is_satisfied(relationship)
    expected_case_satisfied = args.case == "already-correct"
    if satisfied != expected_case_satisfied:
        raise RuntimeError(
            f"Fixture/decision mismatch: case={args.case}, target_satisfied={satisfied}"
        )

    conditional = ConditionalActionPlan(
        action_plan=ActionPlan(list(proposal.actions)),
        condition=TargetCondition(path=("target_satisfied",), expected=True),
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
            raise RuntimeError("Satisfied target exposed or executed a conditional write")
        final = inspect_object_relationship(file_name, EXPECTED_LEFT_OBJECT, EXPECTED_RIGHT_OBJECT)
        if not target_is_satisfied(final):
            raise RuntimeError("Independent no-op verification failed")
        audit.record_verification(final, True)
        print("TARGET ALREADY SATISFIED")
        print("CONDITIONAL WRITE EXECUTION SKIPPED")
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

        final = inspect_object_relationship(file_name, EXPECTED_LEFT_OBJECT, EXPECTED_RIGHT_OBJECT)
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
