from planning.digital_twin_adapter_contract import is_stale
from planning.digital_twin_representation import ProductionTool, create_representation_contract


def test_adapter_contract_note_assumptions_are_executable():
    representation = create_representation_contract(
        "field-001",
        "field-001-unreal-r1",
        "field-001-r2",
        ProductionTool.UNREAL,
        "actor://FieldRoot",
    )
    assert is_stale(representation, "field-001-r2") is False
    assert is_stale(representation, "field-001-r3") is True
