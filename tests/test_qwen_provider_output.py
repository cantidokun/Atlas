import json

import pytest

from qwen.production_proposal import QwenProductionProposal
from qwen.provider_output import parse_qwen_production_output


def _payload():
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


def test_parses_json_string_into_proposal():
    proposal = parse_qwen_production_output(json.dumps(_payload()))
    assert isinstance(proposal, QwenProductionProposal)
    assert proposal.workflow == "broadcast-goal-preparation"


def test_parses_utf8_bytes_into_proposal():
    proposal = parse_qwen_production_output(json.dumps(_payload()).encode("utf-8"))
    assert proposal.version == 1


def test_rejects_malformed_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_qwen_production_output("{bad")


def test_rejects_non_utf8_bytes():
    with pytest.raises(ValueError, match="must be UTF-8 JSON"):
        parse_qwen_production_output(b"\xff")


def test_rejects_execution_fields_after_provider_parsing():
    payload = _payload()
    payload["executor"] = "blender"
    with pytest.raises(ValueError, match="unexpected fields"):
        parse_qwen_production_output(json.dumps(payload))


def test_accepts_already_decoded_json_object():
    proposal = parse_qwen_production_output(_payload())
    assert proposal.parameters["object_name"] == "Goal_Left_post"
