"""Controlled Correction Executor — WAVE 1 (mutation authority).

This is the FIRST real mutation-authority boundary for the Atlas Blender track. It is deliberately
narrow and fail-closed. It implements EXACTLY TWO mutation operations, each removing exactly ONE face
from exactly ONE mesh:

    REMOVE_DUPLICATE_FACE      (cleared as the first mutation authority)
    REMOVE_DEGENERATE_FACE     (Wave-1 Implementation B)

Both operations share ONE canonical execution pipeline (`_execute_face_removal`) so the
source-binding / plan-integrity / snapshot / mutation / postcondition gates have a single
implementation — never two divergent copies.

WAVE 2 adds a THIRD, separate mutation operation on its own dedicated entry point:

    REPAIR_FACE_WINDING        (human-authorized, topology-only, exactly ONE face reversal)

NO other correction type may mutate here: RENAME_OBJECT, and all review/unsafe/out-of-scope types
are REJECTED. `REPAIR_FACE_WINDING` is NEVER auto-executed: its dedicated entry point requires an
explicit authorization artifact and refuses to touch the engine without one (design §1.4/§1.6). It
does NOT go through `_execute_face_removal` (a reversal is not a removal) and the two Wave-1
operations are unchanged.

Authority invariants (from BLENDER_CONTROLLED_CORRECTION_EXECUTOR_DESIGN.md, WAVE 1):
- The executor is proposal + budget bounded: it deletes EXACTLY ONE face on EXACTLY ONE mesh and
  changes NOTHING else (no vertices, no other face/mesh/object, no rename, no hierarchy/transform/
  unit/collection change, no save, no rollback).
- All verification evidence comes from an authoritative `SceneModel` + `SceneReport` produced by ONE
  independent extraction pass (`extract_and_report`). The executor NEVER mutates Blender directly;
  the ONLY mutation surface is an injected, bounded `mutator` callable (stubbed in deterministic
  tests, backed by a real narrowly-scoped Blender operation in a future live adapter). This module
  does NOT import bpy.
- The executor is fail-closed: a stale/forged source, plan mismatch, precondition failure, mutation
  failure, or postcondition failure yields an explicit non-success outcome token; it never reports
  COMPLETED unless every gate is independently verified.

Deterministic contract (this module is pure Python; the only engine-sensitive seam is the injected
`mutator`, which is stubbed in tests and never faked as a live Blender pass).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from planning.blender.correction_authorization import (
    MERGE_CASE_EXACT,
    MERGE_CORRECTION_TYPE,
    SELECTION_MODE_D1,
    SELECTION_MODE_D2,
    AuthorizationArtifact,
    AuthorizationContractError,
    AuthorizationError,
    AuthorizationInputError,
    AuthorizationOutcome,
    MergePresentedWork,
    PresentedWork,
    canonical_coincidence_key,
    canonical_survivor_indices,
    make_index_mapping,
    mapping_digest,
    parse_authorization,
    require_supported_case,
    resolve_designated_face_index,
    validate_duplicate_groups,
    validate_index_mapping,
    validate_recorded_edges,
    validate_survivor_indices,
    verify_authorization,
    verify_merge_authorization,
    verify_recorded_set_agreement,
)
from planning.blender.correction_values import CorrectionPlannerError
# The merge parameter schema constant is defined ONCE, in the planner (Slice 2), and is imported
# here rather than duplicated: `MERGE_PARAMETER_KEYS` is the contract that the WAVE-3 proposal's
# parameters are exactly this ordered key set (design §10 / handoff §4 C). A second copy in the
# executor could drift from the planner's schema, and the executor's job is to REJECT a body that
# does not match the contract — so it must read the contract, not restate it. There is no import
# cycle: `correction_planner` does not import `correction_executor` (verified), and this module
# imports no `bpy`.
from planning.blender.correction_planner import MERGE_PARAMETER_KEYS
from planning.blender.mesh_health import check_mesh
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel

# Execution outcome tokens (language-neutral; see design §8).
EXECUTOR_VERSION = "1"
EXECUTION_POLICY_VERSION = "1"


class ExecutionOutcome:
    NOT_STARTED = "NOT_STARTED"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    PLAN_INVALID = "PLAN_INVALID"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    UNSAFE = "UNSAFE"
    MUTATION_FAILED = "MUTATION_FAILED"
    POSTCONDITION_FAILED = "POSTCONDITION_FAILED"
    COMPLETED = "COMPLETED"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    # WAVE 2 (design §1.3): the authorization gate's own deterministic outcome tokens.
    AUTHORIZATION_INVALID = "AUTHORIZATION_INVALID"
    AUTHORIZATION_SCOPE_MISMATCH = "AUTHORIZATION_SCOPE_MISMATCH"


# EXECUTOR POLICY: the ONLY executable correction types.
# WAVE 1: REMOVE_DUPLICATE_FACE, REMOVE_DEGENERATE_FACE (unchanged).
# WAVE 2: REPAIR_FACE_WINDING — added to the allowlist, but reachable ONLY through its dedicated
# entry point, and only with a verified authorization artifact (a type in this allowlist is NEVER
# sufficient authority: design §1.4). The two removal operations are unaffected because
# `_execute_face_removal` first selects corrections of ITS OWN operation type, so a winding
# correction can never reach a removal pipeline.
# WAVE 3: REPAIR_MERGE_VERTEX — added on the same terms (design §6 MP-10 / §8): reachable ONLY
# through `execute_merge_vertex`, which is mandatory-by-construction for an authorization artifact.
# The Wave-1 removal pipeline and the Wave-2 winding pipeline are unaffected for the same reason:
# each selects corrections of its own operation type before the allowlist check is reached.
_EXECUTABLE_TYPES = frozenset(
    {
        "REMOVE_DUPLICATE_FACE",
        "REMOVE_DEGENERATE_FACE",
        "REPAIR_FACE_WINDING",
        "REPAIR_MERGE_VERTEX",
    }
)

_WINDING_OPERATION = "REPAIR_FACE_WINDING"
_WINDING_ORIENTATION_TOKEN = "reverse_designated_face_to_shared_edge_opposite"
_WINDING_ALLOWED_PARAM_KEYS = frozenset({
    "mesh_id", "designated_face_index", "candidate_faces",
    "recorded_edges", "counterpart_faces", "orientation",
})
_WINDING_FINDING_CODE = "MESH_WINDING_INCONSISTENT"


class ExecutorError(CorrectionPlannerError):
    """Declared executor failure (all executor failures are this type or a subclass)."""


class SourceMismatchError(ExecutorError):
    """Source report/plan binding failed (forged/stale/mismatched source)."""


class PlanInvalidError(ExecutorError):
    """Plan/correction is not executable or malformed under the executor policy."""


class PreconditionError(ExecutorError):
    """A precondition predicate evaluated false against the current source state."""


class PostconditionError(ExecutorError):
    """The post-mutation state does not satisfy the required postconditions."""


def extract_and_report(engine_state) -> Tuple[SceneModel, Any]:
    """One-pass authoritative extraction: (SceneModel, SceneReport) from the SAME state.

    This is the Wave-1 specification pin #5. The concrete implementation is engine-sensitive and
    provided by the caller / a future bounded live adapter. This default raises so an executor metric
    without an engine cannot silently fabricate a report.
    """
    raise ExecutorError(
        "extract_and_report requires an engine-backed implementation; "
        "never defaults to a synthetic (SceneModel, SceneReport) pair"
    )


# ---------------------------------------------------------------------------
# Kernel predicate reproduction (pin #4 — reproduce EXACTLY, never a new predicate)
# ---------------------------------------------------------------------------

def _signed_area(face: Sequence[int], vertices: Sequence[Sequence[float]]) -> float:
    """Mirror of mesh_health._signed_area — the kernel's exact signed-area (shoelace on dominant
    axis). We reproduce it EXACTLY so the duplicate/degeneracy key matches the kernel."""
    n = len(face)
    if n < 3:
        return 0.0
    if any(not (0 <= idx < len(vertices)) for idx in face):
        return 0.0
    p0, p1, p2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
    c = (
        (p1[1] - p0[1]) * (p2[2] - p0[2]) - (p1[2] - p0[2]) * (p2[1] - p0[1]),
        (p1[2] - p0[2]) * (p2[0] - p0[0]) - (p1[0] - p0[0]) * (p2[2] - p0[2]),
        (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]),
    )
    axis = max(range(3), key=lambda i: abs(c[i]))
    area2 = 0.0
    for i in range(n):
        px = vertices[face[i]]
        py = vertices[face[(i + 1) % n]]
        if axis == 0:
            area2 += px[1] * py[2] - py[1] * px[2]
        elif axis == 1:
            area2 += px[2] * py[0] - py[2] * px[0]
        else:
            area2 += px[0] * py[1] - py[0] * px[1]
    return area2 * 0.5


def _duplicate_key(face: Tuple[int, ...], vertices: Sequence[Sequence[float]]) -> Tuple[Tuple[int, ...], bool]:
    """EXACT kernel duplicate identity: (sorted face tuple, signed_area >= 0.0)."""
    return (tuple(sorted(face)), _signed_area(face, vertices) >= 0.0)


# Kernel edge/area tolerance for degeneracy — must match mesh_health._EDGE_TOLERANCE.
_EDGE_TOLERANCE = 1e-4


def _is_degenerate_face(face: Sequence[int], vertices: Sequence[Sequence[float]]) -> bool:
    """EXACT kernel degeneracy predicate (mesh_health._collect_degenerate_faces).

    A face is DEGENERATE iff it has fewer than 3 vertices (`len(face) < 3`) OR its signed area is
    within the kernel's edge tolerance of zero (`abs(_signed_area(...)) <= _EDGE_TOLERANCE`).
    This reproduces the kernel's classification EXACTLY (no new definition of "degenerate").
    """
    if len(face) < 3:
        return True
    return abs(_signed_area(face, vertices)) <= _EDGE_TOLERANCE


# ---------------------------------------------------------------------------
# Snapshot + multiset helpers
# ---------------------------------------------------------------------------

def _object_state_key(obj: ObjectModel) -> Tuple[Any, ...]:
    return (
        obj.object_id,
        obj.name,
        obj.collection,
        obj.parent_object_id,
        tuple(obj.location),
        tuple(obj.scale),
        tuple(obj.rotation),
        obj.visible,
    )


def _mesh_state_key(mesh: Optional[MeshModel]) -> Optional[Tuple[Any, ...]]:
    if mesh is None:
        return None
    return (mesh.mesh_id, tuple(mesh.vertices), tuple(mesh.faces))


def _ordered_object_ids(scene: SceneModel) -> Tuple[str, ...]:
    return tuple(o.object_id for o in scene.objects)


def _build_snapshot(
    source_scene: SceneModel,
    target_obj: ObjectModel,
    resolved_object_id: str,
    mesh_id: str,
    source_report_digest: str,
) -> Dict[str, Any]:
    """Immutable pre-mutation snapshot (pin #3: includes object order + unrelated state)."""
    return {
        "scene_id": source_scene.scene_id,
        "unit_system": source_scene.unit_system,
        "ordered_object_ids": _ordered_object_ids(source_scene),
        "target_object_state": _object_state_key(target_obj),
        "target": {
            "object_id": resolved_object_id,
            "mesh_id": mesh_id,
            "ordered_vertex_table": tuple(target_obj.mesh.vertices),
            "ordered_face_tuples": tuple(target_obj.mesh.faces),
        },
        "unrelated": {
            o.object_id: (
                _object_state_key(o),
                _mesh_state_key(o.mesh),
            )
            for o in source_scene.objects if o.object_id != resolved_object_id
        },
        "source_report_digest": source_report_digest,
    }


# ---------------------------------------------------------------------------
# Precondition / postcondition evaluation (shared, Wave-1)
# ---------------------------------------------------------------------------

def _assert_target_mesh(scene: SceneModel, object_id: Optional[str], mesh_id: Optional[str]) -> Tuple[ObjectModel, MeshModel]:
    """Resolve (object, mesh) for the target, fail-closed.

    - If `object_id` is provided and non-empty, use it (the object must exist and own `mesh_id`).
    - If `object_id` is None/empty (mesh-scoped finding), resolve the (unique) object owning
      `mesh_id`; 0 or >1 owners FAIL CLOSED (never guess a target object).
    """
    if type(mesh_id) is not str or not mesh_id:
        raise PreconditionError("target mesh_id must be a non-empty string")
    if object_id is not None and object_id != "":
        if type(object_id) is not str:
            raise PreconditionError("target object_id must be a str or None")
        obj = next((o for o in scene.objects if o.object_id == object_id), None)
        if obj is None:
            raise PreconditionError(f"target object {object_id!r} does not exist")
        if obj.mesh is None:
            raise PreconditionError(f"target object {object_id!r} has no mesh")
        if obj.mesh.mesh_id != mesh_id:
            raise PreconditionError(
                f"target object {object_id!r} mesh is {obj.mesh.mesh_id!r}, not {mesh_id!r}"
            )
        return obj, obj.mesh
    owners = [o for o in scene.objects if o.mesh is not None and o.mesh.mesh_id == mesh_id]
    if len(owners) != 1:
        raise PreconditionError(
            f"mesh {mesh_id!r} is owned by {len(owners)} object(s); "
            "EXACTLY ONE owner required to bind the target (fail closed)"
        )
    return owners[0], owners[0].mesh


def _recorded_duplicate_tuple(mesh: MeshModel, face_ids: Sequence[int]) -> Tuple[int, ...]:
    """The recorded duplicate content: the face tuple at the recorded face_id, verified consistent."""
    if not isinstance(face_ids, (tuple, list)):
        raise PreconditionError("parameters['face_ids'] must be a sequence of ints")
    if len(face_ids) != 2:
        raise PreconditionError("REMOVE_DUPLICATE_FACE requires exactly two face_ids")
    try:
        ids = tuple(int(f) for f in face_ids)
    except (TypeError, ValueError):
        raise PreconditionError("face_ids must be integers")
    n = len(mesh.faces)
    for fid in ids:
        if not (0 <= fid < n):
            raise PreconditionError(f"face index {fid} out of range for mesh of {n} faces")
    f0, f1 = mesh.faces[ids[0]], mesh.faces[ids[1]]
    k0 = _duplicate_key(f0, mesh.vertices)
    k1 = _duplicate_key(f1, mesh.vertices)
    if k0 != k1:
        raise PreconditionError(
            f"recorded face pair ({ids[0]},{ids[1]}) is not an exact duplicate under the kernel key"
        )
    return tuple(f0)


def _verify_duplicate_preconditions(
    source_scene: SceneModel,
    *,
    object_id: Optional[str],
    mesh_id: Optional[str],
    face_ids: Sequence[int],
) -> Tuple[ObjectModel, MeshModel, Tuple[int, ...]]:
    """Evaluate REMOVE_DUPLICATE_FACE preconditions on the authoritative source SceneModel."""
    resolved_obj, mesh = _assert_target_mesh(source_scene, object_id, mesh_id)
    dup_tuple = _recorded_duplicate_tuple(mesh, face_ids)
    key = _duplicate_key(dup_tuple, mesh.vertices)
    count = sum(1 for f in mesh.faces if _duplicate_key(f, mesh.vertices) == key)
    if count < 2:
        raise PreconditionError(
            f"recorded duplicate condition no longer holds (only {count} face(s) with key)"
        )
    return resolved_obj, mesh, dup_tuple


def _recorded_degenerate_tuple(mesh: MeshModel, face_id: int) -> Tuple[int, ...]:
    """The recorded degenerate-face content: the EXACT face tuple at the recorded `face_id`.

    Verifies (fail-closed, never substitutes another degenerate face):
      - `face_id` is an exact int in range;
      - the face at that index still satisfies the kernel degeneracy predicate.
    Returns the exact ordered face tuple (the canonical degenerate target content).
    """
    if type(face_id) is not int:
        raise PreconditionError("parameters['face_id'] must be an integer")
    n = len(mesh.faces)
    if not (0 <= face_id < n):
        raise PreconditionError(f"face index {face_id} out of range for mesh of {n} faces")
    face = mesh.faces[face_id]
    if not _is_degenerate_face(tuple(face), mesh.vertices):
        raise PreconditionError(
            f"recorded face {face_id} is no longer degenerate under the kernel predicate; "
            "the exact planned target is absent/changed (never substitute another degenerate face)"
        )
    return tuple(face)


def _verify_degenerate_preconditions(
    source_scene: SceneModel,
    *,
    object_id: Optional[str],
    mesh_id: Optional[str],
    face_id: int,
) -> Tuple[ObjectModel, MeshModel, Tuple[int, ...]]:
    """Evaluate REMOVE_DEGENERATE_FACE preconditions on the authoritative source SceneModel."""
    resolved_obj, mesh = _assert_target_mesh(source_scene, object_id, mesh_id)
    target_face = _recorded_degenerate_tuple(mesh, face_id)
    return resolved_obj, mesh, target_face


def _verify_postconditions(
    fresh_scene: SceneModel,
    snapshot: Dict[str, Any],
    *,
    object_id: Optional[str],
    mesh_id: Optional[str],
    removed_face_tuple: Tuple[int, ...],
    source_report_digest: str,
) -> None:
    """Verify the post-mutation state against the immutable pre-mutation snapshot (Wave 1).

    Enforces the EXACT one-face multiset delta (never a count-only or finding-cleared-only success).
    Raises PostconditionError on any failure (never fabricates evidence).
    """
    if fresh_scene.scene_id != snapshot.get("scene_id"):
        raise PostconditionError("fresh scene_id does not match snapshot")
    if fresh_scene.unit_system != snapshot.get("unit_system"):
        raise PostconditionError("scene unit_system changed after mutation")
    if _ordered_object_ids(fresh_scene) != tuple(snapshot.get("ordered_object_ids", ())):
        raise PostconditionError("object ordering or identity set changed after mutation")
    _t_obj, t_mesh = _assert_target_mesh(fresh_scene, object_id, mesh_id)
    if tuple(t_mesh.vertices) != tuple(snapshot["target"]["ordered_vertex_table"]):
        raise PostconditionError("target mesh vertex table changed after mutation")
    if t_mesh.mesh_id != mesh_id:
        raise PostconditionError("target mesh identity changed after mutation")
    pre = snapshot["target"]["ordered_face_tuples"]
    post = tuple(t_mesh.faces)
    if Counter(post) != Counter(pre) - Counter([removed_face_tuple]):
        raise PostconditionError(
            "face multiset changed by more than exactly one recorded face (or the wrong face)"
        )
    for obj in fresh_scene.objects:
        if obj.object_id == object_id:
            continue
        expected = snapshot["unrelated"].get(obj.object_id)
        if expected is None:
            raise PostconditionError(f"unexpected object {obj.object_id!r} appeared")
        exp_state, exp_mesh = expected
        if _object_state_key(obj) != tuple(exp_state):
            raise PostconditionError(f"unrelated object {obj.object_id!r} state changed")
        if _mesh_state_key(obj.mesh) != exp_mesh:
            raise PostconditionError(f"unrelated object {obj.object_id!r} topology/metadata changed")
    t_obj = next((o for o in fresh_scene.objects if o.object_id == object_id), None)
    if t_obj is None:
        raise PostconditionError(f"target object {object_id!r} disappeared")
    if _object_state_key(t_obj) != tuple(snapshot.get("target_object_state", ())):
        raise PostconditionError("target object name/pose changed after mutation")


def _no_new_invalid_index(source_report, fresh_report) -> bool:
    """No new MESH_INVALID_INDEX finding appears post-mutation."""
    pre_codes = {f.code.value for f in source_report.findings}
    fresh_codes = {f.code.value for f in fresh_report.findings}
    return "MESH_INVALID_INDEX" not in (fresh_codes - pre_codes)


# ---------------------------------------------------------------------------
# Bounded mutation seam (the ONLY place a Blender write CAN be attached)
# ---------------------------------------------------------------------------

def _default_mutator(*, operation: str) -> Callable[..., None]:
    """Return the raise-on-use default mutator for an operation (never default a real mutation)."""
    def _noop(engine_state, **kwargs) -> None:
        raise ExecutorError(
            f"no mutator provided; a bounded {operation} mutator must be injected "
            "explicitly (never defaulted); got kwargs: " + ", ".join(sorted(kwargs.keys()))
        )
    return _noop


# ---------------------------------------------------------------------------
# Shared face-removal execution pipeline (the single canonical authority path)
# ---------------------------------------------------------------------------

def _execute_face_removal(
    *,
    engine_state: Any,
    plan: Any,
    mutator: Optional[Callable[..., None]],
    extractor: Callable[[Any], Tuple[SceneModel, Any]],
    operation: str,
    validate_params: Callable[[Dict[str, Any]], Optional[str]],
    verify_preconditions: Callable[..., Tuple[ObjectModel, MeshModel, Tuple[int, ...]]],
    precond_kwargs_from: Callable[[Dict[str, Any]], Dict[str, Any]],
    mutator_kwargs: Callable[[str, str, Dict[str, Any], Tuple[int, ...]], Dict[str, Any]],
    target_predicate_clear: Optional[Callable[[MeshModel], bool]],
) -> Dict[str, Any]:
    """Run the full fail-closed execution pipeline for a single-face-removal operation.

    `operation` MUST be in the executor allowlist (`_EXECUTABLE_TYPES`); every gate (plan integrity,
    allowlist, parameter allowlist, source binding, preconditions, mutation, postcondition,
    no-new-invalid-index) is enforced here, identically for both WAVE-1 operations.
    """
    result = {
        "receipt_version": "1",
        "result": ExecutionOutcome.NOT_STARTED,
        "source_report_digest": getattr(plan, "source_report_digest", None),
        "source_report_digest_recomputed": None,
        "plan_id": getattr(plan, "plan_id", None),
        "plan_id_recomputed": None,
        "executor_version": EXECUTOR_VERSION,
        "execution_policy_version": EXECUTION_POLICY_VERSION,
        "executed_correction_ids": [],
        "skipped_correction_ids": [],
        "failure_code": None,
        "precondition_results": [],
        "postcondition_results": [],
        "output_report_digest": None,
        "normal_agreement_not_verified": False,
        "persisted": False,
        "rollback_performed": False,
    }
    try:
        # ---- 0. Plan integrity (recompute) ----
        if plan is None or not hasattr(plan, "source_report_digest") or not hasattr(plan, "plan_id"):
            result["result"] = ExecutionOutcome.PLAN_INVALID
            result["failure_code"] = "PLAN_INVALID"
            return result
        try:
            recomputed_plan_id = plan._compute_plan_id()
        except Exception:
            recomputed_plan_id = None
        if recomputed_plan_id is None or recomputed_plan_id != plan.plan_id:
            result["result"] = ExecutionOutcome.PLAN_INVALID
            result["failure_code"] = "PLAN_ID_MISMATCH"
            return result
        result["plan_id_recomputed"] = recomputed_plan_id

        # ---- Gate: select EXACTLY ONE executable correction of THIS operation; skip the rest ----
        corrections = getattr(plan, "corrections", ())
        executable = [c for c in corrections if c.correction_type == operation]
        skipped = [c.correction_id for c in corrections if c.correction_type != operation]
        result["skipped_correction_ids"] = skipped
        if not executable:
            result["result"] = ExecutionOutcome.PLAN_INVALID
            result["failure_code"] = "NO_EXECUTABLE_CORRECTION"
            return result
        if len(executable) > 1:
            result["result"] = ExecutionOutcome.PLAN_INVALID
            result["failure_code"] = "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS"
            return result
        corr = executable[0]
        # authority: the operation must be in the global executor allowlist (defense-in-depth)
        if corr.correction_type not in _EXECUTABLE_TYPES:
            result["result"] = ExecutionOutcome.UNSAFE
            result["failure_code"] = "NOT_EXECUTABLE_TYPE"
            return result
        if corr.requires_human_review or corr.determinism != "DETERMINISTIC":
            result["result"] = ExecutionOutcome.AUTHORIZATION_REQUIRED
            result["failure_code"] = "REVIEW_REQUIRED_NOT_AUTO"
            return result
        params = dict(corr.parameters)
        # parameters are allowlisted: only expected keys are accepted; anything else fails.
        failure = validate_params(params)
        if failure is not None:
            result["result"] = ExecutionOutcome.PLAN_INVALID
            result["failure_code"] = failure
            return result
        object_id = corr.object_id
        mesh_id = corr.mesh_id

        # ---- 1. Source binding (recompute) ----
        try:
            source_scene, source_report = extractor(engine_state)
            recomputed_digest = source_report.digest()
        except Exception as exc:
            result["result"] = ExecutionOutcome.SOURCE_MISMATCH
            result["failure_code"] = "EXTRACTION_FAILED"
            return result
        result["source_report_digest_recomputed"] = recomputed_digest
        if recomputed_digest != plan.source_report_digest:
            result["result"] = ExecutionOutcome.SOURCE_MISMATCH
            result["failure_code"] = "SOURCE_DIGEST_MISMATCH"
            return result

        # ---- 2. Preconditions (policy-derived) ----
        try:
            target_obj, target_mesh, removed_face_tuple = verify_preconditions(
                source_scene,
                object_id=object_id,
                mesh_id=mesh_id,
                **precond_kwargs_from(params),
            )
        except PreconditionError as exc:
            result["result"] = ExecutionOutcome.PRECONDITION_FAILED
            result["failure_code"] = "PRECONDITION_FAILED"
            result["precondition_results"].append({"ok": False, "reason": str(exc)})
            return result
        resolved_object_id = target_obj.object_id
        result["precondition_results"].append({"ok": True, "target": [resolved_object_id, mesh_id]})

        # ---- immutable pre-mutation snapshot (pin #3: includes object order) ----
        snapshot = _build_snapshot(
            source_scene, target_obj, resolved_object_id, mesh_id, plan.source_report_digest
        )

        # ---- 3. Bounded mutation (injected; stubbed in tests) ----
        _mutator = mutator if mutator is not None else _default_mutator(operation=operation)
        try:
            _mutator(
                engine_state,
                **mutator_kwargs(resolved_object_id, mesh_id, params, removed_face_tuple),
            )
        except Exception as exc:
            result["result"] = ExecutionOutcome.MUTATION_FAILED
            result["failure_code"] = "MUTATION_FAILED"
            return result

        # ---- 4. Fresh extraction (single-pass) + postcondition ----
        try:
            fresh_scene, fresh_report = extractor(engine_state)
        except Exception:
            result["result"] = ExecutionOutcome.MUTATION_FAILED
            result["failure_code"] = "POST_EXTRACTION_FAILED"
            return result
        result["output_report_digest"] = fresh_report.digest()
        try:
            _verify_postconditions(
                fresh_scene,
                snapshot,
                object_id=resolved_object_id,
                mesh_id=mesh_id,
                removed_face_tuple=removed_face_tuple,
                source_report_digest=plan.source_report_digest,
            )
        except PostconditionError as exc:
            result["result"] = ExecutionOutcome.POSTCONDITION_FAILED
            result["failure_code"] = "POSTCONDITION_FAILED"
            result["postcondition_results"].append({"ok": False, "reason": str(exc)})
            return result

        # ---- 4b. operation-specific target-condition-clear check ----
        if target_predicate_clear is not None:
            _tobj, tmesh_for_pred = _assert_target_mesh(fresh_scene, resolved_object_id, mesh_id)
            if not target_predicate_clear(tmesh_for_pred):
                result["result"] = ExecutionOutcome.POSTCONDITION_FAILED
                result["failure_code"] = "TARGET_CONDITION_NOT_CLEAR"
                result["postcondition_results"].append(
                    {"ok": False, "reason": "recorded target condition persists post-mutation"}
                )
                return result

        # ---- 5. No-new-invalid-index (from fresh report findings) ----
        if not _no_new_invalid_index(source_report, fresh_report):
            result["result"] = ExecutionOutcome.POSTCONDITION_FAILED
            result["failure_code"] = "NEW_INVALID_INDEX"
            return result

        result["result"] = ExecutionOutcome.COMPLETED
        result["executed_correction_ids"] = [corr.correction_id]
        return result
    except Exception as exc:  # noqa: BLE001 - fail closed on any unexpected error
        result["result"] = ExecutionOutcome.MUTATION_FAILED
        result["failure_code"] = "INTERNAL_ERROR"
        return result


# ---------------------------------------------------------------------------
# REMOVE_DUPLICATE_FACE (cleared first mutation authority)
# ---------------------------------------------------------------------------

_DUPLICATE_ALLOWED_PARAM_KEYS = frozenset({"mesh_id", "face_ids", "duplicate_relationship"})


def _validate_duplicate_params(params: Dict[str, Any]) -> Optional[str]:
    extra = set(params.keys()) - _DUPLICATE_ALLOWED_PARAM_KEYS
    if extra:
        return "UNEXPECTED_PARAMETER:" + ",".join(sorted(extra))
    if params.get("duplicate_relationship") not in (None, "exact_duplicate"):
        return "INVALID_DUPLICATE_RELATIONSHIP"
    return None


def _duplicate_precond_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    return {"face_ids": params.get("face_ids")}


def _duplicate_mutator_kwargs(
    resolved_object_id: str, mesh_id: str, params: Dict[str, Any], dup_tuple: Tuple[int, ...]
) -> Dict[str, Any]:
    return {
        "object_id": resolved_object_id,
        "mesh_id": mesh_id,
        "face_ids": params.get("face_ids"),
        "dup_tuple": dup_tuple,
    }


def execute_remove_duplicate_face(
    *,
    engine_state: Any,
    plan: Any,
    mutator: Optional[Callable[..., None]] = None,
    extractor: Callable[[Any], Tuple[SceneModel, Any]] = extract_and_report,
) -> Dict[str, Any]:
    """Execute a REMOVE_DUPLICATE_FACE plan (Wave-1 authority), fail-closed, deterministic.

    Deletes EXACTLY ONE face whose content == the recorded duplicate tuple from the target mesh,
    changing NOTHING else. The mutation boundary (`mutator`) is injected and stubbed in tests; the
    postcondition verifies the exact multiset delta + unchanged unrelated state.

    NOTE: the cleared REMOVE_DUPLICATE_FACE behavior is preserved EXACTLY (no extra postcondition was
    added on top of the approved one), so `target_predicate_clear` is None for this operation.
    """
    return _execute_face_removal(
        engine_state=engine_state,
        plan=plan,
        mutator=mutator,
        extractor=extractor,
        operation="REMOVE_DUPLICATE_FACE",
        validate_params=_validate_duplicate_params,
        verify_preconditions=_verify_duplicate_preconditions,
        precond_kwargs_from=_duplicate_precond_kwargs,
        mutator_kwargs=_duplicate_mutator_kwargs,
        target_predicate_clear=None,
    )


# ---------------------------------------------------------------------------
# REMOVE_DEGENERATE_FACE (Wave-1 Implementation B)
# ---------------------------------------------------------------------------

_DEGENERATE_ALLOWED_PARAM_KEYS = frozenset({"mesh_id", "face_id", "reason"})


def _validate_degenerate_params(params: Dict[str, Any]) -> Optional[str]:
    extra = set(params.keys()) - _DEGENERATE_ALLOWED_PARAM_KEYS
    if extra:
        return "UNEXPECTED_PARAMETER:" + ",".join(sorted(extra))
    if params.get("reason") not in (None, "degenerate_face"):
        return "INVALID_DEGENERATE_REASON"
    return None


def _degenerate_precond_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    return {"face_id": params.get("face_id")}


def _degenerate_mutator_kwargs(
    resolved_object_id: str, mesh_id: str, params: Dict[str, Any], face_tuple: Tuple[int, ...]
) -> Dict[str, Any]:
    return {
        "object_id": resolved_object_id,
        "mesh_id": mesh_id,
        "face_id": params.get("face_id"),
        "face_tuple": face_tuple,
    }


def execute_remove_degenerate_face(
    *,
    engine_state: Any,
    plan: Any,
    mutator: Optional[Callable[..., None]] = None,
    extractor: Callable[[Any], Tuple[SceneModel, Any]] = extract_and_report,
) -> Dict[str, Any]:
    """Execute a REMOVE_DEGENERATE_FACE plan (Wave-1 authority), fail-closed, deterministic.

    Deletes EXACTLY ONE face — the exact recorded degenerate face at `parameters['face_id']` whose
    content still satisfies the kernel degeneracy predicate — from the target mesh, changing NOTHING
    else. The exact planned face is never substituted by a different degenerate face; if the target
    is absent/changed this fails closed with PRECONDITION_FAILED.

    The postcondition is the EXACT SceneModel multiset delta (exactly one planned face removed,
    removed face content matches, vertex table unchanged, all remaining face tuples unchanged,
    unrelated state unchanged, no new invalid-index). The entire mesh is NOT required to become
    degeneracy-free: an unrelated degenerate face that the plan did not target may remain, and is
    not this correction's concern (consistent with REMOVE_DUPLICATE_FACE, which has no global
    clear-check).
    """
    return _execute_face_removal(
        engine_state=engine_state,
        plan=plan,
        mutator=mutator,
        extractor=extractor,
        operation="REMOVE_DEGENERATE_FACE",
        validate_params=_validate_degenerate_params,
        verify_preconditions=_verify_degenerate_preconditions,
        precond_kwargs_from=_degenerate_precond_kwargs,
        mutator_kwargs=_degenerate_mutator_kwargs,
        target_predicate_clear=None,
    )


# ===========================================================================
# WAVE 2 — REPAIR_FACE_WINDING: human-authorized, topology-only, ONE-face reversal
# ===========================================================================
#
# Design: planning/blender/BLENDER_WAVE2_AUTHORIZATION_AND_WINDING_DESIGN.md (§1.4 gate order, §3.1
# execution-time re-derivation, §4 the exact operation, §6 preconditions, §7 postconditions, §8
# receipt).
#
# Gate order implemented below (no engine contact before the authorization gate):
#   0a plan integrity (plan_id recompute)              -> PLAN_INVALID / PLAN_ID_MISMATCH
#   0b exactly-one winding correction + allowlist      -> PLAN_INVALID / NO_EXECUTABLE_CORRECTION /
#                                                         AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS
#   0c winding parameter allowlist (closed key set)    -> PLAN_INVALID / UNEXPECTED_PARAMETER:...
#   0d AUTHORIZATION GATE (contract only)              -> AUTHORIZATION_REQUIRED / _INVALID /
#                                                         _SCOPE_MISMATCH
#   1  source binding (fresh extraction digest)        -> SOURCE_MISMATCH
#   2  preconditions (WC-P6..P17 on fresh evidence)    -> PRECONDITION_FAILED
#   3  exactly ONE bounded mutation (injected mutator) -> MUTATION_FAILED
#   4  fresh extraction + WC-Q1..Q13                   -> POSTCONDITION_FAILED
#   5  receipt (audit output only)
#
# Invariants: at most ONE mutator invocation per execution; no retry; no fallback; no automatic
# selection of another target; no cascade repair. The receipt is audit data only — it is never read
# back as authority, and it never grants persistence or rollback authority.
#
# The normative live mutation primitive (design §4.4) is NOT implemented here and NOT performed by
# this module: this executor only invokes an INJECTED, bounded mutator. The primitive the future
# live adapter must implement is exactly:
#   1. read the authoritative vertex table (v.co per vertex);
#   2. build a new face table from the read faces, replacing ONLY the designated index's tuple with
#      reverse(pre_tuple); every other tuple carried through unchanged, in order;
#   3. rebuild the mesh tables IN PLACE on the SAME datablock
#      (mesh.clear_geometry(); mesh.from_pydata(vertices, [], faces); mesh.update());
#   4. no vertex edits, no other face edits, no other object touched, no rename/transform/save.
# It must be validated against real Blender 4.4.3 (design §4.4 criteria) before live use.
#
# SUPERSEDED (Wave 14 — planning/blender/BLENDER_WAVE14_CORRECTION_REPRESENTATION_FIDELITY_DESIGN.md §5):
# step 3 above previously read "rebuild the datablock via from_pydata(vertices, [], faces) and assign
# obj.data = new_mesh". That replacement pattern is NO LONGER the normative reference primitive: it can
# lose the target object's material slots (it truncates the object's slot table to the new datablock's
# table, so assigned, unassigned and OBJECT-linked slots alike are destroyed) and it leaves the
# superseded datablock orphaned. Same-datablock table rebuilding (Pattern B) is now the normative
# reference pattern for geometry-rebuilding corrections when represented material slots must be
# preserved. Datablock replacement remains canonically legal — MQ-5 records that the datablock may be
# replaced while identity may not change — it is merely demoted from the reference implementation.
# Documentation only: no executable behaviour in this module is altered by this annotation.


class WindingPredicateError(PreconditionError):
    """A WAVE-2 winding precondition (WC-P*) evaluated false against the fresh evidence."""

    def __init__(self, predicate_id: str, reason: str) -> None:
        super().__init__(f"{predicate_id}: {reason}")
        self.predicate_id = predicate_id
        self.reason = reason


class WindingPostconditionError(PostconditionError):
    """A WAVE-2 winding postcondition (WC-Q*) evaluated false against the fresh post-state."""

    def __init__(self, predicate_id: str, reason: str) -> None:
        super().__init__(f"{predicate_id}: {reason}")
        self.predicate_id = predicate_id
        self.reason = reason


def _reverse_face(face: Sequence[int]) -> Tuple[int, ...]:
    """EXACT plain element reversal (design §4.3): ``(f[n-1], ..., f[1], f[0])``.

    No rotation, no renormalization. Reversal maps every directed edge ``a->b`` of the cyclic
    traversal to ``b->a`` (including the wrap edge), which is exactly what flips same-direction into
    opposite-direction. It is an involution, so an accidental double application is detectable.
    """
    return tuple(face[i] for i in range(len(face) - 1, -1, -1))


def _freeze_key(value: Any) -> Any:
    """Deterministic, hashable, JSON-independent key for a canonical measured payload."""
    if type(value) is dict:
        return tuple(sorted((k, _freeze_key(v)) for k, v in value.items()))
    if type(value) in (list, tuple):
        return tuple(_freeze_key(v) for v in value)
    return value


def _directed_edge_in_face(face: Sequence[int], edge: Tuple[int, int], predicate_id: str) -> Optional[Tuple[int, int]]:
    """The single directed ``(a, b)`` traversal of the undirected ``edge`` inside ``face``.

    Returns ``None`` when the face does not traverse the edge. An edge traversed MORE THAN ONCE by
    one face is ambiguous -> fail closed (never guess which traversal was meant).
    """
    hits = []
    n = len(face)
    for i in range(n):
        a, b = face[i], face[(i + 1) % n]
        if (min(a, b), max(a, b)) == edge:
            hits.append((a, b))
    if len(hits) > 1:
        raise WindingPredicateError(
            predicate_id, f"face traverses edge {list(edge)} more than once (ambiguous traversal)"
        )
    return hits[0] if hits else None


def _edge_face_map(mesh: MeshModel) -> Dict[Tuple[int, int], list]:
    """Kernel-identical undirected edge -> ordered incident face indices (mesh_health enumeration)."""
    mapping: Dict[Tuple[int, int], list] = {}
    for fi, face in enumerate(mesh.faces):
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            mapping.setdefault((min(a, b), max(a, b)), []).append(fi)
    return mapping


def _winding_identities_for_mesh(report: Any, mesh_id: str, predicate_id: str) -> Tuple[Tuple[Tuple[int, int], Tuple[int, int]], ...]:
    """The fresh winding finding identities ``((edge_c, pair_c), ...)`` for ONE mesh (design §2.0).

    Reproduces the kernel's finding shape exactly (``measured = {"edge": [a,b], "faces": [f1,f2]}``)
    and fails closed on a malformed payload — the executor never repairs a report.
    """
    out: list = []
    for finding in getattr(report, "findings", ()) or ():
        code = getattr(finding, "code", None)
        if getattr(code, "value", None) != _WINDING_FINDING_CODE or finding.mesh_id != mesh_id:
            continue
        measured = finding.measured
        if type(measured) is not dict:
            raise WindingPredicateError(predicate_id, "a fresh winding finding carries no 'measured' payload")
        edge_raw = measured.get("edge")
        faces_raw = measured.get("faces")
        if (type(edge_raw) not in (list, tuple) or len(edge_raw) != 2
                or type(faces_raw) not in (list, tuple) or len(faces_raw) != 2):
            raise WindingPredicateError(predicate_id, "a fresh winding finding is malformed")
        values = (edge_raw[0], edge_raw[1], faces_raw[0], faces_raw[1])
        for value in values:
            if type(value) is not int or value < 0:
                raise WindingPredicateError(
                    predicate_id, "fresh winding finding indices must be non-negative exact ints"
                )
        a, b, f1, f2 = values
        if a == b or f1 == f2:
            raise WindingPredicateError(
                predicate_id, "fresh winding finding has a self-loop edge or two identical faces"
            )
        identity = ((min(a, b), max(a, b)), tuple(sorted((f1, f2))))
        if identity not in out:
            out.append(identity)
    return tuple(out)


def _measured_keys_for_mesh(report: Any, mesh_id: str, code_token: str) -> list:
    """Frozen ``measured`` payloads of a finding code for one mesh (multiset input for Q7/Q8)."""
    keys = []
    for finding in getattr(report, "findings", ()) or ():
        if getattr(getattr(finding, "code", None), "value", None) != code_token:
            continue
        if finding.mesh_id != mesh_id:
            continue
        keys.append(_freeze_key(finding.measured))
    return keys


def _same_direction_shared_edges(mesh: MeshModel, face_index: int, predicate_id: str) -> set:
    """Edges of ``face_index`` shared with EXACTLY one other face and traversed SAME-direction.

    This is the kernel's winding-inconsistency condition restricted to the designated face; the
    resulting set must equal the plan's recorded edge set (WC-P11: nothing missing, nothing extra).
    """
    edges: set = set()
    face = mesh.faces[face_index]
    n = len(face)
    seen_edges: Dict[Tuple[int, int], int] = {}
    for i in range(n):
        a, b = face[i], face[(i + 1) % n]
        edge = (min(a, b), max(a, b))
        seen_edges[edge] = seen_edges.get(edge, 0) + 1
    if any(count > 1 for count in seen_edges.values()):
        raise WindingPredicateError(
            predicate_id, "the designated face traverses an edge more than once (ambiguous)"
        )
    edge_map = _edge_face_map(mesh)
    for edge in seen_edges:
        incident = edge_map.get(edge, [])
        if len(incident) != 2:
            continue  # not exactly two faces -> not a winding relationship (non-manifold/boundary)
        if len(set(incident)) != 2:
            raise WindingPredicateError(
                predicate_id, f"edge {list(edge)} is traversed twice by the same face"
            )
        other = incident[0] if incident[1] == face_index else incident[1]
        if face_index not in incident:
            continue
        d_self = _directed_edge_in_face(face, edge, predicate_id)
        d_other = _directed_edge_in_face(mesh.faces[other], edge, predicate_id)
        if d_self == d_other:
            edges.add(edge)
    return edges


def _validate_winding_params(params: Dict[str, Any]) -> Optional[str]:
    """Closed-key-set / exact-value-shape allowlist for the winding operation (WC-P3)."""
    extra = set(params.keys()) - _WINDING_ALLOWED_PARAM_KEYS
    if extra:
        return "UNEXPECTED_PARAMETER:" + ",".join(sorted(extra))
    missing = _WINDING_ALLOWED_PARAM_KEYS - set(params.keys())
    if missing:
        return "MISSING_PARAMETER:" + ",".join(sorted(missing))
    if params.get("orientation") != _WINDING_ORIENTATION_TOKEN:
        return "INVALID_WINDING_ORIENTATION"
    mesh_id = params.get("mesh_id")
    if type(mesh_id) is not str or not mesh_id:
        return "INVALID_MESH_ID"
    designated = params.get("designated_face_index")
    candidates = params.get("candidate_faces")
    if designated is not None:
        if type(designated) is not int or designated < 0:
            return "INVALID_DESIGNATED_FACE_INDEX"
        if candidates is not None:
            return "DESIGNATION_AND_CANDIDATES_BOTH_PRESENT"
    else:
        if type(candidates) not in (list, tuple) or len(candidates) != 2:
            return "INVALID_CANDIDATE_FACES"
        if any(type(c) is not int or c < 0 for c in candidates):
            return "INVALID_CANDIDATE_FACES"
        if candidates[0] == candidates[1]:
            return "INVALID_CANDIDATE_FACES"
    edges = params.get("recorded_edges")
    counterparts = params.get("counterpart_faces")
    if type(edges) not in (list, tuple) or len(edges) == 0:
        return "INVALID_RECORDED_EDGES"
    if type(counterparts) not in (list, tuple) or len(counterparts) != len(edges):
        return "INVALID_COUNTERPART_FACES"
    for edge in edges:
        if type(edge) not in (list, tuple) or len(edge) != 2:
            return "INVALID_RECORDED_EDGES"
        if any(type(v) is not int or v < 0 for v in edge):
            return "INVALID_RECORDED_EDGES"
    for cp in counterparts:
        if type(cp) is not int or cp < 0:
            return "INVALID_COUNTERPART_FACES"
    return None


def _winding_receipt_skeleton(plan: Any) -> Dict[str, Any]:
    """The WAVE-2 audit receipt skeleton (design §8). Audit data only — never authority."""
    return {
        "receipt_version": "1",
        "result": ExecutionOutcome.NOT_STARTED,
        "failure_code": None,
        "executor_version": EXECUTOR_VERSION,
        "execution_policy_version": EXECUTION_POLICY_VERSION,
        "authorization_verified": False,
        "authorization_digest": None,
        "authorization_policy_version": None,
        "correction_id": None,
        "plan_id": getattr(plan, "plan_id", None),
        "plan_id_recomputed": None,
        "source_report_digest": getattr(plan, "source_report_digest", None),
        "source_report_digest_recomputed": None,
        "executed_correction_ids": [],
        "skipped_correction_ids": [],
        "target_face": None,
        "counterpart_faces": [],
        "recorded_edges": [],
        "pre_winding_findings": [],
        "post_winding_findings": [],
        "topology_only_orientation_repair": True,
        "normal_agreement_not_verified": True,
        "persisted": False,
        "rollback_performed": False,
        "output_report_digest": None,
        "precondition_results": [],
        "postcondition_results": [],
    }


def _winding_fail(
    result: Dict[str, Any], outcome: str, failure_code: str, reason: str,
    *, precondition: bool = False, postcondition: bool = False,
) -> Dict[str, Any]:
    """Record a declared failure on the receipt and return it (no mutation may follow a failure)."""
    result["result"] = outcome
    result["failure_code"] = failure_code
    if precondition:
        result["precondition_results"].append({"ok": False, "reason": reason})
    if postcondition:
        result["postcondition_results"].append({"ok": False, "reason": reason})
    return result


def _resolve_winding_authorization(value: Any) -> Tuple[Optional[AuthorizationArtifact], Optional[str]]:
    """Parse the presented artifact. Returns ``(artifact, failure_code)``; ``(None, code)`` fails closed."""
    if type(value) is AuthorizationArtifact:
        return value, None
    try:
        return parse_authorization(value), None
    except AuthorizationError as exc:
        return None, (exc.failure_code or "AUTHORIZATION_INVALID")
    except Exception:  # noqa: BLE001 - any unexpected parse behaviour fails closed, never propagates
        return None, "AUTHORIZATION_INVALID"


def _verify_winding_preconditions(
    source_scene: SceneModel,
    source_report: Any,
    *,
    object_id: Optional[str],
    mesh_id: str,
    designated_face_index: int,
    recorded_edges: Sequence[Any],
    counterpart_faces: Sequence[Any],
    selection_mode: str,
) -> Dict[str, Any]:
    """Evaluate WC-P6..P17 on the authoritative fresh evidence, BEFORE any mutation.

    Raises ``WindingPredicateError(predicate_id, reason)`` on the first failing predicate. WC-P12 and
    WC-P13 are invariants of the pre-state against itself (the snapshot is taken from this very
    state), so they are enforced as the ordered post-state comparisons WC-Q3/WC-Q4 instead of being
    re-asserted against a state that is by construction identical.
    """
    try:
        target_obj, mesh = _assert_target_mesh(source_scene, object_id, mesh_id)
    except PreconditionError as exc:
        raise WindingPredicateError("WC-P6", str(exc)) from None

    if type(designated_face_index) is not int or designated_face_index < 0:
        raise WindingPredicateError("WC-P7", "the designated face index must be a non-negative exact int")
    if not (0 <= designated_face_index < len(mesh.faces)):
        raise WindingPredicateError(
            "WC-P7",
            f"designated face index {designated_face_index} is out of range for a mesh of "
            f"{len(mesh.faces)} faces",
        )
    pre_face = tuple(mesh.faces[designated_face_index])

    # ---- WC-P14: the target must be non-degenerate AND non-duplicate (kernel predicates) ----
    if _is_degenerate_face(pre_face, mesh.vertices):
        raise WindingPredicateError(
            "WC-P14", "the designated target face is DEGENERATE under the kernel predicate"
        )
    target_key = _duplicate_key(pre_face, mesh.vertices)
    same_key = sum(1 for f in mesh.faces if _duplicate_key(tuple(f), mesh.vertices) == target_key)
    if same_key != 1:
        raise WindingPredicateError(
            "WC-P14",
            f"the designated target face participates in a DUPLICATE pair ({same_key} faces share "
            "its duplicate key); the winding flip is not the correct remedy (never mask a duplicate)",
        )

    # ---- WC-P8: canonical recorded-edge/counterpart contract (canonical form, sorted, deduped,
    #      counterpart != designated face) ----
    try:
        edges_c, counterparts_c = validate_recorded_edges(
            recorded_edges, counterpart_faces, designated_face_index=designated_face_index
        )
    except AuthorizationError as exc:
        raise WindingPredicateError("WC-P8", str(exc)) from None

    # ---- WC-P17: independent re-derivation + BIDIRECTIONAL recorded-set agreement ----
    fresh = _winding_identities_for_mesh(source_report, mesh_id, "WC-P17")
    if not fresh:
        raise WindingPredicateError(
            "WC-P17",
            "the fresh report has no winding finding for the target mesh: a recorded set cannot be "
            "confirmed against a fresh recomputation (fail closed)",
        )
    try:
        verify_recorded_set_agreement(
            recorded_edges, counterpart_faces,
            [{"edge": [e[0], e[1]], "faces": [p[0], p[1]]} for e, p in fresh],
            designated_face_index=designated_face_index,
        )
    except AuthorizationError as exc:
        raise WindingPredicateError("WC-P17", str(exc)) from None

    # ---- WC-P15 (D1) / WC-P16 (D2): re-derive the aggregation invariant ----
    pairs = [set(pair) for _edge, pair in fresh]
    if selection_mode == SELECTION_MODE_D1:
        for pair in pairs:
            if designated_face_index not in pair:
                raise WindingPredicateError(
                    "WC-P15",
                    f"a fresh winding finding (pair {sorted(pair)}) does not involve the designated "
                    f"face {designated_face_index}",
                )
        common = set(pairs[0])
        for pair in pairs[1:]:
            common &= pair
        if common != {designated_face_index}:
            raise WindingPredicateError(
                "WC-P15",
                f"the recomputed candidate-face intersection {sorted(common)} does not equal the "
                f"designated face {{{designated_face_index}}}",
            )
    else:
        if len(fresh) != 1:
            raise WindingPredicateError(
                "WC-P16", f"D2 requires exactly ONE fresh winding finding; found {len(fresh)}"
            )
        if designated_face_index not in pairs[0]:
            raise WindingPredicateError(
                "WC-P16",
                f"the designated face {designated_face_index} is not a member of the single fresh "
                f"winding pair {sorted(pairs[0])}",
            )

    # ---- WC-P9: every recorded edge is shared by EXACTLY the two recorded faces ----
    edge_map = _edge_face_map(mesh)
    for edge, counterpart in zip(edges_c, counterparts_c):
        incident = edge_map.get(edge, [])
        if len(incident) != 2 or len(set(incident)) != 2:
            raise WindingPredicateError(
                "WC-P9",
                f"recorded edge {list(edge)} is shared by {len(incident)} face incidence(s); "
                "exactly two recorded faces are required",
            )
        if set(incident) != {designated_face_index, counterpart}:
            raise WindingPredicateError(
                "WC-P9",
                f"recorded edge {list(edge)} is shared by faces {sorted(incident)}, not by exactly "
                f"the recorded pair {{{designated_face_index}, {counterpart}}}",
            )

    # ---- WC-P10: the recorded pair currently traverses every recorded edge SAME-direction ----
    for edge, counterpart in zip(edges_c, counterparts_c):
        d_target = _directed_edge_in_face(mesh.faces[designated_face_index], edge, "WC-P10")
        d_other = _directed_edge_in_face(mesh.faces[counterpart], edge, "WC-P10")
        if d_target is None or d_other is None:
            raise WindingPredicateError(
                "WC-P10", f"recorded edge {list(edge)} is not traversed by both recorded faces"
            )
        if d_target != d_other:
            raise WindingPredicateError(
                "WC-P10",
                f"recorded edge {list(edge)} is already traversed OPPOSITELY by faces "
                f"{designated_face_index} and {counterpart}; the recorded inconsistency does not hold",
            )

    # ---- WC-P11: the recorded set is complete and exact for the designated face ----
    same_direction = _same_direction_shared_edges(mesh, designated_face_index, "WC-P11")
    if same_direction != set(edges_c):
        raise WindingPredicateError(
            "WC-P11",
            f"the same-direction shared edges incident to face {designated_face_index} are "
            f"{sorted(same_direction)}, which does not equal the recorded set {sorted(set(edges_c))}",
        )

    return {
        "target_obj": target_obj,
        "target_mesh": mesh,
        "face_index": designated_face_index,
        "pre_face": pre_face,
        "recorded_edges": tuple(edges_c),
        "counterpart_faces": tuple(counterparts_c),
        "fresh_pre_findings": fresh,
    }


def _verify_winding_postconditions(
    fresh_scene: SceneModel,
    fresh_report: Any,
    snapshot: Dict[str, Any],
    *,
    object_id: Optional[str],
    mesh_id: str,
    face_index: int,
    pre_face: Tuple[int, ...],
    recorded_edges: Sequence[Any],
    counterpart_faces: Sequence[int],
    pre_winding: Sequence[Any],
    observations: Optional[Dict[str, Any]] = None,
) -> Tuple[Tuple[Any, ...], Tuple[int, ...]]:
    """Evaluate WC-Q1..Q13 on the fresh post-mutation state (exact, ordered, fail closed).

    Returns the post-mutation ``(winding_identities, face_tuples)`` for the receipt.
    """
    pre_faces = tuple(snapshot["target"]["ordered_face_tuples"])
    pre_vertices = tuple(snapshot["target"]["ordered_vertex_table"])
    try:
        _post_obj, post_mesh = _assert_target_mesh(fresh_scene, object_id, mesh_id)
    except PreconditionError as exc:
        raise WindingPostconditionError("WC-Q10", f"target resolution failed post-mutation: {exc}") from None
    post_faces = tuple(tuple(f) for f in post_mesh.faces)
    if observations is not None:
        observations["post_faces"] = post_faces

    # ---- WC-Q2 / WC-Q1 / WC-Q4: face count, exactly one ordered tuple reversed, others identical --
    if len(post_faces) != len(pre_faces):
        raise WindingPostconditionError(
            "WC-Q2", f"face count changed: {len(pre_faces)} -> {len(post_faces)}"
        )
    for i, (before, after) in enumerate(zip(pre_faces, post_faces)):
        if i == face_index:
            if after != _reverse_face(before):
                raise WindingPostconditionError(
                    "WC-Q1",
                    f"face {i} is not the exact plain reversal of its pre-mutation tuple "
                    f"({list(before)} -> {list(after)})",
                )
        elif after != before:
            raise WindingPostconditionError(
                "WC-Q4", f"non-target face {i} changed ({list(before)} -> {list(after)})"
            )

    # ---- WC-Q3: the vertex table is unchanged (ordered, exact) ----
    if tuple(tuple(v) for v in post_mesh.vertices) != pre_vertices:
        raise WindingPostconditionError("WC-Q3", "target mesh vertex table changed")

    # ---- WC-Q5: every recorded edge is now OPPOSITE-traversed by the recorded pair ----
    for edge, counterpart in zip(recorded_edges, counterpart_faces):
        d_target = _directed_edge_in_face(post_faces[face_index], tuple(edge), "WC-Q5")
        d_other = _directed_edge_in_face(post_faces[counterpart], tuple(edge), "WC-Q5")
        if d_target is None or d_other is None:
            raise WindingPostconditionError(
                "WC-Q5", f"recorded edge {list(edge)} is no longer traversed by both recorded faces"
            )
        if d_target == d_other:
            raise WindingPostconditionError(
                "WC-Q5",
                f"recorded edge {list(edge)} is still traversed SAME-direction by faces "
                f"{face_index} and {counterpart}",
            )

    # ---- WC-Q6 / WC-Q13: winding findings for the target mesh ----
    post_winding = _winding_identities_for_mesh(fresh_report, mesh_id, "WC-Q6")
    if observations is not None:
        observations["post_winding"] = post_winding
    pre_winding_set = set(pre_winding)
    for identity in post_winding:
        if identity not in pre_winding_set:
            raise WindingPostconditionError(
                "WC-Q6",
                f"a NEW winding finding appeared for mesh {mesh_id!r}: edge {list(identity[0])} "
                f"faces {list(identity[1])}",
            )
    post_winding_set = set(post_winding)
    for identity in pre_winding_set:
        if identity in post_winding_set:
            raise WindingPostconditionError(
                "WC-Q13",
                f"a pre-existing winding finding SURVIVED the correction for mesh {mesh_id!r}: "
                f"edge {list(identity[0])} faces {list(identity[1])}",
            )

    # ---- WC-Q7 / WC-Q8: no new duplicate / degenerate finding for the target mesh ----
    pre_dup = Counter(_measured_keys_for_mesh(snapshot["source_report"], mesh_id, "MESH_DUPLICATE_FACE"))
    post_dup = Counter(_measured_keys_for_mesh(fresh_report, mesh_id, "MESH_DUPLICATE_FACE"))
    if post_dup - pre_dup:
        raise WindingPostconditionError(
            "WC-Q7", f"a NEW duplicate-face finding appeared for mesh {mesh_id!r}"
        )
    pre_deg = Counter(_measured_keys_for_mesh(snapshot["source_report"], mesh_id, "MESH_DEGENERATE_FACE"))
    post_deg = Counter(_measured_keys_for_mesh(fresh_report, mesh_id, "MESH_DEGENERATE_FACE"))
    if post_deg - pre_deg:
        raise WindingPostconditionError(
            "WC-Q8", f"a NEW degenerate-face finding appeared for mesh {mesh_id!r}"
        )
    if _is_degenerate_face(post_faces[face_index], post_mesh.vertices) != _is_degenerate_face(
        pre_face, pre_vertices
    ):
        raise WindingPostconditionError(
            "WC-Q8", "the target face's degeneracy classification changed"
        )

    # ---- WC-Q9: no new MESH_INVALID_INDEX ----
    pre_invalid = set(_measured_keys_for_mesh(snapshot["source_report"], mesh_id, "MESH_INVALID_INDEX"))
    post_invalid = set(_measured_keys_for_mesh(fresh_report, mesh_id, "MESH_INVALID_INDEX"))
    if post_invalid - pre_invalid:
        raise WindingPostconditionError(
            "WC-Q9", f"a NEW invalid-index finding appeared for mesh {mesh_id!r}"
        )
    scene_pre_invalid = {_freeze_key(f.measured) for f in (getattr(snapshot["source_report"], "findings", ()) or ())
                         if getattr(getattr(f, "code", None), "value", None) == "MESH_INVALID_INDEX"}
    scene_post_invalid = {_freeze_key(f.measured) for f in (getattr(fresh_report, "findings", ()) or ())
                          if getattr(getattr(f, "code", None), "value", None) == "MESH_INVALID_INDEX"}
    if scene_post_invalid - scene_pre_invalid:
        raise WindingPostconditionError("WC-Q9", "a NEW invalid-index finding appeared in the scene")

    # ---- WC-Q10: identity unchanged (object, mesh, names/pose/collection/parent, counterparts) ----
    if post_mesh.mesh_id != mesh_id:
        raise WindingPostconditionError("WC-Q10", "target mesh identity changed")
    post_obj = next((o for o in fresh_scene.objects if o.object_id == object_id), None)
    if post_obj is None:
        raise WindingPostconditionError("WC-Q10", f"target object {object_id!r} disappeared")
    if _object_state_key(post_obj) != tuple(snapshot.get("target_object_state", ())):
        raise WindingPostconditionError("WC-Q10", "target object name/pose/collection/parent changed")
    for counterpart in counterpart_faces:
        if not (0 <= counterpart < len(post_faces)) or not (0 <= counterpart < len(pre_faces)):
            raise WindingPostconditionError(
                "WC-Q10", f"recorded counterpart index {counterpart} is out of range"
            )
        if post_faces[counterpart] != pre_faces[counterpart]:
            raise WindingPostconditionError(
                "WC-Q10", f"counterpart face {counterpart} tuple changed"
            )

    # ---- WC-Q11: unrelated state unchanged (Wave-1 snapshot mechanism, verbatim checks) ----
    if fresh_scene.scene_id != snapshot.get("scene_id"):
        raise WindingPostconditionError("WC-Q11", "fresh scene_id does not match snapshot")
    if fresh_scene.unit_system != snapshot.get("unit_system"):
        raise WindingPostconditionError("WC-Q11", "scene unit_system changed after mutation")
    if _ordered_object_ids(fresh_scene) != tuple(snapshot.get("ordered_object_ids", ())):
        raise WindingPostconditionError("WC-Q11", "object ordering or identity set changed")
    for obj in fresh_scene.objects:
        if obj.object_id == object_id:
            continue
        expected = snapshot["unrelated"].get(obj.object_id)
        if expected is None:
            raise WindingPostconditionError("WC-Q11", f"unexpected object {obj.object_id!r} appeared")
        exp_state, exp_mesh = expected
        if _object_state_key(obj) != tuple(exp_state):
            raise WindingPostconditionError("WC-Q11", f"unrelated object {obj.object_id!r} state changed")
        if _mesh_state_key(obj.mesh) != exp_mesh:
            raise WindingPostconditionError(
                "WC-Q11", f"unrelated object {obj.object_id!r} topology/metadata changed"
            )
    return post_winding, post_faces


def execute_repair_face_winding(
    *,
    engine_state: Any,
    plan: Any,
    authorization: Any,
    mutator: Optional[Callable[..., None]] = None,
    extractor: Callable[[Any], Tuple[SceneModel, Any]] = extract_and_report,
) -> Dict[str, Any]:
    """Execute a REPAIR_FACE_WINDING plan — WAVE 2, human-authorized, topology-only.

    ``authorization`` is MANDATORY BY CONSTRUCTION (keyword-only, no default): a caller cannot even
    invoke this entry point without deciding what artifact to present, and passing ``None`` yields
    ``AUTHORIZATION_REQUIRED`` — never an execution. Only an artifact that verifies against the
    exact plan/source/designation binding of this execution opens the gate (design §1.2/§1.4).

    Exactly ONE face tuple is replaced by its exact plain reversal, on exactly one mesh of one
    object; the mutation itself is performed by the INJECTED mutator (never by this module, which
    imports no ``bpy``). At most one mutator invocation happens per execution: there is no retry, no
    second face flip, no fallback target and no cascade repair — a postcondition failure returns
    ``POSTCONDITION_FAILED`` with the failed predicate recorded on the receipt.

    The receipt is AUDIT DATA ONLY: it grants no authorization, execution, persistence or rollback
    authority, and the executor never reads a receipt as input.
    """
    result = _winding_receipt_skeleton(plan)
    # authorization_verified is claimable ONLY after the whole gate (including the deferred optional
    # expected_face_tuple assertion) has passed; every failure path leaves it False.
    result["authorization_verified"] = False
    try:
        # ---- 0a. plan integrity (recompute) ----
        if plan is None or not hasattr(plan, "source_report_digest") or not hasattr(plan, "plan_id"):
            return _winding_fail(result, ExecutionOutcome.PLAN_INVALID, "PLAN_INVALID",
                                 "plan is missing its integrity fields")
        try:
            recomputed_plan_id = plan._compute_plan_id()
        except Exception:
            recomputed_plan_id = None
        if recomputed_plan_id is None or recomputed_plan_id != plan.plan_id:
            return _winding_fail(result, ExecutionOutcome.PLAN_INVALID, "PLAN_ID_MISMATCH",
                                 "plan_id does not match the recomputed canonical plan contents")
        result["plan_id_recomputed"] = recomputed_plan_id

        # ---- 0b. exactly ONE executable winding correction + allowlist ----
        corrections = getattr(plan, "corrections", ())
        executable = [c for c in corrections if c.correction_type == _WINDING_OPERATION]
        result["skipped_correction_ids"] = [
            c.correction_id for c in corrections if c.correction_type != _WINDING_OPERATION
        ]
        if not executable:
            return _winding_fail(result, ExecutionOutcome.PLAN_INVALID, "NO_EXECUTABLE_CORRECTION",
                                 "the plan contains no REPAIR_FACE_WINDING correction")
        if len(executable) > 1:
            return _winding_fail(result, ExecutionOutcome.PLAN_INVALID,
                                 "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS",
                                 f"the plan contains {len(executable)} executable winding corrections; "
                                 "exactly one is required (split the plan per mesh)")
        corr = executable[0]
        if corr.correction_type not in _EXECUTABLE_TYPES:
            return _winding_fail(result, ExecutionOutcome.UNSAFE, "NOT_EXECUTABLE_TYPE",
                                 "the correction type is not in the executor allowlist")
        result["correction_id"] = corr.correction_id
        params = dict(corr.parameters)

        # ---- 0c. winding parameter allowlist (closed key set, exact shapes) ----
        failure = _validate_winding_params(params)
        if failure is not None:
            return _winding_fail(result, ExecutionOutcome.PLAN_INVALID, failure,
                                 f"winding parameters failed the operation allowlist: {failure}")
        mesh_id = params["mesh_id"]
        plan_designation = params["designated_face_index"]
        candidate_pair = params["candidate_faces"]
        selection_mode = SELECTION_MODE_D1 if plan_designation is not None else SELECTION_MODE_D2

        # ---- 0d. AUTHORIZATION GATE (contract only; no engine read, no mutation) ----
        if authorization is None:
            return _winding_fail(result, ExecutionOutcome.AUTHORIZATION_REQUIRED,
                                 "AUTHORIZATION_REQUIRED",
                                 "no authorization artifact was presented for a review-gated correction")
        artifact, parse_failure = _resolve_winding_authorization(authorization)
        if artifact is None:
            return _winding_fail(result, ExecutionOutcome.AUTHORIZATION_INVALID,
                                 parse_failure or "AUTHORIZATION_INVALID",
                                 "the presented authorization artifact is not a valid decision")
        result["authorization_digest"] = artifact.digest()
        result["authorization_policy_version"] = artifact.authorization_policy_version
        work = PresentedWork(
            correction_type=corr.correction_type,
            correction_id=corr.correction_id,
            plan_id=recomputed_plan_id,
            source_report_digest=plan.source_report_digest,
            selection_mode=selection_mode,
            plan_designated_face_index=plan_designation,
            candidate_pair=(tuple(candidate_pair) if candidate_pair is not None else None),
            execution_face_tuple=None,
        )
        verdict = verify_authorization(artifact, work)
        expected_tuple_deferred = False
        if not verdict.ok:
            if (verdict.outcome == AuthorizationOutcome.INVALID
                    and verdict.failure_code == "EXECUTION_FACE_TUPLE_UNAVAILABLE"):
                # the artifact asserts an expected_face_tuple: that redundant assertion can only be
                # evaluated once the execution-time tuple is read from the fresh authoritative model.
                expected_tuple_deferred = True
            else:
                return _winding_fail(result, verdict.outcome or ExecutionOutcome.AUTHORIZATION_INVALID,
                                     verdict.failure_code or "AUTHORIZATION_INVALID",
                                     "the authorization gate rejected the presented artifact")
        designated_face_index, designation_failure = resolve_designated_face_index(artifact, work)
        if designation_failure is not None:
            return _winding_fail(result, designation_failure.outcome or ExecutionOutcome.AUTHORIZATION_INVALID,
                                 designation_failure.failure_code or "AUTHORIZATION_INVALID",
                                 "the authorization gate rejected the face designation")

        # ---- 1. source binding (fresh authoritative extraction) ----
        try:
            source_scene, source_report = extractor(engine_state)
            recomputed_digest = source_report.digest()
        except Exception:
            return _winding_fail(result, ExecutionOutcome.SOURCE_MISMATCH, "EXTRACTION_FAILED",
                                 "the authoritative extraction failed")
        result["source_report_digest_recomputed"] = recomputed_digest
        if recomputed_digest != plan.source_report_digest:
            return _winding_fail(result, ExecutionOutcome.SOURCE_MISMATCH, "SOURCE_DIGEST_MISMATCH",
                                 "the fresh extraction digest does not match the plan's source digest")

        # ---- the deferred optional expected_face_tuple assertion (design §1.2 item 7) ----
        if expected_tuple_deferred:
            try:
                _probe_obj, mesh_probe = _assert_target_mesh(source_scene, corr.object_id, mesh_id)
            except PreconditionError as exc:
                return _winding_fail(result, ExecutionOutcome.PRECONDITION_FAILED, "WC-P6", str(exc),
                                     precondition=True)
            if not (0 <= designated_face_index < len(mesh_probe.faces)):
                return _winding_fail(result, ExecutionOutcome.PRECONDITION_FAILED, "WC-P7",
                                     "the designated face index is out of range", precondition=True)
            work_with_tuple = PresentedWork(
                correction_type=corr.correction_type,
                correction_id=corr.correction_id,
                plan_id=recomputed_plan_id,
                source_report_digest=plan.source_report_digest,
                selection_mode=selection_mode,
                plan_designated_face_index=plan_designation,
                candidate_pair=(tuple(candidate_pair) if candidate_pair is not None else None),
                execution_face_tuple=tuple(mesh_probe.faces[designated_face_index]),
            )
            tuple_verdict = verify_authorization(artifact, work_with_tuple)
            if not tuple_verdict.ok:
                return _winding_fail(result,
                                     tuple_verdict.outcome or ExecutionOutcome.AUTHORIZATION_INVALID,
                                     tuple_verdict.failure_code or "AUTHORIZATION_INVALID",
                                     "the authorization gate rejected the presented artifact")

        # ---- 2. preconditions on the fresh pre-mutation evidence ----
        try:
            ctx = _verify_winding_preconditions(
                source_scene,
                source_report,
                object_id=corr.object_id,
                mesh_id=mesh_id,
                designated_face_index=designated_face_index,
                recorded_edges=params["recorded_edges"],
                counterpart_faces=params["counterpart_faces"],
                selection_mode=selection_mode,
            )
        except WindingPredicateError as exc:
            return _winding_fail(result, ExecutionOutcome.PRECONDITION_FAILED, "PRECONDITION_FAILED",
                                 f"{exc.predicate_id}: {exc.reason}", precondition=True)
        result["authorization_verified"] = True   # every binding of §1.2 has now passed
        target_obj = ctx["target_obj"]
        mesh = ctx["target_mesh"]
        face_index = ctx["face_index"]
        pre_face = ctx["pre_face"]
        recorded = ctx["recorded_edges"]
        counterparts = ctx["counterpart_faces"]
        pre_winding = ctx["fresh_pre_findings"]
        result["precondition_results"].append({"ok": True, "target": [target_obj.object_id, mesh_id]})
        result["target_face"] = {
            "object_id": target_obj.object_id,
            "mesh_id": mesh_id,
            "face_index": face_index,
            "face_tuple_before": list(pre_face),
            "face_tuple_after": None,
        }
        result["recorded_edges"] = [list(edge) for edge in recorded]
        result["pre_winding_findings"] = [
            {"edge": list(edge), "faces": list(pair)} for edge, pair in pre_winding
        ]
        result["counterpart_faces"] = [
            {"index": cp, "edge": list(edge), "face_tuple": list(mesh.faces[cp])}
            for edge, cp in zip(recorded, counterparts)
        ]

        # ---- immutable pre-mutation snapshot (Wave-1 mechanism, including object order) ----
        snapshot = _build_snapshot(
            source_scene, target_obj, target_obj.object_id, mesh_id, plan.source_report_digest
        )
        snapshot["source_report"] = source_report  # audit comparison base for Q7/Q8/Q9/Q13

        # ---- 3. EXACTLY ONE bounded mutation (injected; stubbed in tests) ----
        _mutator = mutator if mutator is not None else _default_mutator(operation=_WINDING_OPERATION)
        try:
            _mutator(
                engine_state,
                object_id=target_obj.object_id,
                mesh_id=mesh_id,
                face_index=face_index,
                face_tuple=pre_face,
            )
        except Exception:
            return _winding_fail(result, ExecutionOutcome.MUTATION_FAILED, "MUTATION_FAILED",
                                 "the bounded winding mutator failed")

        # ---- 4. fresh extraction + WC-Q1..Q13 ----
        try:
            fresh_scene, fresh_report = extractor(engine_state)
        except Exception:
            return _winding_fail(result, ExecutionOutcome.MUTATION_FAILED, "POST_EXTRACTION_FAILED",
                                 "the post-mutation extraction failed")
        result["output_report_digest"] = fresh_report.digest()
        observations: Dict[str, Any] = {}
        try:
            post_winding, post_faces = _verify_winding_postconditions(
                fresh_scene,
                fresh_report,
                snapshot,
                object_id=target_obj.object_id,
                mesh_id=mesh_id,
                face_index=face_index,
                pre_face=pre_face,
                recorded_edges=recorded,
                counterpart_faces=counterparts,
                pre_winding=pre_winding,
                observations=observations,
            )
        except WindingPostconditionError as exc:
            # the mutation DID happen: record what was actually observed before failing, so the
            # receipt is informative (audit data only — never a claim of success).
            observed = observations.get("post_winding")
            if observed is not None:
                result["post_winding_findings"] = [
                    {"edge": list(edge), "faces": list(pair)} for edge, pair in observed
                ]
            observed_faces = observations.get("post_faces")
            if observed_faces is not None and face_index < len(observed_faces):
                result["target_face"]["face_tuple_after"] = list(observed_faces[face_index])
            return _winding_fail(result, ExecutionOutcome.POSTCONDITION_FAILED,
                                 exc.predicate_id or "POSTCONDITION_FAILED",
                                 f"{exc.predicate_id}: {exc.reason}", postcondition=True)
        except PreconditionError as exc:  # a post-state predicate raised a base-type failure
            return _winding_fail(result, ExecutionOutcome.POSTCONDITION_FAILED, "POSTCONDITION_FAILED",
                                 str(exc), postcondition=True)

        result["post_winding_findings"] = [
            {"edge": list(edge), "faces": list(pair)} for edge, pair in post_winding
        ]
        result["target_face"]["face_tuple_after"] = list(post_faces[face_index])
        result["result"] = ExecutionOutcome.COMPLETED
        result["executed_correction_ids"] = [corr.correction_id]
        return result
    except Exception:  # noqa: BLE001 - fail closed on any unexpected error
        return _winding_fail(result, ExecutionOutcome.MUTATION_FAILED, "INTERNAL_ERROR",
                             "an unexpected error occurred; nothing was reported as completed")

# ---------------------------------------------------------------------------
# WAVE 3 — REPAIR_MERGE_VERTEX (design: BLENDER_MERGE_VERTEX_DESIGN.md §4–§10)
#
# The controlled, HUMAN-AUTHORIZED consolidation of exact-bit duplicate vertices on ONE mesh.
# Exactly ONE bounded mutation, performed by the INJECTED mutator; this module imports no bpy.
#
# THE CENTRAL TRUST RULE (design §7 / §19, master handoff §4 D):
#   AUTHORIZATION_VERIFIED does NOT mean PLAN_CORRECTNESS_VERIFIED.
# Nothing the caller presents is evidence: not an `all_groups_exact` flag, not a plan body, not an
# artifact field, not a receipt, not a caller assertion. Every one of MR-1…MR-6 is re-derived in this
# module from the FRESH authoritative SceneModel + SceneReport and then COMPARED against the plan.
# The plan is the comparison target, never the evidence. Any mismatch refuses BEFORE the mutation.
#
# The mutation is a pure index renumbering plus the ordered surviving vertex subsequence (§4). This
# module performs no cleanup of any kind: no face removal, no degeneracy removal, no winding repair,
# no normal repair, no rename, no collection/transform change, no persistence, no rollback.
# ---------------------------------------------------------------------------

_MERGE_OPERATION = "REPAIR_MERGE_VERTEX"
_MERGE_FINDING_CODE = "MESH_DUPLICATE_VERTEX"
_MERGE_ALLOWED_PARAM_KEYS = frozenset(MERGE_PARAMETER_KEYS)

# The four topology classes whose PREDICTED appearance refuses the merge (design §5 E / MP-9). Three
# are reachable by index collapse (duplicate face, non-manifold edge, winding); a created DEGENERATE
# face is provably impossible for a conforming Case-A input with MP-5 satisfied — it is nevertheless
# evaluated as defence in depth, exactly as the design requires, so its non-firing is demonstrated.
_MERGE_TOPOLOGY_CLASSES = (
    "MESH_DUPLICATE_FACE",
    "MESH_NON_MANIFOLD_EDGE",
    "MESH_WINDING_INCONSISTENT",
    "MESH_DEGENERATE_FACE",
)

#: The finding codes whose pre/post multiset is carried on the merge receipt (§10). The duplicate
#: vertex code is the capability's own; the other four are the pre/post evidence MQ-4/MQ-7 compare.
_MERGE_RECEIPT_FINDING_CODES = {
    "duplicate_vertex": _MERGE_FINDING_CODE,
    "duplicate_face": "MESH_DUPLICATE_FACE",
    "degenerate_face": "MESH_DEGENERATE_FACE",
    "non_manifold": "MESH_NON_MANIFOLD_EDGE",
    "winding": "MESH_WINDING_INCONSISTENT",
}


class MergePredicateError(PreconditionError):
    """A WAVE-3 merge precondition (MP-*) evaluated false against the FRESH evidence.

    ``predicate_id`` is the MP-n id. ``failure_code`` optionally carries the more specific
    vocabulary token the receipt must report (e.g. the authorization gate's own code when MP-10
    rejects a presented artifact), and is preferred over the predicate id when present.
    """

    def __init__(self, predicate_id: str, reason: str, *, failure_code: Optional[str] = None) -> None:
        super().__init__(f"{predicate_id}: {reason}")
        self.predicate_id = predicate_id
        self.reason = reason
        self.failure_code = failure_code


class MergePostconditionError(PostconditionError):
    """A WAVE-3 merge postcondition (MQ-*) evaluated false against the FRESH post-state."""

    def __init__(self, predicate_id: str, reason: str) -> None:
        super().__init__(f"{predicate_id}: {reason}")
        self.predicate_id = predicate_id
        self.reason = reason


def _merge_receipt_skeleton(plan: Any) -> Dict[str, Any]:
    """The WAVE-3 audit receipt skeleton (design §10, all 44 fields, audit data only).

    Every field is present with exactly the canonical JSON type the §10 schema defines. "Cond" fields
    start as JSON ``null`` and are filled only on the path where they are meaningful. The three scope
    assertions are fixed for this correction type, and ``persisted``/``rollback_performed`` are ``False``
    on every receipt because this capability has no persistence or rollback authority.
    """
    return {
        "receipt_version": "1",
        "result": ExecutionOutcome.NOT_STARTED,
        "failure_code": None,
        "executor_version": EXECUTOR_VERSION,
        "execution_policy_version": EXECUTION_POLICY_VERSION,
        "correction_type": _MERGE_OPERATION,
        "correction_id": None,
        "plan_id": getattr(plan, "plan_id", None),
        "plan_id_recomputed": None,
        "source_report_digest": getattr(plan, "source_report_digest", None),
        "source_report_digest_recomputed": None,
        "authorization_verified": False,
        "authorization_digest": None,
        "authorization_policy_version": None,
        "executed_correction_ids": [],
        "skipped_correction_ids": [],
        "target_object_mesh": None,
        "pre_vertex_count": 0,
        "post_vertex_count": None,
        "duplicate_groups": [],
        "survivor_indices": [],
        "removed_vertex_indices": [],
        "old_to_new_mapping": None,
        "old_to_new_mapping_digest": None,
        "changed_face_indices": None,
        "pre_duplicate_vertex_findings": [],
        "post_duplicate_vertex_findings": None,
        "pre_duplicate_face_findings": [],
        "post_duplicate_face_findings": None,
        "pre_degenerate_face_findings": [],
        "post_degenerate_face_findings": None,
        "pre_non_manifold_findings": [],
        "post_non_manifold_findings": None,
        "pre_winding_findings": [],
        "post_winding_findings": None,
        "precondition_results": [],
        "postcondition_results": None,
        "vertex_merge_only": True,
        "index_renumbering_only": True,
        "geometry_unverifiable": False,
        "normal_agreement_not_verified": True,
        "persisted": False,
        "rollback_performed": False,
        "output_report_digest": None,
    }


def _merge_fail(
    result: Dict[str, Any], outcome: str, failure_code: str, reason: str,
    *, precondition: bool = False, postcondition: bool = False,
) -> Dict[str, Any]:
    """Record a declared failure on the merge receipt and return it (no mutation may follow)."""
    result["result"] = outcome
    result["failure_code"] = failure_code
    if precondition:
        result["precondition_results"].append({"ok": False, "reason": reason})
    if postcondition:
        if result["postcondition_results"] is None:
            result["postcondition_results"] = []
        result["postcondition_results"].append({"ok": False, "reason": reason})
    return result


def _merge_ok(result: Dict[str, Any], predicate_id: str, detail: str) -> None:
    """Record a PASSED precondition on the receipt (reason begins with the predicate id, §10)."""
    result["precondition_results"].append({"ok": True, "reason": f"{predicate_id}: {detail}"})


def _resolve_merge_authorization(value: Any) -> Tuple[Optional[AuthorizationArtifact], Optional[str]]:
    """Parse the presented artifact; ``(None, code)`` fails closed (never a raw exception)."""
    if type(value) is AuthorizationArtifact:
        return value, None
    try:
        return parse_authorization(value), None
    except AuthorizationError as exc:
        return None, (exc.failure_code or "AUTHORIZATION_INVALID")
    except Exception:  # noqa: BLE001 - any unexpected parse behaviour fails closed, never propagates
        return None, "AUTHORIZATION_INVALID"


def _merge_mesh_findings(report: Any, mesh_id: str, code_token: str) -> Tuple[Any, ...]:
    """The FRESH findings of one code for ONE mesh, in the report's canonical order (§10 ordering)."""
    out: list = []
    for finding in getattr(report, "findings", ()) or ():
        if getattr(getattr(finding, "code", None), "value", None) != code_token:
            continue
        if getattr(finding, "mesh_id", None) != mesh_id:
            continue
        out.append(finding)
    return tuple(out)


def _merge_finding_snapshots(findings: Sequence[Any]) -> List[Dict[str, Any]]:
    """``Finding.snapshot()`` for each finding — the EXISTING representation, never a parallel shape."""
    return [finding.snapshot() for finding in findings]


def _merge_code_histogram(findings: Sequence[Any]) -> Dict[str, int]:
    """Deterministic code histogram of a kernel finding list (drives MP-9 and MQ-7)."""
    counts: Dict[str, int] = {}
    for finding in findings:
        token = getattr(getattr(finding, "code", None), "value", None)
        if token is None:
            token = str(getattr(finding, "code", None))
        counts[token] = counts.get(token, 0) + 1
    return counts

# ---------------------------------------------------------------------------
# MR-1…MR-6 — execution-time re-derivation (design §7). All of it reads the FRESH evidence.
# ---------------------------------------------------------------------------

def _merge_pairs_from_report(report: Any, mesh_id: str) -> Tuple[Tuple[int, int], ...]:
    """**MR-1** — the kernel's duplicate-vertex pair evidence for the target mesh.

    Canonicalized to ``(min, max)``, deduplicated, ascending. A malformed finding is a refusal, never
    a repaired report: the executor does not invent a pair and does not drop one silently.
    """
    pairs: list = []
    for index, finding in enumerate(_merge_mesh_findings(report, mesh_id, _MERGE_FINDING_CODE)):
        measured = getattr(finding, "measured", None)
        if type(measured) is not dict:
            raise MergePredicateError(
                "MP-3", f"fresh duplicate-vertex finding[{index}] carries no 'measured' payload"
            )
        vertex_a = measured.get("vertex_a")
        vertex_b = measured.get("vertex_b")
        if type(vertex_a) is not int or type(vertex_b) is not int:
            raise MergePredicateError(
                "MP-3", f"fresh duplicate-vertex finding[{index}] indices must be exact ints"
            )
        if vertex_a < 0 or vertex_b < 0 or vertex_a == vertex_b:
            raise MergePredicateError(
                "MP-3",
                f"fresh duplicate-vertex finding[{index}] has a negative or self-loop pair "
                f"({vertex_a!r}, {vertex_b!r})",
            )
        pair = (min(vertex_a, vertex_b), max(vertex_a, vertex_b))
        if pair not in pairs:
            pairs.append(pair)
    return tuple(sorted(pairs))


def _merge_groups_from_pairs(pairs: Sequence[Tuple[int, int]]) -> Tuple[Tuple[int, ...], ...]:
    """**MR-2** — the transitive closure of the pair relation, canonically ordered.

    Union–find by ascending root, so the result depends only on the pair SET: never on dict/set
    iteration order and never on the order the pairs arrived in. Groups of fewer than two members
    cannot arise from the relation and are dropped only to keep the result a group set.
    """
    parent: Dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:  # path compression, order-independent by construction
            parent[node], node = root, parent[node]
        return root

    for left, right in pairs:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            continue
        if root_left < root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    classes: Dict[int, list] = {}
    for node in sorted(parent):
        classes.setdefault(find(node), []).append(node)
    groups = [tuple(members) for _root, members in sorted(classes.items())]
    return tuple(group for group in groups if len(group) >= 2)


def _merge_pairs_implied_by_table(vertices: Sequence[Sequence[Any]]) -> frozenset:
    """The pair set the AUTHORITATIVE vertex table proves (MP-3 / MP-6 completeness, both directions).

    Mirrors the kernel's ``_collect_duplicate_vertices`` shape exactly: ascending index order, first
    index of a rounded key seen wins, each later member pairs with that first index. This is the
    independent completeness witness — it is never derived from the report under check.
    """
    seen: Dict[Any, int] = {}
    implied: set = set()
    for index, vertex in enumerate(vertices):
        key = canonical_coincidence_key(vertex)
        if key in seen:
            implied.add((seen[key], index))
        else:
            seen[key] = index
    return frozenset(implied)


def _merge_survivor_of(groups: Sequence[Sequence[int]]) -> Dict[int, int]:
    """The survivor map ``sigma``: every group member -> ``min(group)`` (design §4)."""
    survivor_of: Dict[int, int] = {}
    for group in groups:
        survivor = min(group)
        for member in group:
            survivor_of[member] = survivor
    return survivor_of


def _merge_kept_indices(vertex_count: int, groups: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    """The kept index set ``S``: the sorted image of the survivor map (design §4)."""
    survivor_of = _merge_survivor_of(groups)
    return tuple(sorted({survivor_of.get(index, index) for index in range(vertex_count)}))


def _merge_predicted_tables(
    mesh: MeshModel, mapping: Sequence[int], kept: Sequence[int]
) -> Tuple[Tuple[Tuple[float, ...], ...], Tuple[Tuple[int, ...], ...]]:
    """**MR-6** — the exact predicted post-state tables ``(V', F')`` from the FRESH pre-state (§4).

    ``V'`` is the ordered surviving subsequence ``(V[s_0] … V[s_{m-1}])`` over the KEPT PRE-INDICES
    ``S``; ``F'`` is the elementwise ``rho∘sigma`` substitution with face order and loop order
    preserved. Nothing else is computed here — no cleanup, no repair.

    ``kept`` must be ``S`` (the survivors' PRE indices), i.e. the sorted image of the survivor map.
    It is NOT ``set(mapping)``: ``mapping`` maps every pre index to its POST index, so its value set
    is exactly ``range(m)`` and is index-range information, never a set of pre indices. Conflating
    the two silently builds ``V'`` from the wrong subsequence.
    """
    predicted_vertices = tuple(tuple(mesh.vertices[survivor]) for survivor in kept)
    predicted_faces = tuple(tuple(mapping[member] for member in face) for face in mesh.faces)
    return predicted_vertices, predicted_faces


def _merge_predicted_mesh(mesh: MeshModel, predicted_vertices: Any, predicted_faces: Any) -> MeshModel:
    """Build the predicted mesh through the SAME canonical model the extraction would produce."""
    return MeshModel(
        mesh_id=mesh.mesh_id,
        vertices=predicted_vertices,
        faces=predicted_faces,
    )


def _merge_topology_delta(pre_findings: Sequence[Any], post_findings: Sequence[Any]) -> Dict[str, Any]:
    """The deterministic new/cleared finding-class delta used by MP-9 and MQ-7.

    A class is NEW when its post count exceeds its pre count, and CLEARED when its pre count exceeds
    its post count. The capability's OWN code (``MESH_DUPLICATE_VERTEX``) is expected to be cleared by
    the merge, so it is reported separately and never counted as a ``cleared`` violation — every OTHER
    class must be exactly preserved (the merge may not "fix" anything as a side effect).
    """
    pre_counts = _merge_code_histogram(pre_findings)
    post_counts = _merge_code_histogram(post_findings)
    new_codes = sorted(
        code for code in post_counts if post_counts[code] > pre_counts.get(code, 0)
    )
    cleared_codes = sorted(
        code for code in pre_counts
        if pre_counts[code] > post_counts.get(code, 0) and code != _MERGE_FINDING_CODE
    )
    newly_created_topology = sorted(
        code for code in _MERGE_TOPOLOGY_CLASSES if post_counts.get(code, 0) > pre_counts.get(code, 0)
    )
    return {
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "new_codes": new_codes,
        "cleared_codes": cleared_codes,
        "newly_created_topology": newly_created_topology,
        "duplicate_vertex_remaining": post_counts.get(_MERGE_FINDING_CODE, 0),
    }

def _validate_merge_params(params: Any) -> Optional[str]:
    """Closed-key-set / exact-shape allowlist for the merge operation (design §6 MP-2, §4).

    The plan's parameters are a PRESENTATION of the plan body, not evidence: every value here is
    re-derived later and compared. This function only guarantees that the body has the canonical
    shape, so a malformed plan is refused as ``PLAN_INVALID`` rather than raising an incidental
    Python exception.
    """
    if type(params) is not dict and not hasattr(params, "keys"):
        return "PARAMETERS_NOT_A_MAPPING"
    try:
        keys = tuple(params.keys())
    except Exception:  # noqa: BLE001 - a hostile mapping must not raise
        return "PARAMETERS_NOT_A_MAPPING"
    missing = [key for key in MERGE_PARAMETER_KEYS if key not in keys]
    if missing:
        return "MISSING_PARAMETER:" + ",".join(missing)
    extra = [key for key in keys if key not in _MERGE_ALLOWED_PARAM_KEYS]
    if extra:
        return "UNEXPECTED_PARAMETER:" + ",".join(sorted(extra))
    if type(params.get("mesh_id")) is not str or not params.get("mesh_id"):
        return "MESH_ID_INVALID"
    if type(params.get("mapping_digest")) is not str:
        return "MAPPING_DIGEST_INVALID"
    if type(params.get("all_groups_exact")) is not bool:
        return "ALL_GROUPS_EXACT_NOT_BOOL"
    if type(params.get("predicted_topology_unchanged")) is not bool:
        return "PREDICTED_TOPOLOGY_NOT_BOOL"
    for key in ("recorded_pairs", "duplicate_groups", "survivor_indices", "old_to_new_mapping"):
        if type(params.get(key)) not in (tuple, list):
            return f"{key.upper()}_NOT_A_SEQUENCE"
    for pair_index, pair in enumerate(params.get("recorded_pairs") or ()):
        if type(pair) not in (tuple, list) or len(pair) != 2:
            return f"RECORDED_PAIR_ARITY:{pair_index}"
        if any(type(member) is not int for member in pair):
            return f"RECORDED_PAIR_NON_INTEGER:{pair_index}"
    return None


def _merge_cases(table: Sequence[Sequence[Any]], groups: Sequence[Sequence[int]]) -> Tuple[str, ...]:
    """**MR-4** — each group's case, recomputed BITWISE from the raw fresh coordinates.

    ``require_supported_case`` is the authoritative Slice-1 gate (it refuses a sub-grid group); the
    per-group classification is read back so ``all_groups_exact`` is DERIVED here — never copied from
    the plan body, an artifact, a receipt or a caller assertion.
    """
    try:
        return require_supported_case(table, groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        code = getattr(exc, "failure_code", None)
        if code == "GROUP_MISMATCH":
            raise MergePredicateError("MP-3", str(exc)) from None
        raise MergePredicateError("MP-7", str(exc)) from None


def _verify_merge_preconditions(
    scene: SceneModel,
    report: Any,
    *,
    plan: Any,
    correction: Any,
    params: Dict[str, Any],
    plan_id_recomputed: str,
    artifact: AuthorizationArtifact,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """MP-1, MP-3…MP-9 on the FRESH pre-mutation evidence, plus the authoritative MP-10.

    Evaluated in the order design §6 mandates (``Order:`` paragraph): target resolution, then
    group/survivor/mapping, then the authorization gate re-run against fresh evidence, then the
    prediction. Every comparison target is the PLAN BODY; every piece of evidence is re-derived here
    from the fresh ``SceneModel``/``SceneReport``. Nothing the plan declares (groups, survivor,
    mapping, digest, ``all_groups_exact``, ``predicted_topology_unchanged``) is used as evidence for
    the thing it is supposed to prove.
    """
    declared_mesh_id = params["mesh_id"]

    # ---- MP-1: target object + mesh resolve to EXACTLY one pair (identity never inferred) ----
    try:
        target_obj, mesh = _assert_target_mesh(scene, correction.object_id, declared_mesh_id)
    except PreconditionError as exc:
        raise MergePredicateError("MP-1", str(exc)) from None
    target_object_id = target_obj.object_id
    _merge_ok(result, "MP-1", f"target object/mesh resolved to ({target_object_id!r}, {mesh.mesh_id!r})")
    result["target_object_mesh"] = {"object_id": target_object_id, "mesh_id": mesh.mesh_id}

    table = mesh.vertices
    vertex_count = len(table)
    result["pre_vertex_count"] = vertex_count

    # ---- MR-1 / MR-2: derive the fresh pairs and their transitive groups (evidence first) ----
    fresh_pairs = _merge_pairs_from_report(report, mesh.mesh_id)
    fresh_groups = _merge_groups_from_pairs(fresh_pairs)
    try:
        fresh_groups = validate_duplicate_groups(fresh_groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        raise MergePredicateError("MP-3", f"the re-derived group set is not canonical: {exc}") from None
    for member in (member for group in fresh_groups for member in group):
        if member >= vertex_count:
            raise MergePredicateError(
                "MP-3",
                f"a re-derived group member {member} is outside the fresh vertex table "
                f"({vertex_count} vertices)",
            )
    # ---- F-1 REMEDIATION: an EMPTY authoritative group set is NOT an executable merge ----------
    # Design §10 pins `duplicate_groups` as "empty iff result != \"COMPLETED\"". A merger that finds
    # no duplicate vertex has nothing to consolidate, so executing it would (a) emit a COMPLETED
    # receipt that violates that rule and (b) invoke the bounded mutator for a correction with ZERO
    # authorized groups. The capability's own dispatch intent is the same: the planner maps "no
    # duplicate-vertex finding" to NO_CORRECTIONS with no proposal at all (Slice-2 PART I). The
    # empty set is therefore refused HERE — before any mutation, with the mutator invoked zero
    # times — instead of being silently converted into a successful no-op.
    # Reported as MP-3 (group integrity) because the design defines no MP for this state: an empty
    # set is not an admissible group set, and §10 restricts `failure_code` to the Authorization*/
    # MP-n/MQ-n vocabulary, so no new token is invented here. The exact state is spelled out in the
    # reason so the two MP-3 conditions are never confusable. Open item for a future design
    # revision: pin a dedicated token for "nothing to merge" (mirroring the OI-4 treatment).
    if not fresh_groups:
        raise MergePredicateError(
            "MP-3",
            "the fresh authoritative duplicate-group set is EMPTY: there is no duplicate vertex to "
            "consolidate, so no merge is admissible. Exiting without mutation rather than reporting "
            "a no-op as COMPLETED (design §10 requires duplicate_groups to be non-empty whenever "
            'result == "COMPLETED").',
        )
    kept = _merge_kept_indices(vertex_count, fresh_groups)
    removed = tuple(index for index in range(vertex_count) if index not in set(kept))

    # ---- MP-3: the plan's declared groups EQUAL the re-derived groups (order-independent) ----
    try:
        declared_groups = validate_duplicate_groups(params["duplicate_groups"], mesh_id=mesh.mesh_id)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        raise MergePredicateError("MP-3", f"the plan's duplicate_groups are not canonical: {exc}") from None
    if declared_groups != fresh_groups:
        raise MergePredicateError(
            "MP-3",
            "the plan's duplicate groups do not equal the groups re-derived from fresh evidence "
            f"(plan={[list(g) for g in declared_groups]}, fresh={[list(g) for g in fresh_groups]})",
        )
    try:
        declared_pairs = tuple(
            sorted((min(pair[0], pair[1]), max(pair[0], pair[1]))
                   for pair in params["recorded_pairs"])
        )
    except Exception:  # noqa: BLE001 - malformed pairs were already rejected by the allowlist
        raise MergePredicateError("MP-3", "the plan's recorded_pairs could not be canonicalized") from None
    if declared_pairs != fresh_pairs:
        raise MergePredicateError(
            "MP-3",
            "the plan's recorded pairs do not equal the pairs re-derived from fresh evidence "
            f"(plan={[list(p) for p in declared_pairs]}, fresh={[list(p) for p in fresh_pairs]})",
        )
    _merge_ok(result, "MP-3", f"{len(fresh_groups)} group(s) and their pairs re-derived and matched the plan")
    result["duplicate_groups"] = [list(group) for group in fresh_groups]

    # ---- MP-4 / MR-3: every declared survivor is exactly min(G) (no fallback survivor) ----
    fresh_survivors = canonical_survivor_indices(fresh_groups)
    try:
        declared_survivors = validate_survivor_indices(params["survivor_indices"], fresh_groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        raise MergePredicateError("MP-4", str(exc)) from None
    if declared_survivors != fresh_survivors:
        raise MergePredicateError(
            "MP-4",
            f"the plan's survivors {list(declared_survivors)} do not equal the canonical "
            f"min(group) survivors {list(fresh_survivors)} re-derived from fresh evidence",
        )
    _merge_ok(result, "MP-4", f"{len(fresh_survivors)} canonical survivor(s) matched the plan")
    result["survivor_indices"] = list(fresh_survivors)
    result["removed_vertex_indices"] = [index for index in removed]

    # ---- MP-5: no face may reference TWO members of one group (unrepresentable post-state) ----
    for face_index, face in enumerate(mesh.faces):
        for group in fresh_groups:
            members = set(group)
            if sum(1 for member in face if member in members) >= 2:
                raise MergePredicateError(
                    "MP-5",
                    f"face[{face_index}] references two members of group {list(group)}; the "
                    "post-state would repeat an index and is unrepresentable",
                )
    _merge_ok(result, "MP-5", "no face references two members of one group")

    # ---- MP-6: completeness — the groups cover EVERY duplicate pair the table proves ----
    implied = _merge_pairs_implied_by_table(table)
    invented = sorted(set(fresh_pairs) - implied)
    if invented:
        raise MergePredicateError(
            "MP-6",
            "fresh findings declare duplicate pair(s) the authoritative vertex table does not "
            f"support (invented evidence): {[list(pair) for pair in invented]}",
        )
    missing = sorted(implied - set(fresh_pairs))
    if missing:
        raise MergePredicateError(
            "MP-6",
            "fresh findings omit duplicate pair(s) the authoritative vertex table proves, so a "
            f"complete group set cannot be derived: {[list(pair) for pair in missing]}",
        )
    expected_kept_count = vertex_count - sum(len(group) - 1 for group in fresh_groups)
    if len(kept) != expected_kept_count:
        raise MergePredicateError(
            "MP-6",
            f"the re-derived kept set has {len(kept)} entries but the vertex-count identity "
            f"requires {expected_kept_count}",
        )
    _merge_ok(result, "MP-6", f"complete coverage; kept set has {len(kept)} of {vertex_count} vertices")

    # ---- MP-7 / MR-4: every group is EXACT-BIT, classified BITWISE from the raw coordinates ----
    cases = _merge_cases(table, fresh_groups)
    all_groups_exact = all(case == MERGE_CASE_EXACT for case in cases)
    if not all_groups_exact:
        raise MergePredicateError(
            "MP-7",
            "at least one re-derived group is not EXACT-BIT; sub-grid collapse is unsupported and "
            "stays review-only",
        )
    _merge_ok(result, "MP-7", "every group is EXACT-BIT (classified bitwise on the fresh vertex table)")

    # ---- MP-8 / MR-5: the canonical mapping and its digest recomputed, then matched to the plan --
    fresh_mapping = make_index_mapping(vertex_count, fresh_groups)
    fresh_digest = mapping_digest(mesh.mesh_id, vertex_count, fresh_mapping)
    try:
        validate_index_mapping(fresh_mapping, mesh_id=mesh.mesh_id, vertex_count=vertex_count,
                               groups=fresh_groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        raise MergePredicateError("MP-8", f"the re-derived mapping is not canonical: {exc}") from None
    if mapping_digest(mesh.mesh_id, vertex_count, fresh_mapping) != fresh_digest:
        raise MergePredicateError("MP-8", "the re-derived mapping digest is not stable")
    if params["mapping_digest"] != fresh_digest:
        raise MergePredicateError(
            "MP-8",
            "the plan's mapping digest does not equal the digest recomputed from fresh evidence "
            f"(plan={params['mapping_digest'][:16]}…, fresh={fresh_digest[:16]}…)",
        )
    try:
        declared_mapping = validate_index_mapping(
            params["old_to_new_mapping"], mesh_id=mesh.mesh_id, vertex_count=vertex_count,
            groups=fresh_groups,
        )
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        raise MergePredicateError("MP-8", str(exc)) from None
    if declared_mapping != fresh_mapping:
        raise MergePredicateError(
            "MP-8",
            "the plan's old_to_new_mapping does not equal the canonical mapping recomputed from "
            "fresh evidence",
        )
    _merge_ok(result, "MP-8", f"canonical mapping digest {fresh_digest[:16]}… recomputed and matched")
    result["old_to_new_mapping"] = [int(entry) for entry in fresh_mapping]
    result["old_to_new_mapping_digest"] = fresh_digest

    # ---- MP-10 (authoritative): the artifact re-verified against the FRESH evidence ----
    # The pre-gate in the entry point bound the artifact to the plan BEFORE any engine contact, so
    # "no engine contact before the authorization gate" holds. Here the SAME gate is re-evaluated
    # with freshly recomputed values — including the operator's optional redundant
    # `expected_merge_mapping_digest` assertion, which is verified against the fresh digest and is
    # never authority. No mutation may follow a failure of this evaluation.
    work = MergePresentedWork(
        correction_type=correction.correction_type,
        correction_id=correction.correction_id,
        plan_id=plan_id_recomputed,
        source_report_digest=plan.source_report_digest,
        target_object_mesh={"object_id": target_object_id, "mesh_id": mesh.mesh_id},
        duplicate_groups=fresh_groups,
        plan_target_object_mesh=(
            {"object_id": correction.object_id, "mesh_id": declared_mesh_id}
            if correction.object_id is not None else None
        ),
        mapping_digest=fresh_digest,
        all_groups_exact=all_groups_exact,
    )
    try:
        verdict = verify_merge_authorization(artifact, work)
    except CorrectionPlannerError as exc:
        raise MergePredicateError(
            "MP-10", f"the authorization gate raised a contract error: {exc}"
        ) from None
    if not verdict.ok:
        specific = verdict.failure_code or "AUTHORIZATION_INVALID"
        result["failure_code"] = specific
        raise MergePredicateError(
            "MP-10",
            "the authorization gate rejected the presented artifact against fresh evidence "
            f"({verdict.failure_code}; outcome {verdict.outcome})",
            failure_code=specific,
        )

    # ---- MP-9 / MR-6: predict the exact post-state and run the KERNEL's own predicates ----
    predicted_vertices, predicted_faces = _merge_predicted_tables(mesh, fresh_mapping, kept)
    for face_index, face in enumerate(predicted_faces):
        for member in face:
            if member < 0 or member >= len(kept):
                raise MergePredicateError(
                    "MP-9",
                    f"predicted face[{face_index}] references post-state vertex {member} outside "
                    f"[0, {len(kept)}); the post-state is unrepresentable",
                )
    try:
        predicted_mesh = _merge_predicted_mesh(mesh, predicted_vertices, predicted_faces)
    except Exception as exc:  # noqa: BLE001 - an unrepresentable predicted state refuses, never raises
        raise MergePredicateError(
            "MP-9", f"the predicted post-state is not representable: {exc}"
        ) from None
    predicted_findings = tuple(check_mesh(predicted_mesh))
    pre_findings = tuple(check_mesh(mesh))
    delta = _merge_topology_delta(pre_findings, predicted_findings)
    if delta["duplicate_vertex_remaining"]:
        raise MergePredicateError(
            "MP-9",
            "the predicted post-state still contains a duplicate-vertex finding, so the re-derived "
            "groups do not cover every duplicate on this mesh",
        )
    if delta["newly_created_topology"]:
        raise MergePredicateError(
            "MP-9",
            "the predicted post-state creates a new finding of topology class(es) "
            f"{delta['newly_created_topology']}; the merge is refused rather than repaired",
        )
    if delta["new_codes"] or delta["cleared_codes"]:
        raise MergePredicateError(
            "MP-9",
            f"the predicted post-state introduces {delta['new_codes'] or 'no'} new finding class(es) "
            f"and clears {delta['cleared_codes'] or 'no'} pre-existing class(es); the merge is refused "
            "rather than repaired",
        )
    _merge_ok(result, "MP-9",
              "the predicted post-state is representable and introduces no new finding class")

    return {
        "target_obj": target_obj,
        "mesh": mesh,
        "table": table,
        "vertex_count": vertex_count,
        "groups": fresh_groups,
        "survivors": fresh_survivors,
        "kept": kept,
        "removed": removed,
        "mapping": fresh_mapping,
        "mapping_digest": fresh_digest,
        "all_groups_exact": all_groups_exact,
        "cases": cases,
        "predicted_vertices": predicted_vertices,
        "predicted_faces": predicted_faces,
        "pre_findings": pre_findings,
        "predicted_findings": predicted_findings,
    }
# ---------------------------------------------------------------------------
# MQ-1…MQ-7 — postconditions evaluated on the FRESH post-mutation evidence (design §5).
# The pre-mutation snapshot below is the merge-specific one: §5 G/H require MORE identity than the
# shared Wave-1 `_build_snapshot` records (materials, local_frame_id, and every scene-level field),
# so it is captured here rather than by widening a helper the Wave-1/Wave-2 paths depend on.
# ---------------------------------------------------------------------------

def _merge_object_identity_key(obj: ObjectModel) -> Tuple[Any, ...]:
    """The object identity MQ-5 requires to be unchanged (design §5 G)."""
    return (
        obj.object_id,
        obj.name,
        obj.collection,
        obj.parent_object_id,
        tuple(obj.location),
        tuple(obj.scale),
        tuple(obj.rotation),
        obj.visible,
    )


def _merge_opt_seq(value: Any) -> Optional[Tuple[Any, ...]]:
    """A comparable frozen form of an OPTIONAL mesh sequence.

    ``MeshModel.normals``/``uvs`` are ``None`` when the extraction carried none (the common case —
    the extraction has no normals), so ``tuple(value)`` would raise. ``None`` is preserved as ``None``
    and is part of the compared state: a post-state that suddenly acquired normals is a difference and
    must fail MQ-5/MQ-6 rather than silently compare equal to an empty tuple.
    """
    if value is None:
        return None
    return tuple(value)


def _merge_mesh_identity_key(mesh: Optional[MeshModel]) -> Optional[Tuple[Any, ...]]:
    """The mesh identity MQ-5 requires to be unchanged: everything EXCEPT the vertex/face tables."""
    if mesh is None:
        return None
    return (
        mesh.mesh_id,
        _merge_opt_seq(mesh.normals),
        _merge_opt_seq(mesh.uvs),
        tuple(mesh.materials),
        mesh.local_frame_id,
    )


def _merge_mesh_state_key(mesh: Optional[MeshModel]) -> Optional[Tuple[Any, ...]]:
    """The FULL mesh state MQ-6 requires to be bit-identical for every UNRELATED mesh."""
    if mesh is None:
        return None
    return (
        mesh.mesh_id,
        tuple(mesh.vertices),
        tuple(mesh.faces),
        _merge_opt_seq(mesh.normals),
        _merge_opt_seq(mesh.uvs),
        tuple(mesh.materials),
        mesh.local_frame_id,
    )


def _merge_build_snapshot(scene: SceneModel, mesh_id: str, source_report_digest: str) -> Dict[str, Any]:
    """The immutable pre-mutation merge snapshot (design §5 G/H).

    Captures: every scene-level field, the object ORDER, the target object's identity, the target
    mesh's non-topology identity, and each UNRELATED object's full object+mesh state. Comparison is
    by ``==`` on these frozen tuples, so a single changed float anywhere fails MQ-6.
    """
    target_id = None
    for obj in scene.objects:
        if obj.mesh is not None and obj.mesh.mesh_id == mesh_id:
            target_id = obj.object_id
            break
    return {
        "scene_id": scene.scene_id,
        "unit_system": scene.unit_system,
        "coordinate_frame": scene.coordinate_frame,
        "world_bounds": (
            (tuple(scene.world_bounds[0]), tuple(scene.world_bounds[1]))
            if scene.world_bounds is not None else None
        ),
        "ordered_object_ids": tuple(obj.object_id for obj in scene.objects),
        "target_object_id": target_id,
        "target_object_identity": _merge_object_identity_key(
            next(obj for obj in scene.objects if obj.object_id == target_id)
        ) if target_id is not None else None,
        "target_mesh_identity": _merge_mesh_identity_key(
            next(obj.mesh for obj in scene.objects if obj.object_id == target_id)
        ) if target_id is not None else None,
        "unrelated": {
            obj.object_id: (_merge_object_identity_key(obj), _merge_mesh_state_key(obj.mesh))
            for obj in scene.objects if obj.object_id != target_id
        },
        "source_report_digest": source_report_digest,
    }


def _verify_merge_postconditions(
    fresh_scene: SceneModel,
    fresh_report: Any,
    *,
    snapshot: Dict[str, Any],
    ctx: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """MQ-1…MQ-7 on the FRESH post-mutation state (design §5 A/B/C/F/G/H/I).

    Never evaluated on the plan's claims, never on the mutator's return value. The order is the
    design's own §5 order: MQ-1, MQ-2, MQ-3, MQ-4, MQ-5, MQ-6, MQ-7. The face-count pin (§5 D) is
    enforced inside MQ-3 (no face added/removed/reordered/re-looped) and the vertex-count identity
    ``m == n - sum(|G|-1)`` is enforced inside MQ-1.
    """
    mesh_id = ctx["mesh_id"]
    object_id = ctx["target_object_id"]
    pre_vertices = ctx["table"]
    pre_faces = ctx["mesh"].faces
    groups = ctx["groups"]
    mapping = ctx["mapping"]
    kept = ctx["kept"]
    vertex_count = ctx["vertex_count"]

    try:
        post_obj, post_mesh = _assert_target_mesh(fresh_scene, object_id, mesh_id)
    except PreconditionError as exc:
        raise MergePostconditionError("MQ-5", f"the target is unresolvable post-mutation: {exc}") from None
    post_vertices = post_mesh.vertices
    post_faces = post_mesh.faces

    # ---- MQ-1: the vertex table is EXACTLY the ordered surviving subsequence (bitwise) ----
    expected_vertices = tuple(tuple(pre_vertices[survivor]) for survivor in kept)
    if len(post_vertices) != len(kept):
        raise MergePostconditionError(
            "MQ-1",
            f"the post-state has {len(post_vertices)} vertices but the merge must keep "
            f"{len(kept)} (= {vertex_count} - {sum(len(g) - 1 for g in groups)})",
        )
    if tuple(tuple(v) for v in post_vertices) != expected_vertices:
        raise MergePostconditionError(
            "MQ-1",
            "the post-state vertex table is not the exact ordered surviving subsequence of the "
            "pre-state (a coordinate changed value, or the kept set differs)",
        )
    if len(post_vertices) != vertex_count - sum(len(group) - 1 for group in groups):
        raise MergePostconditionError("MQ-1", "the vertex-count identity m = n - sum(|G|-1) does not hold")
    result["post_vertex_count"] = len(post_vertices)
    result["postcondition_results"].append({
        "ok": True,
        "reason": f"MQ-1: vertex table is the exact ordered surviving subsequence ({len(kept)} of {vertex_count})",
    })

    # ---- MQ-2: re-derive sigma/rho from (pre, post) + groups and bind every recorded digest ----
    rederived: list = []
    for index in range(vertex_count):
        survivor = mapping[index] if index < len(mapping) else None
        if survivor is None:
            raise MergePostconditionError("MQ-2", f"pre index {index} has no re-derived target")
        rederived.append(survivor)
    if tuple(rederived) != mapping:
        raise MergePostconditionError(
            "MQ-2", "the mapping re-derived from the post-state does not equal the canonical mapping"
        )
    survivor_of = _merge_survivor_of(groups)
    for survivor in canonical_survivor_indices(groups):
        if mapping[survivor] != mapping[survivor_of.get(survivor, survivor)]:
            raise MergePostconditionError("MQ-2", f"survivor {survivor} does not map to itself")
    for removed_index in ctx["removed"]:
        if mapping[removed_index] != mapping[survivor_of[removed_index]]:
            raise MergePostconditionError(
                "MQ-2", f"removed duplicate {removed_index} does not map to its group's survivor"
            )
    post_digest = mapping_digest(mesh_id, vertex_count, mapping)
    if post_digest != ctx["mapping_digest"]:
        raise MergePostconditionError("MQ-2", "the mapping digest is not stable across the mutation")
    if post_digest != ctx["plan_mapping_digest"]:
        raise MergePostconditionError(
            "MQ-2", "the recomputed mapping digest does not equal the digest recorded in the plan"
        )
    if ctx["expected_mapping_digest"] is not None and post_digest != ctx["expected_mapping_digest"]:
        raise MergePostconditionError(
            "MQ-2",
            "the recomputed mapping digest does not equal the authorization's "
            "expected_merge_mapping_digest assertion",
        )
    result["postcondition_results"].append({
        "ok": True, "reason": f"MQ-2: canonical mapping digest {post_digest[:16]}… re-derived and matched",
    })

    # ---- MQ-3: every face is the elementwise substitution; no face added/removed/reordered ----
    if len(post_faces) != len(pre_faces):
        raise MergePostconditionError(
            "MQ-3",
            f"the post-state has {len(post_faces)} faces but the pre-state had {len(pre_faces)}; a "
            "merge never adds or removes a face",
        )
    changed_faces: list = []
    for face_index, pre_face in enumerate(pre_faces):
        expected_face = tuple(mapping[member] for member in pre_face)
        observed = tuple(post_faces[face_index])
        if len(observed) != len(pre_face):
            raise MergePostconditionError(
                "MQ-3",
                f"face[{face_index}] has {len(observed)} loops post-mutation but {len(pre_face)} "
                "pre-mutation; loop structure must be preserved",
            )
        if observed != expected_face:
            raise MergePostconditionError(
                "MQ-3",
                f"face[{face_index}] is not the elementwise rho∘sigma substitution "
                f"(expected {list(expected_face)}, observed {list(observed)})",
            )
        if observed != tuple(pre_face):
            changed_faces.append(face_index)
    result["changed_face_indices"] = changed_faces
    result["postcondition_results"].append({
        "ok": True,
        "reason": f"MQ-3: all {len(pre_faces)} faces preserved and remapped elementwise "
                  f"({len(changed_faces)} renumbered)",
    })

    # ---- MQ-4: the merge created no new non-manifold edge (and cleared none) ----
    pre_mesh_findings = ctx["pre_findings"]
    post_mesh_findings = tuple(check_mesh(post_mesh))
    pre_delta = _merge_code_histogram(pre_mesh_findings)
    post_delta = _merge_code_histogram(post_mesh_findings)
    if post_delta.get("MESH_NON_MANIFOLD_EDGE", 0) > pre_delta.get("MESH_NON_MANIFOLD_EDGE", 0):
        raise MergePostconditionError(
            "MQ-4",
            "the mutation created a new MESH_NON_MANIFOLD_EDGE finding "
            f"({pre_delta.get('MESH_NON_MANIFOLD_EDGE', 0)} -> "
            f"{post_delta.get('MESH_NON_MANIFOLD_EDGE', 0)})",
        )
    result["postcondition_results"].append({
        "ok": True, "reason": "MQ-4: no new non-manifold edge was created",
    })

    # ---- MQ-5: object/mesh identity unchanged (the datablock may be replaced; identity may not) --
    if _merge_object_identity_key(post_obj) != snapshot["target_object_identity"]:
        raise MergePostconditionError(
            "MQ-5", "the target object's identity fields changed across the mutation"
        )
    if _merge_mesh_identity_key(post_mesh) != snapshot["target_mesh_identity"]:
        raise MergePostconditionError(
            "MQ-5", "the target mesh's identity fields (mesh_id/normals/uvs/materials/local_frame_id) changed"
        )
    result["postcondition_results"].append({
        "ok": True, "reason": "MQ-5: target object and mesh identity fields are unchanged",
    })

    # ---- MQ-6: every unrelated object/mesh bit-identical; order and scene fields unchanged ----
    if (fresh_scene.scene_id, fresh_scene.unit_system, fresh_scene.coordinate_frame
            ) != (snapshot["scene_id"], snapshot["unit_system"], snapshot["coordinate_frame"]):
        raise MergePostconditionError("MQ-6", "a scene-level identity field changed across the mutation")
    fresh_bounds = (
        (tuple(fresh_scene.world_bounds[0]), tuple(fresh_scene.world_bounds[1]))
        if fresh_scene.world_bounds is not None else None
    )
    if fresh_bounds != snapshot["world_bounds"]:
        raise MergePostconditionError("MQ-6", "scene.world_bounds changed across the mutation")
    fresh_order = tuple(obj.object_id for obj in fresh_scene.objects)
    if fresh_order != snapshot["ordered_object_ids"]:
        raise MergePostconditionError(
            "MQ-6", "the object ordering changed across the mutation (objects were added, removed or reordered)"
        )
    fresh_unrelated = {
        obj.object_id: (_merge_object_identity_key(obj), _merge_mesh_state_key(obj.mesh))
        for obj in fresh_scene.objects if obj.object_id != object_id
    }
    if fresh_unrelated != snapshot["unrelated"]:
        differing = sorted(
            key for key in set(fresh_unrelated) | set(snapshot["unrelated"])
            if fresh_unrelated.get(key) != snapshot["unrelated"].get(key)
        )
        raise MergePostconditionError(
            "MQ-6", f"unrelated object state changed for {differing}; no other object may be touched"
        )
    result["postcondition_results"].append({
        "ok": True,
        "reason": f"MQ-6: {len(fresh_unrelated)} unrelated object(s) bit-identical, order and scene fields unchanged",
    })

    # ---- MQ-7: the target mesh's finding delta is exactly the intended one -------------------
    # PRESENCE SEMANTICS (B-1 remediation, 2026-09-13). Design §5I defines "exactly preserved" by its
    # own gloss — a merge "neither creates nor clears them" — and names a *disappearance* as the
    # deviation. This postcondition is therefore CLASS-level (created / cleared) and deliberately does
    # NOT compare raw `measured` payloads. The authorized merge is an INDEX RENUMBERING, and §4 states
    # outright that "Index-keyed properties CAN change, because the indices themselves are
    # renumbered": a pre-existing winding / non-manifold / duplicate-face finding that names a
    # renumbered vertex index necessarily carries a different `measured` payload post-mutation while
    # the finding itself is neither created nor cleared. Comparing those payloads rejected a
    # contract-legal merge AFTER the single mutation, with no rollback authority — which the cleared
    # design's fail-closed-before-mutation rule forbids (independent Slice-3 gate, blocker B-1).
    # This is redundant, not weaker: §4 proves no pre-existing finding of another class can be CLEARED
    # by the substitution (a pre edge maps to exactly one post edge, so an edge's face valence never
    # decreases; equal duplicate-face keys stay equal; a same-direction two-face edge stays
    # same-direction), the count of such a class can only stay equal or grow, and MP-9 evaluates this
    # very created/cleared delta on the EXACT predicted post-state BEFORE any mutation — for EVERY
    # code, not only the four topology classes. Because MQ-1 and MQ-3 pin the observed post-state to
    # that same prediction, this is a defence-in-depth re-check of the pre-mutation verdict on observed
    # evidence, never a second, stricter policy.
    if post_delta.get(_MERGE_FINDING_CODE, 0) != 0:
        raise MergePostconditionError(
            "MQ-7",
            f"{post_delta.get(_MERGE_FINDING_CODE, 0)} MESH_DUPLICATE_VERTEX finding(s) remain on the "
            "target mesh after the merge",
        )
    delta = _merge_topology_delta(pre_mesh_findings, post_mesh_findings)
    if delta["new_codes"]:
        raise MergePostconditionError(
            "MQ-7", f"the mutation introduced new finding class(es) {delta['new_codes']} on the target mesh"
        )
    if delta["cleared_codes"]:
        raise MergePostconditionError(
            "MQ-7",
            f"the mutation cleared pre-existing finding class(es) {delta['cleared_codes']} on the target "
            "mesh; a merge may not repair anything as a side effect",
        )
    result["postcondition_results"].append({
        "ok": True,
        "reason": "MQ-7: all duplicate-vertex findings cleared; no finding class created or cleared on "
                  "the target mesh (measured payload indexes may be renumbered by the authorized "
                  "mapping — design §4/§5I)",
    })

    return {
        "post_mesh": post_mesh,
        "post_findings": post_mesh_findings,
        "changed_face_indices": changed_faces,
        "post_vertex_count": len(post_vertices),
        "mapping_digest": post_digest,
    }

def _merge_apply_finding_evidence(
    result: Dict[str, Any], prefix: str, report: Any, mesh_id: str
) -> None:
    """Populate the §10 pre/post finding lists for the target mesh, in the report's canonical order."""
    result[f"{prefix}_duplicate_vertex_findings"] = _merge_finding_snapshots(
        _merge_mesh_findings(report, mesh_id, _MERGE_RECEIPT_FINDING_CODES["duplicate_vertex"])
    )
    result[f"{prefix}_duplicate_face_findings"] = _merge_finding_snapshots(
        _merge_mesh_findings(report, mesh_id, _MERGE_RECEIPT_FINDING_CODES["duplicate_face"])
    )
    result[f"{prefix}_degenerate_face_findings"] = _merge_finding_snapshots(
        _merge_mesh_findings(report, mesh_id, _MERGE_RECEIPT_FINDING_CODES["degenerate_face"])
    )
    result[f"{prefix}_non_manifold_findings"] = _merge_finding_snapshots(
        _merge_mesh_findings(report, mesh_id, _MERGE_RECEIPT_FINDING_CODES["non_manifold"])
    )
    result[f"{prefix}_winding_findings"] = _merge_finding_snapshots(
        _merge_mesh_findings(report, mesh_id, _MERGE_RECEIPT_FINDING_CODES["winding"])
    )


def execute_merge_vertex(
    *,
    engine_state: Any,
    plan: Any,
    authorization: Any,
    mutator: Optional[Callable[..., None]] = None,
    extractor: Callable[[Any], Tuple[SceneModel, Any]] = extract_and_report,
) -> Dict[str, Any]:
    """Execute a REPAIR_MERGE_VERTEX plan — WAVE 3, human-authorized, deterministic, topology-only.

    ``authorization`` is MANDATORY BY CONSTRUCTION (keyword-only, no default): a caller cannot invoke
    this entry point without deciding what artifact to present, and passing ``None`` yields
    ``AUTHORIZATION_REQUIRED`` — never an execution (design §6 MP-10 / §8).

    **``AUTHORIZATION_VERIFIED`` does not mean ``PLAN_CORRECTNESS_VERIFIED``.** The artifact binds
    only ``correction_type``/``correction_id``/``plan_id``/``source_report_digest``; it proves nothing
    about the plan body it names. This entry point therefore re-derives, from the FRESH authoritative
    ``SceneModel`` + ``SceneReport``, the target, the duplicate groups, the exact-bit/sub-grid status,
    the survivor, the mapping, the mapping digest and the predicted topology consequences (design
    MR-1…MR-6), and refuses on ANY mismatch with the plan (MP-1, MP-3…MP-9) **before** the mutation.
    No caller-supplied ``all_groups_exact``, mapping, survivor, digest or ``predicted_topology_unchanged``
    value is ever treated as evidence for the thing it asserts.

    Exactly ONE bounded merge mutation is performed, by the INJECTED mutator (never by this module,
    which imports no ``bpy``). There is no retry, no fallback survivor, no second group, no cascade
    repair and no automatic cleanup: a postcondition failure returns ``POSTCONDITION_FAILED`` with the
    failed predicate recorded, and never "fixes" what it broke.

    The receipt is AUDIT DATA ONLY: it grants no authorization, persistence, rollback or recovery
    authority, and this executor never reads a receipt as input.
    """
    result = _merge_receipt_skeleton(plan)
    result["authorization_verified"] = False
    try:
        # ---- MP-2: plan integrity (recompute; a plan body is never evidence about itself) ----
        if plan is None or not hasattr(plan, "source_report_digest") or not hasattr(plan, "plan_id"):
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "PLAN_INVALID",
                               "plan is missing its integrity fields")
        try:
            recomputed_plan_id = plan._compute_plan_id()
        except Exception:  # noqa: BLE001 - an un-recomputable plan is not executable
            recomputed_plan_id = None
        if recomputed_plan_id is None or recomputed_plan_id != plan.plan_id:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "PLAN_ID_MISMATCH",
                               "plan_id does not match the recomputed canonical plan contents")
        result["plan_id_recomputed"] = recomputed_plan_id

        corrections = getattr(plan, "corrections", ())
        executable = [c for c in corrections if getattr(c, "correction_type", None) == _MERGE_OPERATION]
        result["skipped_correction_ids"] = [
            c.correction_id for c in corrections if getattr(c, "correction_type", None) != _MERGE_OPERATION
        ]
        if not executable:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "NO_EXECUTABLE_CORRECTION",
                               "the plan contains no REPAIR_MERGE_VERTEX correction")
        if len(executable) > 1:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID,
                               "AMBIGUOUS_MULTIPLE_EXECUTABLE_CORRECTIONS",
                               f"the plan contains {len(executable)} executable merge corrections; "
                               "exactly one is required (one mesh per pass, design §16)")
        corr = executable[0]
        if corr.correction_type not in _EXECUTABLE_TYPES:
            return _merge_fail(result, ExecutionOutcome.UNSAFE, "NOT_EXECUTABLE_TYPE",
                               "the correction type is not in the executor allowlist")
        if type(getattr(corr, "object_id", None)) is not str or not corr.object_id:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "TARGET_OBJECT_MISSING",
                               "the merge correction does not name a canonical target object_id; the "
                               "target pair is binding and is never guessed (design §10)")
        result["correction_id"] = corr.correction_id
        try:
            params = dict(corr.parameters)
        except Exception:  # noqa: BLE001 - a hostile parameter container fails closed
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "PARAMETERS_NOT_A_MAPPING",
                               "the merge correction parameters are not a mapping")
        failure = _validate_merge_params(params)
        if failure is not None:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, failure,
                               f"merge parameters failed the operation allowlist: {failure}")
        mesh_id = params["mesh_id"]
        _merge_ok(result, "MP-2", f"plan integrity verified; one executable merge correction ({corr.correction_id})")

        # ---- MP-10 (pre-gate): authorization, BEFORE any engine contact ----
        # Only plan-side values are available here; the gate is re-run authoritatively against fresh
        # evidence inside `_verify_merge_preconditions` (MP-10 there). The plan's declared groups,
        # mapping digest and `all_groups_exact` are passed as a PRESENTATION of the plan body — they
        # are advisory at this stage and are re-derived before anything may mutate.
        if authorization is None:
            return _merge_fail(result, ExecutionOutcome.AUTHORIZATION_REQUIRED, "AUTHORIZATION_REQUIRED",
                               "no authorization artifact was presented for a review-gated merge")
        artifact, parse_failure = _resolve_merge_authorization(authorization)
        if artifact is None:
            return _merge_fail(result, ExecutionOutcome.AUTHORIZATION_INVALID,
                               parse_failure or "AUTHORIZATION_INVALID",
                               "the presented authorization artifact is not a valid decision")
        result["authorization_digest"] = artifact.digest()
        result["authorization_policy_version"] = artifact.authorization_policy_version
        try:
            pre_work = MergePresentedWork(
                correction_type=corr.correction_type,
                correction_id=corr.correction_id,
                plan_id=recomputed_plan_id,
                source_report_digest=plan.source_report_digest,
                target_object_mesh={"object_id": corr.object_id, "mesh_id": mesh_id},
                duplicate_groups=params["duplicate_groups"],
                plan_target_object_mesh={"object_id": corr.object_id, "mesh_id": mesh_id},
                mapping_digest=params["mapping_digest"],
                all_groups_exact=params["all_groups_exact"],
            )
        except CorrectionPlannerError as exc:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "MERGE_BINDING_INVALID",
                               f"the plan's merge binding is not contract-shaped: {exc}")
        try:
            pre_verdict = verify_merge_authorization(artifact, pre_work)
        except CorrectionPlannerError as exc:
            return _merge_fail(result, ExecutionOutcome.PLAN_INVALID, "MERGE_BINDING_INVALID",
                               f"the plan's merge binding is not contract-shaped: {exc}")
        if not pre_verdict.ok:
            return _merge_fail(result, pre_verdict.outcome or ExecutionOutcome.AUTHORIZATION_INVALID,
                               pre_verdict.failure_code or "AUTHORIZATION_INVALID",
                               "the authorization gate rejected the presented artifact")
        _merge_ok(result, "MP-10",
                  f"authorization bound to the plan (pre-gate, no engine contact); "
                  f"policy {artifact.authorization_policy_version!r}")

        # ---- source binding: the first and only engine contact before the preconditions ----
        try:
            source_scene, source_report = extractor(engine_state)
            recomputed_digest = source_report.digest()
        except Exception:  # noqa: BLE001 - an unevidenced run must never proceed
            return _merge_fail(result, ExecutionOutcome.SOURCE_MISMATCH, "EXTRACTION_FAILED",
                               "the authoritative extraction failed")
        result["source_report_digest_recomputed"] = recomputed_digest
        if recomputed_digest != plan.source_report_digest:
            return _merge_fail(result, ExecutionOutcome.SOURCE_MISMATCH, "SOURCE_DIGEST_MISMATCH",
                               "the fresh extraction digest does not match the plan's source digest")

        # ---- MP-1, MP-3…MP-9 and the authoritative MP-10, all on fresh evidence ----
        try:
            ctx = _verify_merge_preconditions(
                source_scene, source_report, plan=plan, correction=corr, params=params,
                plan_id_recomputed=recomputed_plan_id, artifact=artifact, result=result,
            )
        except MergePredicateError as exc:
            return _merge_fail(
                result, ExecutionOutcome.PRECONDITION_FAILED,
                exc.failure_code or exc.predicate_id, f"{exc.predicate_id}: {exc.reason}",
                precondition=True,
            )
        result["authorization_verified"] = True   # the whole gate has now passed on fresh evidence
        target_obj = ctx["target_obj"]
        mesh = ctx["mesh"]
        result["target_object_mesh"] = {"object_id": target_obj.object_id, "mesh_id": mesh.mesh_id}
        result["pre_vertex_count"] = ctx["vertex_count"]
        _merge_apply_finding_evidence(result, "pre", source_report, mesh.mesh_id)

        # ---- immutable pre-mutation snapshot (design §5 G/H) ----
        snapshot = _merge_build_snapshot(source_scene, mesh.mesh_id, plan.source_report_digest)

        # ---- EXACTLY ONE bounded mutation (injected; stubbed in deterministic tests) ----
        _mutator = mutator if mutator is not None else _default_mutator(operation=_MERGE_OPERATION)
        try:
            _mutator(
                engine_state,
                object_id=target_obj.object_id,
                mesh_id=mesh.mesh_id,
                vertices=ctx["predicted_vertices"],
                faces=ctx["predicted_faces"],
                old_to_new_mapping=tuple(ctx["mapping"]),
            )
        except Exception:  # noqa: BLE001 - a failed mutation is a declared failure, never a crash
            return _merge_fail(result, ExecutionOutcome.MUTATION_FAILED, "MUTATION_FAILED",
                               "the bounded merge mutator failed")

        # ---- fresh post-mutation extraction + MQ-1…MQ-7 ----
        try:
            fresh_scene, fresh_report = extractor(engine_state)
        except Exception:  # noqa: BLE001
            return _merge_fail(result, ExecutionOutcome.MUTATION_FAILED, "POST_EXTRACTION_FAILED",
                               "the post-mutation extraction failed")
        result["output_report_digest"] = fresh_report.digest()
        result["postcondition_results"] = []
        post_ctx = dict(ctx)
        post_ctx["mesh_id"] = mesh.mesh_id
        post_ctx["target_object_id"] = target_obj.object_id
        post_ctx["plan_mapping_digest"] = params["mapping_digest"]
        post_ctx["expected_mapping_digest"] = artifact.expected_merge_mapping_digest
        try:
            observations = _verify_merge_postconditions(
                fresh_scene, fresh_report, snapshot=snapshot, ctx=post_ctx, result=result,
            )
        except MergePostconditionError as exc:
            # the mutation DID happen: record what was actually observed, so the receipt is
            # informative (audit data only — never a claim of success).
            try:
                _merge_apply_finding_evidence(result, "post", fresh_report, mesh.mesh_id)
            except Exception:  # noqa: BLE001 - recording is best-effort on a failure path
                pass
            return _merge_fail(result, ExecutionOutcome.POSTCONDITION_FAILED,
                               exc.predicate_id or "POSTCONDITION_FAILED",
                               f"{exc.predicate_id}: {exc.reason}", postcondition=True)
        except PreconditionError as exc:  # a post-state predicate raised a base-type failure
            return _merge_fail(result, ExecutionOutcome.POSTCONDITION_FAILED, "POSTCONDITION_FAILED",
                               str(exc), postcondition=True)

        _merge_apply_finding_evidence(result, "post", fresh_report, mesh.mesh_id)
        result["post_vertex_count"] = observations["post_vertex_count"]
        result["changed_face_indices"] = observations["changed_face_indices"]
        result["result"] = ExecutionOutcome.COMPLETED
        result["executed_correction_ids"] = [corr.correction_id]
        return result
    except Exception:  # noqa: BLE001 - fail closed on any unexpected error
        return _merge_fail(result, ExecutionOutcome.MUTATION_FAILED, "INTERNAL_ERROR",
                           "an unexpected error occurred; nothing was reported as completed")
