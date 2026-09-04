import pytest

from qwen.production_proposal import (
    QwenProductionProposal,
    QwenProductionProposalError,
    compile_qwen_production_proposal,
    validate_qwen_production_proposal,
)


def _proposal():
    return {
        "workflow": "broadcast-goal-preparation",
        "version": 1,
        "parameters": {
            "file_name": "scene.blend",
            "object_name": "Goal_Left_post",
            "target_location": [0.25, 5.302, 0.0],
            "target_rotation": [0.0, 0.0, 15.0],
        },
    }


def test_valid_qwen_proposal_is_inert_and_typed():
    proposal = validate_qwen_production_proposal(_proposal())
    assert isinstance(proposal, QwenProductionProposal)
    assert proposal.workflow == "broadcast-goal-preparation"
    assert proposal.version == 1
    assert proposal.parameters["target_location"] == [0.25, 5.302, 0.0]
    snapshot = proposal.snapshot()
    assert snapshot["workflow"] == proposal.workflow
    assert snapshot["parameters"] == proposal.parameters


def test_qwen_proposal_rejects_unknown_top_level_fields():
    payload = _proposal()
    payload["execute"] = True
    with pytest.raises(QwenProductionProposalError, match="unexpected fields"):
        validate_qwen_production_proposal(payload)


def test_qwen_proposal_rejects_invalid_envelope():
    with pytest.raises(QwenProductionProposalError, match="must be an object"):
        validate_qwen_production_proposal([])

    payload = _proposal()
    payload["workflow"] = ""
    with pytest.raises(QwenProductionProposalError, match="workflow must be a non-empty string"):
        validate_qwen_production_proposal(payload)

    payload = _proposal()
    payload["version"] = True
    with pytest.raises(QwenProductionProposalError, match="version must be a positive integer"):
        validate_qwen_production_proposal(payload)

    payload = _proposal()
    payload["parameters"] = []
    with pytest.raises(QwenProductionProposalError, match="parameters must be an object"):
        validate_qwen_production_proposal(payload)


def test_qwen_proposal_reuses_catalog_validation_and_rejects_unknown_workflow():
    payload = _proposal()
    payload["workflow"] = "delete-the-field"
    with pytest.raises(QwenProductionProposalError, match="unknown soccer production workflow"):
        compile_qwen_production_proposal(payload)


def test_qwen_proposal_reuses_typed_parameter_validation():
    payload = _proposal()
    payload["parameters"] = {**payload["parameters"], "target_location": "0.25,5.302,0"}
    with pytest.raises(QwenProductionProposalError, match="target_location must be a list or tuple"):
        compile_qwen_production_proposal(payload)


def test_compilation_returns_canonical_production_task_without_authorization():
    task = compile_qwen_production_proposal(_proposal())
    assert task.name == "broadcast-goal-preparation"
    assert task.metadata["workflow_catalog"]["version"] == 1
    assert task.metadata["workflow_parameters"] == _proposal()["parameters"]
    assert task.metadata["workflow_template"] == "broadcast-goal-preparation"
    assert len(task.actions) == 2


def test_qwen_boundary_has_no_execution_fields():
    payload = _proposal()
    payload["parameters"] = {**payload["parameters"], "executor": "blender", "authorization_id": "root"}
    with pytest.raises(QwenProductionProposalError, match="unexpected parameters"):
        compile_qwen_production_proposal(payload)
