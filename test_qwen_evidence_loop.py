from evidence_plan import EvidenceRequest
from qwen_evidence_loop import (
    build_next_qwen_messages,
    execute_evidence_proposal,
    parse_evidence_proposal,
    proposal_to_evidence_plan,
)
from task_planner import TaskPlanProposal


def test_parse_evidence_proposal_rejects_actions():
    assert parse_evidence_proposal(
        '{"evidence":[],"actions":[{"tool":"move_object","arguments":{}}]}',
        {"inspect_scene", "move_object"},
    ) is None


def test_proposal_to_evidence_plan_preserves_validated_requests():
    proposal = TaskPlanProposal(
        evidence=[EvidenceRequest("inspect_scene", {"file_name": "x.blend"}, "scene")],
        actions=[],
    )
    plan = proposal_to_evidence_plan(proposal, {"inspect_scene"})
    assert plan.next_request.tool == "inspect_scene"
    assert plan.next_request.arguments == {"file_name": "x.blend"}


def test_execute_evidence_proposal_is_read_only(monkeypatch):
    seen = []

    monkeypatch.setattr(
        "qwen_evidence_loop.execute_read_only_plan",
        lambda proposal: seen.append(proposal) or {
            "read_only": True,
            "execution_authorized": False,
            "results": [{"tool": "inspect_scene", "result": {"total_objects": 6}}],
        },
    )

    proposal = TaskPlanProposal(
        evidence=[EvidenceRequest("inspect_scene", {}, "scene")],
        actions=[],
    )
    result = execute_evidence_proposal(proposal, {"inspect_scene"})

    assert result["read_only"] is True
    assert result["execution_authorized"] is False
    assert len(seen) == 1
    assert seen[0].actions == []


def test_feedback_contains_only_verified_results():
    messages = build_next_qwen_messages(
        [{"role": "system", "content": "Atlas"}],
        {"results": [{"tool": "inspect_scene", "result": {"total_objects": 6}}]},
    )
    assert len(messages) == 2
    assert "ATLAS_VERIFIED_EVIDENCE:" in messages[-1]["content"]
    assert "total_objects" in messages[-1]["content"]
