"""Temporal v1 admission boundary.

Admission decides only stream membership and baseline mutation. Pair comparability belongs to the
evaluation layer and can never retract an accepted observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .model import TemporalObservation, SourceTime


class AdmissionOutcome(str, Enum):
    INITIAL_ACCEPTED = "INITIAL_ACCEPTED"
    ACCEPTED = "ACCEPTED"
    NEW_EPOCH = "NEW_EPOCH"
    DUPLICATE_ACKNOWLEDGED = "DUPLICATE_ACKNOWLEDGED"
    REJECTED_STALE = "REJECTED_STALE"
    REJECTED_INVALID = "REJECTED_INVALID"


class AdmissionReasonCode(str, Enum):
    STALE_SEQUENCE_REJECTED = "STALE_SEQUENCE_REJECTED"
    ORDERING_EPOCH_REGRESSION = "ORDERING_EPOCH_REGRESSION"
    CONTRADICTORY_SEQUENCE = "CONTRADICTORY_SEQUENCE"
    SOURCE_TIME_DOMAIN_MISMATCH = "SOURCE_TIME_DOMAIN_MISMATCH"
    SOURCE_TIME_RATE_MISMATCH = "SOURCE_TIME_RATE_MISMATCH"
    SOURCE_TIME_NON_MONOTONIC = "SOURCE_TIME_NON_MONOTONIC"
    SCENE_SCOPE_CHANGED = "SCENE_SCOPE_CHANGED"
    CONTINUITY_DECLARATION_MISMATCH = "CONTINUITY_DECLARATION_MISMATCH"


@dataclass(frozen=True)
class FromIdentity:
    last_accepted_observation_id: str
    last_accepted_state_digest: str
    last_accepted_admission_identity_digest: str
    last_accepted_continuity_id: str
    last_accepted_producer_session_id: str
    last_accepted_ordering_epoch: int

    def canonical(self):
        return {
            "last_accepted_observation_id": self.last_accepted_observation_id,
            "last_accepted_state_digest": self.last_accepted_state_digest,
            "last_accepted_admission_identity_digest": self.last_accepted_admission_identity_digest,
            "last_accepted_continuity_id": self.last_accepted_continuity_id,
            "last_accepted_producer_session_id": self.last_accepted_producer_session_id,
            "last_accepted_ordering_epoch": self.last_accepted_ordering_epoch,
        }


@dataclass
class AdmissionState:
    stream_id: str
    continuity_id: Optional[str] = None
    producer_session_id: Optional[str] = None
    ordering_epoch: Optional[int] = None
    last_accepted_sequence: Optional[int] = None
    last_accepted_source_time: Optional[SourceTime] = None
    last_accepted_scene_id: Optional[str] = None
    last_accepted_state_digest: Optional[str] = None
    last_accepted_observation_id: Optional[str] = None
    last_accepted_admission_identity_digest: Optional[str] = None
    accepted_count: int = 0
    duplicate_acknowledged_count: int = 0
    rejected_stale_count: int = 0
    invalid_count: int = 0
    epoch_count: int = 0
    last_admission_identity_digest: Optional[str] = None
    last_admission_outcome: Optional[AdmissionOutcome] = None

    @property
    def has_baseline(self) -> bool:
        return self.last_accepted_observation_id is not None

    def from_identity(self) -> Optional[FromIdentity]:
        if not self.has_baseline:
            return None
        assert self.continuity_id is not None
        assert self.producer_session_id is not None
        assert self.ordering_epoch is not None
        assert self.last_accepted_sequence is not None
        assert self.last_accepted_state_digest is not None
        assert self.last_accepted_admission_identity_digest is not None
        return FromIdentity(
            last_accepted_observation_id=self.last_accepted_observation_id,
            last_accepted_state_digest=self.last_accepted_state_digest,
            last_accepted_admission_identity_digest=self.last_accepted_admission_identity_digest,
            last_accepted_continuity_id=self.continuity_id,
            last_accepted_producer_session_id=self.producer_session_id,
            last_accepted_ordering_epoch=self.ordering_epoch,
        )


@dataclass(frozen=True)
class AdmissionDecision:
    outcome: AdmissionOutcome
    reason_codes: Tuple[AdmissionReasonCode, ...]
    observation: TemporalObservation
    from_identity: Optional[FromIdentity]
    advances_baseline: bool

    @property
    def accepted(self) -> bool:
        return self.outcome in {
            AdmissionOutcome.INITIAL_ACCEPTED,
            AdmissionOutcome.ACCEPTED,
            AdmissionOutcome.NEW_EPOCH,
        }


class AdmissionEngine:
    """Pure admission classification plus explicit commit."""

    def prepare(self, state: AdmissionState, observation: TemporalObservation) -> AdmissionDecision:
        if observation.stream_id != state.stream_id:
            raise ValueError("DIFFERENT_STREAM is routing, not an admission outcome")

        previous = state.from_identity()

        if previous is None:
            return AdmissionDecision(
                AdmissionOutcome.INITIAL_ACCEPTED,
                (),
                observation,
                None,
                True,
            )

        assert state.ordering_epoch is not None
        assert state.last_accepted_sequence is not None
        assert state.last_accepted_source_time is not None
        assert state.last_accepted_scene_id is not None

        # Step 1: epoch ordering / continuity declaration.
        if observation.ordering_epoch < state.ordering_epoch:
            return self._reject_stale(
                state,
                observation,
                previous,
                AdmissionReasonCode.ORDERING_EPOCH_REGRESSION,
            )

        if observation.ordering_epoch == state.ordering_epoch:
            if observation.continuity_id != state.continuity_id:
                return self._reject_invalid(
                    state,
                    observation,
                    previous,
                    AdmissionReasonCode.CONTINUITY_DECLARATION_MISMATCH,
                )
            if observation.producer.producer_session_id != state.producer_session_id:
                return self._reject_invalid(
                    state,
                    observation,
                    previous,
                    AdmissionReasonCode.CONTINUITY_DECLARATION_MISMATCH,
                )
            new_epoch = False
        else:
            if observation.continuity_id == state.continuity_id:
                return self._reject_invalid(
                    state,
                    observation,
                    previous,
                    AdmissionReasonCode.CONTINUITY_DECLARATION_MISMATCH,
                )
            new_epoch = True

        # A declared new epoch re-establishes sequence, scene and source-time baselines.
        if new_epoch:
            return AdmissionDecision(
                AdmissionOutcome.NEW_EPOCH,
                (),
                observation,
                previous,
                True,
            )

        # Step 2: sequence.
        if observation.sequence < state.last_accepted_sequence:
            return self._reject_stale(
                state,
                observation,
                previous,
                AdmissionReasonCode.STALE_SEQUENCE_REJECTED,
            )

        # Step 3: same-sequence admission identity.
        if observation.sequence == state.last_accepted_sequence:
            if observation.admission_identity_digest == state.last_accepted_admission_identity_digest:
                return self._preserve(
                    state,
                    observation,
                    previous,
                    AdmissionOutcome.DUPLICATE_ACKNOWLEDGED,
                )
            return self._reject_invalid(
                state,
                observation,
                previous,
                AdmissionReasonCode.CONTRADICTORY_SEQUENCE,
            )

        # Step 4: scene scope.
        scene_id = _scene_id(observation)
        if scene_id != state.last_accepted_scene_id:
            return self._reject_invalid(
                state,
                observation,
                previous,
                AdmissionReasonCode.SCENE_SCOPE_CHANGED,
            )

        # Step 5-6: source-time domain and rate.
        current_time = observation.source_time
        previous_time = state.last_accepted_source_time
        if current_time.domain != previous_time.domain:
            return self._reject_invalid(
                state,
                observation,
                previous,
                AdmissionReasonCode.SOURCE_TIME_DOMAIN_MISMATCH,
            )
        if (current_time.rate_num, current_time.rate_den) != (
            previous_time.rate_num,
            previous_time.rate_den,
        ):
            return self._reject_invalid(
                state,
                observation,
                previous,
                AdmissionReasonCode.SOURCE_TIME_RATE_MISMATCH,
            )

        # Step 7: exact source-time monotonicity.
        if current_time.value < previous_time.value:
            return self._reject_invalid(
                state,
                observation,
                previous,
                AdmissionReasonCode.SOURCE_TIME_NON_MONOTONIC,
            )

        return AdmissionDecision(
            AdmissionOutcome.ACCEPTED,
            (),
            observation,
            previous,
            True,
        )

    def commit(self, state: AdmissionState, decision: AdmissionDecision) -> None:
        outcome = decision.outcome
        observation = decision.observation
        state.last_admission_identity_digest = observation.admission_identity_digest
        state.last_admission_outcome = outcome

        if outcome == AdmissionOutcome.DUPLICATE_ACKNOWLEDGED:
            state.duplicate_acknowledged_count += 1
            return

        if outcome == AdmissionOutcome.REJECTED_STALE:
            state.rejected_stale_count += 1
            return

        if outcome == AdmissionOutcome.REJECTED_INVALID:
            state.invalid_count += 1
            return

        scene_id = _scene_id(observation)
        state.continuity_id = observation.continuity_id
        state.producer_session_id = observation.producer.producer_session_id
        state.ordering_epoch = observation.ordering_epoch
        state.last_accepted_sequence = observation.sequence
        state.last_accepted_source_time = observation.source_time
        state.last_accepted_scene_id = scene_id
        state.last_accepted_state_digest = observation.state_digest
        state.last_accepted_observation_id = observation.observation_id
        state.last_accepted_admission_identity_digest = observation.admission_identity_digest
        state.accepted_count += 1

        if outcome == AdmissionOutcome.INITIAL_ACCEPTED:
            state.epoch_count = 1
        elif outcome == AdmissionOutcome.NEW_EPOCH:
            state.epoch_count += 1


def _scene_id(observation: TemporalObservation) -> str:
    try:
        return observation.snapshot["scene_id"]
    except KeyError as exc:
        raise ValueError("canonical snapshot is missing scene_id") from exc


def _reason_tuple(reason: AdmissionReasonCode) -> Tuple[AdmissionReasonCode, ...]:
    return (reason,)


def _decision(
    outcome: AdmissionOutcome,
    observation: TemporalObservation,
    previous: Optional[FromIdentity],
    reason: Optional[AdmissionReasonCode] = None,
) -> AdmissionDecision:
    return AdmissionDecision(
        outcome,
        (reason,) if reason is not None else (),
        observation,
        previous,
        False,
    )


def _reject_invalid(
    state: AdmissionState,
    observation: TemporalObservation,
    previous: FromIdentity,
    reason: AdmissionReasonCode,
) -> AdmissionDecision:
    return _decision(AdmissionOutcome.REJECTED_INVALID, observation, previous, reason)


def _reject_stale(
    state: AdmissionState,
    observation: TemporalObservation,
    previous: FromIdentity,
    reason: AdmissionReasonCode,
) -> AdmissionDecision:
    return _decision(AdmissionOutcome.REJECTED_STALE, observation, previous, reason)


def _preserve(
    state: AdmissionState,
    observation: TemporalObservation,
    previous: FromIdentity,
    outcome: AdmissionOutcome,
) -> AdmissionDecision:
    return _decision(outcome, observation, previous)
