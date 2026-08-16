"""Live harness for the first Qwen-proposed, Python-authorized write test.

The model may propose evidence and actions, but the read-only evidence executor
receives an evidence-only copy of the proposal. The original proposal then
passes through the Python authorization gate before any write is executed.

The live model is treated as untrusted: malformed schema output is rejected
and corrected through a bounded prompt retry rather than being coerced into an
action. No write occurs until a fully validated proposal passes the Python
authorization gate.
"""

import json
from typing import Any, Dict, List

import requests

from action_plan import ActionPlan
from qwen_planning_runtime import parse_qwen_plan
from qwen_planning_executor import execute_read_only_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
FILE = "goalpost_test.blend"
MAX_PLAN_ATTEMPTS = 3

ALLOWED_TOOLS = {
    "inspect_object_relationship",
    "move_object",
}

SYSTEM_PROMPT = """You are the Atlas planning assistant.

The user has authorized this specific Blender task:
- Move Goal_Left_post to [0.0, 5.233, 0.0].
- Move Goal_Right_Post to [0.0, -5.233, 0.0].

Return ONLY valid JSON with exactly two top-level fields: evidence and actions.
Both fields MUST be JSON arrays.

Every evidence item MUST have exactly these conceptual fields:
- tool
- arguments
- name

The evidence request MUST be:
{"tool":"inspect_object_relationship","arguments":{"file_name":"goalpost_test.blend","object1_name":"Goal_Left_post","object2_name":"Goal_Right_Post"},"name":"inspect goalpost relationship"}

Every action item MUST have these fields:
- tool
- arguments
- name

The actions MUST contain exactly these two move_object actions, in this order:
1. {"tool":"move_object","arguments":{"file_name":"goalpost_test.blend","object_name":"Goal_Left_post","location":[0.0,5.233,0.0]},"name":"move left goalpost"}
2. {"tool":"move_object","arguments":{"file_name":"goalpost_test.blend","object_name":"Goal_Right_Post","location":[0.0,-5.233,0.0]},"name":"move right goalpost"}

Do NOT use alternative field names such as action, target_position, object, or type.
Do NOT make evidence an object; it MUST be an array.
Do NOT add other actions, tools, coordinates, fields, markdown, or explanations.
Do not execute tools yourself."""

CORRECTION_PROMPT = """Your previous output did not match the Atlas task-plan schema.
Return ONLY the corrected JSON object.

Required top-level shape:
{"evidence":[{"tool":"inspect_object_relationship","arguments":{"file_name":"goalpost_test.blend","object1_name":"Goal_Left_post","object2_name":"Goal_Right_Post"},"name":"inspect goalpost relationship"}],"actions":[{"tool":"move_object","arguments":{"file_name":"goalpost_test.blend","object_name":"Goal_Left_post","location":[0.0,5.233,0.0]},"name":"move left goalpost"},{"tool":"move_object","arguments":{"file_name":"goalpost_test.blend","object_name":"Goal_Right_Post","location":[0.0,-5.233,0.0]},"name":"move right goalpost"}]}

Both evidence and actions MUST be arrays. Use tool/arguments/name exactly. Do not use action or target_position."""


def ask_qwen(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def get_validated_plan() -> TaskPlanProposal:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Create the authorized Atlas task plan."},
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
            return proposal

        if attempt < MAX_PLAN_ATTEMPTS:
            messages.extend(
                [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": CORRECTION_PROMPT},
                ]
            )

    raise RuntimeError(
        f"Qwen did not produce a valid Atlas task plan after {MAX_PLAN_ATTEMPTS} attempts: {last_error}"
    )


def execute_move_action(action: Any) -> Dict[str, Any]:
    if action.tool != "move_object":
        raise RuntimeError(f"Unexpected action tool: {action.tool}")
    return move_object(**action.arguments)


def main() -> None:
    proposal = get_validated_plan()

    print("--- PLAN VALIDATION ---")
    print(f"Evidence requests: {len(proposal.evidence)}")
    print(f"Actions: {len(proposal.actions)}")

    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise RuntimeError("Unexpected plan shape")

    if any(action.tool != "move_object" for action in proposal.actions):
        raise RuntimeError("Unexpected action tool")

    # The read-only executor must never receive actions. Give it an inert,
    # evidence-only copy of the validated proposal.
    evidence_only = TaskPlanProposal(
        evidence=proposal.evidence,
        actions=[],
    )

    evidence_execution = execute_read_only_plan(evidence_only)
    print("--- BEFORE EVIDENCE ---")
    print(json.dumps(evidence_execution, indent=2))

    relationship = evidence_execution["results"][0]["result"]
    if relationship["object_a"]["location"] != [0.0, 5.302, 0.0]:
        raise RuntimeError("Unexpected BEFORE left-post location")
    if relationship["object_b"]["location"] != [0.0, -5.164, 0.0]:
        raise RuntimeError("Unexpected BEFORE right-post location")
    if relationship["midpoint"] != [0.0, 0.069, 0.0]:
        raise RuntimeError("Unexpected BEFORE midpoint")

    print("--- BEFORE STATE CONFIRMED ---")

    authorize_task_plan(
        proposal,
        evidence_complete=True,
        allowed_action_tools={"move_object"},
        allow_writes=True,
    )
    print("--- WRITE AUTHORIZATION ---")
    print("AUTHORIZED: True")

    action_plan = ActionPlan(proposal.actions)
    while not action_plan.complete:
        action = action_plan.next_action
        if action is None:
            raise RuntimeError("Action plan unexpectedly has no next action")

        print(f"--- ACTION {action_plan.current_index + 1} ---")
        result = execute_move_action(action)
        print(json.dumps(result, indent=2))

        success = result.get("status") == "moved"
        action_plan.record_result(result, success=success)
        if not success:
            raise RuntimeError(f"Authorized action failed: {result}")

    print("--- ACTION PLAN COMPLETE ---")
    print(json.dumps(action_plan.snapshot(), indent=2))

    print("--- FINAL INDEPENDENT VERIFICATION ---")
    final = inspect_object_relationship(
        FILE,
        "Goal_Left_post",
        "Goal_Right_Post",
    )
    print(json.dumps(final, indent=2))

    assert final["object_a"]["location"] == [0.0, 5.233, 0.0]
    assert final["object_b"]["location"] == [0.0, -5.233, 0.0]
    assert final["midpoint"] == [0.0, 0.0, 0.0]
    assert final["symmetric_about_origin"] is True
    assert final["distance"] == 10.466

    print("--- ATLAS RESULT ---")
    print("QWEN PROPOSAL ACCEPTED")
    print("PYTHON AUTHORIZATION ACCEPTED")
    print("TWO WRITES EXECUTED")
    print("FINAL STATE INDEPENDENTLY VERIFIED")
    print("ATLAS END-TO-END WRITE TEST: PASS")


if __name__ == "__main__":
    main()
