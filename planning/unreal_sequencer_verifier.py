"""Semantic verification for Unreal Sequencer playback-range evidence."""

from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_state_verifier import UnrealStateVerificationError


def verify_sequencer_playback_range(
    evidence: UnrealEvidence,
    expected_start_frame: int,
    expected_end_frame: int,
) -> UnrealEvidence:
    """Prove that fresh Unreal evidence contains the requested playback range."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be an UnrealEvidence instance")
    if isinstance(expected_start_frame, bool) or not isinstance(expected_start_frame, int):
        raise TypeError("expected_start_frame must be an integer")
    if isinstance(expected_end_frame, bool) or not isinstance(expected_end_frame, int):
        raise TypeError("expected_end_frame must be an integer")
    if expected_start_frame > expected_end_frame:
        raise ValueError("expected_start_frame must not exceed expected_end_frame")

    for entity_id in evidence.entity_ids:
        try:
            entity_state = evidence.observed_state[entity_id]
        except (KeyError, TypeError):
            raise UnrealStateVerificationError(
                f"verification evidence is missing entity '{entity_id}'"
            )
        if not isinstance(entity_state, Mapping):
            raise UnrealStateVerificationError(
                f"verification state for entity '{entity_id}' must be a mapping"
            )
        sequencer_state = entity_state.get("sequencer")
        if not isinstance(sequencer_state, Mapping):
            raise UnrealStateVerificationError(
                f"verification state for entity '{entity_id}' is missing sequencer"
            )

        playback_range = sequencer_state.get("playback_range")
        if isinstance(playback_range, Mapping):
            actual_start = playback_range.get("start_frame")
            actual_end = playback_range.get("end_frame")
        else:
            # The live Unreal transport currently returns start/end directly
            # under "sequencer". Accept that wire representation while keeping
            # the canonical nested playback_range form as the preferred shape.
            actual_start = sequencer_state.get("start_frame")
            actual_end = sequencer_state.get("end_frame")
            if actual_start is None or actual_end is None:
                raise UnrealStateVerificationError(
                    f"verification state for entity '{entity_id}' is missing sequencer playback_range"
                )

        if actual_start != expected_start_frame or actual_end != expected_end_frame:
            raise UnrealStateVerificationError(
                f"entity '{entity_id}' sequencer playback_range=({actual_start!r}, {actual_end!r}) "
                f"does not match expected ({expected_start_frame!r}, {expected_end_frame!r})"
            )

    return evidence
