"""Ordered TemporalObservation stream coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .admission import (
    AdmissionDecision,
    AdmissionEngine,
    AdmissionOutcome,
    AdmissionState,
)
from .evaluator import (
    BoundaryInput,
    BoundaryRefusalInput,
    ComparisonInput,
    RefusalInput,
    evaluate,
    finalize_record,
)
from .model import TemporalObservation
from .recovery import AdmissionCheckpoint, RecoveryCheckpointError, validate_reinitialization_declaration


@dataclass(frozen=True)
class StepResult:
    admission: AdmissionDecision
    record: Optional[dict]


class ObservationStream:
    """One serialized input stream. Callers must not invoke step concurrently for one stream."""

    def __init__(self, stream_id: str):
        self.state = AdmissionState(stream_id=stream_id)
        self._admission = AdmissionEngine()

    @property
    def stream_id(self) -> str:
        return self.state.stream_id

    @classmethod
    def from_checkpoint(cls, checkpoint: AdmissionCheckpoint) -> "ObservationStream":
        state = checkpoint.restore_state()
        stream = cls(state.stream_id)
        stream.state = state
        return stream

    def reinitialize(
        self,
        *,
        new_continuity_id: str,
        new_ordering_epoch: int,
    ) -> None:
        """Explicitly discard the current baseline under a new TemporalEpochKey.

        No synthetic StateDelta is emitted. The next valid observation is INITIAL_ACCEPTED.
        """
        validate_reinitialization_declaration(
            self.state,
            new_continuity_id=new_continuity_id,
            new_ordering_epoch=new_ordering_epoch,
        )
        self.state = AdmissionState(
            stream_id=self.state.stream_id,
            accepted_count=self.state.accepted_count,
            duplicate_acknowledged_count=self.state.duplicate_acknowledged_count,
            rejected_stale_count=self.state.rejected_stale_count,
            invalid_count=self.state.invalid_count,
            epoch_count=self.state.epoch_count,
        )

    def step(self, observation: TemporalObservation, predecessor: Optional[TemporalObservation] = None) -> StepResult:
        if observation.stream_id != self.stream_id:
            raise ValueError("DIFFERENT_STREAM is routing, not an admission outcome")

        decision = self._admission.prepare(self.state, observation)

        if not decision.accepted:
            self._admission.commit(self.state, decision)
            return StepResult(decision, None)

        if decision.outcome == AdmissionOutcome.INITIAL_ACCEPTED:
            self._admission.commit(self.state, decision)
            return StepResult(decision, None)

        from_identity = decision.from_identity
        if from_identity is None:
            raise RuntimeError("accepted non-initial observation is missing FromIdentity")

        if decision.outcome == AdmissionOutcome.NEW_EPOCH:
            if predecessor is None:
                evaluation_input = BoundaryRefusalInput(
                    b=observation,
                    from_identity=from_identity,
                    reason=_pair_unavailable_reason(),
                )
            else:
                evaluation_input = BoundaryInput(
                    a=predecessor,
                    b=observation,
                    from_identity=from_identity,
                )
        else:
            if predecessor is None:
                evaluation_input = RefusalInput(
                    b=observation,
                    from_identity=from_identity,
                    reason=_pair_unavailable_reason(),
                )
            else:
                evaluation_input = ComparisonInput(
                    a=predecessor,
                    b=observation,
                    from_identity=from_identity,
                )

        draft = evaluate(evaluation_input)
        from_origin = (
            "UNEMITTED_EPOCH_ANCHOR"
            if self.state.last_admission_outcome == AdmissionOutcome.INITIAL_ACCEPTED
            else "EMITTED_PREDECESSOR"
        )
        record = finalize_record(draft, from_origin)

        self._admission.commit(self.state, decision)
        return StepResult(decision, record)


def _pair_unavailable_reason():
    from .evaluator import DeltaReasonCode
    return DeltaReasonCode.PAIR_INPUT_UNAVAILABLE
