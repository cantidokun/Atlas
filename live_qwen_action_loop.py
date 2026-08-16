"""Live harness for the first Qwen-proposed, Python-authorized write test.

The model may propose evidence and actions, but the read-only evidence executor
receives an evidence-only copy of the proposal. The original proposal then
passes through the Python authorization gate before any write is executed.
"""

import json
from typing import Any, Dict, List

import requests

from action_plan import ActionPlan
from qwen_planning_runtime import parse_qwen_plan
from qwen_planning_executor import execute_read_only_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
FILE = "goalpost_test.blend"

ALLOWED_TOOLS = {
    "inspect_object_relationship",
    "move_object",
}

SYSTEM_PROMPT = """You are the Atlas planning assistant.

The user has authorized this specific Blender task:
- Move Goal_Left_post to [0.0, 5.233, 0.0].
- Move Goal_Right_Post to [0.0, -5.233, 0.0].

Return ONLY valid JSON with exactly two top-level fields: evidence and actions.

The evidence request MUST be:
{"tool":"inspect_object_relationship","arguments":{"file_name":"goalpost_test.blend","object1_name":"Goal_Left_post","object2_name":"Goal_Right_Post"},"name":"inspect goalpost relationship"}

The actions MUST contain exactly these two move_object actions, in this order:
1. Goal_Left_post -> [0.0, 5.233, 0.0]
2. Goal_Right_Post -> [0.0, -5.233, 0.0]

Do not add other actions, tools, coordinates, fields, markdown, or explanations.
Do not execute tools yourself."""


def ask_qwen() -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Create the authorized Atlas task plan."},
            ],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def execute_move_action(action: Any) -> Dict[str, Any]:
    if action.tool != "move_object":
        raise RuntimeError(f"Unexpected action tool: {action.tool}")
    return move_object(**action.arguments)


def main() -> None:
    raw = ask_qwen()
    print("--- QWEN PLAN ---")
    print(raw)

    proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
    if proposal is None:
        raise RuntimeError("Qwen proposal was rejected")

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
