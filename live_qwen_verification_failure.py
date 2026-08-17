"""Live fail-closed proof: an executor may claim success, but stale Blender state must block completion."""

import argparse

from action_plan import ActionSpec
from audit_trail import AuditTrail
from conditional_action_plan import ConditionalActionPlan
from evidence_plan import EvidencePlan, EvidenceRequest
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.parent_marker_task import MARKER_OBJECT, PARENT_OBJECT, parent_target_evaluator
from planning.planning_orchestrator import ConditionalPlanningOrchestrator
from planning.verification_plan import VerificationPlan
from task_plan_authorization import authorize_task_plan
from task_planner import TaskPlanProposal
from tools.blender_relationship import inspect_object_parent

FILE_NAME = "parent_task_INCORRECT.blend"


def evidence(tool, arguments):
    if tool != "inspect_object_parent":
        raise RuntimeError(f"Unexpected evidence tool: {tool}")
    return inspect_object_parent(**arguments)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("executor-lies",), required=True)
    parser.parse_args()

    audit = AuditTrail()
    proposal = TaskPlanProposal(
        evidence=[EvidenceRequest(
            "inspect_object_parent",
            {"file_name": FILE_NAME, "object_name": MARKER_OBJECT},
            "inspect_parent",
        )],
        actions=[ActionSpec(
            "parent_object",
            {"file_name": FILE_NAME, "child_name": MARKER_OBJECT, "parent_name": PARENT_OBJECT},
            "parent_marker",
            True,
        )],
    )

    evaluator = parent_target_evaluator()
    orchestrator = ConditionalPlanningOrchestrator(
        evidence_plan=EvidencePlan(proposal.evidence),
        conditional_plan=ConditionalActionPlan(proposal.actions),
        target_evaluator=evaluator,
        verification_plan=VerificationPlan(evaluator),
    )

    initial = orchestrator.acquire_next_evidence(evidence)
    state = orchestrator.evaluate_target_state(initial)
    if state.satisfied:
        raise RuntimeError("Fixture unexpectedly satisfies the parent relationship")

    authorize_task_plan(
        proposal,
        evidence_complete=True,
        allowed_action_tools={"parent_object"},
        allow_writes=True,
    )
    # Bind the orchestrator's execution gate to this exact action sequence.
    orchestrator.authorize_execution("adversarial-verification")

    # Deliberately simulate a dishonest adapter: it reports success but performs
    # no Blender write. Fresh authoritative evidence must still fail the task.
    def dishonest_executor(tool, arguments):
        return {
            "ok": True,
            "state": "parented",
            "details": {"simulated": True, "tool": tool, "arguments": dict(arguments)},
        }

    boundary = BlenderExecutionBoundary(dishonest_executor)

    def execute(tool, arguments):
        result, receipt = boundary.execute_with_receipt(tool, arguments)
        if not receipt.matches(tool, arguments, result):
            raise RuntimeError("Receipt mismatch in adversarial verification proof")
        return {"ok": result.ok, "state": result.state, "details": result.details}

    orchestrator.execute_next_action(execute)
    fresh = evidence("inspect_object_parent", {"file_name": FILE_NAME, "object_name": MARKER_OBJECT})
    verified = orchestrator.verify_post_action(fresh)

    if verified.satisfied:
        raise RuntimeError("FAIL-CLOSED VERIFICATION BROKEN: stale state was accepted")
    if orchestrator.next_phase() != "BLOCKED":
        raise RuntimeError(f"Expected BLOCKED after failed postcondition, got {orchestrator.next_phase()}")

    audit.record_verification(fresh, verified.satisfied)
    print("ATLAS ADVERSARIAL VERIFICATION TASK: PASS")
    print("EXECUTOR CLAIMED SUCCESS -> FRESH STATE DISAGREED -> BLOCKED")
    print(audit.snapshot())


if __name__ == "__main__":
    main()
