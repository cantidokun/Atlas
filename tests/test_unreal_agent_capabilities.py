from planning.unreal_agent_capabilities import (
    UnrealCapability,
    capability_spec,
)


def test_unreal_inspection_capabilities_are_read_only():
    for capability in (
        UnrealCapability.WORLD_INSPECTION,
        UnrealCapability.ENTITY_INSPECTION,
        UnrealCapability.ASSET_INSPECTION,
    ):
        spec = capability_spec(capability)
        assert spec.read_only is True
        assert spec.requires_authorization is False
        assert spec.requires_independent_verification is True


def test_unreal_write_capabilities_require_authorization_and_verification():
    for capability in UnrealCapability:
        if capability in {
            UnrealCapability.WORLD_INSPECTION,
            UnrealCapability.ENTITY_INSPECTION,
            UnrealCapability.ASSET_INSPECTION,
        }:
            continue
        spec = capability_spec(capability)
        assert spec.read_only is False
        assert spec.requires_authorization is True
        assert spec.requires_independent_verification is True


def test_capability_vocabulary_includes_real_time_production_domains():
    assert UnrealCapability.NIAGARA_MODIFICATION.value == "niagara_modification"
    assert UnrealCapability.SEQUENCER_MODIFICATION.value == "sequencer_modification"
    assert UnrealCapability.RENDER_TEST.value == "render_test"
