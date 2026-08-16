"""Live conditional harness for the reusable centered-goal geometry scenario.

This intentionally reuses the proven Qwen plan validation, read-only evidence
execution, authorization gate, action execution, and independent verification
from live_qwen_conditional_loop.py. The only changed decision rule is the
application-owned centered_goal_condition predicate.
"""

import argparse
import json
from typing import Any, Dict

from action_plan import ActionPlan
from audit_trail import AuditTrail
from live_qwen_conditional_loop import (
    EXPECTED_LEFT_OBJECT,
    EXPECTED_RIGHT_OBJECT,
    WORKING_CORRECT_FILE,
    action_payload,
    get_validated_plan,
    prepare_case,
)
from planning.conditional_action import ConditionalActionPlan
from qwen_planning_executor import execute_read_only_plan
from scenarios.goal_geometry import centered_goal_condition, goal_center_alignment
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal
from tools.blender import inspect_object_relationship


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("already-correct", "incorrect"), required=True)
    args = parser.parse_args()

    fixture_path = prepare_case(args.case)
    file_name = WORKING_CORRECT_FILE.name if args.case == "already-correct" else fixture_path.rsplit("\\", 1)[-1]
    audit = AuditTrail()
    proposal = get_validated_plan(file_name, audit)

    evidence_only = TaskPlanProposal(evidence=proposal.evidence, actions=[])
    evidence_execution = execute_read_only_plan(evidence_only)
    if not evidence_execution.get("read_only") or evidence_execution.get("execution_authorized"):
        raise RuntimeError("Evidence executor crossed the write boundary")

    relationship: Dict[str, Any] = evidence_execution["results"][0]["result"]
    audit.record_evidence(action_payload(proposal.evidence[0]), relationship)

    evidence = {"relationship": relationship}
    satisfied = goal_center_alignment(evidence)
    expected = args.case == "already-correct"
    if satisfied != expected:
        raise RuntimeError(
            f"Centered-goal fixture/decision mismatch: case={args.case}, target_satisfied={satisfied}"
        )

    conditional = ConditionalActionPlan(
        action_plan=ActionPlan(list(proposal.actions)),
        condition=centered_goal_condition(),
    )
    conditional.evaluate(evidence)
    audit.record(
        "conditional_decision",
        "skip" if satisfied else "execute",
        target_satisfied=satisfied,
        scenario="centered_goal_geometry",
        case=args.case,
    )

    print("--- CENTERED-GOAL CONDITIONAL DECISION ---")
    print(json.dumps(conditional.snapshot(), indent=2))

    if satisfied:
        if conditional.next_action is not None:
            raise RuntimeError("Satisfied centered-goal target exposed a conditional write")
        final = inspect_object_relationship(file_name, EXPECTED_LEFT_OBJECT, EXPECTED_RIGHT_OBJECT)
        final_ok = goal_center_alignment({"relationship": final})
        audit.record_verification(final, final_ok)
        if not final_ok:
            raise RuntimeError("Centered-goal independent no-op verification failed")
        print("CENTERED GOAL ALREADY SATISFIED")
        print("CENTERED-GOAL WRITE EXECUTION SKIPPED")
        print("ATLAS CENTERED-GOAL ALREADY-CORRECT TEST: PASS")
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
                raise RuntimeError("Centered-goal conditional plan has no executable action")
            index = conditional.action_plan.current_index
            result = __import__("tools.blender", fromlist=["move_object"]).move_object(**action.arguments)
            success = result.get("status") == "moved"
            audit.record_action(index, action_payload(action), result, success)
            conditional.action_plan.record_result(result, success)
            if not success:
                raise RuntimeError(f"Authorized centered-goal action failed: {result}")

        final = inspect_object_relationship(file_name, EXPECTED_LEFT_OBJECT, EXPECTED_RIGHT_OBJECT)
        final_ok = goal_center_alignment({"relationship": final})
        audit.record_verification(final, final_ok)
        if not final_ok:
            raise RuntimeError("Centered-goal independent final verification failed")
        print("CENTERED GOAL FINAL STATE INDEPENDENTLY VERIFIED")
        print("ATLAS CENTERED-GOAL INCORRECT-STATE TEST: PASS")

    print("--- AUDIT TRAIL ---")
    print(json.dumps(audit.snapshot(), indent=2))


if __name__ == "__main__":
    main()
