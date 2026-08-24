import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_sequencer_verifier import verify_sequencer_playback_range
from planning.unreal_state_verifier import UnrealStateVerificationError


ENTITY_ID = "FIELD_SURFACE"


def _evidence(start=10, end=120):
    return UnrealEvidence(
        operation_name="verify_sequencer_playback_range",
        entity_ids=(ENTITY_ID,),
        observed_state={
            ENTITY_ID: {
                "sequencer": {
                    "playback_range": {
                        "start_frame": start,
                        "end_frame": end,
                    }
                }
            }
        },
        source="unreal-test",
    )


def test_sequencer_verifier_accepts_matching_playback_range():
    evidence = verify_sequencer_playback_range(_evidence(), 10, 120)
    assert evidence.verified is False


def test_sequencer_verifier_rejects_mismatched_playback_range():
    with pytest.raises(UnrealStateVerificationError, match="playback_range"):
        verify_sequencer_playback_range(_evidence(), 10, 121)


def test_sequencer_verifier_rejects_missing_playback_range():
    evidence = UnrealEvidence(
        operation_name="verify_sequencer_playback_range",
        entity_ids=(ENTITY_ID,),
        observed_state={ENTITY_ID: {"sequencer": {}}},
        source="unreal-test",
    )
    with pytest.raises(UnrealStateVerificationError, match="playback_range"):
        verify_sequencer_playback_range(evidence, 10, 120)


def test_sequencer_verifier_rejects_invalid_expected_range():
    with pytest.raises(ValueError, match="must not exceed"):
        verify_sequencer_playback_range(_evidence(), 120, 10)
