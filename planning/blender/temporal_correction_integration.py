"""Ephemeral Temporal transaction integration for the Blender correction bridge.

This module owns only the in-process observation/admission/evaluation transaction for one
disposable correction session. It does not own planning, correction authorization, persistence,
retry, rollback, or recovery.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from planning.temporal import (
    AdmissionOutcome,
    CapabilityContract,
    ProducerProvenance,
    SourceTime,
    TemporalObservation,
)
from planning.temporal.stream import ObservationStream
from planning.temporal.model import _scene_to_canonical, temporal_state_digest


_COMPARISON_FIELDS = (
    "collection",
    "faces",
    "location",
    "materials",
    "mesh_id",
    "mesh_presence",
    "parent_object_id",
    "rotation",
    "scale",
    "scene_id",
    "unit_system",
    "vertices",
    "visible",
)
_UNOBSERVABLE_FIELDS = (
    "coordinate_frame",
    "local_frame_id",
    "normals",
    "uvs",
)


@dataclass(frozen=True)
class TemporalExtractionEvidence:
    ordinal: int
    report_digest: str
    state_digest: str
    snapshot: Mapping[str, Any]


@dataclass
class TemporalCorrectionSession:
    """One disposable producer session containing exactly one A/B observation pair."""

    stream_id: Optional[str] = None
    continuity_id: Optional[str] = None
    ordering_epoch: int = 0
    producer_session_id: Optional[str] = None
    producer_instance_ordinal: int = 0
    engine_version: Optional[str] = None
    engine_build: Optional[str] = None
    pre: Optional[TemporalExtractionEvidence] = None
    post: Optional[TemporalExtractionEvidence] = None
    observation_a: Optional[TemporalObservation] = None
    observation_b: Optional[TemporalObservation] = None
    admission_a: Optional[Mapping[str, Any]] = None
    admission_b: Optional[Mapping[str, Any]] = None
    delta_record: Optional[Mapping[str, Any]] = None
    _representation_state: Tuple[str, ...] = ()
    _stream: Optional[ObservationStream] = None

    def start(self, *, scene_id: str, engine_version: str, engine_build: str) -> None:
        if self.producer_session_id is not None:
            raise RuntimeError("temporal correction session already started")
        self.stream_id = scene_id
        self.producer_session_id = (
            f"blender-proc-{os.getpid()}-{secrets.token_hex(16)}"
        )
        self.continuity_id = f"correction-session-{self.producer_session_id}"
        self.engine_version = engine_version
        self.engine_build = engine_build

    def _capability(self) -> CapabilityContract:
        return CapabilityContract(
            contract_id="extraction_fidelity_v1",
            observable_fields=tuple(sorted(_COMPARISON_FIELDS)),
            unobservable_fields=tuple(sorted(_UNOBSERVABLE_FIELDS)),
            representation_state=self._representation_state,
        )

    def _observation(
        self,
        *,
        snapshot: Mapping[str, Any],
        sequence: int,
        frame_index: int,
    ) -> TemporalObservation:
        if self.stream_id is None or self.continuity_id is None:
            raise RuntimeError("temporal correction session has not started")
        if self.engine_version is None or self.engine_build is None:
            raise RuntimeError("temporal correction session engine provenance is incomplete")
        state_digest = temporal_state_digest(snapshot)
        return TemporalObservation(
            stream_id=self.stream_id,
            continuity_id=self.continuity_id,
            sequence=sequence,
            source_time=SourceTime(
                domain="FRAME_INDEX",
                value=frame_index,
                rate_num=1,
                rate_den=1,
                ordering_epoch=self.ordering_epoch,
            ),
            producer=ProducerProvenance(
                producer_source="BLENDER",
                producer_contract="extraction_fidelity_v1",
                engine_version=self.engine_version,
                engine_build=self.engine_build,
                producer_session_id=self.producer_session_id,
                producer_instance_ordinal=self.producer_instance_ordinal,
            ),
            capability=self._capability(),
            snapshot=snapshot,
            state_digest=state_digest,
        )

    @staticmethod
    def _decision_json(decision) -> Dict[str, Any]:
        return {
            "outcome": decision.outcome.value,
            "reason_codes": [code.value for code in decision.reason_codes],
            "observation_id": decision.observation.observation_id,
            "admission_identity_digest": decision.observation.admission_identity_digest,
            "envelope_digest": decision.observation.envelope_digest,
            "state_digest": decision.observation.state_digest,
            "from_identity": None
            if decision.from_identity is None
            else decision.from_identity.canonical(),
            "advances_baseline": decision.advances_baseline,
        }

    def capture(
        self,
        *,
        scene: Any,
        report: Any,
        ordinal: int,
        representation_state: Tuple[str, ...] = (),
    ) -> Tuple[Any, Any]:
        """Capture the exact executor extraction result before it is returned to the executor."""
        self._representation_state = tuple(sorted(representation_state))
        snapshot = _scene_to_canonical(scene)
        evidence = TemporalExtractionEvidence(
            ordinal=ordinal,
            report_digest=report.digest(),
            state_digest=temporal_state_digest(snapshot),
            snapshot=snapshot,
        )
        raw_frame_index = __import__("bpy").context.scene.frame_current
        if type(raw_frame_index) is not int or isinstance(raw_frame_index, bool):
            raise RuntimeError("FRAME_INDEX source_time requires Blender scene.frame_current to be an exact int")
        frame_index = raw_frame_index

        if ordinal == 1:
            self.start(
                scene_id=str(snapshot["scene_id"]),
                engine_version=str(__import__("bpy").app.version_string),
                engine_build=_engine_build(__import__("bpy")),
            )
            self.pre = evidence
            observation = self._observation(
                snapshot=snapshot,
                sequence=0,
                frame_index=frame_index,
            )
            self._stream = ObservationStream(self.stream_id)
            step = self._stream.step(observation)
            decision = step.admission
            if not decision.accepted or decision.outcome != AdmissionOutcome.INITIAL_ACCEPTED:
                raise RuntimeError(
                    "pre-correction Temporal admission failed: "
                    + ",".join(code.value for code in decision.reason_codes)
                )
            self.observation_a = observation
            self.admission_a = self._decision_json(decision)
            return scene, report

        if ordinal == 2:
            if self.observation_a is None or self.pre is None:
                raise RuntimeError("post extraction occurred without admitted A")
            if str(snapshot["scene_id"]) != self.stream_id:
                raise RuntimeError("post extraction changed scene scope")
            self.post = evidence
            observation = self._observation(
                snapshot=snapshot,
                sequence=1,
                frame_index=frame_index,
            )
            if self._stream is None:
                raise RuntimeError("post extraction occurred without an initialized ObservationStream")
            step = self._stream.step(observation, predecessor=self.observation_a)
            decision = step.admission
            self.admission_b = self._decision_json(decision)
            if not decision.accepted or decision.outcome != AdmissionOutcome.ACCEPTED:
                raise RuntimeError(
                    "post-correction Temporal admission failed: "
                    + ",".join(code.value for code in decision.reason_codes)
                )
            self.observation_b = observation
            self.delta_record = step.record
            return scene, report

        raise RuntimeError(f"unexpected extraction ordinal: {ordinal}")

    def wrap(
        self,
        extractor: Callable[[Any], Tuple[Any, Any]],
    ) -> Callable[[Any], Tuple[Any, Any]]:
        ordinal = {"value": 0}

        def captured(engine_state):
            ordinal["value"] += 1
            scene, report = extractor(engine_state)
            representation_state = getattr(extractor, "temporal_representation_state", ())
            return self.capture(
                scene=scene,
                report=report,
                ordinal=ordinal["value"],
                representation_state=representation_state,
            )

        return captured

    def result_payload(self) -> Dict[str, Any]:
        return {
            "temporal_transaction": {
                "producer_session_id": self.producer_session_id,
                "producer_instance_ordinal": self.producer_instance_ordinal,
                "stream_id": self.stream_id,
                "continuity_id": self.continuity_id,
                "ordering_epoch": self.ordering_epoch,
                "engine_version": self.engine_version,
                "engine_build": self.engine_build,
                "pre_snapshot": None if self.pre is None else dict(self.pre.snapshot),
                "post_snapshot": None if self.post is None else dict(self.post.snapshot),
                "pre_report_digest": None if self.pre is None else self.pre.report_digest,
                "post_report_digest": None if self.post is None else self.post.report_digest,
                "pre_state_digest": None if self.pre is None else self.pre.state_digest,
                "post_state_digest": None if self.post is None else self.post.state_digest,
                "pre_extraction_ordinal": None if self.pre is None else self.pre.ordinal,
                "post_extraction_ordinal": None if self.post is None else self.post.ordinal,
                "observation_a": _observation_json(self.observation_a),
                "observation_b": _observation_json(self.observation_b),
                "admission_a": self.admission_a,
                "admission_b": self.admission_b,
                "delta_record": self.delta_record,
            }
        }


def _engine_build(bpy_module: Any) -> str:
    value = bpy_module.app.build_hash
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("ascii")
    return str(value)


def _observation_json(observation: Optional[TemporalObservation]) -> Optional[Dict[str, Any]]:
    if observation is None:
        return None
    return {
        "observation_id": observation.observation_id,
        "admission_identity_digest": observation.admission_identity_digest,
        "envelope_digest": observation.envelope_digest,
        "state_digest": observation.state_digest,
        "stream_id": observation.stream_id,
        "continuity_id": observation.continuity_id,
        "sequence": observation.sequence,
        "source_time": observation.source_time.canonical(),
        "capability": {
            "contract_id": observation.capability.contract_id,
            "observable_fields": list(observation.capability.observable_fields),
            "unobservable_fields": list(observation.capability.unobservable_fields),
            "representation_state": list(observation.capability.representation_state),
        },
        "producer": {
            "producer_source": observation.producer.producer_source,
            "producer_contract": observation.producer.producer_contract,
            "engine_version": observation.producer.engine_version,
            "engine_build": observation.producer.engine_build,
            "producer_session_id": observation.producer.producer_session_id,
            "producer_instance_ordinal": observation.producer.producer_instance_ordinal,
        },
    }
