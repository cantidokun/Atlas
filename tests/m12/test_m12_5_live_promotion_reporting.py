"""Deterministic tests for the M12.5 live-gate evidence classifier."""

from types import SimpleNamespace

from tests.m12.m12_5_live_promotion_gate import _render_dimension_summary


def test_render_dimension_summary_exposes_the_v1_closed_dimensions():
    record = SimpleNamespace(canonical_digital_twin_id="twin-1")
    task = SimpleNamespace(digital_twin_id="twin-1")
    dimensions = _render_dimension_summary(
        record=record,
        task=task,
        observed_state={"config_digest": "abc"},
        m5_verified=True,
        m5_config_digest_checked=True,
    )
    assert dimensions == {
        "twin_agreement": "ENFORCED",
        "config_digest_agreement": "ENFORCED",
        "request_digest_agreement": "NOT_ESTABLISHED",
        "sequence_agreement": "NOT_ESTABLISHED",
        "artifact_asset_identity": "UNKNOWN",
    }


def test_render_dimension_summary_fails_twin_and_config_closed():
    record = SimpleNamespace(canonical_digital_twin_id="record-twin")
    task = SimpleNamespace(digital_twin_id="task-twin")
    dimensions = _render_dimension_summary(
        record=record,
        task=task,
        observed_state={"config_digest": "abc"},
        m5_verified=False,
        m5_config_digest_checked=False,
    )
    assert dimensions["twin_agreement"] == "NOT_ESTABLISHED"
    assert dimensions["config_digest_agreement"] == "NOT_ESTABLISHED"
    assert dimensions["request_digest_agreement"] == "NOT_ESTABLISHED"
    assert dimensions["sequence_agreement"] == "NOT_ESTABLISHED"
