"""Deterministic Cleanup/Correction Planner (proposal engine only; never executes).

Consumes:

    SceneReport (or its canonical JSON)  +  SoccerFieldValidationProfile (policy/config only)

and produces a deterministic :class:`~planning.blender.correction_contract.CorrectionPlan`
containing ordered, dependency-resolved :class:`~planning.blender.correction_contract.CorrectionProposal`
objects. It NEVER executes, mutates, saves, rolls back, or imports bpy/Blender runners/authority —
it is a pure proposal engine whose output is suficient for a FUTURE separate controlled executor.

Deterministic contract:
- Same ``SceneReport`` + same ``planner_version`` + same profile → byte-identical plan.
- The plan binds to ``source_report_digest``; a plan for an unknown/changed report is rejected.
- Malformed input fails through the planner's declared error model (``CorrectionInputError`` /
  ``CorrectionPlannerError``), never by invoking arbitrary protocol behavior.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import json

from dataclasses import dataclass

from planning.blender.correction_codes import (
    CorrectionDeterminism,
    CorrectionRiskClass,
    PlannerState,
)
from planning.blender.correction_contract import CorrectionPlan, CorrectionProposal
from planning.blender.correction_dependencies import resolve
from planning.blender.correction_mapping import classify
from planning.blender.correction_values import (
    CorrectionInputError,
    CorrectionPlanError,
    _canonical_scalar,
    canonical_json_bytes,
    require_report_format_version,
)
from planning.blender.correction_authorization import (
    AuthorizationContractError,
    AuthorizationInputError,
    canonical_coincidence_key,
    canonical_survivor_indices,
    classify_duplicate_group_case,
    make_index_mapping,
    mapping_digest,
    require_supported_case,
    validate_duplicate_groups,
    validate_index_mapping,
)
from planning.blender.finding_codes import FindingCode, severity_of
from planning.blender.mesh_health import check_mesh
from planning.blender.scene_model import SceneReportInputError, parse_scene_report_input
from planning.blender.scene_report import REPORT_FORMAT_VERSION

PLANNER_VERSION = "1"


def _require_scene_report_payload(payload: Any) -> Dict[str, Any]:
    """Validate + extract the fields the planner reads from a SceneReport-shaped dict."""
    if type(payload) is not dict:
        raise CorrectionInputError("SceneReport input must be a dict")
    required = ("digest", "findings")
    missing = [k for k in required if k not in payload]
    if missing:
        raise CorrectionInputError(
            "SceneReport input missing required keys: " + ", ".join(sorted(missing))
        )
    digest = payload["digest"]
    # D2: the source_report_digest must be a SHA-256 (64 lowercase hex chars) — the documented
    # representation of SceneReport.digest(). A malformed non-empty arbitrary string is rejected
    # at the input boundary with the declared error model, never accepted into a plan's provenance.
    if type(digest) is not str or not _is_sha256_hex(digest):
        raise CorrectionInputError("SceneReport digest must be a 64-char lowercase SHA-256 hex string")
    if type(payload["findings"]) is not list:
        raise CorrectionInputError("SceneReport findings must be a list")
    # L1: MANDATORY planner-side digest recomputation (Wave-1 source provenance). The supplied
    # digest is a *claim*; recompute it from the report content and reject a mismatch. This is
    # exactly SceneReport.digest(): sha256(canonical JSON of to_json_compatible(), which is the
    # payload minus the injected 'digest' key).
    report_body = {k: v for k, v in payload.items() if k != "digest"}
    recomputed = _digest_of_report_body(report_body)
    if recomputed != digest:
        raise CorrectionInputError(
            "SceneReport source digest does not match the report content (forged/stale digest); "
            "refusing to bind a plan to an unverified source"
        )
    return payload


def _digest_of_report_body(body: Dict[str, Any]) -> str:
    """Recompute the SceneReport SHA-256 from its canonical JSON body (no 'digest' key)."""
    import hashlib

    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


def _finding_to_proposal(finding: Dict[str, Any], *, report_digest: str,
                         profile: Dict[str, Any], object_scope_optional: bool,
                         index: int) -> List[CorrectionProposal]:
    """Build 0..1 proposal for one finding (dict) using ONLY data actually present.

    Returns an EMPTY list when the finding is intentionally OUT_OF_SCOPE / UNSAFE / has no safe
    deterministic target (those are surfaced as planner state, NOT as a fabricated proposal).
    """
    code_raw = finding.get("code")
    if type(code_raw) is not str:
        raise CorrectionInputError(f"finding[{index}].code must be an exact str")
    try:
        code = FindingCode(code_raw)
    except ValueError:
        raise CorrectionInputError(f"unsupported finding code: {code_raw!r}") from None

    # measured/expected are canonical JSON-native via the report; exact-type guard here anyway.
    measured = finding.get("measured")
    expected = finding.get("expected")
    if type(measured) is not dict and measured is not None:
        raise CorrectionInputError(f"finding[{index}].measured must be a dict or None")
    if type(expected) is not dict and expected is not None:
        raise CorrectionInputError(f"finding[{index}].expected must be a dict or None")

    object_id = finding.get("object_id")
    mesh_id = finding.get("mesh_id")
    if object_id is not None and type(object_id) is not str:
        raise CorrectionInputError(f"finding[{index}].object_id must be str or None")
    if mesh_id is not None and type(mesh_id) is not str:
        raise CorrectionInputError(f"finding[{index}].mesh_id must be str or None")

    determinism, correction_type, risk, reversibility, auto_propose = classify(
        code, measured
    )

    # OUT_OF_SCOPE / UNSAFE / missing-target findings produce no proposal (surfaced as state).
    if not auto_propose or correction_type is None:
        return []

    # ---- deterministic parameterization from the ACTUAL finding data (never invent) ----
    parameters: Dict[str, Any] = {}
    if mesh_id is not None:
        parameters["mesh_id"] = mesh_id

    if code is FindingCode.MESH_DEGENERATE_FACE:
        face = (measured or {}).get("face")
        if face is None:
            raise CorrectionInputError(
                f"finding[{index}] {code} missing 'face'; cannot form a safe proposal"
            )
        parameters["face_id"] = face
        parameters["reason"] = "degenerate_face"
    elif code is FindingCode.MESH_DUPLICATE_FACE:
        faces = (measured or {}).get("face_a"), (measured or {}).get("face_b")
        if faces[0] is None or faces[1] is None:
            raise CorrectionInputError(
                f"finding[{index}] {code} missing face_a/face_b; cannot form a safe proposal"
            )
        parameters["face_ids"] = [faces[0], faces[1]]
        parameters["duplicate_relationship"] = "exact_duplicate"
    elif code is FindingCode.MESH_WINDING_INCONSISTENT:
        # WAVE 2 (§2.5 step L/M): winding proposals come ONLY from the aggregation pass
        # (``_aggregate_winding_corrections``); this per-finding path NEVER emits one, for D1, D2
        # and D3 meshes alike — there is no mesh with both a per-edge and an aggregated proposal.
        return []
    elif code is FindingCode.SCENE_UNIT_INVALID:
        current = (measured or {}).get("unit_system")
        expected_tok = None
        allowed = (expected or {}).get("allowed_units")
        if type(allowed) is list and allowed:
            # choose the canonical meters token deterministically if present
            for tok in allowed:
                if str(tok).upper() == "METERS":
                    expected_tok = "METERS"
                    break
        parameters["current_unit"] = current
        parameters["target_unit"] = expected_tok
        # An unambiguous target is required for a HEURISTIC auto proposal.
        if not expected_tok:
            return []  # no unambiguous canonical unit -> not auto-proposed (surfaces as review)
    elif code is FindingCode.OBJECT_NAME_INVALID:
        current_name = (measured or {}).get("name")
        pattern = (expected or {}).get("pattern")
        parameters["current_name"] = current_name
        parameters["proposed_name"] = _suggest_name(current_name, pattern)
        if not parameters["proposed_name"]:
            return []  # cannot deterministically propose a canonical name -> review
    else:
        # No parameterization rule for this code in auto-proposal path -> not auto-proposed.
        return []

    # requires_human_review: deterministic from risk class + design auto/suggest policy.
    requires_human_review = (risk != CorrectionRiskClass.FIDELITY_SAFE.value) or (
        code is FindingCode.OBJECT_NAME_INVALID
    )

    correction_id = _correction_id(code, object_id, mesh_id, parameters)
    return [
        CorrectionProposal(
            correction_id=correction_id,
            finding_code=code.value,
            object_id=object_id,
            mesh_id=mesh_id,
            correction_type=correction_type,
            parameters=parameters,
            rationale=("deterministic correction for finding " + code.value),
            preconditions=(
                {"source_report_digest": report_digest},
                {"finding_code": code.value},
                {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}},
            ),
            expected_postcondition={
                "finding_cleared": code.value,
                "unrelated_topology_unchanged": True,
            },
            risk=risk,
            # severity is fixed per code by the contract (severity_of); the finding-level value is
            # ignored and NOT a proposal input — the proposal always carries the canonical code
            # severity so a mismatched/spoofed finding severity can never leak through.
            severity=severity_of(code).value,
            reversibility=reversibility,
            dependencies=(),
            determinism=determinism,
            requires_human_review=requires_human_review,
            out_of_scope=False,
        )
    ]


# ---------------------------------------------------------------------------
# WAVE 2 — planner-side winding aggregation (design §2; the ONLY producer of
# REPAIR_FACE_WINDING proposals). The executor never aggregates.
# ---------------------------------------------------------------------------

WINDING_ORIENTATION = "reverse_designated_face_to_shared_edge_opposite"

# The exact, closed aggregated-parameter key set (design §2.2). No extra authority-bearing key may
# ever be added: the executor allowlists this set explicitly.
WINDING_PARAMETER_KEYS = (
    "mesh_id",
    "designated_face_index",
    "candidate_faces",
    "recorded_edges",
    "counterpart_faces",
    "orientation",
)


def _winding_identity(finding: Dict[str, Any], index: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Validate one winding finding and return its canonical identity ``(edge_c, pair_c)`` (§2.0).

    ``edge_c = (min(a,b), max(a,b))`` (undirected, canonical) and ``pair_c = tuple(sorted((f1,f2)))``
    (undirected face pair). Exact-int indices only: a non-int index (including ``bool``) is a
    malformed report, never a silently coerced one.
    """
    code_token = FindingCode.MESH_WINDING_INCONSISTENT.value
    measured = finding.get("measured")
    if type(measured) is not dict:
        raise CorrectionInputError(f"measured must be a dict carrying 'edge' and 'faces'")
    edge_raw = measured.get("edge")
    faces_raw = measured.get("faces")
    if type(edge_raw) not in (list, tuple) or len(edge_raw) != 2:
        raise CorrectionInputError(f"measured['edge'] must be a 2-element list of vertex indices")
    if type(faces_raw) not in (list, tuple) or len(faces_raw) != 2:
        raise CorrectionInputError(f"measured['faces'] must be a 2-element list of face indices")
    values = (edge_raw[0], edge_raw[1], faces_raw[0], faces_raw[1])
    for value in values:
        if type(value) is not int or value < 0:
            raise CorrectionInputError(
                f"measured edge/face indices must be non-negative exact ints (got {value!r})"
            )
    a, b, f1, f2 = values
    if a == b:
        raise CorrectionInputError(f"measured['edge'] must not be a self-loop ({a},{b})")
    if f1 == f2:
        raise CorrectionInputError(f"measured['faces'] must be two DISTINCT face indices")
    return (min(a, b), max(a, b)), tuple(sorted((f1, f2)))


