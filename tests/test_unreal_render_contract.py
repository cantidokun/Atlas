import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_contract import verify_render_config


EXPECTED = {
    "width": 640,
    "height": 360,
    "start_frame": 1,
    "end_frame": 2,
    "output_directory": "Saved/AtlasRenderOutput",
    "output_format": "png",
}


def _evidence(**render_overrides):
    render = dict(EXPECTED)
    render.update(render_overrides)
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"render_job": {"render": render}},
        verified=True,
        source="render-contract-test",
    )


def test_verify_render_config_accepts_matching_verified_inspection():
    evidence = _evidence()
    assert verify_render_config(evidence, EXPECTED) is evidence


def test_verify_render_config_accepts_immutable_evidence_state():
    evidence = _evidence()
    assert verify_render_config(evidence, EXPECTED) is evidence
    assert isinstance(evidence.observed_state, dict) is False


def test_verify_render_config_rejects_unverified_evidence():
    evidence = UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"render_job": {"render": EXPECTED}},
        verified=False,
        source="render-contract-test",
    )
    with pytest.raises(ValueError, match="verified"):
        verify_render_config(evidence, EXPECTED)


def test_verify_render_config_rejects_wrong_operation():
    evidence = UnrealEvidence(
        operation_name="submit_render",
        entity_ids=("FIELD_SURFACE",),
        observed_state={"render_job": {"render": EXPECTED}},
        verified=True,
        source="render-contract-test",
    )
    with pytest.raises(ValueError, match="inspect_render_job"):
        verify_render_config(evidence, EXPECTED)


def test_verify_render_config_rejects_non_evidence_input():
    with pytest.raises(TypeError, match="UnrealEvidence"):
        verify_render_config(object(), EXPECTED)


def test_verify_render_config_rejects_render_drift():
    evidence = _evidence(width=1280)
    with pytest.raises(ValueError, match="does not match expected configuration"):
        verify_render_config(evidence, EXPECTED)
