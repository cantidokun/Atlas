"""Pure Temporal v1 evaluation and StateDelta construction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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


EvaluationInput = ComparisonInput | BoundaryInput | RefusalInput | BoundaryRefusalInput


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


def _record_base(
    *,
    outcome: DeltaOutcome,
    pair_input: str,
    continuity: str,
    a: Optional[TemporalObservation],
    b: TemporalObservation,
    reason_codes: Sequence[DeltaReasonCode],
    entity_deltas: Sequence[Mapping[str, Any]],
    coverage: Mapping[str, FieldObservationState],
    observations_skipped: int,
    source_time_hold: bool,
    from_origin: str,
) -> Dict[str, Any]:
    from_id = a.observation_id if a is not None else None
    from_digest = a.state_digest if a is not None else None

    if a is None:
        from_id = "obs:unknown"
        from_digest = "0" * 64

    reason_values = sorted({r.value if isinstance(r, Enum) else str(r) for r in reason_codes})
    record = {
        "delta_schema_version": 1,
        "outcome": outcome.value,
        "pair_input": pair_input,
        "stream_id": b.stream_id,
        "from_observation_id": from_id,
        "from_observation_origin": from_origin,
        "to_observation_id": b.observation_id,
        "from_state_digest": from_digest,
        "to_state_digest": b.state_digest,
        "state_digest_changed": a is None or from_digest != b.state_digest,
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
    record["delta_digest"] = sha256_digest({k: v for k, v in record.items() if k != "delta_digest"})
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


def evaluate(evaluation_input: EvaluationInput, *, from_origin: str) -> Dict[str, Any]:
    """Pure evaluator. It reads only the supplied EvaluationInput and the explicit origin value."""

    if isinstance(evaluation_input, BoundaryRefusalInput):
        return _refusal(
            evaluation_input.b,
            evaluation_input.from_identity,
            evaluation_input.reason,
            continuity="NEW_EPOCH",
            from_origin=from_origin,
            boundary=True,
        )

    if isinstance(evaluation_input, RefusalInput):
        return _refusal(
            evaluation_input.b,
            evaluation_input.from_identity,
            evaluation_input.reason,
            continuity="SAME_EPOCH",
            from_origin=from_origin,
            boundary=False,
        )

    if isinstance(evaluation_input, BoundaryInput):
        if not _identity_agrees(evaluation_input.a, evaluation_input.from_identity):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH,
                continuity="NEW_EPOCH",
                from_origin=from_origin,
                boundary=True,
                supplied_a=evaluation_input.a,
            )
        reasons = _boundary_reasons(evaluation_input.a, evaluation_input.b)
        coverage = _invalid_coverage(evaluation_input.b.capability)
        return _record_base(
            outcome=DeltaOutcome.TEMPORAL_DISCONTINUITY,
            pair_input="AVAILABLE",
            continuity="NEW_EPOCH",
            a=evaluation_input.a,
            b=evaluation_input.b,
            reason_codes=reasons,
            entity_deltas=[],
            coverage=coverage,
            observations_skipped=0,
            source_time_hold=False,
            from_origin=from_origin,
        )

    if isinstance(evaluation_input, ComparisonInput):
        if not _identity_agrees(evaluation_input.a, evaluation_input.from_identity):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.PAIR_INPUT_IDENTITY_MISMATCH,
                continuity="SAME_EPOCH",
                from_origin=from_origin,
                boundary=False,
                supplied_a=evaluation_input.a,
            )

        if not _capability_compatible(evaluation_input.a, evaluation_input.b):
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.CAPABILITY_MISMATCH,
                continuity="SAME_EPOCH",
                from_origin=from_origin,
                boundary=False,
                supplied_a=evaluation_input.a,
            )

        a_scene = snapshot_to_scene(evaluation_input.a.snapshot)
        b_scene = snapshot_to_scene(evaluation_input.b.snapshot)
        if a_scene.unit_system != b_scene.unit_system:
            return _refusal(
                evaluation_input.b,
                evaluation_input.from_identity,
                DeltaReasonCode.UNIT_SYSTEM_CHANGED,
                continuity="SAME_EPOCH",
                from_origin=from_origin,
                boundary=False,
                supplied_a=evaluation_input.a,
            )

        return _compare(evaluation_input.a, evaluation_input.b, a_scene, b_scene, from_origin)

    raise TypeError(f"unsupported EvaluationInput: {type(evaluation_input).__name__}")


def _refusal(
    b: TemporalObservation,
    from_identity: FromIdentity,
    reason: DeltaReasonCode,
    *,
    continuity: str,
    from_origin: str,
    boundary: bool,
    supplied_a: Optional[TemporalObservation] = None,
) -> Dict[str, Any]:
    coverage = _invalid_coverage(b.capability)
    return _record_base(
        outcome=DeltaOutcome.OBSERVATION_INVALID,
        pair_input="AVAILABLE" if supplied_a is not None else "UNAVAILABLE",
        continuity=continuity,
        a=supplied_a,
        b=b,
        reason_codes=[reason],
        entity_deltas=[],
        coverage=coverage,
        observations_skipped=0,
        source_time_hold=False,
        from_origin=from_origin,
    )


def _compare(
    a: TemporalObservation,
    b: TemporalObservation,
    a_scene: SceneModel,
    b_scene: SceneModel,
    from_origin: str,
) -> Dict[str, Any]:
    a_objects = _object_map(a_scene)
    b_objects = _object_map(b_scene)
    entity_deltas: List[Dict[str, Any]] = []
    changed_fields = set()
    rotation_sign_only = False

    for object_id in sorted(set(a_objects) | set(b_objects)):
        left = a_objects.get(object_id, [])
        right = b_objects.get(object_id, [])

        if len(left) != 1 or len(right) != 1:
            if left or right:
                entity_deltas.append(
                    {"object_id": object_id, "kind": EntityDeltaKind.IDENTITY_AMBIGUOUS.value, "field_changes": []}
                )
            continue

        before_obj, after_obj = left[0], right[0]
        field_changes = []
        local_sign_only = False

        for field in FIELD_ORDER:
            supported, available = _field_supported_and_available(field, a, b)
            if not supported or not available:
                continue
            before = _field_value(before_obj, field)
            after = _field_value(after_obj, field)
            equal, sign_equivalent = _field_equal(field, before, after)
            if equal:
                local_sign_only = local_sign_only or sign_equivalent
                if sign_equivalent:
                    rotation_sign_only = True
                continue
            field_changes.append(_field_change(field, before, after))
            changed_fields.add(field)

        kind = (
            EntityDeltaKind.OBJECT_CHANGED.value
            if field_changes
            else EntityDeltaKind.NO_CHANGE.value
        )
        entity_deltas.append(
            {
                "object_id": object_id,
                "kind": kind,
                "field_changes": field_changes,
            }
        )

    for object_id in sorted(set(b_objects) - set(a_objects)):
        if len(b_objects[object_id]) == 1:
            entity_deltas.append(
                {"object_id": object_id, "kind": EntityDeltaKind.OBJECT_ADDED.value, "field_changes": []}
            )
    for object_id in sorted(set(a_objects) - set(b_objects)):
        if len(a_objects[object_id]) == 1:
            entity_deltas.append(
                {"object_id": object_id, "kind": EntityDeltaKind.OBJECT_REMOVED.value, "field_changes": []}
            )

    # Re-sort entity output by the canonical object_id order after add/remove construction.
    entity_deltas.sort(key=lambda item: item["object_id"])

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

    if any(item["kind"] == EntityDeltaKind.IDENTITY_AMBIGUOUS.value for item in entity_deltas):
        # Ambiguity is factual but does not become a field-level comparison result.
        pass

    real_field_change = bool(changed_fields)
    source_time_hold = a.source_time.tuple_equal(b.source_time) and real_field_change

    reasons = []
    if rotation_sign_only and not real_field_change:
        reasons.append(DeltaReasonCode.ROTATION_SIGN_EQUIVALENT_ONLY)
    elif rotation_sign_only:
        reasons.append(DeltaReasonCode.ROTATION_SIGN_EQUIVALENT_ONLY)

    return _record_base(
        outcome=DeltaOutcome.COMPUTED,
        pair_input="AVAILABLE",
        continuity="SAME_EPOCH",
        a=a,
        b=b,
        reason_codes=reasons,
        entity_deltas=entity_deltas,
        coverage=coverage,
        observations_skipped=max(0, b.sequence - a.sequence - 1),
        source_time_hold=source_time_hold,
        from_origin=from_origin,
    )
