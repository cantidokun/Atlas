import pytest

from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from task_planner import TaskPlanProposal
from task_runtime_bridge import TaskRuntimeBridge, TaskRuntimeBridgeError


def make_bridge():
    proposal = TaskPlanProposal(
        evidence=[
            EvidenceRequest(tool="inspect_scene", arguments={"file": "scene.blend"})
        ],
        actions=[
            ActionSpec(tool="modify_scene", arguments={"value": 1})
        ],
    )
    return TaskRuntimeBridge(proposal)


def test_actions_cannot_be_authorized_before_evidence():
    bridge = make_bridge()

    with pytest.raises(TaskRuntimeBridgeError, match="evidence"):
        bridge.authorize_actions()


def test_evidence_then_action_then_verification():
    bridge = make_bridge()

    evidence = bridge.acquire_next_evidence(
        lambda tool, args: {"success": True, "tool": tool}
    )
    assert evidence["tool"] == "inspect_scene"
    assert bridge.evidence_complete is True

    bridge.execution.allowed_action_tools = {"modify_scene"}
    bridge.execution.allow_writes = True
    bridge.authorize_actions()

    action = bridge.execute_next_action(
        lambda tool, args: {"success": True, "tool": tool}
    )
    assert action["tool"] == "modify_scene"

    bridge.mark_verified({"success": True, "verified": True})
    assert bridge.complete is True


def test_failed_evidence_blocks_progress():
    bridge = make_bridge()

    with pytest.raises(TaskRuntimeBridgeError, match="Evidence acquisition failed"):
        bridge.acquire_next_evidence(lambda tool, args: {"success": False})

    assert bridge.evidence_plan.blocked is True
    assert bridge.evidence_complete is False


def test_reused_evidence_is_recorded_without_changing_request_order():
    bridge = make_bridge()

    bridge.acquire_next_evidence(
        lambda tool, args: {"success": True, "source": "ledger"},
        reused=True,
    )

    snapshot = bridge.snapshot()
    assert snapshot["evidence_plan"]["skipped"][0]["reused"] is True
    assert snapshot["evidence_plan"]["complete"] is True
