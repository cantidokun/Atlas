"""Live Qwen planning harness for evidence-to-action orchestration.

This harness keeps the model untrusted: Qwen proposes a structured task plan,
Python validates it, read-only evidence is executed first, and only then is the
resulting action plan surfaced. No Blender writes are performed by this harness.
"""

import json
from typing import Any, Dict, List

import requests

from qwen_planning_runtime import parse_qwen_plan
from qwen_planning_executor import execute_read_only_plan
from task_planner import TaskPlanValidationError
from planning.planning_orchestrator import PlanningOrchestrator
from planning.evidence_plan import EvidencePlan
from planning.action_plan import ActionPlan

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
FILE = "goalpost_test.blend"

ALLOWED_TOOLS = {"inspect_scene", "inspect_object_relationship", "move_object"}

SYSTEM_PROMPT = """You are the Atlas planning assistant.
Return ONLY JSON with exactly two top-level fields: evidence and actions.
Both fields MUST be arrays. Every item MUST contain tool, arguments, and name.

For this test, produce a plan to establish the current goalpost relationship,
then propose moving the two goalposts so their midpoint is the world origin:
- Goal_Left_post -> [0.0, 5.233, 0.0]
- Goal_Right_Post -> [0.0, -5.233, 0.0]

Required evidence:
inspect_object_relationship(file_name="goalpost_test.blend",
  object1_name="Goal_Left_post", object2_name="Goal_Right_Post")

Required actions, in order:
1. move_object(file_name="goalpost_test.blend", object_name="Goal_Left_post", location=[0.0,5.233,0.0])
2. move_object(file_name="goalpost_test.blend", object_name="Goal_Right_Post", location=[0.0,-5.233,0.0])

Do not add tools, fields, markdown, or explanations."""


def ask_qwen(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def main() -> None:
    raw = ask_qwen("Create the structured Atlas plan.")
    print("--- QWEN STRUCTURED PLAN ---")
    print(raw)

    try:
        proposal = parse_qwen_plan(raw, allowed_tools=ALLOWED_TOOLS)
    except (TaskPlanValidationError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Qwen plan rejected: {exc}") from exc

    if proposal is None:
        raise RuntimeError("Qwen did not produce a valid structured plan")

    print("--- PLAN VALIDATED ---")
    print(json.dumps({
        "evidence_requests": len(proposal.evidence),
        "actions": len(proposal.actions),
    }, indent=2))

    if not proposal.evidence:
        raise RuntimeError("No evidence requests in structured plan")
    if not proposal.actions:
        raise RuntimeError("No action requests in structured plan")

    evidence_only = type(proposal)(evidence=proposal.evidence, actions=[])
    evidence_result = execute_read_only_plan(evidence_only)
    print("--- READ-ONLY EVIDENCE ---")
    print(json.dumps(evidence_result, indent=2))

    if not evidence_result.get("read_only") or evidence_result.get("execution_authorized"):
        raise RuntimeError("Evidence executor crossed the write boundary")

    evidence_plan = EvidencePlan(proposal.evidence)
    for result in evidence_result.get("results", []):
        evidence_plan.record_result(result, success=True)

    action_plan = ActionPlan(proposal.actions)
    orchestrator = PlanningOrchestrator(evidence_plan=evidence_plan, action_plan=action_plan)
    snapshot = orchestrator.snapshot()

    print("--- PLANNING ORCHESTRATOR ---")
    print(json.dumps(snapshot, indent=2, default=str))

    if snapshot.get("blocked"):
        raise RuntimeError("Planning orchestrator unexpectedly blocked")
    if not evidence_plan.complete:
        raise RuntimeError("Evidence plan did not complete")
    if action_plan.complete:
        raise RuntimeError("Action plan should remain unexecuted")

    print("--- ATLAS PLANNING RESULT ---")
    print("QWEN PLAN ACCEPTED")
    print("EVIDENCE VERIFIED READ-ONLY")
    print("ACTION PLAN STRUCTURED")
    print("WRITE EXECUTION NOT PERFORMED")
    print("ATLAS QWEN PLANNING BRIDGE TEST: PASS")


if __name__ == "__main__":
    main()
