"""Immutable Temporal Observation v1 models and digest projections."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from planning.blender.scene_model import SceneModel, parse_scene_report_input

from .canonical import CanonicalValueError, sha256_digest, temporal_canonical_bytes


TEMPORAL_OBSERVATION_SCHEMA_VERSION = "1"
DELTA_SCHEMA_VERSION = 1
PRODUCER_SOURCES = frozenset({"BLENDER", "UNREAL", "PHOTOGRAMMETRY", "REPLAY", "OTHER"})

TEMPORAL_COMPARISON_FIELDS = (
    "scene_id",
    "unit_system",
    "collection",
    "parent_object_id",
    "location",
    "scale",
    "rotation",
    "visible",
    "mesh_presence",
    "mesh_id",
    "vertices",
    "faces",
    "materials",
)

DECLARED_UNOBSERVABLE_FIELDS = (
    "normals",
    "uvs",
    "local_frame_id",
    "coordinate_frame",
)

TEMPORAL_FIELD_UNIVERSE = frozenset(
    TEMPORAL_COMPARISON_FIELDS + DECLARED_UNOBSERVABLE_FIELDS
)

_HEX = frozenset("0123456789abcdef")


class TemporalValidationError(ValueError):
    """Malformed TemporalObservation or immutable component."""


def _require_string(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise TemporalValidationError(f"{label} must be a non-empty exact built-in string")
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise TemporalValidationError(f"{label} contains a Unicode surrogate")
    return value


def _require_i64(value: Any, label: str, *, minimum: Optional[int] = None) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TemporalValidationError(f"{label} must be an exact built-in int")
    if value < -(1 << 63) or value > (1 << 63) - 1:
        raise TemporalValidationError(f"{label} must fit signed int64")
    if minimum is not None and value < minimum:
        raise TemporalValidationError(f"{label} must be >= {minimum}")
    return value


def _validate_digest(value: Any, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise TemporalValidationError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _sorted_unique_strings(values: Any, label: str) -> Tuple[str, ...]:
    if type(values) not in (list, tuple):
        raise TemporalValidationError(f"{label} must be a list/tuple")
    out = tuple(_require_string(v, f"{label}[]") for v in values)
    if len(set(out)) != len(out):
        raise TemporalValidationError(f"{label} must contain unique strings")
    if tuple(sorted(out)) != out:
        raise TemporalValidationError(f"{label} must be canonically sorted")
    return out


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


def _reject_duplicate_json_keys(pairs, object_name: str):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TemporalValidationError(f"{object_name} contains duplicate key {key!r}")
        result[key] = value
    return result


def parse_canonical_snapshot_json(text: str) -> Dict[str, Any]:
    """Parse canonical snapshot JSON while rejecting duplicate object keys before mapping."""
    if type(text) is not str:
        raise TemporalValidationError("snapshot JSON must be an exact built-in string")
    try:
        value = json.loads(
            text,
            object_pairs_hook=lambda pairs: _reject_duplicate_json_keys(pairs, "snapshot object"),
        )
    except json.JSONDecodeError as exc:
        raise TemporalValidationError(f"invalid snapshot JSON: {exc}") from exc
    if type(value) is not dict:
        raise TemporalValidationError("snapshot JSON root must be an object")
    return value


def _scene_to_canonical(scene: SceneModel) -> Dict[str, Any]:
    def mesh_dict(mesh):
        if mesh is None:
            return None
        return {
            "mesh_id": mesh.mesh_id,
            "vertices": [list(v) for v in mesh.vertices],
            "faces": [list(face) for face in mesh.faces],
            "materials": list(mesh.materials),
        }

    return {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "objects": [
            {
                "object_id": obj.object_id,
                "name": obj.name,
                "collection": obj.collection,
                "parent_object_id": obj.parent_object_id,
                "location": list(obj.location),
                "scale": list(obj.scale),
                "rotation": list(obj.rotation),
                "visible": obj.visible,
                "mesh": mesh_dict(obj.mesh),
            }
            for obj in scene.objects
        ],
        "coordinate_frame": scene.coordinate_frame,
        "world_bounds": (
            [list(scene.world_bounds[0]), list(scene.world_bounds[1])]
            if scene.world_bounds is not None
            else None
        ),
    }


def _temporal_state_projection(scene: SceneModel) -> Dict[str, Any]:
    objects = []
    for obj in scene.objects:
        item: Dict[str, Any] = {
            "object_id": obj.object_id,
            "name": obj.name,
            "collection": obj.collection,
            "parent_object_id": obj.parent_object_id,
            "location": list(obj.location),
            "scale": list(obj.scale),
            "rotation": list(obj.rotation),
            "visible": obj.visible,
            "mesh_presence": obj.mesh is not None,
            "mesh": None,
        }
        if obj.mesh is not None:
            item["mesh"] = {
                "mesh_id": obj.mesh.mesh_id,
                "vertices": [list(v) for v in obj.mesh.vertices],
                "faces": [list(face) for face in obj.mesh.faces],
                "materials": list(obj.mesh.materials),
            }
        entity_digest = sha256_digest(item)
        objects.append((obj.object_id, entity_digest, item))
    objects.sort(key=lambda row: (row[0], row[1]))
    return {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "objects": [item for _, _, item in objects],
    }


def snapshot_to_scene(snapshot: Mapping[str, Any]) -> SceneModel:
    """Parse an admissible observation snapshot into the frozen canonical model."""
    try:
        return parse_scene_report_input(_thaw(snapshot))
    except Exception as exc:
        raise TemporalValidationError(f"snapshot is not canonical: {exc}") from exc


def temporal_state_digest(snapshot: Mapping[str, Any]) -> str:
    """Compute the raw temporal state digest from the normative snapshot."""
    scene = snapshot_to_scene(snapshot)
    return sha256_digest(_temporal_state_projection(scene))


@dataclass(frozen=True)
class SourceTime:
    domain: str
    value: int
    rate_num: int
    rate_den: int
    ordering_epoch: int

    def __post_init__(self) -> None:
        if self.domain not in {"MEDIA_TICKS", "FRAME_INDEX", "SOURCE_SECONDS_EXACT"}:
            raise TemporalValidationError(f"unsupported source_time domain: {self.domain!r}")
        _require_i64(self.value, "source_time.value")
        _require_i64(self.rate_num, "source_time.rate.num", minimum=1)
        _require_i64(self.rate_den, "source_time.rate.den", minimum=1)
        _require_i64(self.ordering_epoch, "source_time.ordering_epoch", minimum=0)
        if self.domain == "SOURCE_SECONDS_EXACT" and (self.rate_num, self.rate_den) != (1_000_000, 1):
            raise TemporalValidationError("SOURCE_SECONDS_EXACT requires rate {1000000, 1}")

    def canonical(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "value": self.value,
            "rate": {"num": self.rate_num, "den": self.rate_den},
            "ordering_epoch": self.ordering_epoch,
        }

    def tuple_equal(self, other: "SourceTime") -> bool:
        return self.canonical() == other.canonical()


@dataclass(frozen=True)
class ProducerProvenance:
    producer_source: str
    producer_contract: str
    engine_version: str
    engine_build: str
    producer_session_id: str
    producer_instance_ordinal: int = 0

    def __post_init__(self) -> None:
        if self.producer_source not in PRODUCER_SOURCES:
            raise TemporalValidationError(f"unsupported producer_source: {self.producer_source!r}")
        _require_string(self.producer_contract, "producer.producer_contract")
        _require_string(self.engine_version, "producer.engine_version")
        _require_string(self.engine_build, "producer.engine_build")
        _require_string(self.producer_session_id, "producer.producer_session_id")
        _require_i64(self.producer_instance_ordinal, "producer.producer_instance_ordinal", minimum=0)


@dataclass(frozen=True)
class CapabilityContract:
    contract_id: str
    observable_fields: Tuple[str, ...]
    unobservable_fields: Tuple[str, ...]
    representation_state: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_string(self.contract_id, "capability.contract_id")
        obs = _sorted_unique_strings(self.observable_fields, "capability.observable_fields")
        unobs = _sorted_unique_strings(self.unobservable_fields, "capability.unobservable_fields")
        rep = _sorted_unique_strings(self.representation_state, "capability.representation_state")
        if set(obs) & set(unobs):
            raise TemporalValidationError("capability observable/unobservable fields overlap")
        if set(obs) | set(unobs) != TEMPORAL_FIELD_UNIVERSE:
            raise TemporalValidationError("capability must enumerate the complete temporal field universe")
        if any(v in {"world_bounds", "schema_version"} for v in (*obs, *unobs)):
            raise TemporalValidationError("derived/out-of-contract fields cannot appear in capability")
        object.__setattr__(self, "observable_fields", obs)
        object.__setattr__(self, "unobservable_fields", unobs)
        object.__setattr__(self, "representation_state", rep)


@dataclass(frozen=True)
class TemporalObservation:
    stream_id: str
    continuity_id: str
    sequence: int
    source_time: SourceTime
    producer: ProducerProvenance
    capability: CapabilityContract
    snapshot: Mapping[str, Any]
    state_digest: str
    observation_schema_version: str = TEMPORAL_OBSERVATION_SCHEMA_VERSION
    capture_time: Optional[int] = None

    def __post_init__(self) -> None:
        _require_string(self.stream_id, "stream_id")
        _require_string(self.continuity_id, "continuity_id")
        _require_i64(self.sequence, "sequence", minimum=0)
        if self.observation_schema_version != TEMPORAL_OBSERVATION_SCHEMA_VERSION:
            raise TemporalValidationError("unsupported temporal observation schema version")
        if not isinstance(self.snapshot, Mapping):
            raise TemporalValidationError("snapshot must be a mapping")
        raw_snapshot = _thaw(self.snapshot)
        if type(raw_snapshot) is not dict:
            raise TemporalValidationError("snapshot must map to an exact built-in dict")
        parsed = snapshot_to_scene(raw_snapshot)
        actual = temporal_state_digest(raw_snapshot)
        _validate_digest(self.state_digest, "state_digest")
        if self.state_digest != actual:
            raise TemporalValidationError("state_digest does not match Atlas recomputation")
        if self.capture_time is not None:
            _require_i64(self.capture_time, "capture_time")
        if self.source_time.ordering_epoch < 0:
            raise TemporalValidationError("ordering_epoch must be >= 0")
        object.__setattr__(self, "snapshot", _freeze(raw_snapshot))

    @property
    def ordering_epoch(self) -> int:
        return self.source_time.ordering_epoch

    @property
    def observation_id(self) -> str:
        tuple_value = ["v1", self.stream_id, self.continuity_id, self.ordering_epoch, self.sequence]
        return "obs:" + hashlib.sha256(temporal_canonical_bytes(tuple_value)).hexdigest()[:16]

    @property
    def admission_identity_projection(self) -> Dict[str, Any]:
        return {
            "observation_schema_version": self.observation_schema_version,
            "stream_id": self.stream_id,
            "continuity_id": self.continuity_id,
            "sequence": self.sequence,
            "source_time": self.source_time.canonical(),
            "producer_session_id": self.producer.producer_session_id,
            "capability": {
                "contract_id": self.capability.contract_id,
                "observable_fields": list(self.capability.observable_fields),
                "unobservable_fields": list(self.capability.unobservable_fields),
                "representation_state": list(self.capability.representation_state),
            },
            "state_digest": self.state_digest,
        }

    @property
    def admission_identity_digest(self) -> str:
        return sha256_digest(self.admission_identity_projection)

    @property
    def envelope_digest(self) -> str:
        envelope = {
            "observation_schema_version": self.observation_schema_version,
            "stream_id": self.stream_id,
            "continuity_id": self.continuity_id,
            "sequence": self.sequence,
            "source_time": self.source_time.canonical(),
            "capture_time": self.capture_time,
            "producer": {
                "producer_source": self.producer.producer_source,
                "producer_contract": self.producer.producer_contract,
                "engine_version": self.producer.engine_version,
                "engine_build": self.producer.engine_build,
                "producer_session_id": self.producer.producer_session_id,
                "producer_instance_ordinal": self.producer.producer_instance_ordinal,
            },
            "capability": {
                "contract_id": self.capability.contract_id,
                "observable_fields": list(self.capability.observable_fields),
                "unobservable_fields": list(self.capability.unobservable_fields),
                "representation_state": list(self.capability.representation_state),
            },
            "snapshot": _thaw(self.snapshot),
            "state_digest": self.state_digest,
        }
        return sha256_digest(envelope)
