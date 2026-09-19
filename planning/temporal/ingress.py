"""Temporal v1 ingress validation and envelope parsing.

Transport serialization remains outside scope. This module accepts already-decoded Python values
or canonical JSON text and applies the Rev9 arrival-validation precedence before constructing a
TemporalObservation.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .admission import AdmissionReasonCode
from .canonical import CanonicalValueError
from .model import CapabilityContract, ProducerProvenance, SourceTime, TemporalObservation, TemporalValidationError


_ALLOWED_TOP_LEVEL = {
    "observation_schema_version",
    "stream_id",
    "continuity_id",
    "sequence",
    "source_time",
    "capture_time",
    "producer",
    "capability",
    "snapshot",
    "state_digest",
}


class ArrivalValidationError(ValueError):
    """Structured stage-1 arrival rejection."""

    def __init__(self, reason_code: AdmissionReasonCode, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _reject(reason: AdmissionReasonCode, message: str) -> "NoReturn":
    raise ArrivalValidationError(reason, message)


def _scalar_string(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip() or any(
        0xD800 <= ord(ch) <= 0xDFFF for ch in value
    ):
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, f"{label} must be a valid non-empty Unicode scalar string")
    return value


def _parse_source_time(value: Any) -> SourceTime:
    if not isinstance(value, Mapping):
        _reject(AdmissionReasonCode.MISSING_SOURCE_TIME, "source_time is missing or not an object")
    required = {"domain", "value", "rate", "ordering_epoch"}
    if not required.issubset(value):
        _reject(AdmissionReasonCode.MALFORMED_TIME, "source_time is incomplete")
    rate = value.get("rate")
    if not isinstance(rate, Mapping) or "num" not in rate or "den" not in rate:
        _reject(AdmissionReasonCode.MALFORMED_TIME, "source_time.rate is incomplete")
    try:
        return SourceTime(
            domain=value["domain"],
            value=value["value"],
            rate_num=rate["num"],
            rate_den=rate["den"],
            ordering_epoch=value["ordering_epoch"],
        )
    except TemporalValidationError as exc:
        _reject(AdmissionReasonCode.MALFORMED_TIME, str(exc))


def _parse_producer(value: Any) -> ProducerProvenance:
    if not isinstance(value, Mapping):
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, "producer is missing or not an object")
    required = {
        "producer_source",
        "producer_contract",
        "engine_version",
        "engine_build",
        "producer_session_id",
        "producer_instance_ordinal",
    }
    if not required.issubset(value):
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, "producer provenance is incomplete")
    try:
        return ProducerProvenance(
            producer_source=value["producer_source"],
            producer_contract=value["producer_contract"],
            engine_version=value["engine_version"],
            engine_build=value["engine_build"],
            producer_session_id=value["producer_session_id"],
            producer_instance_ordinal=value["producer_instance_ordinal"],
        )
    except TemporalValidationError as exc:
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, str(exc))


def _parse_capability(value: Any) -> CapabilityContract:
    if not isinstance(value, Mapping):
        _reject(AdmissionReasonCode.CAPABILITY_UNIVERSE_INCOMPLETE, "capability is missing or not an object")
    required = {"contract_id", "observable_fields", "unobservable_fields", "representation_state"}
    if not required.issubset(value):
        _reject(
            AdmissionReasonCode.CAPABILITY_UNIVERSE_INCOMPLETE,
            "capability declaration is incomplete",
        )
    try:
        return CapabilityContract(
            contract_id=value["contract_id"],
            observable_fields=tuple(value["observable_fields"]),
            unobservable_fields=tuple(value["unobservable_fields"]),
            representation_state=tuple(value["representation_state"]),
        )
    except (TemporalValidationError, TypeError, ValueError) as exc:
        _reject(AdmissionReasonCode.CAPABILITY_UNIVERSE_INCOMPLETE, str(exc))


def parse_temporal_observation(value: Mapping[str, Any]) -> TemporalObservation:
    """Validate and construct one TemporalObservation using Rev9 arrival precedence."""
    if not isinstance(value, Mapping):
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, "temporal observation must be an object")

    unknown = sorted(set(value) - _ALLOWED_TOP_LEVEL)
    if unknown:
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, f"unknown temporal observation fields: {unknown}")

    version = value.get("observation_schema_version")
    if version != "1":
        _reject(AdmissionReasonCode.UNKNOWN_SCHEMA_VERSION, f"unsupported observation schema version: {version!r}")

    for field in ("stream_id", "continuity_id"):
        if field not in value:
            _reject(AdmissionReasonCode.MALFORMED_IDENTITY, f"missing {field}")
        _scalar_string(value[field], field)

    sequence = value.get("sequence")
    if type(sequence) is not int or isinstance(sequence, bool) or sequence < 0 or sequence > (1 << 63) - 1:
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, "sequence must be signed int64 >= 0")

    source_time = _parse_source_time(value.get("source_time"))
    producer = _parse_producer(value.get("producer"))
    capability = _parse_capability(value.get("capability"))

    snapshot = value.get("snapshot")
    if not isinstance(snapshot, Mapping):
        _reject(AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN, "snapshot must be a mapping")
    try:
        parsed_snapshot = dict(snapshot)
        # Reuse the frozen canonical parser as the authority for allowed keys/types.
        from .model import snapshot_to_scene
        snapshot_to_scene(parsed_snapshot)
    except CanonicalValueError as exc:
        _reject(AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN, str(exc))

    state_digest = value.get("state_digest")
    if type(state_digest) is not str:
        _reject(AdmissionReasonCode.STATE_DIGEST_MISMATCH, "state_digest is missing")
    try:
        observation = TemporalObservation(
            stream_id=value["stream_id"],
            continuity_id=value["continuity_id"],
            sequence=sequence,
            source_time=source_time,
            producer=producer,
            capability=capability,
            snapshot=parsed_snapshot,
            state_digest=state_digest,
            observation_schema_version=version,
            capture_time=value.get("capture_time"),
        )
    except TemporalValidationError as exc:
        if "state_digest" in str(exc):
            _reject(AdmissionReasonCode.STATE_DIGEST_MISMATCH, str(exc))
        if "canonical" in str(exc) or "snapshot" in str(exc):
            _reject(AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN, str(exc))
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, str(exc))
    return observation


def parse_temporal_observation_json(text: str) -> TemporalObservation:
    """Parse canonical JSON while rejecting duplicate object keys before mapping."""
    try:
        value = json.loads(text, object_pairs_hook=lambda pairs: _reject_duplicate_keys(pairs))
    except json.JSONDecodeError as exc:
        _reject(AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN, f"invalid JSON: {exc}")
    except ValueError as exc:
        _reject(AdmissionReasonCode.INVALID_CANONICAL_VALUE_DOMAIN, str(exc))
    if not isinstance(value, dict):
        _reject(AdmissionReasonCode.MALFORMED_IDENTITY, "temporal observation JSON root must be an object")
    return parse_temporal_observation(value)


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result
