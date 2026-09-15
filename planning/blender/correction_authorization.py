"""Wave-2 authorization contract for the controlled correction executor.

This module implements ONLY the authorization *contract layer* of the Wave-2 design
(``BLENDER_WAVE2_AUTHORIZATION_AND_WINDING_DESIGN.md``, §1, §6/§6.1, §8). It is deliberately
inert: it validates an authorization artifact, binds it to a precisely-described unit of work,
and validates the plan-side recorded-edge/counterpart set against a freshly recomputed winding
finding set (``WC-P17``). It performs NO mutation, holds NO persistence, and grants NO authority
of its own.

Implemented here (Wave-2 slice 1, extended by Wave-3 slice 1):

- Wave-3 (`REPAIR_MERGE_VERTEX`) contract layer: the artifact's optional
  ``expected_merge_mapping_digest`` assertion, the exact ``target_object_mesh`` shape, the canonical
  duplicate-group / survivor / index-mapping validators, the exact-bit vs sub-grid case rule, the
  canonical mapping digest, and ``verify_merge_authorization``. All of it is inert validation: no
  grouping is inferred, no survivor is chosen at runtime, no coordinate is normalized, and no
  topology is mutated.

- ``AuthorizationArtifact`` — the immutable artifact contract (closed field set, exact types,
  deep-frozen canonical values) plus canonical JSON serialization and a stable digest.
- ``parse_authorization`` — strict canonical-JSON parsing (duplicate keys rejected, non-finite
  numbers rejected, closed grammar, exact tokens only).
- ``verify_authorization`` — the binding gate: all bindings of design §1.2 are recomputed and
  compared; the result is a deterministic outcome token, never an exception for a legitimate
  mismatch.
- ``validate_recorded_edges`` / ``verify_recorded_set_agreement`` — the explicit ``WC-P17``
  canonical-edge validation, BIDIRECTIONAL recorded-set equality against the fresh recomputation,
  positional counterpart agreement, and the explicit ``counterpart != designated_face`` rule.

NOT implemented here (and not authorized by this module):

- any ``bpy``/Blender read or write, any winding mutation, any live entry point, any change to the
  existing duplicate/degenerate operations, any persistence/rollback/receipt authority.

Trust boundary (design §1.7): binding-only. This module establishes that an artifact applies to
exactly the work presented (type, correction id, plan id, source digest, policy version, decision,
face designation). It does NOT establish who authored the artifact, and it must never be read as
doing so — controlling who may submit an artifact is the calling boundary's responsibility.

Determinism: pure Python, no I/O, no environment reads, no clocks, no randomness; the same inputs
always produce the same outcome token or the same declared error. This module never imports
``bpy``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from planning.blender.correction_values import (
    CorrectionPlannerError,
    _canonical_scalar,
)

# ---------------------------------------------------------------------------
# Contract version / accepted policy versions (design §1.1, §1.8)
# ---------------------------------------------------------------------------

AUTHORIZATION_VERSION = "1"

#: Closed, code-defined allowlist. Never profile-, plan- or caller-supplied. There is no
#: normalization, no prefix/major-minor matching, and no silent downgrade (design §1.8).
ACCEPTED_AUTHORIZATION_POLICY_VERSIONS = frozenset({"1"})

#: Wave-2 correction type.
WINDING_CORRECTION_TYPE = "REPAIR_FACE_WINDING"

#: Wave-3 correction type (bounded, human-authorized duplicate-vertex consolidation).
MERGE_CORRECTION_TYPE = "REPAIR_MERGE_VERTEX"

#: Closed, code-defined set of correction types this contract can authorize. Never profile-, plan-
#: or caller-extended; an artifact naming anything else fails CORRECTION_TYPE_NOT_AUTHORIZABLE.
AUTHORIZABLE_CORRECTION_TYPES = frozenset({WINDING_CORRECTION_TYPE, MERGE_CORRECTION_TYPE})

#: Canonical duplicate-group case tokens (Wave-3 design §2/§4). EXACT = every member is bit-identical
#: to the group's survivor; SUB_GRID = equal only under the kernel's rounded coincidence key.
MERGE_CASE_EXACT = "EXACT"
MERGE_CASE_SUB_GRID = "SUB_GRID"

#: The kernel's canonical coincidence-grid precision (`mesh_health._rounded_vertex_key` uses
#: ``round(value, 6)``, i.e. decimal half-to-even at six places).
MERGE_COINCIDENCE_DECIMALS = 6

DECISION_APPROVED = "APPROVED"

#: Selection modes (design §3): D1 = evidence-designated, D2 = authorization-designated.
SELECTION_MODE_D1 = "D1"
SELECTION_MODE_D2 = "D2"

#: Selection modes the authorization layer understands.
_SELECTION_MODES = frozenset({SELECTION_MODE_D1, SELECTION_MODE_D2})

#: Closed artifact field set (an unknown extra key is AUTHORIZATION_INVALID — design §1.1, §8.1).
_AUTHORIZATION_FIELDS = frozenset(
    {
        "authorization_version",
        "authorization_policy_version",
        "decision",
        "correction_type",
        "correction_id",
        "plan_id",
        "source_report_digest",
        "authorized_by",
        "authorized_at_utc",
        "designated_face_index",
        "expected_face_tuple",
        "expected_merge_mapping_digest",
        "scope_note",
    }
)

_REQUIRED_FIELDS = frozenset(
    {
        "authorization_version",
        "authorization_policy_version",
        "decision",
        "correction_type",
        "correction_id",
        "plan_id",
        "source_report_digest",
        "authorized_by",
        "authorized_at_utc",
    }
)

_OPTIONAL_FIELDS = frozenset(
    {
        "designated_face_index",
        "expected_face_tuple",
        "expected_merge_mapping_digest",
        "scope_note",
    }
)


# ---------------------------------------------------------------------------
# Deterministic errors and outcome tokens
# ---------------------------------------------------------------------------


class AuthorizationError(CorrectionPlannerError):
    """Base class for every declared authorization-contract failure.

    Every declared failure carries a structured ``failure_code`` drawn from
    :class:`AuthorizationFailureCode` (``None`` only where no code applies), so callers, receipts and
    tests identify the failure by VALUE instead of by parsing prose.
    """

    def __init__(self, message: str, *, failure_code: "Optional[str]" = None) -> None:
        super().__init__(message)
        self.failure_code = failure_code


class AuthorizationInputError(AuthorizationError):
    """A malformed/unparsable authorization artifact (fail closed)."""


class AuthorizationContractError(AuthorizationError):
    """A recorded-edge / counterpart / designation contract violation (fail closed)."""


class AuthorizationOutcome:
    """Deterministic authorization-gate outcome tokens (design §1.3)."""

    VERIFIED = "AUTHORIZATION_VERIFIED"
    REQUIRED = "AUTHORIZATION_REQUIRED"
    INVALID = "AUTHORIZATION_INVALID"
    SCOPE_MISMATCH = "AUTHORIZATION_SCOPE_MISMATCH"


class AuthorizationFailureCode:
    """Deterministic, language-neutral failure codes for the authorization gate.

    A code identifies exactly which binding or contract rule failed, so callers never have to
    parse prose. ``AUTHORIZATION_EXPIRED`` is intentionally absent: the design (§1.5) defines it
    but forbids emitting it — content-addressed bindings replace any validity window.
    """

    # parse / shape
    MALFORMED_JSON = "MALFORMED_JSON"
    DUPLICATE_JSON_KEY = "DUPLICATE_JSON_KEY"
    NON_FINITE_NUMBER = "NON_FINITE_NUMBER"
    NOT_A_MAPPING = "NOT_A_MAPPING"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    MISSING_FIELD = "MISSING_FIELD"
    FIELD_TYPE_INVALID = "FIELD_TYPE_INVALID"
    FIELD_EMPTY = "FIELD_EMPTY"
    # artifact semantics
    UNSUPPORTED_AUTHORIZATION_VERSION = "UNSUPPORTED_AUTHORIZATION_VERSION"
    UNSUPPORTED_POLICY_VERSION = "UNSUPPORTED_POLICY_VERSION"
    DECISION_NOT_APPROVED = "DECISION_NOT_APPROVED"
    CORRECTION_TYPE_NOT_AUTHORIZABLE = "CORRECTION_TYPE_NOT_AUTHORIZABLE"
    DIGEST_FORMAT_INVALID = "DIGEST_FORMAT_INVALID"
    # bindings
    CORRECTION_ID_MISMATCH = "CORRECTION_ID_MISMATCH"
    PLAN_ID_MISMATCH = "PLAN_ID_MISMATCH"
    SOURCE_DIGEST_MISMATCH = "SOURCE_DIGEST_MISMATCH"
    CORRECTION_TYPE_MISMATCH = "CORRECTION_TYPE_MISMATCH"
    # designation
    DESIGNATION_REQUIRED = "DESIGNATION_REQUIRED"
    DESIGNATION_SUPPLIED_FOR_D1 = "DESIGNATION_SUPPLIED_FOR_D1"
    DESIGNATION_NOT_IN_CANDIDATE_PAIR = "DESIGNATION_NOT_IN_CANDIDATE_PAIR"
    PLAN_DESIGNATION_MISSING = "PLAN_DESIGNATION_MISSING"
    CANDIDATE_PAIR_MISSING = "CANDIDATE_PAIR_MISSING"
    CANDIDATE_PAIR_INVALID = "CANDIDATE_PAIR_INVALID"
    SELECTION_MODE_INVALID = "SELECTION_MODE_INVALID"
    EXPECTED_FACE_TUPLE_MISMATCH = "EXPECTED_FACE_TUPLE_MISMATCH"
    EXECUTION_FACE_TUPLE_UNAVAILABLE = "EXECUTION_FACE_TUPLE_UNAVAILABLE"
    # recorded-set / counterpart contract (WC-P17)
    RECORDED_EDGES_MISSING = "RECORDED_EDGES_MISSING"
    RECORDED_EDGES_EMPTY = "RECORDED_EDGES_EMPTY"
    RECORDED_EDGE_ARITY = "RECORDED_EDGE_ARITY"
    RECORDED_EDGE_NON_INTEGER = "RECORDED_EDGE_NON_INTEGER"
    RECORDED_EDGE_SELF_LOOP = "RECORDED_EDGE_SELF_LOOP"
    RECORDED_EDGE_NOT_CANONICAL = "RECORDED_EDGE_NOT_CANONICAL"
    RECORDED_EDGES_NOT_SORTED = "RECORDED_EDGES_NOT_SORTED"
    RECORDED_EDGES_DUPLICATED = "RECORDED_EDGES_DUPLICATED"
    COUNTERPART_COUNT_MISMATCH = "COUNTERPART_COUNT_MISMATCH"
    COUNTERPART_NON_INTEGER = "COUNTERPART_NON_INTEGER"
    COUNTERPART_EQUALS_DESIGNATED_FACE = "COUNTERPART_EQUALS_DESIGNATED_FACE"
    RECORDED_SET_MISMATCH = "RECORDED_SET_MISMATCH"
    FRESH_FINDING_INVALID = "FRESH_FINDING_INVALID"
    DUPLICATE_FRESH_EDGE = "DUPLICATE_FRESH_EDGE"
    DESIGNATED_NOT_IN_FRESH_PAIR = "DESIGNATED_NOT_IN_FRESH_PAIR"
    COUNTERPART_NOT_IN_FRESH_PAIR = "COUNTERPART_NOT_IN_FRESH_PAIR"
    DESIGNATED_FACE_INVALID = "DESIGNATED_FACE_INVALID"
    # merge-vertex contract (Wave-3 design §4, §6, §8)
    TARGET_SHAPE_INVALID = "TARGET_SHAPE_INVALID"
    TARGET_EXTRA_KEY = "TARGET_EXTRA_KEY"
    TARGET_MESH_UNRESOLVED = "TARGET_MESH_UNRESOLVED"
    TARGET_CROSS_MESH = "TARGET_CROSS_MESH"
    GROUP_MISMATCH = "GROUP_MISMATCH"
    GROUP_TOO_SMALL = "GROUP_TOO_SMALL"
    GROUP_MEMBERS_NOT_UNIQUE = "GROUP_MEMBERS_NOT_UNIQUE"
    GROUP_MEMBERS_NOT_ASCENDING = "GROUP_MEMBERS_NOT_ASCENDING"
    GROUP_MEMBERS_OVERLAP = "GROUP_MEMBERS_OVERLAP"
    GROUP_NOT_CANONICALLY_ORDERED = "GROUP_NOT_CANONICALLY_ORDERED"
    SURVIVOR_NOT_IN_GROUP = "SURVIVOR_NOT_IN_GROUP"
    SURVIVOR_NOT_GROUP_MINIMUM = "SURVIVOR_NOT_GROUP_MINIMUM"
    SURVIVOR_COUNT_MISMATCH = "SURVIVOR_COUNT_MISMATCH"
    SUB_GRID_COLLAPSE_UNSUPPORTED = "SUB_GRID_COLLAPSE_UNSUPPORTED"
    MAPPING_LENGTH_MISMATCH = "MAPPING_LENGTH_MISMATCH"
    MAPPING_ENTRY_INVALID = "MAPPING_ENTRY_INVALID"
    MAPPING_TARGET_OUT_OF_RANGE = "MAPPING_TARGET_OUT_OF_RANGE"
    MAPPING_SURVIVOR_MISMATCH = "MAPPING_SURVIVOR_MISMATCH"
    MAPPING_REMOVED_NOT_MAPPED = "MAPPING_REMOVED_NOT_MAPPED"
    MAPPING_NONCANONICAL = "MAPPING_NONCANONICAL"
    MAPPING_DIGEST_MISMATCH = "MAPPING_DIGEST_MISMATCH"
    EXPECTED_MAPPING_DIGEST_MISMATCH = "EXPECTED_MAPPING_DIGEST_MISMATCH"
    FIELD_NOT_APPLICABLE_TO_MERGE = "FIELD_NOT_APPLICABLE_TO_MERGE"
    FIELD_NOT_APPLICABLE_TO_TYPE = "FIELD_NOT_APPLICABLE_TO_TYPE"


# ---------------------------------------------------------------------------
# Strict canonical parsing (design §8.1)
# ---------------------------------------------------------------------------


def _reject_constant(token: str) -> Any:
    """``json.loads`` hook: reject ``NaN`` / ``Infinity`` / ``-Infinity`` at parse time."""
    raise AuthorizationInputError(
        f"authorization artifact contains a non-finite number literal {token!r}"
    ,
              failure_code=AuthorizationFailureCode.NON_FINITE_NUMBER,)


def _pairs_hook(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    """``json.loads`` hook: reject duplicate keys instead of silently keeping the last."""
    out: Dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise AuthorizationInputError(f"authorization artifact has duplicate key {key!r}", failure_code=AuthorizationFailureCode.DUPLICATE_JSON_KEY)
        out[key] = value
    return out


def parse_authorization_json(text: Any) -> Dict[str, Any]:
    """Parse strict canonical JSON text into a plain mapping (duplicate keys / NaN rejected)."""
    if type(text) is not str:
        raise AuthorizationInputError("authorization artifact must be supplied as a str", failure_code=AuthorizationFailureCode.NOT_A_MAPPING)
    try:
        parsed = json.loads(text, object_pairs_hook=_pairs_hook, parse_constant=_reject_constant)
    except AuthorizationInputError:
        raise
    except ValueError as exc:
        raise AuthorizationInputError(f"authorization artifact is not valid JSON: {exc}", failure_code=AuthorizationFailureCode.MALFORMED_JSON) from exc
    if type(parsed) is not dict:
        raise AuthorizationInputError("authorization artifact must be a JSON object", failure_code=AuthorizationFailureCode.NOT_A_MAPPING)
    return parsed


# ---------------------------------------------------------------------------
# Exact-type field helpers
# ---------------------------------------------------------------------------


def _exact_str(value: Any, field: str) -> str:
    if type(value) is not str:
        raise AuthorizationInputError(f"{field}: must be an exact built-in str", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    if not value.strip():
        raise AuthorizationInputError(f"{field}: must be a non-empty string", failure_code=AuthorizationFailureCode.FIELD_EMPTY)
    return value


def _exact_int(value: Any, field: str) -> int:
    # bool is a subclass of int; the exact-type check keeps True/False out of index fields.
    if type(value) is not int:
        raise AuthorizationInputError(f"{field}: must be an exact built-in int", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    if value < 0:
        raise AuthorizationInputError(f"{field}: must be a non-negative index", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    return value


def _sha256_hex(value: Any, field: str) -> str:
    """Require exactly 64 lowercase hex characters (``SceneReport.digest()`` representation)."""
    text = _exact_str(value, field)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AuthorizationInputError(f"{field}: must be 64 lowercase hex characters", failure_code=AuthorizationFailureCode.DIGEST_FORMAT_INVALID)
    return text


def _face_tuple(value: Any, field: str) -> Tuple[int, ...]:
    """Canonical ordered face tuple: >= 3 exact ints, no repeats (matches the SceneModel rule)."""
    if type(value) not in (tuple, list):
        raise AuthorizationInputError(f"{field}: must be a list/tuple of vertex indices", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    canon = tuple(value)
    if len(canon) < 3:
        raise AuthorizationInputError(f"{field}: must contain at least 3 vertex indices", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    for idx in canon:
        if type(idx) is not int:
            raise AuthorizationInputError(f"{field}: vertex indices must be exact ints", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
        if idx < 0:
            raise AuthorizationInputError(f"{field}: vertex indices must be non-negative", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    if len(set(canon)) != len(canon):
        raise AuthorizationInputError(f"{field}: must not repeat a vertex index", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID)
    return canon


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthorizationArtifact:
    """An immutable, canonical human-authorization decision artifact (design §1.1).

    Construct via :func:`parse_authorization` (which enforces the closed field set, exact types,
    exact tokens, and canonical-value grammar). Direct construction also validates, so a caller
    cannot mint an artifact that bypasses the contract — but it cannot make one *authentic*:
    authorization provenance is out of scope for this milestone by design (§1.7).
    """

    authorization_version: str
    authorization_policy_version: str
    decision: str
    correction_type: str
    correction_id: str
    plan_id: str
    source_report_digest: str
    authorized_by: str
    authorized_at_utc: str
    designated_face_index: Optional[int] = None
    expected_face_tuple: Optional[Tuple[int, ...]] = None
    expected_merge_mapping_digest: Optional[str] = None
    scope_note: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "authorization_version", _exact_str(
            self.authorization_version, "authorization_version"))
        object.__setattr__(self, "authorization_policy_version", _exact_str(
            self.authorization_policy_version, "authorization_policy_version"))
        object.__setattr__(self, "decision", _exact_str(self.decision, "decision"))
        object.__setattr__(self, "correction_type", _exact_str(
            self.correction_type, "correction_type"))
        object.__setattr__(self, "correction_id", _exact_str(self.correction_id, "correction_id"))
        object.__setattr__(self, "plan_id", _sha256_hex(self.plan_id, "plan_id"))
        object.__setattr__(self, "source_report_digest", _sha256_hex(
            self.source_report_digest, "source_report_digest"))
        object.__setattr__(self, "authorized_by", _exact_str(self.authorized_by, "authorized_by"))
        object.__setattr__(self, "authorized_at_utc", _exact_str(
            self.authorized_at_utc, "authorized_at_utc"))
        if self.designated_face_index is not None:
            object.__setattr__(self, "designated_face_index", _exact_int(
                self.designated_face_index, "designated_face_index"))
        if self.expected_face_tuple is not None:
            object.__setattr__(self, "expected_face_tuple", _face_tuple(
                self.expected_face_tuple, "expected_face_tuple"))
        if self.expected_merge_mapping_digest is not None:
            object.__setattr__(self, "expected_merge_mapping_digest", _sha256_hex(
                self.expected_merge_mapping_digest, "expected_merge_mapping_digest"))
        if self.scope_note is not None:
            object.__setattr__(self, "scope_note", _exact_str(self.scope_note, "scope_note"))
        # field applicability (Wave-3 design §8): the merge fields and the winding fields are mutually
        # exclusive, so an artifact can never carry a parameter that does not belong to its operation.
        if self.correction_type == MERGE_CORRECTION_TYPE:
            if self.designated_face_index is not None or self.expected_face_tuple is not None:
                raise AuthorizationInputError(
                    "a REPAIR_MERGE_VERTEX artifact must not carry designated_face_index or "
                    "expected_face_tuple",
                    failure_code=AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_MERGE,
                )
        elif self.expected_merge_mapping_digest is not None:
            raise AuthorizationInputError(
                f"expected_merge_mapping_digest is not applicable to correction_type "
                f"{self.correction_type!r}",
                failure_code=AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_TYPE,
            )
        # exact tokens only (no case-folding, trimming, prefix or alias normalization)
        if self.authorization_version != AUTHORIZATION_VERSION:
            raise AuthorizationInputError(
                f"authorization_version {self.authorization_version!r} is not supported "
                f"(supported: {AUTHORIZATION_VERSION!r})",
                failure_code=AuthorizationFailureCode.UNSUPPORTED_AUTHORIZATION_VERSION,
            )
        if self.authorization_policy_version not in ACCEPTED_AUTHORIZATION_POLICY_VERSIONS:
            raise AuthorizationInputError(
                f"authorization_policy_version {self.authorization_policy_version!r} is not "
                f"accepted (accepted: {sorted(ACCEPTED_AUTHORIZATION_POLICY_VERSIONS)})",
                failure_code=AuthorizationFailureCode.UNSUPPORTED_POLICY_VERSION,
            )
        if self.decision != DECISION_APPROVED:
            raise AuthorizationInputError(
                f"decision {self.decision!r} is not actionable (only {DECISION_APPROVED!r} is)",
                      failure_code=AuthorizationFailureCode.DECISION_NOT_APPROVED,)
        if self.correction_type not in AUTHORIZABLE_CORRECTION_TYPES:
            raise AuthorizationInputError(
                f"correction_type {self.correction_type!r} is not authorizable by this contract "
                f"(authorizable: {sorted(AUTHORIZABLE_CORRECTION_TYPES)})",
                      failure_code=AuthorizationFailureCode.CORRECTION_TYPE_NOT_AUTHORIZABLE,)

    # -- deterministic serialization ---------------------------------------

    def to_json_compatible(self) -> Dict[str, Any]:
        """JSON-native view of the artifact (attribution fields are inert data, never parsed)."""
        return {
            "authorization_version": self.authorization_version,
            "authorization_policy_version": self.authorization_policy_version,
            "decision": self.decision,
            "correction_type": self.correction_type,
            "correction_id": self.correction_id,
            "plan_id": self.plan_id,
            "source_report_digest": self.source_report_digest,
            "authorized_by": self.authorized_by,
            "authorized_at_utc": self.authorized_at_utc,
            "designated_face_index": self.designated_face_index,
            "expected_face_tuple": (
                list(self.expected_face_tuple) if self.expected_face_tuple is not None else None
            ),
            "scope_note": self.scope_note,
            **(
                {"expected_merge_mapping_digest": self.expected_merge_mapping_digest}
                if self.expected_merge_mapping_digest is not None
                else {}
            ),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical JSON (sorted keys, compact separators, ASCII, no NaN)."""
        return json.dumps(
            self.to_json_compatible(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def digest(self) -> str:
        """SHA-256 over the canonical form — the value recorded in the receipt."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def parse_authorization(value: Any) -> AuthorizationArtifact:
    """Parse an artifact from canonical JSON text or a plain mapping (fail closed).

    Accepts either a ``str`` (strict JSON: duplicate keys and NaN/Infinity rejected) or an exact
    built-in ``dict``. In both cases the value is normalized through the project's canonical-value
    grammar before the contract fields are validated, so subclasses, arbitrary mappings,
    non-JSON types and non-finite numbers never reach the artifact.
    """
    if type(value) is str:
        raw = parse_authorization_json(value)
    elif type(value) is dict:
        raw = value
    else:
        raise AuthorizationInputError(
            "authorization artifact must be canonical JSON text or an exact built-in dict"
        ,
                  failure_code=AuthorizationFailureCode.NOT_A_MAPPING,)

    unknown = sorted(set(raw) - _AUTHORIZATION_FIELDS)
    if unknown:
        raise AuthorizationInputError(f"authorization artifact has unknown field(s): {unknown}", failure_code=AuthorizationFailureCode.UNKNOWN_FIELD)
    missing = sorted(_REQUIRED_FIELDS - set(raw))
    if missing:
        raise AuthorizationInputError(f"authorization artifact is missing field(s): {missing}", failure_code=AuthorizationFailureCode.MISSING_FIELD)

    # Canonicalize through the shared grammar, but keep THIS module's declared error boundary:
    # the grammar raises CorrectionInputError, which is not an AuthorizationError, so a caller
    # catching the authorization error type must not be able to miss it.
    try:
        canon = _canonical_scalar(dict(raw), label="authorization")
    except CorrectionPlannerError as exc:
        raise AuthorizationInputError(f"authorization artifact is not canonical: {exc}", failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID) from exc

    return AuthorizationArtifact(
        authorization_version=canon["authorization_version"],
        authorization_policy_version=canon["authorization_policy_version"],
        decision=canon["decision"],
        correction_type=canon["correction_type"],
        correction_id=canon["correction_id"],
        plan_id=canon["plan_id"],
        source_report_digest=canon["source_report_digest"],
        authorized_by=canon["authorized_by"],
        authorized_at_utc=canon["authorized_at_utc"],
        designated_face_index=canon.get("designated_face_index"),
        expected_face_tuple=canon.get("expected_face_tuple"),
        expected_merge_mapping_digest=canon.get("expected_merge_mapping_digest"),
        scope_note=canon.get("scope_note"),
    )


# ---------------------------------------------------------------------------
# Binding gate (design §1.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PresentedWork:
    """The freshly recomputed identity of the work an artifact is being checked against.

    Every field is a value the caller obtained *outside* the artifact: the selected correction's
    type/id (from the plan), the plan id (recomputed from plan contents by the caller), the source
    digest (recomputed from a fresh extraction by the caller), and the plan-side face designation.
    """

    correction_type: str
    correction_id: str
    plan_id: str
    source_report_digest: str
    selection_mode: str
    plan_designated_face_index: Optional[int] = None
    candidate_pair: Optional[Tuple[int, int]] = None
    execution_face_tuple: Optional[Tuple[int, ...]] = None

    def __post_init__(self) -> None:
        if self.selection_mode not in _SELECTION_MODES:
            raise AuthorizationInputError(
                f"selection_mode must be one of {sorted(_SELECTION_MODES)}"
            ,
                      failure_code=AuthorizationFailureCode.SELECTION_MODE_INVALID,)
        object.__setattr__(self, "correction_type", _exact_str(
            self.correction_type, "presented.correction_type"))
        object.__setattr__(self, "correction_id", _exact_str(
            self.correction_id, "presented.correction_id"))
        object.__setattr__(self, "plan_id", _sha256_hex(self.plan_id, "presented.plan_id"))
        object.__setattr__(self, "source_report_digest", _sha256_hex(
            self.source_report_digest, "presented.source_report_digest"))
        if self.plan_designated_face_index is not None:
            object.__setattr__(self, "plan_designated_face_index", _exact_int(
                self.plan_designated_face_index, "presented.plan_designated_face_index"))
        if self.candidate_pair is not None:
            pair = tuple(self.candidate_pair)
            if len(pair) != 2:
                raise AuthorizationInputError("presented.candidate_pair must have 2 face indices", failure_code=AuthorizationFailureCode.CANDIDATE_PAIR_INVALID)
            for idx in pair:
                _exact_int(idx, "presented.candidate_pair[]")
            if pair[0] == pair[1]:
                raise AuthorizationInputError(
                    "presented.candidate_pair must be two DISTINCT face indices"
                ,
                          failure_code=AuthorizationFailureCode.CANDIDATE_PAIR_INVALID,)
            object.__setattr__(self, "candidate_pair", (pair[0], pair[1]))
        if self.execution_face_tuple is not None:
            object.__setattr__(self, "execution_face_tuple", _face_tuple(
                self.execution_face_tuple, "presented.execution_face_tuple"))


@dataclass(frozen=True, slots=True)
class AuthorizationVerdict:
    """Deterministic result of the authorization gate (never an exception for a mismatch)."""

    ok: bool
    outcome: str
    failure_code: Optional[str] = None

    @property
    def verified(self) -> bool:
        return self.ok

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "authorization_verified": self.ok,
            "outcome": self.outcome,
            "failure_code": self.failure_code,
        }


def _fail(outcome: str, code: str) -> AuthorizationVerdict:
    return AuthorizationVerdict(ok=False, outcome=outcome, failure_code=code)


def resolve_designated_face_index(
    artifact: AuthorizationArtifact, work: PresentedWork
) -> Tuple[Optional[int], Optional[AuthorizationVerdict]]:
    """Return the face index the executor must use, or a failing verdict.

    D1: the plan designates (evidence-derived); the artifact must NOT supply a designation.
    D2: the artifact designates; the index must be one of the plan's recorded candidate pair.
    """
    if work.selection_mode == SELECTION_MODE_D1:
        if artifact.designated_face_index is not None:
            return None, _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                               AuthorizationFailureCode.DESIGNATION_SUPPLIED_FOR_D1)
        if work.plan_designated_face_index is None:
            return None, _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                               AuthorizationFailureCode.PLAN_DESIGNATION_MISSING)
        return work.plan_designated_face_index, None

    # D2
    if work.candidate_pair is None:
        return None, _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                           AuthorizationFailureCode.CANDIDATE_PAIR_MISSING)
    if work.candidate_pair[0] == work.candidate_pair[1]:
        return None, _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                           AuthorizationFailureCode.CANDIDATE_PAIR_INVALID)
    if artifact.designated_face_index is None:
        return None, _fail(AuthorizationOutcome.REQUIRED,
                           AuthorizationFailureCode.DESIGNATION_REQUIRED)
    if artifact.designated_face_index not in work.candidate_pair:
        return None, _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                           AuthorizationFailureCode.DESIGNATION_NOT_IN_CANDIDATE_PAIR)
    return artifact.designated_face_index, None


def verify_authorization(
    artifact: AuthorizationArtifact, work: PresentedWork
) -> AuthorizationVerdict:
    """Verify every binding of design §1.2. Returns a deterministic verdict; never mutates.

    The check order is fixed and stable (it is part of the contract): policy/decision/version
    semantics were already enforced at construction; this gate compares the artifact against the
    *presented* work identity and the plan-side designation.
    """
    # bindings: type -> correction id -> plan id -> source digest
    if artifact.correction_type != work.correction_type:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.CORRECTION_TYPE_MISMATCH)
    if artifact.correction_id != work.correction_id:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.CORRECTION_ID_MISMATCH)
    if artifact.plan_id != work.plan_id:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH, AuthorizationFailureCode.PLAN_ID_MISMATCH)
    if artifact.source_report_digest != work.source_report_digest:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.SOURCE_DIGEST_MISMATCH)

    # designation agreement
    designated, failure = resolve_designated_face_index(artifact, work)
    if failure is not None:
        return failure

    # optional redundant assertion: never authority, but a present-and-disagreeing value fails
    if artifact.expected_face_tuple is not None:
        if work.execution_face_tuple is None:
            return _fail(AuthorizationOutcome.INVALID,
                         AuthorizationFailureCode.EXECUTION_FACE_TUPLE_UNAVAILABLE)
        if tuple(artifact.expected_face_tuple) != tuple(work.execution_face_tuple):
            return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                         AuthorizationFailureCode.EXPECTED_FACE_TUPLE_MISMATCH)

    return AuthorizationVerdict(
        ok=True, outcome=AuthorizationOutcome.VERIFIED, failure_code=None
    )


# ---------------------------------------------------------------------------
# WC-P17: recorded-edge / counterpart contract (design §6 P17, §6.1)
# ---------------------------------------------------------------------------


def _exact_edge(value: Any, label: str) -> Tuple[int, int]:
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(f"{label}: must be a 2-element list/tuple", failure_code=AuthorizationFailureCode.RECORDED_EDGE_ARITY)
    edge = tuple(value)
    if len(edge) != 2:
        raise AuthorizationContractError(
            f"{label}: {AuthorizationFailureCode.RECORDED_EDGE_ARITY}"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGE_ARITY,)
    for idx in edge:
        if type(idx) is not int or type(idx) is bool:
            raise AuthorizationContractError(
                f"{label}: {AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER}"
            ,
                      failure_code=AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER,)
        if idx < 0:
            raise AuthorizationContractError(
                f"{label}: {AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER}"
            ,
                      failure_code=AuthorizationFailureCode.RECORDED_EDGE_NON_INTEGER,)
    if edge[0] == edge[1]:
        raise AuthorizationContractError(
            f"{label}: {AuthorizationFailureCode.RECORDED_EDGE_SELF_LOOP}"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGE_SELF_LOOP,)
    if edge[0] > edge[1]:
        raise AuthorizationContractError(
            f"{label}: {AuthorizationFailureCode.RECORDED_EDGE_NOT_CANONICAL} "
            "(each edge must be written with the smaller index first)"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGE_NOT_CANONICAL,)
    return (edge[0], edge[1])


def validate_recorded_edges(
    recorded_edges: Any,
    counterpart_faces: Any,
    *,
    designated_face_index: Optional[int] = None,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...]]:
    """Validate the plan-side recorded edge/counterpart sets; return them canonicalized.

    Enforced (deterministically, in this order):

    1. ``recorded_edges`` is present and non-empty;
    2. every edge is exactly two non-negative exact ints, not a self-loop, and written
       canonically (smaller index first);
    3. the edge list is strictly increasing — i.e. sorted AND deduplicated (a repeated edge is
       rejected rather than silently collapsed);
    4. ``counterpart_faces`` has exactly one entry per recorded edge (positional alignment);
    5. every counterpart is an exact non-negative int;
    6. **every counterpart differs from the designated face** — an edge cannot list the face being
       reversed as its own counterpart (this is the explicit ``counterpart != designated_face``
       rule; without it the pair check could pass and only the edge-traversal postcondition would
       catch the error downstream).
    """
    if recorded_edges is None:
        raise AuthorizationContractError(
            f"recorded_edges: {AuthorizationFailureCode.RECORDED_EDGES_MISSING}"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGES_MISSING,)
    if type(recorded_edges) not in (tuple, list):
        raise AuthorizationContractError(
            f"recorded_edges: {AuthorizationFailureCode.RECORDED_EDGES_MISSING}"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGES_MISSING,)
    if len(recorded_edges) == 0:
        raise AuthorizationContractError(
            f"recorded_edges: {AuthorizationFailureCode.RECORDED_EDGES_EMPTY}"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_EDGES_EMPTY,)

    edges = tuple(
        _exact_edge(e, f"recorded_edges[{i}]") for i, e in enumerate(recorded_edges)
    )
    for i in range(1, len(edges)):
        if edges[i] == edges[i - 1]:
            raise AuthorizationContractError(
                f"recorded_edges[{i}]: {AuthorizationFailureCode.RECORDED_EDGES_DUPLICATED}"
            ,
                      failure_code=AuthorizationFailureCode.RECORDED_EDGES_DUPLICATED,)
        if edges[i] < edges[i - 1]:
            raise AuthorizationContractError(
                f"recorded_edges[{i}]: {AuthorizationFailureCode.RECORDED_EDGES_NOT_SORTED}"
            ,
                      failure_code=AuthorizationFailureCode.RECORDED_EDGES_NOT_SORTED,)

    if counterpart_faces is None or type(counterpart_faces) not in (tuple, list):
        raise AuthorizationContractError(
            f"counterpart_faces: {AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH}"
        ,
                  failure_code=AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH,)
    if len(counterpart_faces) != len(edges):
        raise AuthorizationContractError(
            f"counterpart_faces: {AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH} "
            f"({len(counterpart_faces)} entries for {len(edges)} recorded edges)"
        ,
                  failure_code=AuthorizationFailureCode.COUNTERPART_COUNT_MISMATCH,)

    counterparts = []
    for i, cp in enumerate(counterpart_faces):
        if type(cp) is not int or type(cp) is bool or cp < 0:
            raise AuthorizationContractError(
                f"counterpart_faces[{i}]: {AuthorizationFailureCode.COUNTERPART_NON_INTEGER}"
            ,
                      failure_code=AuthorizationFailureCode.COUNTERPART_NON_INTEGER,)
        if designated_face_index is not None and cp == designated_face_index:
            raise AuthorizationContractError(
                f"counterpart_faces[{i}]: {AuthorizationFailureCode.COUNTERPART_EQUALS_DESIGNATED_FACE}"
            ,
                      failure_code=AuthorizationFailureCode.COUNTERPART_EQUALS_DESIGNATED_FACE,)
        counterparts.append(cp)

    return edges, tuple(counterparts)


def _fresh_finding(value: Any, label: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Normalize one freshly recomputed winding finding: ``(edge, face_pair)``, both canonical."""
    if type(value) is not dict:
        raise AuthorizationContractError(f"{label}: {AuthorizationFailureCode.FRESH_FINDING_INVALID}", failure_code=AuthorizationFailureCode.FRESH_FINDING_INVALID)
    edge_raw = value.get("edge")
    faces_raw = value.get("faces")
    try:
        edge = _exact_edge(edge_raw, f"{label}.edge")
    except AuthorizationContractError as exc:
        # A malformed edge INSIDE a fresh finding is reported in the fresh-finding vocabulary; the
        # specific edge defect is preserved in the message.
        raise AuthorizationContractError(
            f"{label}: {AuthorizationFailureCode.FRESH_FINDING_INVALID} ({exc})",
            failure_code=AuthorizationFailureCode.FRESH_FINDING_INVALID,
        ) from exc
    if type(faces_raw) not in (tuple, list) or len(faces_raw) != 2:
        raise AuthorizationContractError(
            f"{label}.faces: {AuthorizationFailureCode.FRESH_FINDING_INVALID}"
        ,
                  failure_code=AuthorizationFailureCode.FRESH_FINDING_INVALID,)
    faces = tuple(faces_raw)
    for idx in faces:
        if type(idx) is not int or type(idx) is bool or idx < 0:
            raise AuthorizationContractError(
                f"{label}.faces: {AuthorizationFailureCode.FRESH_FINDING_INVALID}"
            ,
                      failure_code=AuthorizationFailureCode.FRESH_FINDING_INVALID,)
    if faces[0] == faces[1]:
        raise AuthorizationContractError(
            f"{label}.faces: {AuthorizationFailureCode.FRESH_FINDING_INVALID}"
        ,
                  failure_code=AuthorizationFailureCode.FRESH_FINDING_INVALID,)
    return edge, (min(faces), max(faces))


def verify_recorded_set_agreement(
    recorded_edges: Any,
    counterpart_faces: Any,
    fresh_findings: Sequence[Any],
    *,
    designated_face_index: int,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...]]:
    """Execute ``WC-P17`` against the freshly recomputed winding finding set.

    ``fresh_findings`` is the executor's own recomputation of the target mesh's
    ``MESH_WINDING_INCONSISTENT`` findings, each as ``{"edge": [a, b], "faces": [f1, f2]}``.

    Required, all fail-closed:

    - the recorded set is itself valid and canonical (:func:`validate_recorded_edges`);
    - **bidirectional equality**: the recorded edge set equals the recomputed edge set —
      ``recorded ⊆ recomputed`` AND ``recomputed ⊆ recorded`` (a missing edge and an extra edge are
      both ``RECORDED_SET_MISMATCH``);
    - for every recorded edge, the fresh pair contains the designated face
      (``DESIGNATED_NOT_IN_FRESH_PAIR``) and the recorded counterpart
      (``COUNTERPART_NOT_IN_FRESH_PAIR``), and the fresh pair is exactly
      ``{designated, counterpart}``.

    Returns the canonical ``(edges, counterparts)``; raises :class:`AuthorizationContractError`
    with a deterministic failure code otherwise. ``WC-P17`` is load-bearing (design §6.1): the
    recorded-edge postcondition can only be as strong as this set, so it is validated against a
    fresh recomputation rather than trusted.
    """
    if type(designated_face_index) is not int or type(designated_face_index) is bool:
        raise AuthorizationContractError(
            f"designated_face_index: {AuthorizationFailureCode.DESIGNATED_FACE_INVALID}"
        ,
                  failure_code=AuthorizationFailureCode.DESIGNATED_FACE_INVALID,)
    if designated_face_index < 0:
        raise AuthorizationContractError(
            f"designated_face_index: {AuthorizationFailureCode.DESIGNATED_FACE_INVALID}"
        ,
                  failure_code=AuthorizationFailureCode.DESIGNATED_FACE_INVALID,)

    edges, counterparts = validate_recorded_edges(
        recorded_edges, counterpart_faces, designated_face_index=designated_face_index
    )

    fresh: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for i, finding in enumerate(fresh_findings):
        edge, faces = _fresh_finding(finding, f"fresh_findings[{i}]")
        # A duplicated canonical edge is REJECTED, never resolved by ordering or last-write-wins:
        # a contradictory recomputation is a malformed input, not something to pick a winner from.
        if edge in fresh:
            raise AuthorizationContractError(
                f"fresh_findings[{i}]: {AuthorizationFailureCode.DUPLICATE_FRESH_EDGE} "
                f"(edge {edge} recomputed more than once)",
                failure_code=AuthorizationFailureCode.DUPLICATE_FRESH_EDGE,
            )
        fresh[edge] = faces

    missing = [e for e in edges if e not in fresh]
    extra = sorted(e for e in fresh if e not in set(edges))
    if missing or extra:
        raise AuthorizationContractError(
            f"{AuthorizationFailureCode.RECORDED_SET_MISMATCH} "
            f"(missing={missing}, extra={extra})"
        ,
                  failure_code=AuthorizationFailureCode.RECORDED_SET_MISMATCH,)

    for edge, cp in zip(edges, counterparts):
        faces = fresh[edge]
        if designated_face_index not in faces:
            raise AuthorizationContractError(
                f"{AuthorizationFailureCode.DESIGNATED_NOT_IN_FRESH_PAIR} (edge {edge})"
            ,
                      failure_code=AuthorizationFailureCode.DESIGNATED_NOT_IN_FRESH_PAIR,)
        if cp not in faces:
            raise AuthorizationContractError(
                f"{AuthorizationFailureCode.COUNTERPART_NOT_IN_FRESH_PAIR} (edge {edge})"
            ,
                      failure_code=AuthorizationFailureCode.COUNTERPART_NOT_IN_FRESH_PAIR,)
        # No further check is needed, and none is written: ``_fresh_finding`` guarantees the pair
        # has exactly two entries, ``validate_recorded_edges`` guarantees ``cp != designated``, and
        # both members were just proven present — therefore ``set(faces)`` is exactly
        # ``{designated_face_index, cp}``. Writing that as a runtime branch would be unreachable
        # code; the implication is asserted by the tests instead.

    return edges, counterparts


__all__ = [
    "ACCEPTED_AUTHORIZATION_POLICY_VERSIONS",
    "AUTHORIZATION_VERSION",
    "AuthorizationArtifact",
    "AuthorizationContractError",
    "AuthorizationError",
    "AuthorizationFailureCode",
    "AuthorizationInputError",
    "AuthorizationOutcome",
    "AuthorizationVerdict",
    "AUTHORIZABLE_CORRECTION_TYPES",
    "DECISION_APPROVED",
    "MERGE_CASE_EXACT",
    "MERGE_CASE_SUB_GRID",
    "MERGE_COINCIDENCE_DECIMALS",
    "MERGE_CORRECTION_TYPE",
    "MergePresentedWork",
    "PresentedWork",
    "SELECTION_MODE_D1",
    "SELECTION_MODE_D2",
    "WINDING_CORRECTION_TYPE",
    "parse_authorization",
    "parse_authorization_json",
    "canonical_coincidence_key",
    "canonical_survivor_indices",
    "classify_duplicate_group_case",
    "make_index_mapping",
    "mapping_digest",
    "require_supported_case",
    "resolve_designated_face_index",
    "validate_duplicate_groups",
    "validate_index_mapping",
    "validate_survivor_indices",
    "validate_target_object_mesh",
    "verify_merge_authorization",
    "validate_recorded_edges",
    "verify_authorization",
    "verify_recorded_set_agreement",
]


# ---------------------------------------------------------------------------
# Wave-3: REPAIR_MERGE_VERTEX contract layer (design §2/§3/§4/§8)
# ---------------------------------------------------------------------------
#
# This section validates the merge contract's *values*. It is inert: it derives nothing from a plan
# it was not given, never picks a survivor at runtime, never normalizes a coordinate, and never
# touches topology. Every failure is a declared AuthorizationContractError / AuthorizationInputError
# carrying a stable failure code.


def validate_target_object_mesh(value: Any) -> Tuple[str, str]:
    """Validate the exact ``target_object_mesh`` shape (Wave-3 design §10).

    ``{"object_id": <canonical string>, "mesh_id": <canonical string>}`` with NO extra keys. The
    pair is binding data only: no alias, no identity semantics, no cross-object/cross-mesh scope.
    """
    if type(value) is not dict:
        raise AuthorizationContractError(
            "target_object_mesh must be an exact built-in dict",
            failure_code=AuthorizationFailureCode.TARGET_SHAPE_INVALID,
        )
    extra = sorted(set(value) - {"object_id", "mesh_id"})
    if extra:
        raise AuthorizationContractError(
            f"target_object_mesh has unknown field(s): {extra}",
            failure_code=AuthorizationFailureCode.TARGET_EXTRA_KEY,
        )
    missing = sorted({"object_id", "mesh_id"} - set(value))
    if missing:
        raise AuthorizationContractError(
            f"target_object_mesh is missing field(s): {missing}",
            failure_code=AuthorizationFailureCode.TARGET_MESH_UNRESOLVED,
        )
    object_id = _exact_str(value["object_id"], "target_object_mesh.object_id")
    mesh_id = _exact_str(value["mesh_id"], "target_object_mesh.mesh_id")
    return object_id, mesh_id


def _canonical_coordinate(value: Any, field: str = "coordinate") -> Tuple[Any, Any, Any]:
    """Validate a vertex coordinate as a 3-component sequence of exact int/float values.

    Container and member shape are checked BEFORE any indexing or arithmetic, so malformed input fails
    closed through the declared boundary instead of leaking a raw ``TypeError``/``ValueError``. Values
    are passed through unchanged (no coercion): the case decision stays a bitwise comparison.
    """
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(
            f"{field} must be a list/tuple of three numeric components",
            failure_code=AuthorizationFailureCode.MAPPING_ENTRY_INVALID,
        )
    if len(value) != 3:
        raise AuthorizationContractError(
            f"{field} must have exactly three components",
            failure_code=AuthorizationFailureCode.MAPPING_ENTRY_INVALID,
        )
    for position, component in enumerate(value):
        if type(component) is not int and type(component) is not float:
            raise AuthorizationContractError(
                f"{field}[{position}] must be an exact built-in int or float",
                failure_code=AuthorizationFailureCode.MAPPING_ENTRY_INVALID,
            )
    return (value[0], value[1], value[2])


def _canonical_vertex_table(value: Any) -> Tuple[Tuple[Any, Any, Any], ...]:
    """Validate a fresh vertex table as a sequence of 3-component coordinates (shape only).

    Reuses ``_canonical_coordinate`` so there is ONE coordinate grammar in the module. Coordinates are
    preserved verbatim — the EXACT/SUB_GRID decision must see the raw values.
    """
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(
            "vertex_table must be a list/tuple of coordinates",
            failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID,
        )
    table = []
    for position, coordinate in enumerate(value):
        table.append(_canonical_coordinate(coordinate, f"vertex_table[{position}]"))
    return tuple(table)


def _canonical_groups(value: Any) -> Tuple[Tuple[int, ...], ...]:
    """The ONE declared duplicate-group validation path, reused by every consumer (design §4)."""
    return validate_duplicate_groups(value)


def _canonical_mapping(value: Any, field: str = "mapping") -> Tuple[int, ...]:
    """Validate an index-mapping sequence before it is iterated (declared errors only)."""
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(
            f"{field} must be a list/tuple of vertex indices",
            failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID,
        )
    return tuple(_exact_int(entry, f"{field}[]") for entry in value)


def canonical_coincidence_key(coordinate: Sequence[float]) -> Tuple[float, float, float]:
    """The kernel's canonical coincidence key: decimal half-to-even at six places, per component.

    Mirrors ``mesh_health._rounded_vertex_key`` exactly. A C++ implementation must reproduce this
    rounding rule bit-for-bit (design §14).
    """
    x, y, z = _canonical_coordinate(coordinate)
    return (
        round(x, MERGE_COINCIDENCE_DECIMALS),
        round(y, MERGE_COINCIDENCE_DECIMALS),
        round(z, MERGE_COINCIDENCE_DECIMALS),
    )


def validate_duplicate_groups(value: Any, *, mesh_id: Optional[str] = None) -> Tuple[Tuple[int, ...], ...]:
    """Validate the canonical duplicate-group representation (Wave-3 design §4).

    Rules (all fail closed, nothing is inferred): a list/tuple of groups; each group has at least two
    members; members are exact non-negative ints, strictly ascending and unique; groups are pairwise
    disjoint; groups are ordered by ascending survivor (which is ``min(group)``). Omitted members are
    NEVER inferred — the declared representation must be complete or it is rejected.
    """
    if mesh_id is not None:
        _exact_str(mesh_id, "mesh_id")
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(
            "duplicate_groups must be a list/tuple of groups",
            failure_code=AuthorizationFailureCode.GROUP_MISMATCH,
        )
    groups: list = []
    seen: set = set()
    for position, raw_group in enumerate(value):
        if type(raw_group) not in (tuple, list):
            raise AuthorizationContractError(
                f"duplicate_groups[{position}] must be a list/tuple of vertex indices",
                failure_code=AuthorizationFailureCode.GROUP_MISMATCH,
            )
        members = tuple(_exact_int(i, f"duplicate_groups[{position}][]") for i in raw_group)
        if len(members) < 2:
            raise AuthorizationContractError(
                f"duplicate_groups[{position}] must have at least two members",
                failure_code=AuthorizationFailureCode.GROUP_TOO_SMALL,
            )
        if len(set(members)) != len(members):
            raise AuthorizationContractError(
                f"duplicate_groups[{position}] repeats a member index",
                failure_code=AuthorizationFailureCode.GROUP_MEMBERS_NOT_UNIQUE,
            )
        if tuple(sorted(members)) != members:
            raise AuthorizationContractError(
                f"duplicate_groups[{position}] members must be in ascending order",
                failure_code=AuthorizationFailureCode.GROUP_MEMBERS_NOT_ASCENDING,
            )
        overlap = sorted(set(members) & seen)
        if overlap:
            raise AuthorizationContractError(
                f"duplicate_groups[{position}] overlaps an earlier group at {overlap}",
                failure_code=AuthorizationFailureCode.GROUP_MEMBERS_OVERLAP,
            )
        seen.update(members)
        groups.append(members)
    for previous, current in zip(groups, groups[1:]):
        if min(previous) >= min(current):
            raise AuthorizationContractError(
                "duplicate_groups must be ordered by ascending canonical survivor",
                failure_code=AuthorizationFailureCode.GROUP_NOT_CANONICALLY_ORDERED,
            )
    return tuple(groups)


def canonical_survivor_indices(groups: Sequence[Sequence[int]]) -> Tuple[int, ...]:
    """The canonical survivor of each group is ``min(group)`` — pinned, never chosen at runtime."""
    return tuple(min(group) for group in _canonical_groups(groups))


def validate_survivor_indices(
    declared: Any, groups: Sequence[Sequence[int]]
) -> Tuple[int, ...]:
    """Validate declared survivor indices against the canonical rule (Wave-3 design §3).

    There is no fallback survivor: a declaration that differs from ``min(group)`` in any position, or
    that has the wrong length, or that names a non-member, is rejected.
    """
    if declared is None:
        raise AuthorizationContractError(
            "survivor_indices must be declared explicitly (never inferred)",
            failure_code=AuthorizationFailureCode.SURVIVOR_COUNT_MISMATCH,
        )
    if type(declared) not in (tuple, list):
        raise AuthorizationContractError(
            "survivor_indices must be a list/tuple of vertex indices",
            failure_code=AuthorizationFailureCode.SURVIVOR_COUNT_MISMATCH,
        )
    declared_tuple = tuple(_exact_int(i, "survivor_indices[]") for i in declared)
    canonical_groups = _canonical_groups(groups)
    canonical = tuple(min(group) for group in canonical_groups)
    if len(declared_tuple) != len(canonical):
        raise AuthorizationContractError(
            f"survivor_indices has {len(declared_tuple)} entries but the plan declares "
            f"{len(canonical)} group(s)",
            failure_code=AuthorizationFailureCode.SURVIVOR_COUNT_MISMATCH,
        )
    for group, declared_survivor in zip(canonical_groups, declared_tuple):
        if declared_survivor not in group:
            raise AuthorizationContractError(
                f"survivor {declared_survivor} is not a member of its group",
                failure_code=AuthorizationFailureCode.SURVIVOR_NOT_IN_GROUP,
            )
        if declared_survivor != min(group):
            raise AuthorizationContractError(
                f"survivor {declared_survivor} is not the canonical survivor {min(group)} of its "
                f"group",
                failure_code=AuthorizationFailureCode.SURVIVOR_NOT_GROUP_MINIMUM,
            )
    return declared_tuple


def classify_duplicate_group_case(
    vertex_table: Sequence[Sequence[float]], group: Sequence[int]
) -> str:
    """Classify a group as EXACT (all members bit-identical to the survivor) or SUB_GRID.

    The decision is a strict bitwise comparison of the raw coordinate tuples — never the rounded
    coincidence key, never a tolerance (Wave-3 design §2). Malformed input fails closed with a
    declared contract error rather than an incidental Python exception.
    """
    if type(group) not in (tuple, list):
        raise AuthorizationContractError(
            "group must be a list/tuple of vertex indices",
            failure_code=AuthorizationFailureCode.GROUP_MISMATCH,
        )
    members = tuple(_exact_int(member, "group[]") for member in group)
    if len(members) < 2:
        raise AuthorizationContractError(
            "group must have at least two members",
            failure_code=AuthorizationFailureCode.GROUP_TOO_SMALL,
        )
    table = _canonical_vertex_table(vertex_table)
    vertex_count = len(table)
    survivor = min(members)
    for member in members:
        if member >= vertex_count:
            raise AuthorizationContractError(
                f"group member {member} is outside the vertex table ({vertex_count} vertices)",
                failure_code=AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE,
            )
    reference = tuple(table[survivor])
    for member in members:
        if tuple(table[member]) != reference:
            return MERGE_CASE_SUB_GRID
    return MERGE_CASE_EXACT


def require_supported_case(
    vertex_table: Sequence[Sequence[float]], groups: Sequence[Sequence[int]]
) -> Tuple[str, ...]:
    """Return each group's case, refusing the unsupported sub-grid case (design PIN M1).

    Case B (sub-grid: equal only under the rounded key) is refused fail-closed — merging it would
    change a coordinate by up to 1e-6 per component, which this capability does not claim to be
    lossless about. Nothing is normalized or reinterpreted here.
    """
    table = _canonical_vertex_table(vertex_table)
    canonical_groups = _canonical_groups(groups)
    for group in canonical_groups:
        for member in group:
            if member >= len(table):
                raise AuthorizationContractError(
                    f"group member {member} is outside the vertex table ({len(table)} vertices)",
                    failure_code=AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE,
                )
        keys = [canonical_coincidence_key(table[member]) for member in group]
        if any(key != keys[0] for key in keys[1:]):
            raise AuthorizationContractError(
                "GROUP_MISMATCH: a declared group's members do not share the kernel's canonical "
                "coincidence key; groups must be real coincidence classes",
                failure_code=AuthorizationFailureCode.GROUP_MISMATCH,
            )
    cases = tuple(classify_duplicate_group_case(table, group) for group in canonical_groups)
    if MERGE_CASE_SUB_GRID in cases:
        raise AuthorizationContractError(
            "SUB_GRID_COLLAPSE_UNSUPPORTED: at least one duplicate group is not bit-identical; "
            "sub-grid groups must stay review-only",
            failure_code=AuthorizationFailureCode.SUB_GRID_COLLAPSE_UNSUPPORTED,
        )
    return cases


def make_index_mapping(
    vertex_count: int, groups: Sequence[Sequence[int]]
) -> Tuple[int, ...]:
    """Derive the canonical old -> new index mapping (sigma then rho, design §4).

    Integer-only and independent of any container iteration order: the kept set is the sorted image
    of the survivor map, and each entry is that vertex's rank in it.
    """
    vertex_count = _exact_int(vertex_count, "vertex_count")
    canonical_groups = _canonical_groups(groups)
    survivor_of: Dict[int, int] = {}
    for group in canonical_groups:
        survivor = min(group)
        for member in group:
            if member >= vertex_count:
                raise AuthorizationContractError(
                    f"group member {member} is outside the vertex table ({vertex_count} vertices)",
                    failure_code=AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE,
                )
            survivor_of[member] = survivor
    kept = sorted({survivor_of.get(i, i) for i in range(vertex_count)})
    rank = {vertex: position for position, vertex in enumerate(kept)}
    return tuple(rank[survivor_of.get(i, i)] for i in range(vertex_count))


def mapping_digest(mesh_id: str, vertex_count: int, mapping: Sequence[int]) -> str:
    """The canonical mapping digest (design §4 R6): SHA-256 over canonical JSON, no new digest kind."""
    mesh_id = _exact_str(mesh_id, "mesh_id")
    vertex_count = _exact_int(vertex_count, "vertex_count")
    canonical = _canonical_mapping(mapping)
    kept = sorted(set(canonical))
    payload = {
        "mesh_id": mesh_id,
        "n": vertex_count,
        "m": len(kept),
        "kept": list(kept),
        "sigma": list(canonical),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def validate_index_mapping(
    value: Any,
    *,
    mesh_id: str,
    vertex_count: int,
    groups: Sequence[Sequence[int]],
) -> Tuple[int, ...]:
    """Validate a declared mapping against the derived canonical one (Wave-3 design §4/§6).

    Every source vertex must be represented exactly once, survivors must map to themselves, removed
    members must map to their group's survivor, and the declared entry must equal the derived one —
    a "close" mapping is not accepted, because the mapping is the contract.
    """
    mesh_id = _exact_str(mesh_id, "mesh_id")
    vertex_count = _exact_int(vertex_count, "vertex_count")
    canonical_groups = _canonical_groups(groups)
    derived = make_index_mapping(vertex_count, canonical_groups)
    expected_digest = mapping_digest(mesh_id, vertex_count, derived)
    if type(value) not in (tuple, list):
        raise AuthorizationContractError(
            "old_to_new_mapping must be a list/tuple of vertex indices",
            failure_code=AuthorizationFailureCode.MAPPING_LENGTH_MISMATCH,
        )
    if len(value) != vertex_count:
        raise AuthorizationContractError(
            f"old_to_new_mapping has {len(value)} entries but the pre-state has {vertex_count} "
            f"vertices",
            failure_code=AuthorizationFailureCode.MAPPING_LENGTH_MISMATCH,
        )
    declared = tuple(_exact_int(entry, "old_to_new_mapping[]") for entry in value)
    kept_count = len(set(derived))
    for index, entry in enumerate(declared):
        if entry >= kept_count:
            raise AuthorizationContractError(
                f"old_to_new_mapping[{index}] = {entry} is outside the post-state range "
                f"[0, {kept_count})",
                failure_code=AuthorizationFailureCode.MAPPING_TARGET_OUT_OF_RANGE,
            )
    survivor_set = set(canonical_survivor_indices(canonical_groups))
    for index, (declared_entry, derived_entry) in enumerate(zip(declared, derived)):
        if declared_entry == derived_entry:
            continue
        if index in survivor_set:
            raise AuthorizationContractError(
                f"old_to_new_mapping[{index}] must map the survivor to itself",
                failure_code=AuthorizationFailureCode.MAPPING_SURVIVOR_MISMATCH,
            )
        if index in {member for group in canonical_groups for member in group}:
            raise AuthorizationContractError(
                f"old_to_new_mapping[{index}] must map the removed duplicate to its survivor",
                failure_code=AuthorizationFailureCode.MAPPING_REMOVED_NOT_MAPPED,
            )
        raise AuthorizationContractError(
            f"old_to_new_mapping[{index}] is not canonical (expected {derived_entry}, got "
            f"{declared_entry})",
            failure_code=AuthorizationFailureCode.MAPPING_NONCANONICAL,
        )
    if mapping_digest(mesh_id, vertex_count, declared) != expected_digest:
        raise AuthorizationContractError(
            "old_to_new_mapping digest does not match the canonical mapping",
            failure_code=AuthorizationFailureCode.MAPPING_DIGEST_MISMATCH,
        )
    return declared


@dataclass(frozen=True, slots=True)
class MergePresentedWork:
    """The freshly recomputed identity of the merge work an artifact is checked against.

    Every field is a value the caller obtained OUTSIDE the artifact: the selected correction's
    type/id (from the plan), the plan id (recomputed from plan contents), the source digest
    (recomputed from a fresh extraction), the exact target pair, the **plan-side** target pair (so a
    pair naming another object or mesh can never be presented against an artifact bound to a different
    one), the canonical duplicate groups, the recomputed canonical mapping digest, and whether every
    group is case-EXACT.
    """

    correction_type: str
    correction_id: str
    plan_id: str
    source_report_digest: str
    target_object_mesh: Tuple[str, str]
    duplicate_groups: Tuple[Tuple[int, ...], ...]
    plan_target_object_mesh: Optional[Tuple[str, str]] = None
    mapping_digest: Optional[str] = None
    all_groups_exact: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "correction_type", _exact_str(
            self.correction_type, "presented.correction_type"))
        object.__setattr__(self, "correction_id", _exact_str(
            self.correction_id, "presented.correction_id"))
        object.__setattr__(self, "plan_id", _sha256_hex(self.plan_id, "presented.plan_id"))
        object.__setattr__(self, "source_report_digest", _sha256_hex(
            self.source_report_digest, "presented.source_report_digest"))
        object_id, mesh_id = validate_target_object_mesh(self.target_object_mesh)
        object.__setattr__(self, "target_object_mesh", (object_id, mesh_id))
        object.__setattr__(self, "duplicate_groups", validate_duplicate_groups(
            self.duplicate_groups, mesh_id=mesh_id))
        if self.plan_target_object_mesh is not None:
            object.__setattr__(self, "plan_target_object_mesh", validate_target_object_mesh(
                self.plan_target_object_mesh))
        if self.mapping_digest is not None:
            object.__setattr__(self, "mapping_digest", _sha256_hex(
                self.mapping_digest, "presented.mapping_digest"))
        if type(self.all_groups_exact) is not bool:
            raise AuthorizationInputError(
                "presented.all_groups_exact must be an exact bool",
                failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID,
            )

    @property
    def survivor_indices(self) -> Tuple[int, ...]:
        return canonical_survivor_indices(self.duplicate_groups)


def verify_merge_authorization(
    artifact: AuthorizationArtifact, work: MergePresentedWork
) -> AuthorizationVerdict:
    """Verify every binding of the merge contract. Deterministic verdict; never mutates.

    The merge operation's target pair, group scope, survivor rule, case classification and mapping
    equivalence are bound to the artifact through the plan (``plan_id`` + ``correction_id``) and,
    optionally, through the human's ``expected_merge_mapping_digest`` assertion — which is *verified*
    against the recomputed canonical digest, never trusted as authority.
    """
    if not isinstance(work, MergePresentedWork):
        raise AuthorizationInputError(
            "verify_merge_authorization requires MergePresentedWork",
            failure_code=AuthorizationFailureCode.FIELD_TYPE_INVALID,
        )
    # field applicability first: an artifact may never carry a parameter of another operation.
    if artifact.designated_face_index is not None or artifact.expected_face_tuple is not None:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_MERGE)
    if artifact.correction_type != MERGE_CORRECTION_TYPE:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.FIELD_NOT_APPLICABLE_TO_TYPE)
    # the presented target must be the target the PLAN refers to (a plan-side value, never the
    # artifact's), so a pair naming another object or mesh can never ride an artifact for this one.
    if work.plan_target_object_mesh is not None and tuple(work.plan_target_object_mesh) != tuple(
        work.target_object_mesh
    ):
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.TARGET_CROSS_MESH)
    # bindings: type -> correction id -> plan id -> source digest
    if artifact.correction_type != work.correction_type:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.CORRECTION_TYPE_MISMATCH)
    if artifact.correction_id != work.correction_id:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.CORRECTION_ID_MISMATCH)
    if artifact.plan_id != work.plan_id:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH, AuthorizationFailureCode.PLAN_ID_MISMATCH)
    if artifact.source_report_digest != work.source_report_digest:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.SOURCE_DIGEST_MISMATCH)
    # the operation itself must be admissible before any authority is granted
    if not work.all_groups_exact:
        return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                     AuthorizationFailureCode.SUB_GRID_COLLAPSE_UNSUPPORTED)
    # optional redundant human assertion: verified, never authority
    if artifact.expected_merge_mapping_digest is not None:
        if work.mapping_digest is None:
            return _fail(AuthorizationOutcome.INVALID,
                         AuthorizationFailureCode.MAPPING_DIGEST_MISMATCH)
        if artifact.expected_merge_mapping_digest != work.mapping_digest:
            return _fail(AuthorizationOutcome.SCOPE_MISMATCH,
                         AuthorizationFailureCode.EXPECTED_MAPPING_DIGEST_MISMATCH)
    return AuthorizationVerdict(
        ok=True, outcome=AuthorizationOutcome.VERIFIED, failure_code=None
    )
