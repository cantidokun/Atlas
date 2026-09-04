from qwen.structured_plan import PRODUCTION_PROPOSAL_JSON_SCHEMA


def test_production_proposal_schema_is_proposal_only():
    assert PRODUCTION_PROPOSAL_JSON_SCHEMA["additionalProperties"] is False
    assert PRODUCTION_PROPOSAL_JSON_SCHEMA["required"] == ["workflow", "parameters"]
    assert set(PRODUCTION_PROPOSAL_JSON_SCHEMA["properties"]) == {"workflow", "version", "parameters"}


def test_production_proposal_schema_has_no_execution_capabilities():
    properties = PRODUCTION_PROPOSAL_JSON_SCHEMA["properties"]
    assert "executor" not in properties
    assert "authorization" not in properties
    assert "authorization_id" not in properties
    assert "tool" not in properties
    assert "actions" not in properties
    assert "recovery" not in properties


def test_version_contract_is_positive_or_null():
    version = PRODUCTION_PROPOSAL_JSON_SCHEMA["properties"]["version"]
    assert version["minimum"] == 1
    assert version["type"] == ["integer", "null"]
