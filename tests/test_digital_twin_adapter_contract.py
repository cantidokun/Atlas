import pytest

from planning.digital_twin_adapter_contract import (
    DigitalTwinToolAdapter,
    ToolActionResult,
    ToolEvidence,
    is_stale,
    require_current_representation,
)
from planning.digital_twin_representation import (
    ProductionTool,
    RepresentationState,
    create_representation_contract,
    mark_representation_state,
)


def representation(revision="field-001-r2"):
    return create_representation_contract(
        "field-001",
        "field-001-unreal-r2",
        revision,
        ProductionTool.UNREAL,
        "actor://FieldRoot",
    )


def test_current_representation_is_not_stale():
    current = representation()
    assert is_stale(current, "field-001-r2") is False
    assert require_current_representation(current, "field-001-r2") is current


def test_representation_from_old_revision_is_stale():
    current = representation("field-001-r1")
    assert is_stale(current, "field-001-r2") is True
    with pytest.raises(ValueError, match="stale"):
        require_current_representation(current, "field-001-r2")


def test_explicitly_stale_state_is_rejected():
    stale = mark_representation_state(representation(), RepresentationState.STALE)
    assert is_stale(stale, "field-001-r2") is True


def test_empty_current_revision_is_rejected():
    with pytest.raises(ValueError, match="current_revision_id"):
        is_stale(representation(), "   ")


def test_tool_evidence_requires_identity():
    with pytest.raises(ValueError, match="identity"):
        ToolEvidence("", "evidence-1", {})


def test_action_result_is_metadata_only():
    result = ToolActionResult("field-001-unreal-r2", "move-goal", True, ("evidence-7",))
    assert result.success is True
    assert result.evidence_ids == ("evidence-7",)


def test_contract_is_engine_neutral_protocol():
    assert hasattr(DigitalTwinToolAdapter, "inspect")
    assert hasattr(DigitalTwinToolAdapter, "apply_authorized_action")
    assert hasattr(DigitalTwinToolAdapter, "synchronize")
