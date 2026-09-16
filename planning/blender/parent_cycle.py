"""Wave-12 bounded parent-cycle correction."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.blender.correction_values import CorrectionPlannerError

CYCLE_CORRECTION_TYPE = "REPAIR_PARENT_CYCLE"
CYCLE_PLANNER_VERSION = "1"
_CYCLE_PARAMS = frozenset({"expected_parent_id"})
_AUTH_KEYS = frozenset(
    {
        "decision",
        "correction_type",
        "correction_id",
        "plan_id",
        "source_report_digest",
        "target_object_id",
        "expected_parent_id",
    }
)


class ParentCycleError(CorrectionPlannerError):
    def __init__(self, message: str, failure_code: str) -> None:
        super().__init__(message)
        self.failure_code = failure_code


@dataclass(frozen=True)
class CyclePresentedWork:
    correction_id: str
    plan_id: str
    source_report_digest: str
    target_object_id: str
    expected_parent_id: str


@dataclass(frozen=True)
class CycleAuthorizationVerdict:
    verified: bool
    outcome: str
    failure_code: Optional[str] = None


def _canon_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canon_json(value).encode("utf-8")).hexdigest()


def _objects(scene_model: Any):
    if isinstance(scene_model, Mapping):
        return scene_model.get("objects", ())
    return getattr(scene_model, "objects", ())


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _object_id(obj: Any) -> Optional[str]:
    return _get(obj, "object_id", _get(obj, "id"))


def _parent_id(obj: Any) -> Optional[str]:
    return _get(obj, "parent_object_id", _get(obj, "parent_id"))


def _index_objects(scene_model: Any):
    by_id = {}
    for obj in _objects(scene_model):
        ident = _object_id(obj)
        if ident is None:
            raise ParentCycleError(
                "every object must have a non-empty object_id", "OBJECT_ID_INVALID"
            )
        if ident in by_id:
            raise ParentCycleError(
                f"duplicate object id {ident!r}", "DUPLICATE_OBJECT_ID"
            )
        by_id[ident] = obj
    return by_id


def _cycle_from_index(by_id: Mapping[str, Any], target_object_id: str) -> Tuple[str, ...]:
    current = target_object_id
    path = []
    positions = {}
    while current is not None:
        if current in positions:
            cycle = tuple(path[positions[current] :])
            return cycle if target_object_id in cycle else ()
        if current not in by_id:
            return ()
        positions[current] = len(path)
        path.append(current)
        current = _parent_id(by_id[current])
    return ()


def _cycle_from_target(scene_model: Any, target_object_id: str) -> Tuple[str, ...]:
    return _cycle_from_index(_index_objects(scene_model), target_object_id)


def _cycle_edges_from_index(
    by_id: Mapping[str, Any], cycle: Tuple[str, ...]
) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((ident, _parent_id(by_id[ident])) for ident in cycle))


def _cycle_edges_from_target(
    scene_model: Any, target_object_id: str
) -> Tuple[Tuple[str, str], ...]:
    by_id = _index_objects(scene_model)
    cycle = _cycle_from_index(by_id, target_object_id)
    if not cycle:
        return ()
    return _cycle_edges_from_index(by_id, cycle)


def _cycle_signatures(scene_model: Any) -> frozenset[Tuple[Tuple[str, str], ...]]:
    """Return every concrete parent-cycle edge signature in O(n) time."""
    by_id = _index_objects(scene_model)
    state = {}
    stack = []
    stack_positions = {}
    cycles = set()

    for start in by_id:
        if state.get(start) == 2:
            continue
        current = start
        while current is not None and current in by_id and state.get(current, 0) == 0:
            state[current] = 1
            stack_positions[current] = len(stack)
            stack.append(current)
            current = _parent_id(by_id[current])

        if current is not None and current in by_id and state.get(current) == 1:
            cycle = tuple(stack[stack_positions[current] :])
            cycles.add(_cycle_edges_from_index(by_id, cycle))

        while stack:
            finished = stack.pop()
            stack_positions.pop(finished, None)
            state[finished] = 2

    return frozenset(cycles)


def target_is_in_parent_cycle(scene_model: Any, target_object_id: str) -> bool:
    return bool(_cycle_from_target(scene_model, target_object_id))


def _proposal_id(
    target_object_id: str, expected_parent_id: str, source_report_digest: str
) -> str:
    return _digest(
        {
            "correction_type": CYCLE_CORRECTION_TYPE,
            "target_object_id": target_object_id,
            "expected_parent_id": expected_parent_id,
            "source_report_digest": source_report_digest,
        }
    )


def _plan_body(
    *,
    target_object_id: str,
    expected_parent_id: str,
    source_report_digest: str,
    correction_id: str,
) -> Mapping[str, Any]:
    return {
        "planner_version": CYCLE_PLANNER_VERSION,
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": correction_id,
        "source_report_digest": source_report_digest,
        "target_object_id": target_object_id,
        "params": {"expected_parent_id": expected_parent_id},
    }


def _make_plan(
    *,
    target_object_id: str,
    expected_parent_id: str,
    source_report_digest: str,
) -> Mapping[str, Any]:
    correction_id = _proposal_id(
        target_object_id, expected_parent_id, source_report_digest
    )
    body = _plan_body(
        target_object_id=target_object_id,
        expected_parent_id=expected_parent_id,
        source_report_digest=source_report_digest,
        correction_id=correction_id,
    )
    return {**body, "plan_id": _digest(body)}


def _validate_digest(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ParentCycleError(
            f"{label} must be a 64-character lowercase hex digest",
            "SOURCE_DIGEST_INVALID",
        )
    return value


def plan_parent_cycle_correction(
    scene_model: Any,
    source_report_digest: str,
    *,
    target_object_id: str,
    expected_parent_id: str,
) -> Mapping[str, Any]:
    _validate_digest(source_report_digest, "source report digest")
    if type(target_object_id) is not str or not target_object_id:
        raise ParentCycleError("target object id is required", "TARGET_OBJECT_INVALID")
    if type(expected_parent_id) is not str or not expected_parent_id:
        raise ParentCycleError(
            "expected parent id is required", "EXPECTED_PARENT_INVALID"
        )
    by_id = _index_objects(scene_model)
    target = by_id.get(target_object_id)
    if target is None:
        raise ParentCycleError(
            "target object must resolve exactly once", "TARGET_OBJECT_NOT_FOUND"
        )
    actual_parent = _parent_id(target)
    if actual_parent != expected_parent_id:
        raise ParentCycleError(
            "target does not present the expected parent edge",
            "EXPECTED_PARENT_MISMATCH",
        )
    if expected_parent_id not in by_id:
        raise ParentCycleError(
            "expected parent identifier is dangling; use Wave 4", "PARENT_IS_DANGLING"
        )
    cycle = _cycle_from_index(by_id, target_object_id)
    if not cycle:
        raise ParentCycleError(
            "target is not a member of a parent cycle", "CYCLE_NOT_FOUND"
        )
    if expected_parent_id not in cycle:
        raise ParentCycleError(
            "target parent is not the cycle edge selected by the plan",
            "PARENT_NOT_IN_CYCLE",
        )
    return _make_plan(
        target_object_id=target_object_id,
        expected_parent_id=expected_parent_id,
        source_report_digest=source_report_digest,
    )


def verify_parent_cycle_authorization(
    presented: CyclePresentedWork, authorization: Mapping[str, Any]
) -> CycleAuthorizationVerdict:
    if not isinstance(authorization, Mapping):
        return CycleAuthorizationVerdict(False, "AUTHORIZATION_INVALID", "NOT_A_MAPPING")
    if set(authorization) != _AUTH_KEYS:
        return CycleAuthorizationVerdict(False, "AUTHORIZATION_INVALID", "FIELDS_NOT_CLOSED")
    if authorization.get("decision") != "APPROVED":
        return CycleAuthorizationVerdict(False, "AUTHORIZATION_INVALID", "DECISION_NOT_APPROVED")
    for field, expected, code in (
        ("correction_type", CYCLE_CORRECTION_TYPE, "CORRECTION_TYPE_MISMATCH"),
        ("correction_id", presented.correction_id, "CORRECTION_ID_MISMATCH"),
        ("plan_id", presented.plan_id, "PLAN_ID_MISMATCH"),
        ("source_report_digest", presented.source_report_digest, "SOURCE_DIGEST_MISMATCH"),
        ("target_object_id", presented.target_object_id, "TARGET_OBJECT_MISMATCH"),
        ("expected_parent_id", presented.expected_parent_id, "EXPECTED_PARENT_MISMATCH"),
    ):
        if authorization.get(field) != expected:
            return CycleAuthorizationVerdict(False, "AUTHORIZATION_SCOPE_MISMATCH", code)
    return CycleAuthorizationVerdict(True, "AUTHORIZATION_VERIFIED")


def _extract(extractor: Callable[[], Tuple[Any, str]]) -> Tuple[Any, str]:
    result = extractor()
    if not isinstance(result, tuple) or len(result) != 2:
        raise ParentCycleError(
            "extractor must return (scene_model, report_digest)", "EXTRACTOR_INVALID"
        )
    return result


def _object_projection(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return copy.deepcopy(dict(obj))
    result = {}
    for name in (
        "object_id",
        "name",
        "collection",
        "parent_object_id",
        "location",
        "scale",
        "rotation",
        "visible",
        "mesh",
    ):
        if hasattr(obj, name):
            result[name] = copy.deepcopy(getattr(obj, name))
    return result


def _non_parent_object_projection(obj: Any) -> Any:
    projection = _object_projection(obj)
    return {k: copy.deepcopy(v) for k, v in projection.items() if k != "parent_object_id"}


def _scene_projection(
    scene_model: Any, *, exclude_object_id: Optional[str] = None
) -> Tuple[Tuple[str, Any], ...]:
    rows = []
    for obj in _objects(scene_model):
        ident = _object_id(obj)
        if ident is None:
            raise ParentCycleError(
                "post-state contains an object without an id", "OBJECT_ID_INVALID"
            )
        if ident == exclude_object_id:
            continue
        rows.append((ident, _object_projection(obj)))
    return tuple(sorted(rows, key=lambda row: row[0]))


def _scene_digest_payload(scene_model: Any) -> Any:
    if isinstance(scene_model, Mapping):
        return copy.deepcopy(dict(scene_model))

    objects = []
    for obj in _objects(scene_model):
        mesh = _get(obj, "mesh")
        mesh_payload = None
        if mesh is not None:
            mesh_payload = {
                "mesh_id": _get(mesh, "mesh_id"),
                "vertices": [list(v) for v in _get(mesh, "vertices", ())],
                "faces": [list(f) for f in _get(mesh, "faces", ())],
                "normals": [list(v) for v in _get(mesh, "normals", ())],
                "uvs": [list(v) for v in _get(mesh, "uvs", ())],
                "materials": list(_get(mesh, "materials", ())),
                "local_frame_id": _get(mesh, "local_frame_id"),
            }
        objects.append(
            {
                "object_id": _object_id(obj),
                "name": _get(obj, "name"),
                "collection": _get(obj, "collection"),
                "parent_object_id": _parent_id(obj),
                "location": list(_get(obj, "location", ())),
                "scale": list(_get(obj, "scale", ())),
                "rotation": list(_get(obj, "rotation", ())),
                "visible": _get(obj, "visible"),
                "mesh": mesh_payload,
            }
        )
    world_bounds = _get(scene_model, "world_bounds")
    return {
        "scene_id": _get(scene_model, "scene_id"),
        "unit_system": _get(scene_model, "unit_system"),
        "objects": objects,
        "coordinate_frame": _get(scene_model, "coordinate_frame"),
        "world_bounds": None if world_bounds is None else [list(world_bounds[0]), list(world_bounds[1])],
    }


def _scene_digest(scene_model: Any) -> str:
    return _digest(_scene_digest_payload(scene_model))


def _scene_non_object_projection(scene_model: Any) -> Any:
    if isinstance(scene_model, Mapping):
        return copy.deepcopy({key: value for key, value in scene_model.items() if key != "objects"})
    result = {}
    for name in ("scene_id", "unit_system", "coordinate_frame", "world_bounds"):
        if hasattr(scene_model, name):
            result[name] = copy.deepcopy(getattr(scene_model, name))
    return result


def _target_local_transform(obj: Any) -> Tuple[Any, Any, Any]:
    return (
        copy.deepcopy(_get(obj, "location")),
        copy.deepcopy(_get(obj, "rotation")),
        copy.deepcopy(_get(obj, "scale")),
    )


@dataclass(frozen=True)
class _ExecutionOutcome:
    ok: bool
    outcome: str
    failure_code: Optional[str]
    source_report_digest: str
    output_report_digest: Optional[str]


def execute_repair_parent_cycle(
    plan: Mapping[str, Any],
    authorization: Mapping[str, Any],
    *,
    extractor: Callable[[], Tuple[Any, str]],
    mutator: Callable[[str, str, None], None],
) -> _ExecutionOutcome:
    if not isinstance(plan, Mapping):
        return _ExecutionOutcome(False, "PLAN_INVALID", "NOT_A_MAPPING", "", None)
    if plan.get("correction_type") != CYCLE_CORRECTION_TYPE:
        return _ExecutionOutcome(
            False,
            "PLAN_INVALID",
            "CORRECTION_TYPE_MISMATCH",
            str(plan.get("source_report_digest")),
            None,
        )
    params = plan.get("params")
    if not isinstance(params, Mapping) or set(params) != _CYCLE_PARAMS:
        return _ExecutionOutcome(
            False, "PLAN_INVALID", "PARAMS_INVALID", str(plan.get("source_report_digest")), None
        )
    source_digest = plan.get("source_report_digest")
    target_id = plan.get("target_object_id")
    correction_id = plan.get("correction_id")
    plan_id = plan.get("plan_id")
    expected_parent_id = params.get("expected_parent_id")
    if not all(
        type(v) is str and v
        for v in (source_digest, target_id, correction_id, plan_id, expected_parent_id)
    ):
        return _ExecutionOutcome(False, "PLAN_INVALID", "PLAN_FIELDS_INVALID", str(source_digest), None)
    if len(source_digest) != 64 or any(c not in "0123456789abcdef" for c in source_digest):
        return _ExecutionOutcome(False, "PLAN_INVALID", "SOURCE_DIGEST_INVALID", source_digest, None)

    expected_correction_id = _proposal_id(target_id, expected_parent_id, source_digest)
    if correction_id != expected_correction_id:
        return _ExecutionOutcome(False, "PLAN_INVALID", "CORRECTION_ID_INVALID", source_digest, None)
    expected_body = _plan_body(
        target_object_id=target_id,
        expected_parent_id=expected_parent_id,
        source_report_digest=source_digest,
        correction_id=expected_correction_id,
    )
    if plan_id != _digest(expected_body):
        return _ExecutionOutcome(False, "PLAN_INVALID", "PLAN_ID_INVALID", source_digest, None)

    verdict = verify_parent_cycle_authorization(
        CyclePresentedWork(correction_id, plan_id, source_digest, target_id, expected_parent_id),
        authorization,
    )
    if not verdict.verified:
        return _ExecutionOutcome(False, "AUTHORIZATION_REFUSED", verdict.failure_code, source_digest, None)

    try:
        scene_before, fresh_digest = _extract(extractor)
    except Exception:
        return _ExecutionOutcome(False, "MUTATION_FAILED", "EXTRACTION_FAILED", source_digest, None)

    try:
        _validate_digest(fresh_digest, "extractor source report digest")
    except ParentCycleError:
        return _ExecutionOutcome(False, "PLAN_INVALID", "SOURCE_DIGEST_INVALID", str(fresh_digest), None)

    try:
        computed_source_digest = _scene_digest(scene_before)
    except Exception:
        return _ExecutionOutcome(
            False, "PLAN_INVALID", "SCENE_DIGEST_COMPUTATION_FAILED", str(fresh_digest), None
        )
    if fresh_digest != computed_source_digest:
        return _ExecutionOutcome(
            False, "PLAN_INVALID", "SOURCE_DIGEST_INVALID", computed_source_digest, None
        )
    if computed_source_digest != source_digest:
        return _ExecutionOutcome(
            False, "PLAN_INVALID", "SOURCE_DIGEST_MISMATCH", computed_source_digest, None
        )

    try:
        by_id = _index_objects(scene_before)
        target = by_id.get(target_id)
        if target is None:
            return _ExecutionOutcome(False, "PLAN_INVALID", "TARGET_OBJECT_NOT_FOUND", computed_source_digest, None)
        if _parent_id(target) != expected_parent_id:
            return _ExecutionOutcome(False, "PLAN_INVALID", "EXPECTED_PARENT_MISMATCH", computed_source_digest, None)
        if expected_parent_id not in by_id:
            return _ExecutionOutcome(False, "PLAN_INVALID", "PARENT_IS_DANGLING", computed_source_digest, None)
        before_cycles = _cycle_signatures(scene_before)
        selected_cycle = _cycle_from_index(by_id, target_id)
        selected_cycle_signature = _cycle_edges_from_index(by_id, selected_cycle)
        if not selected_cycle_signature:
            return _ExecutionOutcome(False, "PLAN_INVALID", "CYCLE_NOT_FOUND", computed_source_digest, None)
        if expected_parent_id not in selected_cycle:
            return _ExecutionOutcome(False, "PLAN_INVALID", "PARENT_NOT_IN_CYCLE", computed_source_digest, None)
        before_identity = tuple(sorted(by_id))
        before_target_non_parent = _non_parent_object_projection(target)
        before_target_local_transform = _target_local_transform(target)
        before_unrelated = _scene_projection(scene_before, exclude_object_id=target_id)
        before_scene_non_object = _scene_non_object_projection(scene_before)
    except ParentCycleError as exc:
        return _ExecutionOutcome(False, "PLAN_INVALID", exc.failure_code, computed_source_digest, None)
    except Exception:
        return _ExecutionOutcome(False, "PLAN_INVALID", "SCENE_VALIDATION_FAILED", computed_source_digest, None)

    try:
        mutator(target_id, expected_parent_id, None)
    except Exception:
        return _ExecutionOutcome(False, "MUTATION_FAILED", "MUTATOR_EXCEPTION", computed_source_digest, None)

    try:
        scene_after, output_digest = _extract(extractor)
    except Exception:
        return _ExecutionOutcome(False, "MUTATION_FAILED", "POST_EXTRACTION_FAILED", computed_source_digest, None)
    try:
        _validate_digest(output_digest, "output report digest")
    except ParentCycleError:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "OUTPUT_DIGEST_INVALID", computed_source_digest, None)

    try:
        computed_output_digest = _scene_digest(scene_after)
    except Exception:
        return _ExecutionOutcome(
            False, "POSTCONDITION_FAILED", "OUTPUT_DIGEST_COMPUTATION_FAILED", computed_source_digest, output_digest
        )
    if output_digest != computed_output_digest:
        return _ExecutionOutcome(
            False, "POSTCONDITION_FAILED", "OUTPUT_DIGEST_INVALID", computed_source_digest, output_digest
        )

    try:
        after_by_id = _index_objects(scene_after)
        target_after = after_by_id.get(target_id)
        if target_after is None:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_OBJECT_MISSING", computed_source_digest, output_digest)
        if _parent_id(target_after) is not None:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "PARENT_NOT_DETACHED", computed_source_digest, output_digest)
        if _non_parent_object_projection(target_after) != before_target_non_parent:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_NON_PARENT_CHANGED", computed_source_digest, output_digest)
        if _target_local_transform(target_after) != before_target_local_transform:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_LOCAL_TRANSFORM_CHANGED", computed_source_digest, output_digest)
        if tuple(sorted(after_by_id)) != before_identity:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "OBJECT_IDENTITY_CHANGED", computed_source_digest, output_digest)
        after_cycles = _cycle_signatures(scene_after)
        if selected_cycle_signature in after_cycles:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "CYCLE_REMAINS", computed_source_digest, output_digest)
        if not after_cycles.issubset(before_cycles - {selected_cycle_signature}):
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "NEW_CYCLE_CREATED", computed_source_digest, output_digest)
        if _scene_projection(scene_after, exclude_object_id=target_id) != before_unrelated:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNRELATED_OBJECT_CHANGED", computed_source_digest, output_digest)
        if _scene_non_object_projection(scene_after) != before_scene_non_object:
            return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "SCENE_STATE_CHANGED", computed_source_digest, output_digest)
    except ParentCycleError as exc:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", exc.failure_code, computed_source_digest, output_digest)
    except Exception:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "POSTCONDITION_VALIDATION_FAILED", computed_source_digest, output_digest)

    return _ExecutionOutcome(True, "CORRECTION_APPLIED", None, computed_source_digest, output_digest)
