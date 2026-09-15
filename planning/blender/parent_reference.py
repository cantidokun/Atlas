"""Wave-4 bounded parent-reference correction.

This module is intentionally narrow: it plans and executes only the repair of a
reported dangling parent identifier by detaching the target object from its
parent. It does not create parents, repair cycles, normalize hierarchy, persist
files, or own recovery/receipt authority.

The execution boundary is adapter-driven. A caller supplies a fresh extractor
and a single object-model mutator; the executor verifies the source digest and
all required preconditions before invoking the mutator exactly once, then
re-extracts and checks the postconditions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

from planning.blender.correction_values import CorrectionPlannerError

PARENT_CORRECTION_TYPE = "REPAIR_PARENT_REFERENCE"
PARENT_PLANNER_VERSION = "1"
_PARENT_PARAMS = frozenset({"expected_parent_id", "detach_to"})


class ParentReferenceError(CorrectionPlannerError):
    """Declared Wave-4 planning/execution failure."""

    def __init__(self, message: str, failure_code: str) -> None:
        super().__init__(message)
        self.failure_code = failure_code


@dataclass(frozen=True)
class ParentPresentedWork:
    correction_id: str
    plan_id: str
    source_report_digest: str
    target_object_id: str
    expected_parent_id: str


@dataclass(frozen=True)
class ParentAuthorizationVerdict:
    verified: bool
    outcome: str
    failure_code: Optional[str] = None


def _canon_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canon_json(value).encode("utf-8")).hexdigest()


def _get(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, Mapping):
        return mapping.get(key, default)
    return getattr(mapping, key, default)


def _target_objects(scene_model: Any) -> Sequence[Any]:
    objects = _get(scene_model, "objects", ())
    return tuple(objects)


def _find_object(scene_model: Any, object_id: str) -> Any:
    matches = [obj for obj in _target_objects(scene_model) if _get(obj, "object_id") == object_id or _get(obj, "id") == object_id]
    if len(matches) != 1:
        return None
    return matches[0]


def _object_identity(obj: Any) -> Any:
    return _get(obj, "object_id", _get(obj, "id"))


def _parent_id(obj: Any) -> Optional[str]:
    value = _get(obj, "parent_id", _get(obj, "parent"))
    if value is None:
        return None
    if isinstance(value, str):
        return value
    ident = _get(value, "object_id", _get(value, "id"))
    return ident if isinstance(ident, str) else None


def _non_parent_projection(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {k: v for k, v in obj.items() if k not in {"parent_id", "parent"}}
    result = {}
    for name in ("object_id", "id", "name", "mesh_id", "transform", "location", "rotation", "scale", "children", "data"):
        if hasattr(obj, name):
            result[name] = getattr(obj, name)
    return result


def _full_object_projection(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return dict(obj)
    result = {}
    for name in ("object_id", "id", "name", "mesh_id", "transform", "location", "rotation", "scale", "children", "data", "parent_id", "parent"):
        if hasattr(obj, name):
            result[name] = getattr(obj, name)
    return result


def _scene_identity_snapshot(scene_model: Any) -> Tuple[Any, ...]:
    return tuple(sorted(_object_identity(obj) for obj in _target_objects(scene_model)))


def _scene_unrelated_snapshot(scene_model: Any, target_object_id: str) -> Tuple[Tuple[Any, Any], ...]:
    snapshot = []
    for obj in _target_objects(scene_model):
        if _object_identity(obj) == target_object_id:
            continue
        snapshot.append((_object_identity(obj), _full_object_projection(obj)))
    return tuple(sorted(snapshot, key=lambda item: str(item[0])))


def _has_cycle(scene_model: Any, target_object_id: str) -> bool:
    seen = set()
    current = _find_object(scene_model, target_object_id)
    while current is not None:
        ident = _get(current, "object_id", _get(current, "id"))
        if ident in seen:
            return True
        seen.add(ident)
        parent_id = _parent_id(current)
        if parent_id is None:
            return False
        current = _find_object(scene_model, parent_id)
    return False


def verify_parent_authorization(
    presented: ParentPresentedWork,
    authorization: Mapping[str, Any],
) -> ParentAuthorizationVerdict:
    """Verify Wave-4 authorization bindings without performing mutation."""
    if not isinstance(authorization, Mapping):
        return ParentAuthorizationVerdict(False, "AUTHORIZATION_INVALID", "NOT_A_MAPPING")
    if authorization.get("decision") != "APPROVED":
        return ParentAuthorizationVerdict(False, "AUTHORIZATION_INVALID", "DECISION_NOT_APPROVED")
    if authorization.get("correction_type") != PARENT_CORRECTION_TYPE:
        return ParentAuthorizationVerdict(False, "AUTHORIZATION_SCOPE_MISMATCH", "CORRECTION_TYPE_MISMATCH")
    checks = (
        ("correction_id", presented.correction_id, "CORRECTION_ID_MISMATCH"),
        ("plan_id", presented.plan_id, "PLAN_ID_MISMATCH"),
        ("source_report_digest", presented.source_report_digest, "SOURCE_DIGEST_MISMATCH"),
    )
    for field, expected, code in checks:
        if authorization.get(field) != expected:
            return ParentAuthorizationVerdict(False, "AUTHORIZATION_SCOPE_MISMATCH", code)
    if authorization.get("target_object_id") not in (None, presented.target_object_id):
        return ParentAuthorizationVerdict(False, "AUTHORIZATION_SCOPE_MISMATCH", "TARGET_OBJECT_MISMATCH")
    if authorization.get("expected_parent_id") not in (None, presented.expected_parent_id):
        return ParentAuthorizationVerdict(False, "AUTHORIZATION_SCOPE_MISMATCH", "EXPECTED_PARENT_MISMATCH")
    return ParentAuthorizationVerdict(True, "AUTHORIZATION_VERIFIED")


def _proposal_id(
    correction_type: str,
    target_object_id: str,
    expected_parent_id: str,
    source_report_digest: str,
) -> str:
    return _digest(
        {
            "correction_type": correction_type,
            "target_object_id": target_object_id,
            "expected_parent_id": expected_parent_id,
            "source_report_digest": source_report_digest,
        }
    )


def _make_plan(
    *,
    target_object_id: str,
    expected_parent_id: str,
    source_report_digest: str,
) -> Mapping[str, Any]:
    correction_id = _proposal_id(
        PARENT_CORRECTION_TYPE,
        target_object_id,
        expected_parent_id,
        source_report_digest,
    )
    body = {
        "planner_version": PARENT_PLANNER_VERSION,
        "correction_type": PARENT_CORRECTION_TYPE,
        "correction_id": correction_id,
        "source_report_digest": source_report_digest,
        "target_object_id": target_object_id,
        "params": {"expected_parent_id": expected_parent_id, "detach_to": None},
    }
    return {**body, "plan_id": _digest(body)}


def plan_parent_reference_correction(
    scene_model: Any,
    source_report_digest: str,
    *,
    target_object_id: str,
    expected_parent_id: str,
) -> Mapping[str, Any]:
    """Create a closed Wave-4 plan for one reported dangling parent reference."""
    if not isinstance(source_report_digest, str) or len(source_report_digest) != 64:
        raise ParentReferenceError("source report digest must be a 64-character digest", "SOURCE_DIGEST_INVALID")
    if not isinstance(target_object_id, str) or not target_object_id:
        raise ParentReferenceError("target object id is required", "TARGET_OBJECT_INVALID")
    if not isinstance(expected_parent_id, str) or not expected_parent_id:
        raise ParentReferenceError("expected parent id is required", "EXPECTED_PARENT_INVALID")

    target = _find_object(scene_model, target_object_id)
    if target is None:
        raise ParentReferenceError("target object must resolve exactly once", "TARGET_OBJECT_NOT_FOUND")
    if _has_cycle(scene_model, target_object_id):
        raise ParentReferenceError("cyclic hierarchy cannot be repaired by Wave-4", "CYCLE_DETECTED")
    actual_parent = _parent_id(target)
    if actual_parent != expected_parent_id:
        raise ParentReferenceError("target does not currently present the expected parent reference", "EXPECTED_PARENT_MISMATCH")
    if _find_object(scene_model, expected_parent_id) is not None:
        raise ParentReferenceError("expected parent identifier still resolves in the presented model", "PARENT_STILL_PRESENT")

    return _make_plan(
        target_object_id=target_object_id,
        expected_parent_id=expected_parent_id,
        source_report_digest=source_report_digest,
    )


def _extract(extractor: Callable[[], Tuple[Any, str]]) -> Tuple[Any, str]:
    result = extractor()
    if not isinstance(result, tuple) or len(result) != 2:
        raise ParentReferenceError("extractor must return (scene_model, report_digest)", "EXTRACTOR_INVALID")
    return result


@dataclass(frozen=True)
class _ExecutionOutcome:
    ok: bool
    outcome: str
    failure_code: Optional[str]
    source_report_digest: str
    output_report_digest: Optional[str]


def execute_repair_parent_reference(
    plan: Mapping[str, Any],
    authorization: Mapping[str, Any],
    *,
    extractor: Callable[[], Tuple[Any, str]],
    mutator: Callable[[str, None], None],
) -> _ExecutionOutcome:
    """Execute one narrowly-scoped detach after fresh source binding checks."""
    plan_id = plan.get("plan_id")
    source_digest = plan.get("source_report_digest")
    target_id = plan.get("target_object_id")
    params = plan.get("params")
    expected_parent_id = params.get("expected_parent_id") if isinstance(params, Mapping) else None

    if plan.get("correction_type") != PARENT_CORRECTION_TYPE:
        return _ExecutionOutcome(False, "PLAN_INVALID", "CORRECTION_TYPE_MISMATCH", str(source_digest), None)
    if not isinstance(params, Mapping) or set(params) != set(_PARENT_PARAMS):
        return _ExecutionOutcome(False, "PLAN_INVALID", "PARAMS_INVALID", str(source_digest), None)
    if params.get("detach_to") is not None:
        return _ExecutionOutcome(False, "PLAN_INVALID", "DETACH_TARGET_INVALID", str(source_digest), None)
    if not isinstance(source_digest, str):
        return _ExecutionOutcome(False, "PLAN_INVALID", "SOURCE_DIGEST_INVALID", "", None)

    auth = verify_parent_authorization(
        ParentPresentedWork(
            correction_id=str(plan.get("correction_id")),
            plan_id=str(plan_id),
            source_report_digest=source_digest,
            target_object_id=str(target_id),
            expected_parent_id=str(expected_parent_id),
        ),
        authorization,
    )
    if not auth.verified:
        return _ExecutionOutcome(False, "AUTHORIZATION_REFUSED", auth.failure_code, source_digest, None)

    scene_before, fresh_digest = _extract(extractor)
    if fresh_digest != source_digest:
        return _ExecutionOutcome(False, "PLAN_INVALID", "SOURCE_DIGEST_MISMATCH", fresh_digest, None)

    target = _find_object(scene_before, str(target_id))
    if target is None:
        return _ExecutionOutcome(False, "PLAN_INVALID", "TARGET_OBJECT_NOT_FOUND", fresh_digest, None)
    if _parent_id(target) != expected_parent_id:
        return _ExecutionOutcome(False, "PLAN_INVALID", "EXPECTED_PARENT_MISMATCH", fresh_digest, None)
    if _find_object(scene_before, expected_parent_id) is not None:
        return _ExecutionOutcome(False, "PLAN_INVALID", "PARENT_STILL_PRESENT", fresh_digest, None)

    before_non_parent = _non_parent_projection(target)
    before_identity = _scene_identity_snapshot(scene_before)
    before_unrelated = _scene_unrelated_snapshot(scene_before, str(target_id))

    mutator(str(target_id), None)

    scene_after, output_digest = _extract(extractor)
    target_after = _find_object(scene_after, str(target_id))
    if target_after is None:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_OBJECT_MISSING", fresh_digest, output_digest)
    if _parent_id(target_after) is not None:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "PARENT_NOT_DETACHED", fresh_digest, output_digest)
    if _non_parent_projection(target_after) != before_non_parent:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "TARGET_NON_PARENT_CHANGED", fresh_digest, output_digest)
    if _scene_identity_snapshot(scene_after) != before_identity:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "OBJECT_IDENTITY_CHANGED", fresh_digest, output_digest)
    if _scene_unrelated_snapshot(scene_after, str(target_id)) != before_unrelated:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "UNRELATED_OBJECT_CHANGED", fresh_digest, output_digest)
    if _find_object(scene_after, expected_parent_id) is not None:
        return _ExecutionOutcome(False, "POSTCONDITION_FAILED", "PARENT_REAPPEARED", fresh_digest, output_digest)

    return _ExecutionOutcome(True, "CORRECTION_APPLIED", None, fresh_digest, output_digest)