def _aggregate_winding_corrections(
    winding_findings: List[Tuple[int, Dict[str, Any], Any]], *, report_digest: str
) -> Tuple[List[CorrectionProposal], List[str], List[str]]:
    """Aggregate ``MESH_WINDING_INCONSISTENT`` findings per mesh (design §2.1).

    Returns ``(proposals, planning_error_messages, review_only_meshes)`` where ``review_only_meshes``
    lists the meshes whose findings were deliberately NOT turned into a correction (D3: the
    candidate-face intersection is empty, so the findings "remain review-only" by design) — the
    caller must surface those as REVIEW_REQUIRED, never as NO_CORRECTIONS. Exactly ZERO or ONE winding proposal is
    produced per mesh: D1 (multiple findings with a single common face) or D2 (exactly one finding,
    requiring an authorization designation); D3 (an empty candidate-face intersection) produces no
    proposal at all and the findings remain review-only. Deterministic: findings are consumed in the
    canonical order the caller already established, identities are deduplicated, and the emitted
    parameter lists are canonically ordered.
    """
    code = FindingCode.MESH_WINDING_INCONSISTENT
    errors: List[str] = []
    per_mesh: Dict[str, Dict[str, Any]] = {}
    for index, finding, mesh_id in winding_findings:
        object_id = finding.get("object_id")
        try:
            edge, pair = _winding_identity(finding, index)
        except CorrectionInputError as exc:
            errors.append(f"finding[{index}] {code.value}: {exc}")
            continue
        if type(mesh_id) is not str or not mesh_id:
            errors.append(
                f"finding[{index}] {code.value}: mesh_id must be a non-empty str to aggregate a "
                "winding finding (never inferred)"
            )
            continue
        entry = per_mesh.get(mesh_id)
        if entry is None:
            entry = {"order": [], "seen": set(), "object_ids": [], "edges": {}, "conflict": False}
            per_mesh[mesh_id] = entry
        identity = (edge, pair)
        if identity in entry["seen"]:
            # §2.0: a repeated identity is the SAME finding and is counted once.
            continue
        entry["seen"].add(identity)
        entry["order"].append(identity)
        entry["object_ids"].append(object_id)
        if edge in entry["edges"] and entry["edges"][edge] != pair:
            # One canonical edge attributed to two different face pairs within a mesh cannot be
            # resolved into a positional counterpart mapping -> fail closed (never guessed).
            errors.append(
                f"finding[{index}] {code.value}: edge {list(edge)} is attributed to two different "
                "face pairs on mesh " + repr(mesh_id) + "; refusing to aggregate"
            )
            entry["conflict"] = True
        entry["edges"][edge] = pair

    proposals: List[CorrectionProposal] = []
    review_only_meshes: List[str] = []
    for mesh_id in sorted(per_mesh):
        entry = per_mesh[mesh_id]
        identities: List[Tuple[Tuple[int, int], Tuple[int, int]]] = entry["order"]
        if entry["conflict"] or not identities:
            continue
        distinct_object_ids = {oid for oid in entry["object_ids"]}
        if len(distinct_object_ids) != 1:
            errors.append(
                f"winding findings for mesh {mesh_id!r} disagree on object_id; "
                "refusing to aggregate (one owner per correction)"
            )
            continue
        object_id = entry["object_ids"][0]

        common = set(identities[0][1])
        for _edge, pair in identities[1:]:
            common &= set(pair)

        if len(identities) >= 2 and len(common) == 1:
            # ---- D1: evidence-designated single common face ----
            designated = sorted(common)[0]
            ordered = sorted(identities, key=lambda item: item[0])
            parameters: Dict[str, Any] = {
                "mesh_id": mesh_id,
                "designated_face_index": designated,
                "candidate_faces": None,
                "recorded_edges": [[edge[0], edge[1]] for edge, _pair in ordered],
                "counterpart_faces": [
                    pair[0] if pair[1] == designated else pair[1] for _edge, pair in ordered
                ],
                "orientation": WINDING_ORIENTATION,
            }
        elif len(identities) == 1:
            # ---- D2: one finding; the AUTHORIZATION designates one of the candidate pair ----
            edge, pair = identities[0]
            parameters = {
                "mesh_id": mesh_id,
                "designated_face_index": None,
                "candidate_faces": [pair[0], pair[1]],
                "recorded_edges": [[edge[0], edge[1]]],
                # the counterpart is the OTHER member of the canonical pair; the executor enforces
                # ``counterpart != designated_face``, so the designatable member is the other one.
                "counterpart_faces": [pair[1]],
                "orientation": WINDING_ORIENTATION,
            }
        else:
            # ---- D3: empty candidate-face intersection -> NO winding correction (§2.1 step E) ----
            # The findings REMAIN REVIEW-ONLY: this refusal must be visible as REVIEW_REQUIRED.
            review_only_meshes.append(mesh_id)
            continue

        if tuple(parameters.keys()) != WINDING_PARAMETER_KEYS:
            errors.append(
                f"internal parameter schema violation for mesh {mesh_id!r}; refusing to propose"
            )
            continue

        # the winding mapping row is NOT measured-dispatched (only OBJECT_HIERARCHY_INVALID is),
        # so the classification is a pure function of the finding code here.
        determinism, correction_type, risk, reversibility, auto_propose = classify(code, None)
        if not auto_propose or correction_type is None:
            errors.append(f"mesh {mesh_id!r}: winding aggregation is not proposable by policy")
            continue

        parameters = {key: parameters[key] for key in WINDING_PARAMETER_KEYS}
        proposals.append(
            CorrectionProposal(
                correction_id=_correction_id(code, object_id, mesh_id, parameters),
                finding_code=code.value,
                object_id=object_id,
                mesh_id=mesh_id,
                correction_type=correction_type,
                parameters=parameters,
                rationale=(
                    "deterministic aggregated winding correction for finding "
                    + code.value
                    + " (evidence-designated aggregate; one face reversal resolves every "
                    "recorded edge)"
                ),
                preconditions=(
                    {"source_report_digest": report_digest},
                    {"finding_code": code.value},
                    {"affected_entity": {"object_id": object_id, "mesh_id": mesh_id}},
                ),
                expected_postcondition={
                    "finding_cleared": code.value,
                    "unrelated_topology_unchanged": True,
                },
                risk=risk,
                severity=severity_of(code).value,
                reversibility=reversibility,
                dependencies=(),
                determinism=determinism,
                # identical policy to every other FIDELITY_GEOMETRY correction: review-gated, so an
                # aggregated winding correction is NEVER auto-executed without an authorization.
                requires_human_review=True,
                out_of_scope=False,
            )
        )
    return proposals, errors, review_only_meshes


