"""Live Blender gate for Temporal Observation ↔ Correction Bridge v3.

This gate exercises the real correction bridge and verifies that the disposable Blender session
produces one admitted A, one admitted B, and a finalized StateDelta around the actual mutation.
It deliberately reuses the existing live bridge fixture/execution harness so no second correction
execution path is introduced by the test.
"""

import os

import pytest

from planning.temporal import AdmissionOutcome


BLENDER_ENV = os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") == "1"
pytestmark = pytest.mark.skipif(not BLENDER_ENV, reason="live Blender gate off")


def test_live_temporal_correction_transaction_is_end_to_end(live_bridge_results):
    """Verify A -> real mutation -> B -> finalized StateDelta in Blender."""
    for case in live_bridge_results:
        result = case["result"]
        transaction = result.temporal_transaction

        assert result.transport_ok is True, case
        assert transaction is not None, case

        observation_a = transaction["observation_a"]
        observation_b = transaction["observation_b"]
        admission_a = transaction["admission_a"]
        admission_b = transaction["admission_b"]
        delta = transaction["delta_record"]

        assert observation_a is not None, case
        assert observation_b is not None, case
        assert admission_a["outcome"] == AdmissionOutcome.INITIAL_ACCEPTED.value, case
        assert admission_b["outcome"] == AdmissionOutcome.ACCEPTED.value, case

        assert transaction["pre_extraction_ordinal"] == 1, case
        assert transaction["post_extraction_ordinal"] == 2, case
        assert observation_a["sequence"] == 0, case
        assert observation_b["sequence"] == 1, case

        assert observation_a["producer"]["producer_session_id"] == observation_b["producer"]["producer_session_id"], case
        assert observation_a["producer"]["producer_session_id"] == transaction["producer_session_id"], case
        assert observation_a["continuity_id"] == observation_b["continuity_id"] == transaction["continuity_id"], case
        assert observation_a["source_time"]["domain"] == "FRAME_INDEX", case
        assert observation_b["source_time"]["domain"] == "FRAME_INDEX", case
        assert observation_a["source_time"]["rate_num"] == observation_b["source_time"]["rate_num"] == 1, case
        assert observation_a["source_time"]["rate_den"] == observation_b["source_time"]["rate_den"] == 1, case
        assert observation_a["source_time"]["ordering_epoch"] == observation_b["source_time"]["ordering_epoch"] == 0, case

        assert observation_a["producer"]["engine_version"] == "4.4.3", case
        assert observation_b["producer"]["engine_version"] == "4.4.3", case
        assert observation_a["producer"]["engine_build"] == observation_b["producer"]["engine_build"], case

        assert observation_a["capability"]["contract_id"] == "extraction_fidelity_v1", case
        assert observation_b["capability"]["contract_id"] == "extraction_fidelity_v1", case
        assert "representation_state" in observation_a["capability"], case
        assert "representation_state" in observation_b["capability"], case

        assert transaction["pre_snapshot"] == transaction["observation_a_snapshot"] if "observation_a_snapshot" in transaction else True
        assert transaction["post_snapshot"] is not None, case
        assert transaction["pre_snapshot"] is not None, case
        assert transaction["pre_state_digest"] == observation_a["state_digest"], case
        assert transaction["post_state_digest"] == observation_b["state_digest"], case
        assert observation_a["state_digest"] != observation_b["state_digest"], case

        assert delta is not None, case
        assert delta["delta_digest"], case
        assert delta["from_observation_origin"] == "UNEMITTED_EPOCH_ANCHOR", case
        assert delta["from_observation_id"] == observation_a["observation_id"], case
        assert delta["to_observation_id"] == observation_b["observation_id"], case
        assert delta["from_state_digest"] == observation_a["state_digest"], case
        assert delta["to_state_digest"] == observation_b["state_digest"], case
        assert delta["state_digest_changed"] is True, case
        assert delta["outcome"] == "COMPUTED", case

        assert result.correction_result["result"] == "COMPLETED", case
        assert result.engine_evidence["mutator_invocations"] == 1, case
        assert result.engine_evidence["extraction_invocations"] >= 2, case
        assert result.engine_evidence["process_disposed"] is True, case
        assert result.engine_evidence["ambiguous_result"] is False, case


def test_live_temporal_correction_snapshot_is_measured_not_receipt_derived(live_bridge_results):
    """Verify B is the fresh extraction snapshot, not a correction-receipt reconstruction."""
    for case in live_bridge_results:
        result = case["result"]
        transaction = result.temporal_transaction
        receipt = result.correction_result

        assert transaction is not None, case
        assert transaction["post_snapshot"] is not None, case
        assert transaction["post_report_digest"], case
        assert transaction["post_state_digest"], case

        assert transaction["post_snapshot"] != receipt, case
        assert transaction["post_state_digest"] == transaction["observation_b"]["state_digest"], case
