"""Pure Temporal v1 evaluation and StateDelta construction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from planning.blender.scene_model import ObjectModel, SceneModel

from .admission import FromIdentity
from .canonical import sha256_digest
from .model import (
    CapabilityContract,
    TemporalObservation,
    snapshot_to_scene,
    TEMPORAL_COMPARISON_FIELDS,
)


class DeltaOutcome(str, Enum):
    COMPUTED = "COMPUTED"
    TEMPORAL_DISCONTINUITY = "TEMPORAL_DISCONTINUITY"
    OBSERVATION_INVALID = "OBSERVATION_INVALID"


class EntityDeltaKind(str, Enum):
    OBJECT_ADDED = "OBJECT_ADDED"
    OBJECT_REMOVED = "OBJECT_REMOVED"
    OBJECT_CHANGED = "OBJECT_CHANGED"
    NO_CHANGE = "NO_CHANGE"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"


class FieldObservationState(str, Enum):
    OBSERVED_UNCHANGED = "OBSERVED_UNCHANGED"
    OBSERVED_CHANGED = "OBSERVED_CHANGED"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED_BY_PRODUCER = "UNSUPPORTED_BY_PRODUCER"
    INVALID_OBSERVATION = "INVALID_OBSERVATION"


class DeltaReasonCode(str, Enum):
    TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE = "TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE"
    RESTART_PRODUCER_SESSION = "RESTART_PRODUCER_SESSION"
    ORDERING_EPOCH_CHANGE = "ORDERING_EPOCH_CHANGE"
    PAIR_INPUT_UNAVAILABLE = "PAIR_INPUT_UNAVAILABLE"
    PAIR_INPUT_IDENTITY_MISMATCH = "PAIR_INPUT_IDENTITY_MISMATCH"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    UNIT_SYSTEM_CHANGED = "UNIT_SYSTEM_CHANGED"
    IDENTITY_AMBIGUOUS_IDS = "IDENTITY_AMBIGUOUS_IDS"
    ROTATION_SIGN_EQUIVALENT_ONLY = "ROTATION_SIGN_EQUIVALENT_ONLY"


@dataclass(frozen=True)
class ComparisonInput:
    a: TemporalObservation
    b: TemporalObservation
    from_identity: FromIdentity


@dataclass(frozen=True)
class BoundaryInput:
    a: TemporalObservation
    b: TemporalObservation
    from_identity: FromIdentity


@dataclass(frozen=True)
class RefusalInput:
    b: TemporalObservation
    from_identity: FromIdentity
    reason: DeltaReasonCode


@dataclass(frozen=True)
class BoundaryRefusalInput:
    b: TemporalObservation
    from_identity: FromIdentity
    reason: DeltaReasonCode


EvaluationInput = Union[ComparisonInput, BoundaryInput, RefusalInput, BoundaryRefusalInput]


FIELD_ORDER = (
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


def _draft_base(
    *,
    outcome: DeltaOutcome,
    pair_input: str,
    continuity: str,
    b: TemporalObservation,
    from_identity: FromIdentity,
    reason_codes: Sequence[DeltaReasonCode],
    entity_deltas: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, FieldObservationState],
    observations_skipped: int,
    source_time_hold: bool,
) -> Dict[str, Any]:
    reason_values = sorted({reason.value for reason in reason_codes})
    return {
        "delta_schema_version": 1,
        "outcome": outcome.value,
        "pair_input": pair_input,
        "stream_id": b.stream_id,
        "from_observation_id": from_identity.last_accepted_observation_id,
        "to_observation_id": b.observation_id,
        "from_state_digest": from_identity.last_accepted_state_digest,
        "to_state_digest": b.state_digest,
        "state_digest_changed": from_identity.last_accepted_state_digest != b.state_digest,
        "continuity": continuity,
        "observations_skipped": observations_skipped,
        "source_time_hold": source_time_hold,
        "identity_ambiguous_ids": sorted(
            item["object_id"]
            for item in entity_deltas
            if item["kind"] == EntityDeltaKind.IDENTITY_AMBIGUOUS.value
        ),
        "entity_deltas": list(entity_deltas),
        "coverage": {key: coverage[key].value for key in sorted(coverage)},
        "reason_codes": reason_values,
    }


def finalize_record(draft: Mapping[str, Any], from_origin: str) -> Dict[str, Any]:
    record = dict(draft)
    record["from_observation_origin"] = from_origin
    record["delta_digest"] = sha256_digest(
        {key: value for key, value in record.items() if key != "delta_digest"}
    )
    return record


def _invalid_coverage(capability: CapabilityContract) -> Dict[str, FieldObservationState]:
    return {
        field: (
            FieldObservationState.UNSUPPORTED_BY_PRODUCER
            if field in capability.unobservable_fields
            else FieldObservationState.INVALID_OBSERVATION
        )
        for field in sorted(
            set(capability.observable_fields) | set(capability.unobservable_fields)
        )
    }


def _capability_compatible(a: TemporalObservation, b: TemporalObservation) -> bool:
    return (
        a.capability.contract_id == b.capability.contract_id
        and a.capability.observable_fields == b.capability.observable_fields
        and a.capability.unobservable_fields == b.capability.unobservable_fields
    )


def _materials_available(observation: TemporalObservation) -> bool:
    return not any(
        value == "materials:omitted"
        for value in observation.capability.representation_state
    )


def _field_supported_and_available(
    field: str,
    a: TemporalObservation,
    b: TemporalObservation,
) -> Tuple[bool, bool]:
    if field in a.capability.unobservable_fields:
        return False, False
    if field == "materials" and (not _materials_available(a) or not _materials_available(b)):
        return True, False
    return True, True


def _object_map(scene: SceneModel) -> Dict[str, List[ObjectModel]]:
    out: Dict[str, List[ObjectModel]] = {}
    for obj in scene.objects:
        out.setdefault(obj.object_id, []).append(obj)
    return out


def _rotation_equal(a: Tuple[float, ...], b: Tuple[float, ...]) -> Tuple[bool, bool]:
    if a == b:
        return True, False
    negated = tuple(-value for value in a)
    if negated == b:
        return True, True
    return False, False


def _field_value(obj: ObjectModel, field: str):
    if field == "mesh_presence":
        return obj.mesh is not None
    if field == "mesh_id":
        return None if obj.mesh is None else obj.mesh.mesh_id
    if field == "vertices":
        return None if obj.mesh is None else obj.mesh.vertices
    if field == "faces":
        return None if obj.mesh is None else obj.mesh.faces
    if field == "materials":
        return None if obj.mesh is None else obj.mesh.materials
    return getattr(obj, field)


def _field_equal(field: str, before, after) -> Tuple[bool, bool]:
    if field == "rotation":
        return _rotation_equal(before, after)
    return before == after, False


def _field_change(field: str, before, after) -> Dict[str, Any]:
    return {
        "field": field,
        "before": _plain(before),
        "after": _plain(after),
    }


def _plain(value):
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _boundary_reasons(a: TemporalObservation, b: TemporalObservation) -> List[DeltaReasonCode]:
    reasons = []
    if a.continuity_id != b.continuity_id:
        reasons.append(DeltaReasonCode.TEMPORAL_DISCONTINUITY_CONTINUITY_ID_CHANGE)
    if a.producer.producer_session_id != b.producer.producer_session_id:
        reasons.append(DeltaReasonCode.RESTART_PRODUCER_SESSION)
    if a.ordering_epoch != b.ordering_epoch:
        reasons.append(DeltaReasonCode.ORDERING_EPOCH_CHANGE)
    return reasons


def _identity_agrees(a: TemporalObservation, from_identity: FromIdentity) -> bool:
    return (
        a.observation_id == from_identity.last_accepted_observation_id
        and a.state_digest == from_identity.last_accepted_state_digest
        and a.admission_identity_digest == from_identity.last_accepted_admission_identity_digest
    )


def evaluate(evaluation_input: EvaluationInput) -> Dict[str, Any]:
    """Pure evaluator. It reads only the supplied EvaluationInput."""

    if isinstance(evaluation_input, BoundaryRefusalInput):
        return _refusal(
            evaluation_input.b,
            evaluation_input.from_identity,
            evaluation_input.reason,
            continuity="NEW_EPOCH",
            pair_input="UNAVAILABLE",
        )

    if isinstance(evaluation_input, RefusalInput):
        return _refusal(
            evaluation_input.b,
            evaluation_input.from_identity,
            evaluation_input.reason,
            continuity="SAME_EPOCH",
            pair_input="UNAVAILABLE",
        )

    if isinstance(evaluation_input, BoundaryInput):
        if not _identity_agrees(evaluation_input.a, evaluation_input.from_identity):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH,
                continuity="NEW_EPOCH",
                pair_input="AVAILABLE",
            )
        return _draft_base(
            outcome=DeltaOutcome.TEMPORAL_DISCONTINUITY,
            pair_input="AVAILABLE",
            continuity="NEW_EPOCH",
            b=evaluation_input.b,
            from_identity=evaluation_input.from_identity,
            reason_codes=_boundary_reasons(evaluation_input.a, evaluation_input.b),
            entity_deltas=[],
            coverage=_invalid_coverage(evaluation_input.b.capability),
            observations_skipped=0,
            source_time_hold=False,
        )

    if isinstance(evaluation_input, ComparisonInput):
        if not _identity_agrees(evaluation_input.a, evaluation_input.from_identity):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH,
                continuity="SAME_EPOCH",
                pair_input="AVAILABLE",
            )

        if not _capability_compatible(evaluation_input.a, evaluation_input.b):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.CAPABILITY_MISMATCH,
                continuity="SAME_EPOCH",
                pair_input="AVAILABLE",
            )

        a_scene = snapshot_to_scene(evaluation_input.a.snapshot)
        b_scene = snapshot_to_scene(evaluation_input.b.snapshot)
        if a_scene.unit_system != b_scene.unit_system:
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.UNIT_SYSTEM_CHANGED,
                continuity="SAME_EPOCH",
                pair_input="AVAILABLE",
            )

        return _compare(
            evaluation_input.a,
            evaluation_input.b,
            evaluation_input.from_identity,
            a_scene,
            b_scene,
        )

    raise TypeError("unsupported EvaluationInput: %s" % type(evaluation_input).__name__)


def _refusal(
    b: TemporalObservation,
    from_identity: FromIdentity,
    reason: DeltaReasonCode,
    *,
    continuity: str,
    pair_input: str,
) -> Dict[str, Any]:
    return _draft_base(
        outcome=DeltaOutcome.OBSERVATION_INVALID,
        pair_input=pair_input,
        continuity=continuity,
        b=b,
        from_identity=from_identity,
        reason_codes=[reason],
        entity_deltas=[],
        coverage=_invalid_coverage(b.capability),
        observations_skipped=0,
        source_time_hold=False,
    )


def _compare(
    a: TemporalObservation,
    b: TemporalObservation,
    from_identity: FromIdentity,
    a_scene: SceneModel,
    b_scene: SceneModel,
) -> Dict[str, Any]:
    a_objects = _object_map(a_scene)
    b_objects = _object_map(b_scene)

    entity_deltas: List[Dict[str, Any]] = []
    changed_fields = set()
    rotation_sign_only = False
    ambiguous = False

    for object_id in sorted(set(a_objects) | set(b_objects)):
        left = a_objects.get(object_id, [])
        right = b_objects.get(object_id, [])

        if len(left) > 1 or len(right) > 1:
            ambiguous = True
            entity_deltas.append({
                "object_id": object_id,
                "kind": EntityDeltaKind.IDENTITY_AMBIGUOUS.value,
                "field_changes": [],
                "ambiguity": {
                    "count_before": len(left),
                    "count_after": len(right),
                },
            })
            continue

        if len(left) == 0:
            entity_deltas.append({
                "object_id": object_id,
                "kind": EntityDeltaKind.OBJECT_ADDED.value,
                "field_changes": [],
            })
            continue

        if len(right) == 0:
            entity_deltas.append({
                "object_id": object_id,
                "kind": EntityDeltaKind.OBJECT_REMOVED.value,
                "field_changes": [],
            })
            continue

        before_obj = left[0]
        after_obj = right[0]
        field_changes: List[Dict[str, Any]] = []

        for field in FIELD_ORDER:
            supported, available = _field_supported_and_available(field, a, b)
            if not supported or not available:
                continue

            if field in {"mesh_id", "vertices", "faces", "materials"}:
                if before_obj.mesh is None or after_obj.mesh is None:
                    continue

            before = _field_value(before_obj, field)
            after = _field_value(after_obj, field)
            equal, sign_equivalent = _field_equal(field, before, after)
            if equal:
                if sign_equivalent:
                    rotation_sign_only = True
                continue

            field_changes.append(_field_change(field, before, after))
            changed_fields.add(field)

        entity_deltas.append({
            "object_id": object_id,
            "kind": (
                EntityDeltaKind.OBJECT_CHANGED.value
                if field_changes
                else EntityDeltaKind.NO_CHANGE.value
            ),
            "field_changes": field_changes,
        })

    coverage: Dict[str, FieldObservationState] = {}
    for field in TEMPORAL_COMPARISON_FIELDS:
        supported, available = _field_supported_and_available(field, a, b)
        if not supported:
            coverage[field] = FieldObservationState.UNSUPPORTED_BY_PRODUCER
        elif not available:
            coverage[field] = FieldObservationState.UNAVAILABLE
        elif field in changed_fields:
            coverage[field] = FieldObservationState.OBSERVED_CHANGED
        else:
            coverage[field] = FieldObservationState.OBSERVED_UNCHANGED

    for field in sorted(a.capability.unobservable_fields):
        coverage[field] = FieldObservationState.UNSUPPORTED_BY_PRODUCER

    reasons: List[DeltaReasonCode] = []
    if ambiguous:
        reasons.append(DeltaReasonCode.IDENTITY_AMBIGUOUS_IDS)
    if rotation_sign_only:
        reasons.append(DeltaReasonCode.ROTATION_SIGN_EQUIVALENT_ONLY)

    return _draft_base(
        outcome=DeltaOutcome.COMPUTED,
        pair_input="AVAILABLE",
        continuity="SAME_EPOCH",
        b=b,
        from_identity=from_identity,
        reason_codes=reasons,
        entity_deltas=entity_deltas,
        coverage=coverage,
        observations_skipped=max(0, b.sequence - a.sequence - 1),
        source_time_hold=a.source_time.tuple_equal(b.source_time) and bool(changed_fields),
    )

