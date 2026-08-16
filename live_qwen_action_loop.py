"""Live harness for Qwen-proposed, Python-authorized write planning."""
import json
from typing import Any, Dict, List
import requests
from action_plan import ActionPlan
from audit_trail import AuditTrail
from qwen_planning_runtime import parse_qwen_plan
from qwen_planning_executor import execute_read_only_plan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal, TaskPlanValidationError
from tools.blender import inspect_object_relationship, move_object

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
FILE = "goalpost_test.blend"
MAX_PLAN_ATTEMPTS = 3
ALLOWED_TOOLS = {"inspect_object_relationship", "move_object"}
TARGETS = {"Goal_Left_post": [0.0, 5.233, 0.0], "Goal_Right_Post": [0.0, -5.233, 0.0]}
SYSTEM_PROMPT = '''You are the Atlas planning assistant. The user has authorized this task: move Goal_Left_post to [0.0, 5.233, 0.0] and Goal_Right_Post to [0.0, -5.233, 0.0]. Return ONLY valid JSON with exactly two top-level array fields: evidence and actions. Evidence must contain exactly one inspect_object_relationship request for the two goalposts. Actions must contain exactly two move_object actions in left-then-right order. Use only tool, arguments, and name fields.'''
CORRECTION_PROMPT = '''Return only corrected Atlas task-plan JSON. evidence and actions must both be arrays. Use tool, arguments, name exactly. Evidence: inspect_object_relationship on goalpost_test.blend for Goal_Left_post and Goal_Right_Post. Actions: move Goal_Left_post to [0.0,5.233,0.0], then Goal_Right_Post to [0.0,-5.233,0.0].'''

def ask_qwen(messages: List[Dict[str, str]]) -> str:
    r = requests.post(OLLAMA_URL, json={"model": MODEL, "messages": messages, "stream": False}, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]

def get_validated_plan(audit: AuditTrail) -> TaskPlanProposal:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "Create the authorized Atlas task plan."}]
    last_error = None
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
        audit.record_qwen_proposal(raw, attempt, False, str(last_error) if last_error else "schema validation failed")
        if attempt < MAX_PLAN_ATTEMPTS:
            messages.extend([{ "role": "assistant", "content": raw}, {"role": "user", "content": CORRECTION_PROMPT}])
    raise RuntimeError(f"Qwen did not produce a valid Atlas task plan after {MAX_PLAN_ATTEMPTS} attempts: {last_error}")

def _item_dict(item: Any) -> Dict[str, Any]:
    return {"tool": item.tool, "arguments": dict(item.arguments), "name": item.name}

def main() -> None:
    audit = AuditTrail()
    proposal = get_validated_plan(audit)
    if len(proposal.evidence) != 1 or len(proposal.actions) != 2:
        raise RuntimeError("Unexpected plan shape")
    if [a.tool for a in proposal.actions] != ["move_object", "move_object"]:
        raise RuntimeError("Unexpected action tools")
    evidence_only = TaskPlanProposal(evidence=proposal.evidence, actions=[])
    evidence_execution = execute_read_only_plan(evidence_only)
    print("--- EVIDENCE ---")
    print(json.dumps(evidence_execution, indent=2))
    relationship = evidence_execution["results"][0]["result"]
    audit.record_evidence(_item_dict(proposal.evidence[0]), relationship)
    current = {relationship["object_a"]["name"]: relationship["object_a"]["location"], relationship["object_b"]["name"]: relationship["object_b"]["location"]}
    if current == TARGETS:
        print("--- ACTION PLAN DECISION ---")
        print("TARGET ALREADY SATISFIED: TRUE")
        print("WRITE EXECUTION: SKIPPED")
        verification = inspect_object_relationship(FILE, "Goal_Left_post", "Goal_Right_Post")
        ok = verification.get("midpoint") == [0.0, 0.0, 0.0] and verification.get("symmetric_about_origin") is True
        audit.record_verification(verification, ok)
        if not ok:
            raise RuntimeError("No-op verification failed")
        print("--- ATLAS RESULT ---")
        print("QWEN PROPOSAL ACCEPTED")
        print("EVIDENCE VERIFIED READ-ONLY")
        print("TARGET ALREADY SATISFIED")
        print("NO WRITES EXECUTED")
        print("STATE INDEPENDENTLY VERIFIED")
        print("ATLAS NO-OP PLANNING TEST: PASS")
        return
    authorize_task_plan(proposal, evidence_complete=True, allowed_action_tools={"move_object"}, allow_writes=True)
    audit.record_authorization(True, action_count=len(proposal.actions))
    action_plan = ActionPlan(proposal.actions)
    while not action_plan.complete:
        action = action_plan.next_action
        if action is None:
            raise RuntimeError("Action plan unexpectedly has no next action")
        index = action_plan.current_index
        payload = _item_dict(action)
        result = move_object(**action.arguments)
        success = result.get("status") == "moved"
        audit.record_action(index, payload, result, success)
        action_plan.record_result(result, success=success)
        if not success:
            raise RuntimeError(f"Authorized action failed: {result}")
    final = inspect_object_relationship(FILE, "Goal_Left_post", "Goal_Right_Post")
    ok = final["object_a"]["location"] == TARGETS["Goal_Left_post"] and final["object_b"]["location"] == TARGETS["Goal_Right_Post"] and final["midpoint"] == [0.0, 0.0, 0.0] and final["symmetric_about_origin"] is True
    audit.record_verification(final, ok)
    if not ok:
        raise RuntimeError("Independent final verification failed")
    print("--- ATLAS RESULT ---")
    print("QWEN PROPOSAL ACCEPTED")
    print("PYTHON AUTHORIZATION ACCEPTED")
    print("ACTION PLAN EXECUTED")
    print("FINAL STATE INDEPENDENTLY VERIFIED")
    print("AUDIT TRAIL COMPLETE")
    print("ATLAS END-TO-END ACTION TEST: PASS")

if __name__ == "__main__":
    main()