def _correction_id(code: FindingCode, object_id: Optional[str], mesh_id: Optional[str],
                   parameters: Dict[str, Any]) -> str:
    """Derive a STABLE, content-addressed correction id (no positional index).

    The id is a short digest over (code, object_id, mesh_id, canonicalized parameters), so:
    - equivalent logical findings produce IDENTICAL ids regardless of input finding order;
    - two genuinely DISTINCT same-code findings with different parameters produce DISTINCT ids
      (they are not collapsed by id);
    - two truly identical findings (same code + scope + parameters) produce the SAME id, which the
      dependency resolver then deduplicates deterministically.
    """
    import hashlib, json

    body = {
        "code": code.value,
        "object_id": object_id,
        "mesh_id": mesh_id,
        "parameters": parameters,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    scope = object_id or mesh_id or "scene"
    return f"{code.value}-{scope}-{digest[:8]}"


def _suggest_name(current_name: Any, pattern: Any) -> Optional[str]:
    """A deterministic canonical-name suggestion OR None (no fabrication).

    If the profile pattern is a dotted/kebab lowercase token pattern, normalize the current name by
    lowercasing and substituting invalid chars with an underscore, then verify it matches. If the
    pattern cannot be applied deterministically, return None (review).
    """
    if type(pattern) is not str:
        return None
    if type(current_name) is not str:
        return None
    import re

    cleaned = re.sub(r"[^a-z0-9._-]", "_", current_name.lower())
    if not cleaned or not re.fullmatch(pattern, cleaned):
        return None
    return cleaned


def _summary(counts: Dict[str, int]) -> Dict[str, Any]:
    return {
        "total": counts.get("total", 0),
        "deterministic": counts.get("deterministic", 0),
        "heuristic": counts.get("heuristic", 0),
        "requires_review": counts.get("requires_review", 0),
        "unsafe_to_automate": counts.get("unsafe_to_automate", 0),
        "unsupported": counts.get("unsupported", 0),
        "planning_errors": counts.get("planning_errors", 0),
    }


def plan_scene_report(
    report: Dict[str, Any],
    *,
    profile: Dict[str, Any],
    planner_version: str = PLANNER_VERSION,
) -> CorrectionPlan:
    """Deterministically produce a ``CorrectionPlan`` from a SceneReport-shaped dict.

    ``report`` expects the canonical ``SceneReport`` JSON shape augmented with a ``"digest"`` key
    (the report's ``SceneReport.digest()``) and a ``"report_format_version"`` key. ``profile`` is a
    language-neutral config dict (the serialized ``SoccerFieldValidationProfile``-equivalent: at
    minimum ``name`` + ``allowed_units`` + ``name_pattern`` for the soccer profile).
    """
    # --- provenance / format gate ---
    pl = _require_scene_report_payload(report)
    require_report_format_version(report.get("report_format_version"))
    source_digest = pl["digest"]
    source_revision_id = report.get("source_revision_id")
    if source_revision_id is not None and type(source_revision_id) is not str:
        raise CorrectionInputError("source_revision_id must be str or None")
    if type(profile) is not dict or type(profile.get("name")) is not str:
        raise CorrectionInputError("profile must be a dict with a 'name' str")

    probe = pl["findings"]

    # Canonicalize finding ITERATION ORDER first: the plan must be INDEPENDENT of the caller's
    # insertion/finding order (determinism requirement). Correction ids are content-addressed
    # (see _correction_id), so this sort makes the whole computation order-stable end to end.
    # D3: the sort key normalizes each finding through the canonical-value grammar FIRST, so a
    # NaN/Inf (or any malformed JSON-native value) is rejected with the DECLARED CorrectionInputError
    # here — never a raw ValueError escaping the planner's error boundary.
    def _finding_sort_key(f: Any) -> str:
        if type(f) is not dict:
            raise CorrectionInputError("finding must be a dict")
        return json.dumps(
            _canonical_scalar(f, label="finding"),
            sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        )

    probe_sorted = sorted(probe, key=_finding_sort_key)

    proposals: List[CorrectionProposal] = []
    counts: Dict[str, int] = {
        "total": 0, "deterministic": 0, "heuristic": 0, "requires_review": 0,
        "unsafe_to_automate": 0, "unsupported": 0, "planning_errors": 0,
    }
    unsupported: List[str] = []
    planning_error_msgs: List[str] = []
    # F6: a non-accepted unit cannot be auto-normalized (see _finding_to_proposal); such a finding
    # itself REQUIRES_REVIEW regardless of whether any auto proposal exists.
    unit_review_required = False

    # WAVE 2 (§2.0): winding findings are collected and aggregated per mesh AFTER this scan; the
    # scan itself still classifies/counts them (state + summary) exactly as before.
    winding_inputs: List[Tuple[int, Dict[str, Any], Any]] = []

    for i, finding in enumerate(probe_sorted):
        if type(finding) is not dict:
            raise CorrectionInputError(f"finding[{i}] must be a dict")
        try:
            code_raw = finding.get("code")
            if type(code_raw) is not str:
                raise CorrectionInputError(f"finding[{i}].code must be an exact str")
            code = FindingCode(code_raw)
        except (ValueError, CorrectionInputError):
            counts["unsupported"] += 1
            unsupported.append(str(i))
            planning_error_msgs.append(f"unsupported finding code at index {i}")
            continue
        counts["total"] += 1

        determinism, correction_type, risk, reversibility, auto_propose = classify(
            code, finding.get("measured")
        )
        # classify the state buckets deterministically (by classification, not by proposal flags)
        if determinism == CorrectionDeterminism.DETERMINISTIC.value:
            counts["deterministic"] += 1
        elif determinism == CorrectionDeterminism.HEURISTIC.value:
            counts["heuristic"] += 1
        elif determinism == CorrectionDeterminism.REQUIRES_REVIEW.value:
            counts["requires_review"] += 1
        elif determinism == CorrectionDeterminism.UNSAFE_TO_AUTOMATE.value:
            counts["unsafe_to_automate"] += 1

        if code is FindingCode.SCENE_UNIT_INVALID:
            # F6: no automatic metadata normalization. A non-accepted unit signals that the
            # declared coordinate semantic may differ; picking a target (e.g. "METERS") would be a
            # fabricated semantic scale change. Default to human review.
            unit_review_required = True
            continue

        if code is FindingCode.MESH_WINDING_INCONSISTENT:
            winding_inputs.append((i, finding, finding.get("mesh_id")))
            continue

        try:
            proposals.extend(
                _finding_to_proposal(
                    finding, report_digest=source_digest, profile=profile,
                    object_scope_optional=True, index=i,
                )
            )
        except CorrectionInputError as exc:
            # A finding that cannot form a safe proposal is a planning error, never a silent skip.
            counts["planning_errors"] += 1
            planning_error_msgs.append(f"finding[{i}] {code.value}: {exc}")

    # --- WAVE 2 §2.1: planner-side winding aggregation (the only winding proposal producer) ---
    aggregated, aggregation_errors, winding_review_only_meshes = _aggregate_winding_corrections(
        winding_inputs, report_digest=source_digest
    )
    proposals.extend(aggregated)
    for message in aggregation_errors:
        counts["planning_errors"] += 1
        planning_error_msgs.append(message)
    # WAVE 2: a mesh whose winding findings were refused at planning time (D3) keeps them
    # REVIEW-ONLY, so the plan must say REVIEW_REQUIRED — never NO_CORRECTIONS (which would imply
    # there was nothing to review). Same precedence slot as the existing F6 unit-review flag.
    winding_review_required = bool(winding_review_only_meshes)

    # --- dependency resolution ---
    explicit_edges: List[Tuple[str, str]] = []
    # deterministic ordering: topological garbage before winding recompute on the same mesh
    for p in proposals:
        if p.correction_type in ("REMOVE_DEGENERATE_FACE", "REMOVE_DUPLICATE_FACE"):
            for other in proposals:
                if (
                    other.correction_type in ("REPAIR_FACE_WINDING", "REPAIR_NORMAL_CONSISTENCY")
                    and other.mesh_id == p.mesh_id and other.correction_id != p.correction_id
                ):
                    explicit_edges.append((p.correction_id, other.correction_id))

    resolved = resolve(
        proposals,
        explicit_edges=explicit_edges,
        proposal_dependencies=sum((list(p.dependencies) for p in proposals), []),
    )
    for c in resolved["contradictions"]:
        counts["planning_errors"] += 1
        planning_error_msgs.append(
            f"conflicting targets {c['correction_types']} for {c['target']}"
        )

    dedup_count = len(resolved["deduplicated"])
    if dedup_count:
        counts["total"] += dedup_count

    # --- state reduction (deterministic; F3 required precedence) ---
    retained = resolved["corrections"]
    any_review_retained = any(p.requires_human_review for p in retained)
    any_auto_retained = any(not p.requires_human_review for p in retained)

    if resolved["cycle_nodes"] or counts["unsupported"] or counts["planning_errors"]:
        if resolved["cycle_nodes"]:
            planning_error_msgs.append("dependency cycle detected: " + ",".join(resolved["cycle_nodes"]))
            for _node in resolved["cycle_nodes"]:
                counts["planning_errors"] += 1
        state = PlannerState.PLANNING_ERROR.value
    elif counts["unsafe_to_automate"] > 0:
        state = PlannerState.UNSAFE_TO_AUTOMATE.value
    elif (any_review_retained or counts["requires_review"] > 0 or unit_review_required
          or winding_review_required):
        state = PlannerState.REVIEW_REQUIRED.value
    elif any_auto_retained:
        state = PlannerState.AUTO_PROPOSALS_AVAILABLE.value
    else:
        state = PlannerState.NO_CORRECTIONS.value

    plan = CorrectionPlan(
        plan_id="",  # recomputed deterministically in __post_init__
        source_report_digest=source_digest,
        source_revision_id=source_revision_id,
        planner_version=planner_version,
        profile={
            "name": profile.get("name", ""),
            "version": profile.get("version", ""),
        },
        corrections=tuple(resolved["corrections"]),
        dependencies=tuple(resolved["edges"]),
        summary_metrics=_summary(counts),
        state=state,
        planning_errors=tuple(planning_error_msgs),
    )
    return plan


# ===========================================================================
# WAVE 3 — planner-side REPAIR_MERGE_VERTEX derivation (design §1–§7)
# ===========================================================================
#
# DISPATCH (design §11, and §18/OI-2 resolved as its "explicit operator request" branch): the
# AUTOMATIC pass in :func:`plan_scene_report` is UNCHANGED and emits no merge proposal while the
# mapping row keeps ``auto_propose = False`` — whose own definition in ``correction_mapping.py`` is
# "the planner emits a proposal for this finding automatically". :func:`plan_merge_vertex_correction`
# below is the ONLY producer of a merge correction and runs only when the operator invokes it
# explicitly. The emitted correction is review-gated (``requires_human_review = True``), is never
# executed here, and confers no execution authority: the future executor must re-derive every
# commitment (design MR-1…MR-6) and must never treat ``all_groups_exact`` as evidence.
#
# This module derives; it never mutates. No engine contact, no bpy, no I/O, no clock, no randomness.

MERGE_FINDING_CODE = FindingCode.MESH_DUPLICATE_VERTEX
MERGE_CORRECTION_TYPE_TOKEN = "REPAIR_MERGE_VERTEX"

#: Closed merge plan-parameter key set. Every key traces to a design clause, and the future executor
#: allowlists exactly this set — no free-form geometry instruction may ever be added.
MERGE_PARAMETER_KEYS = (
    "mesh_id",                        # scope (parameters convention; the proposal also carries object_id)
    "recorded_pairs",                 # MR-1: the kernel pair evidence the groups were closed from
    "duplicate_groups",               # MR-2 / MP-3 / MP-6
    "survivor_indices",               # MR-3 / MP-4
    "old_to_new_mapping",             # MR-5 / §4
    "mapping_digest",                 # MR-5 / MP-8
    "all_groups_exact",               # MR-4 / MP-7 — DERIVED here; the executor MUST re-derive it
    "predicted_topology_unchanged",   # MR-6 / MP-9 — DERIVED here; the executor MUST re-derive it
)


class MergePlanningCode:
    """Closed diagnostic vocabulary for the merge planning path.

    First block: the design's own §12 codes. ``FINDING_MALFORMED`` and ``MULTI_CORRECTION_REFUSED``
    are planner-local diagnostics for states the design describes in prose ("malformed/ambiguous
    finding", "more than one executable merge correction") but gives no token for. Neither grants
    authority, and both are reported through this path only.
    """

    # design §12 codes
    GROUP_MISMATCH = "GROUP_MISMATCH"
    SUB_GRID_COLLAPSE_UNSUPPORTED = "SUB_GRID_COLLAPSE_UNSUPPORTED"
    SURVIVOR_NOT_GROUP_MINIMUM = "SURVIVOR_NOT_GROUP_MINIMUM"
    PARTIAL_GROUP_COVERAGE = "PARTIAL_GROUP_COVERAGE"
    FACE_REPEATS_GROUP_MEMBERS = "FACE_REPEATS_GROUP_MEMBERS"
    TOPOLOGY_CONSEQUENCE_PREDICTED = "TOPOLOGY_CONSEQUENCE_PREDICTED"
    MAPPING_DIGEST_MISMATCH = "MAPPING_DIGEST_MISMATCH"
    TARGET_MESH_UNRESOLVED = "TARGET_MESH_UNRESOLVED"
    # planner-local diagnostics (the design gives no token for these states)
    FINDING_MALFORMED = "FINDING_MALFORMED"
    MULTI_CORRECTION_REFUSED = "MULTI_CORRECTION_REFUSED"


#: Refusals that leave the finding REVIEW-VISIBLE: no proposal, state REVIEW_REQUIRED, and NOT a
#: planning error (mirrors the Wave-2 D3 precedent). Every other code is an input/provenance defect.
MERGE_REVIEW_VISIBLE_CODES = frozenset(
    {
        MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED,
        MergePlanningCode.PARTIAL_GROUP_COVERAGE,
        MergePlanningCode.FACE_REPEATS_GROUP_MEMBERS,
        MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED,
    }
)


@dataclass(frozen=True, slots=True)
class MergeVertexPlanningOutcome:
    """Result of one explicit merge-planning pass (planner-local; carries no authority).

    ``refusal_code`` is ``None`` exactly when a review-gated merge proposal was produced. When it is
    set, ``plan.corrections`` is empty and the plan's state distinguishes a review-visible refusal
    (``REVIEW_REQUIRED``) from an input/provenance defect (``PLANNING_ERROR``) — never
    ``NO_CORRECTIONS``, which would imply there was nothing to review.
    """

    plan: CorrectionPlan
    refusal_code: Optional[str] = None
    refusal_detail: Optional[str] = None


def _canonical_findings(findings: Any) -> List[Dict[str, Any]]:
    """Canonicalize finding iteration order — the same rule the automatic pass uses.

    Correction ids are content-addressed, so this sort is what makes the whole derivation
    independent of the caller's finding order.
    """
    if type(findings) is not list:
        raise CorrectionInputError("report findings must be a list")

    def _key(f: Any) -> str:
        if type(f) is not dict:
            raise CorrectionInputError("finding must be a dict")
        return json.dumps(
            _canonical_scalar(f, label="finding"),
            sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        )

    return sorted(findings, key=_key)


def _merge_pair(finding: Dict[str, Any], index: int, vertex_count: int) -> Tuple[int, int]:
    """Extract one ``(vertex_a, vertex_b)`` duplicate-vertex pair as a canonical undirected pair.

    Exact non-negative ints only (a bool is a malformed report, never a coerced index), and both
    indices must address the authoritative vertex table. Nothing is inferred from a partial input.
    """
    measured = finding.get("measured")
    if type(measured) is not dict:
        raise CorrectionInputError(
            f"finding[{index}] {MERGE_FINDING_CODE.value}: measured must be a dict carrying "
            "vertex_a/vertex_b"
        )
    a, b = measured.get("vertex_a"), measured.get("vertex_b")
    for value in (a, b):
        if type(value) is not int or value < 0:
            raise CorrectionInputError(
                f"finding[{index}] {MERGE_FINDING_CODE.value}: vertex_a/vertex_b must be "
                f"non-negative exact ints (got {value!r})"
            )
    if a == b:
        raise CorrectionInputError(
            f"finding[{index}] {MERGE_FINDING_CODE.value}: vertex_a == vertex_b ({a}) is not a "
            "duplicate pair"
        )
    if a >= vertex_count or b >= vertex_count:
        raise CorrectionInputError(
            f"finding[{index}] {MERGE_FINDING_CODE.value}: pair ({a},{b}) addresses a vertex "
            f"outside the authoritative table ({vertex_count} vertices)"
        )
    return (min(a, b), max(a, b))


def _coincidence_classes(vertices: Sequence[Sequence[Any]]) -> Dict[Any, List[int]]:
    """The kernel's canonical coincidence classes over the authoritative vertex table.

    Uses the SAME key function the kernel uses (``correction_authorization.canonical_coincidence_key``
    mirrors ``mesh_health._rounded_vertex_key``) — one implementation, no second grammar.
    """
    classes: Dict[Any, List[int]] = {}
    for index, coordinate in enumerate(vertices):
        classes.setdefault(canonical_coincidence_key(coordinate), []).append(index)
    return classes


def _pairs_implied_by_table(vertices: Sequence[Sequence[Any]]) -> Set[Tuple[int, int]]:
    """The pair set the kernel itself would emit for this table (first-seen member vs each later).

    Iteration is in vertex-index order, so the first-seen member of a class is its minimum index —
    exactly the representative ``mesh_health._collect_duplicate_vertices`` records in ``vertex_a``.
    """
    pairs: Set[Tuple[int, int]] = set()
    for members in _coincidence_classes(vertices).values():
        if len(members) < 2:
            continue
        first = members[0]
        for later in members[1:]:
            pairs.add((first, later))
    return pairs


def _groups_from_pairs(pairs: Sequence[Tuple[int, int]]) -> Tuple[Tuple[int, ...], ...]:
    """Transitive closure over the pair evidence (design MR-2), canonically ordered.

    Groups are closed over the pair graph (a transitive duplicate group is ONE group), members are
    sorted ascending, and groups are ordered by ascending canonical survivor (``min(G)``) — the
    canonical form ``validate_duplicate_groups`` accepts.
    """
    parent: Dict[int, int] = {}

    def _find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for a, b in sorted(pairs):
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    by_root: Dict[int, List[int]] = {}
    for node in sorted(parent):
        by_root.setdefault(_find(node), []).append(node)
    groups = [tuple(sorted(members)) for members in by_root.values() if len(members) >= 2]
    return tuple(sorted(groups, key=lambda group: min(group)))


def _topology_code_counts(findings: Sequence[Any]) -> Dict[str, int]:
    """Deterministic code histogram of a kernel finding list."""
    counts: Dict[str, int] = {}
    for finding in findings:
        token = finding.code.value if hasattr(finding.code, "value") else str(finding.code)
        counts[token] = counts.get(token, 0) + 1
    return counts


def _merge_plan(
    *,
    state: str,
    source_digest: str,
    source_revision_id: Optional[str],
    planner_version: str,
    profile: Dict[str, Any],
    corrections: Tuple[CorrectionProposal, ...] = (),
    planning_errors: Tuple[str, ...] = (),
    errors: int = 0,
    review: int = 0,
) -> CorrectionPlan:
    """Build the merge plan through the SAME content-addressed machinery as every other plan."""
    counts = {
        "total": len(corrections), "deterministic": 0, "heuristic": 0, "requires_review": review,
        "unsafe_to_automate": 0, "unsupported": 0, "planning_errors": errors,
    }
    return CorrectionPlan(
        plan_id="",  # recomputed deterministically in __post_init__
        source_report_digest=source_digest,
        source_revision_id=source_revision_id,
        planner_version=planner_version,
        profile={"name": profile.get("name", ""), "version": profile.get("version", "")},
        corrections=corrections,
        dependencies=(),
        summary_metrics=_summary(counts),
        state=state,
        planning_errors=planning_errors,
    )


def _merge_refuse(
    code: str,
    detail: str,
    *,
    source_digest: str,
    source_revision_id: Optional[str],
    planner_version: str,
    profile: Dict[str, Any],
) -> MergeVertexPlanningOutcome:
    """Refuse without a proposal. Review-visible refusals stay REVIEW_REQUIRED (never planning errors,
    never NO_CORRECTIONS); input/provenance defects are PLANNING_ERROR and carry the message."""
    review_visible = code in MERGE_REVIEW_VISIBLE_CODES
    plan = _merge_plan(
        state=(PlannerState.REVIEW_REQUIRED.value if review_visible
               else PlannerState.PLANNING_ERROR.value),
        source_digest=source_digest,
        source_revision_id=source_revision_id,
        planner_version=planner_version,
        profile=profile,
        planning_errors=() if review_visible else (f"{code}: {detail}",),
        errors=0 if review_visible else 1,
        review=1 if review_visible else 0,
    )
    return MergeVertexPlanningOutcome(plan=plan, refusal_code=code, refusal_detail=detail)


def plan_merge_vertex_correction(
    report: Dict[str, Any],
    scene_input: Dict[str, Any],
    *,
    profile: Dict[str, Any],
    planner_version: str = PLANNER_VERSION,
) -> MergeVertexPlanningOutcome:
    """Explicitly-requested merge planning pass (design §1–§7; OI-2 "explicit operator request").

    Consumes the authoritative ``SceneReport``-shaped dict (the kernel's duplicate-vertex evidence,
    MP-3/MR-1) and the authoritative scene input (the vertex table, MR-4/MR-5), and returns either one
    review-gated ``REPAIR_MERGE_VERTEX`` correction or a declared refusal. Everything is re-derived
    from that evidence: no caller-supplied group, survivor, mapping or ``all_groups_exact`` flag is
    ever trusted, and nothing is normalized or repaired.

    Scope (design §16): ONE target object/mesh per pass. More than one target scope is refused rather
    than aggregated, because multi-correction execution is not authorized by the design.
    """
    # ---- provenance gate (identical to the automatic pass) ----
    pl = _require_scene_report_payload(report)
    require_report_format_version(report.get("report_format_version"))
    source_digest = pl["digest"]
    source_revision_id = report.get("source_revision_id")
    if source_revision_id is not None and type(source_revision_id) is not str:
        raise CorrectionInputError("source_revision_id must be str or None")
    if type(profile) is not dict or type(profile.get("name")) is not str:
        raise CorrectionInputError("profile must be a dict with a 'name' str")

    findings = _canonical_findings(pl["findings"])
    merge_findings = [f for f in findings if f.get("code") == MERGE_FINDING_CODE.value]

    def _refuse(code: str, detail: str) -> MergeVertexPlanningOutcome:
        return _merge_refuse(code, detail, source_digest=source_digest,
                             source_revision_id=source_revision_id,
                             planner_version=planner_version, profile=profile)

    # ---- PART I: no duplicate-vertex finding -> nothing to review for this capability ----
    if not merge_findings:
        plan = _merge_plan(
            state=PlannerState.NO_CORRECTIONS.value, source_digest=source_digest,
            source_revision_id=source_revision_id, planner_version=planner_version, profile=profile,
        )
        return MergeVertexPlanningOutcome(plan=plan)

    # ---- MP-1: exactly one explicit object/mesh target (identity never inferred) ----
    scopes: Set[Tuple[Optional[str], str]] = set()
    for index, finding in enumerate(merge_findings):
        mesh_id = finding.get("mesh_id")
        object_id = finding.get("object_id")
        if type(mesh_id) is not str or not mesh_id.strip():
            return _refuse(MergePlanningCode.TARGET_MESH_UNRESOLVED,
                           f"finding[{index}] {MERGE_FINDING_CODE.value} has no canonical mesh_id")
        if object_id is not None and type(object_id) is not str:
            return _refuse(MergePlanningCode.FINDING_MALFORMED,
                           f"finding[{index}] object_id must be str or None")
        scopes.add((object_id, mesh_id))
    mesh_ids = {mesh_id for _object_id, mesh_id in scopes}
    # the kernel's mesh-level findings legitimately carry object_id = None, so only the NON-None
    # object ids are evidence here; the object identity is resolved from the authoritative scene below.
    declared_object_ids = {object_id for object_id, _mesh_id in scopes if object_id is not None}
    if len(mesh_ids) > 1 or len(declared_object_ids) > 1:
        return _refuse(
            MergePlanningCode.MULTI_CORRECTION_REFUSED,
            "duplicate-vertex findings name more than one object/mesh target "
            f"({len(declared_object_ids)} object(s), {len(mesh_ids)} mesh(es)); one pass corrects "
            "exactly one target, and multi-correction execution is not authorized by the design",
        )
    mesh_id = next(iter(mesh_ids))

    # ---- authoritative scene/vertex evidence (existing closed grammar, no new parser) ----
    try:
        scene = parse_scene_report_input(scene_input)
    except SceneReportInputError as exc:
        raise CorrectionInputError(f"scene_input: {exc}") from None
    candidates = tuple(
        obj for obj in scene.objects if obj.mesh is not None and obj.mesh.mesh_id == mesh_id
    )
    if len(candidates) != 1:
        return _refuse(
            MergePlanningCode.TARGET_MESH_UNRESOLVED,
            f"mesh_id {mesh_id!r} does not resolve to exactly one object in the scene "
            f"({len(candidates)} candidate object(s))",
        )
    target_object = candidates[0]
    mesh = target_object.mesh
    target_object_id = target_object.object_id
    if declared_object_ids and target_object_id not in declared_object_ids:
        return _refuse(
            MergePlanningCode.TARGET_MESH_UNRESOLVED,
            f"the findings attribute mesh {mesh_id!r} to object {sorted(declared_object_ids)!r} but "
            f"the authoritative scene resolves it to {target_object_id!r}",
        )
    table = mesh.vertices
    vertex_count = len(table)

    # ---- MR-1: the kernel's pair evidence, canonicalized and deduplicated ----
    pairs: List[Tuple[int, int]] = []
    try:
        for index, finding in enumerate(merge_findings):
            pair = _merge_pair(finding, index, vertex_count)
            if pair not in pairs:
                pairs.append(pair)
    except CorrectionInputError as exc:
        return _refuse(MergePlanningCode.FINDING_MALFORMED, str(exc))

    # ---- MP-3/MP-6 completeness against the AUTHORITATIVE table (nothing inferred, nothing partial) ----
    implied = _pairs_implied_by_table(table)
    invented = sorted(set(pairs) - implied)
    if invented:
        return _refuse(
            MergePlanningCode.GROUP_MISMATCH,
            "the report declares duplicate pair(s) the authoritative vertex table does not support "
            f"(invented or mismatched evidence): {[list(pair) for pair in invented]}",
        )
    missing = sorted(implied - set(pairs))
    if missing:
        return _refuse(
            MergePlanningCode.PARTIAL_GROUP_COVERAGE,
            "the report omits duplicate pair(s) the authoritative vertex table proves, so a complete "
            f"group set cannot be derived (no member is ever inferred): {[list(pair) for pair in missing]}",
        )

    # ---- MR-2: transitive groups, canonically ordered ----
    groups = _groups_from_pairs(pairs)
    try:
        groups = validate_duplicate_groups(groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        return _refuse(MergePlanningCode.GROUP_MISMATCH, str(exc))

    # ---- MP-7 / MR-4: exact-bit vs sub-grid, DERIVED from the raw coordinates ----
    try:
        require_supported_case(table, groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        code = getattr(exc, "failure_code", None) or MergePlanningCode.GROUP_MISMATCH
        if code == MergePlanningCode.GROUP_MISMATCH:
            return _refuse(MergePlanningCode.GROUP_MISMATCH, str(exc))
        return _refuse(MergePlanningCode.SUB_GRID_COLLAPSE_UNSUPPORTED, str(exc))
    cases = tuple(classify_duplicate_group_case(table, group) for group in groups)
    all_groups_exact = all(case == "EXACT" for case in cases)

    # ---- MP-4 / MR-3: the canonical survivor of each group ----
    survivors = canonical_survivor_indices(groups)

    # ---- MP-8 / MR-5: the canonical mapping and its digest, recomputed (never trusted) ----
    old_to_new = make_index_mapping(vertex_count, groups)
    digest = mapping_digest(mesh_id, vertex_count, old_to_new)
    try:
        validate_index_mapping(old_to_new, mesh_id=mesh_id, vertex_count=vertex_count, groups=groups)
    except (AuthorizationContractError, AuthorizationInputError) as exc:
        return _refuse(MergePlanningCode.MAPPING_DIGEST_MISMATCH,
                       f"internal mapping invariant failed: {exc}")
    # old_to_new is indexed by PRE-state vertex and stores POST-state indices.
    # Therefore set(old_to_new) is the post-index range, not the surviving PRE-state
    # indices. That shortcut is only accidentally correct when every removed vertex is a
    # suffix of the table. Derive the kept PRE-state subsequence explicitly from the
    # canonical groups/survivors so interleaved or middle-table duplicate groups are predicted
    # against the same vertex table the executor is authorized to construct.
    removed_indices = {
        member
        for group in groups
        for member in group
        if member != min(group)
    }
    kept = [index for index in range(vertex_count) if index not in removed_indices]
    if digest != mapping_digest(mesh_id, vertex_count, old_to_new):
        return _refuse(MergePlanningCode.MAPPING_DIGEST_MISMATCH,
                       "the recomputed mapping digest is not stable")

    # ---- MP-5: no face may reference two members of one group (unrepresentable post-state) ----
    for face_index, face in enumerate(mesh.faces):
        for group in groups:
            if sum(1 for member in face if member in group) >= 2:
                return _refuse(
                    MergePlanningCode.FACE_REPEATS_GROUP_MEMBERS,
                    f"face[{face_index}] references two members of group {list(group)}; the "
                    "post-state would repeat an index and is unrepresentable",
                )

    # ---- MP-9 / MR-6: predict the exact post-state and run the KERNEL's own predicates on it ----
    for face_index, face in enumerate(mesh.faces):
        for member in face:
            if type(member) is not int or member < 0 or member >= vertex_count:
                return _refuse(
                    MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED,
                    f"face[{face_index}] references vertex index {member!r} outside the pre-state "
                    f"vertex table ({vertex_count} vertices); the post-state cannot be represented",
                )
    predicted_vertices = tuple(table[survivor] for survivor in kept)
    predicted_faces = tuple(tuple(old_to_new[member] for member in face) for face in mesh.faces)
    if any(member < 0 or member >= len(kept) for face in predicted_faces for member in face):
        return _refuse(MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED,
                       "the predicted post-state is unrepresentable (a face index falls outside the "
                       "post-state vertex table)")
    try:
        predicted_scene = parse_scene_report_input(
            {
                "scene_id": scene.scene_id,
                "unit_system": scene.unit_system,
                "objects": [
                    {
                        "object_id": target_object.object_id,
                        "name": target_object.name,
                        "mesh": {
                            "mesh_id": mesh.mesh_id,
                            "vertices": [list(v) for v in predicted_vertices],
                            "faces": [list(f) for f in predicted_faces],
                        },
                    }
                ],
            }
        )
    except SceneReportInputError as exc:
        return _refuse(MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED,
                       f"the predicted post-state is not representable: {exc}")
    predicted_findings = check_mesh(predicted_scene.objects[0].mesh)
    pre_counts = _topology_code_counts(check_mesh(mesh))
    post_counts = _topology_code_counts(predicted_findings)
    if post_counts.get(MERGE_FINDING_CODE.value):
        return _refuse(
            MergePlanningCode.PARTIAL_GROUP_COVERAGE,
            "the predicted post-state still contains a duplicate-vertex finding, so the derived "
            "groups do not cover every duplicate on this mesh",
        )
    new_codes = sorted({code for code in post_counts if post_counts[code] > pre_counts.get(code, 0)})
    cleared_codes = sorted({code for code in pre_counts
                            if pre_counts[code] > post_counts.get(code, 0)
                            and code != MERGE_FINDING_CODE.value})
    if new_codes or cleared_codes:
        return _refuse(
            MergePlanningCode.TOPOLOGY_CONSEQUENCE_PREDICTED,
            f"the predicted post-state introduces {new_codes or 'no'} new finding class(es) and clears "
            f"{cleared_codes or 'no'} pre-existing class(es); the merge is refused rather than repaired",
        )

    # ---- PART F: exactly one canonical, review-gated merge proposal ----
    # ``auto_propose`` is deliberately NOT consumed as a gate on this path: this IS the
    # explicit-operator-request entry point (design §18/OI-2), and the proposal below is review-gated
    # regardless of its value. The AUTOMATIC pass in ``plan_scene_report`` remains the place where the
    # dispatch flag decides emission — and it emits nothing for this finding.
    determinism, correction_type, risk, reversibility, _auto_propose = classify(
        MERGE_FINDING_CODE, None
    )
    if correction_type is None or correction_type != MERGE_CORRECTION_TYPE_TOKEN:
        return _refuse(MergePlanningCode.GROUP_MISMATCH,
                       "the correction mapping does not classify MESH_DUPLICATE_VERTEX as "
                       "REPAIR_MERGE_VERTEX")
    parameters: Dict[str, Any] = {
        "mesh_id": mesh_id,
        "recorded_pairs": [list(pair) for pair in sorted(pairs)],
        "duplicate_groups": [list(group) for group in groups],
        "survivor_indices": list(survivors),
        "old_to_new_mapping": list(old_to_new),
        "mapping_digest": digest,
        "all_groups_exact": all_groups_exact,
        "predicted_topology_unchanged": True,
    }
    if tuple(parameters.keys()) != MERGE_PARAMETER_KEYS:
        raise CorrectionPlanError("internal merge parameter schema violation")
    proposal = CorrectionProposal(
        correction_id=_correction_id(MERGE_FINDING_CODE, target_object_id, mesh_id, parameters),
        finding_code=MERGE_FINDING_CODE.value,
        object_id=target_object_id,
        mesh_id=mesh_id,
        correction_type=correction_type,
        parameters=parameters,
        rationale=(
            "deterministic merge correction for finding " + MERGE_FINDING_CODE.value +
            " (explicit operator request; duplicate groups re-derived from the authoritative vertex "
            "table, case classified bitwise, mapping recomputed, predicted post-state checked)"
        ),
        preconditions=(
            {"source_report_digest": source_digest},
            {"finding_code": MERGE_FINDING_CODE.value},
            {"affected_entity": {"object_id": target_object_id, "mesh_id": mesh_id}},
        ),
        expected_postcondition={
            "finding_cleared": MERGE_FINDING_CODE.value,
            "unrelated_topology_unchanged": True,
        },
        risk=risk,
        severity=severity_of(MERGE_FINDING_CODE).value,
        reversibility=reversibility,
        dependencies=(),
        determinism=determinism,
        # HUMAN-AUTHORIZED and review-gated regardless of the dispatch classification: the artifact
        # gate (correction_authorization.py) is mandatory before any future executor may act.
        requires_human_review=True,
        out_of_scope=False,
    )
    plan = _merge_plan(
        state=PlannerState.REVIEW_REQUIRED.value, source_digest=source_digest,
        source_revision_id=source_revision_id, planner_version=planner_version, profile=profile,
        corrections=(proposal,), review=1,
    )
    return MergeVertexPlanningOutcome(plan=plan)
