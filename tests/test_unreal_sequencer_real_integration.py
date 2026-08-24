"""Real Unreal integration coverage for the Sequencer production boundary."""

import pytest

from planning.unreal_adapter_production import create_production_adapter
from planning.unreal_agent import UnrealTaskIntent
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_transport_named_pipe import NamedPipeTransportError
from planning.unreal_task_planner import UnrealTaskPlanner


pytestmark = pytest.mark.integration

ENTITY_ID = "FIELD_SURFACE"


def _intent(intent_id: str) -> UnrealTaskIntent:
    return UnrealTaskIntent(
        intent_id=intent_id,
        description="real Unreal Sequencer playback-range integration",
        target_entity_ids=(ENTITY_ID,),
    )


def _sequencer_state(evidence):
    state = evidence.observed_state[ENTITY_ID]
    return dict(state["sequencer"])


def test_real_unreal_sequencer_playback_range_round_trip():
    """Exercise read/write/verify Sequencer state against the live Unreal boundary."""
    try:
        adapter = create_production_adapter("sequencer-integration")
        executor = UnrealPlanExecutor(adapter)
        planner = UnrealTaskPlanner()

        original = executor.execute(
            planner.plan_sequencer_playback_range(
                _intent("real-sequencer-original"),
                0,
                1,
            ),
            "real-sequencer-original-auth",
        )
        original_state = _sequencer_state(original.evidence_ledger[0])
        original_start = int(original_state["start_frame"])
        original_end = int(original_state["end_frame"])
        assert original_start <= original_end

        target_start = original_start + 10
        target_end = original_end + 10
        if target_start > target_end:
            target_end = target_start

        try:
            write_plan = planner.plan_sequencer_playback_range(
                _intent("real-sequencer-write"),
                target_start,
                target_end,
            )
            result = executor.execute(
                write_plan,
                "real-sequencer-write-auth",
            )
            assert result.success is True

            verified_state = _sequencer_state(result.evidence_ledger[2])
            assert int(verified_state["start_frame"]) == target_start
            assert int(verified_state["end_frame"]) == target_end
        finally:
            restore_plan = planner.plan_sequencer_playback_range(
                _intent("real-sequencer-restore"),
                original_start,
                original_end,
            )
            restore_result = executor.execute(
                restore_plan,
                "real-sequencer-restore-auth",
            )
            assert restore_result.success is True
            restored_state = _sequencer_state(restore_result.evidence_ledger[2])
            assert int(restored_state["start_frame"]) == original_start
            assert int(restored_state["end_frame"]) == original_end

    except NamedPipeTransportError as exc:
        message = str(exc).lower()
        if "not available" in message or "pipe not found" in message:
            pytest.skip("Unreal Editor transport is unavailable")
        if "not found" in message:
            pytest.skip("FIELD_SURFACE Sequencer fixture is not present in Unreal")
        raise
