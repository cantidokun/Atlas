"""M12.4 semantic -> existing Atlas/Unreal runtime adapter (narrow bridge).

M12.4 is an ADAPTER, never a new authority. It consumes a validated
:class:`UnrealExecutionPlan` (M12.3) together with the validated source
:class:`UnrealProductionTaskDefinition` (M12.1) and produces an immutable
:class:`UnrealRuntimeMapping` describing exactly how each semantic step maps onto
the EXISTING Atlas runtime representation (an :class:`AtlasTaskDefinition` via
the existing M12.1 compile boundary).

Critical invariants (enforced by construction AND by one canonical validation
path, not by convention):

- It does NOT authorize, execute, schedule, retry, recover, persist, mint receipts,
  produce evidence manifests, or verify anything. ``can_execute`` is always False.
- It does NOT import or reach any M4-M10 production-authority module (render
  submission, recovery coordinator, receipt/store, evidence, job store/record).
- It does NOT create a second runtime, scheduler, retry, persistence, receipt,
  recovery, or evidence authority. M12.4 reuses the existing M12.1 compiler to
  produce the existing :class:`AtlasTaskDefinition` runtime representation.
- RENDER CLASSIFICATION derives from the UNION of authoritative axes: the source
  task's canonical task class AND the canonical fragment render semantics
  (``render_execution_constrained`` / non-``expandable`` fragments such as
  ``render_setup``). Any conflict between class and canonical fragment render
  semantics FAILS CLOSED. A render-constrained split or non-expandable fragment
  is NEVER routed through the ordinary non-render runtime path.
- RUNTIME ACTION AUTHORITY is independently reconciled against the inspect-only
  contract: after compiling the source task, the adapter verifies the compiled
  ``AtlasTaskDefinition`` carries ONLY the ``unreal_inspect`` tool in
  ``allowed_action_tools`` and that every action and evidence tool is
  ``unreal_inspect`` with write authority removed. Any write/render tool in the
  emitted runtime representation FAILS CLOSED (it is never merely zeroed).
- Authority/security material (authorization IDs, receipts, HMAC, credentials,
  protected flags, recovery/artifact authority, scheduler/retry directives,
  session/jwt/bearer/token/secret/signature/mac/key/grant/capability/approved/
  claims/scope/permission material) is REJECTED via a CLOSED ALLOWLIST of
  provenance keys plus a recursive scan of structured values; unknown or
  authority-shaped material FAILS CLOSED, never silently forwarded.
- Step semantics (required inputs, dependencies, target-state contributions,
  idempotence, fragment identity/version, preconditions, verification
  requirements) are re-derived from the CANONICAL fragment and reconciled with
  the plan for EVERY mapped step, including render-bearing steps. Every required
  input/dependency MUST be authoritatively resolved by an earlier producer; an
  unresolved requirement FAILS CLOSED (never an empty-dependency representation).
- The runtime representation honors the plan's semantic capability: an
  inspect-only plan never emits a write-capable ``AtlasTaskDefinition``.
- The mapping's runtime-task SNAPSHOT is the SOLE authoritative runtime-task
  representation; it is immutable and JSON-serializable. ``materialize_runtime_task()``
  rebuilds ONLY from that snapshot (no hidden mutable backing object) and asserts
  the rebuilt snapshot's digest equals the recorded ``runtime_task_digest``.
- Canonical identity/version fields have ONE authoritative source. Caller-supplied
  ``catalog_version`` must agree with the plan and (when present) the resolved
  source metadata, or it fails closed. No shadow representations survive.
- Fields are classified machine-visibly: ``reconciled`` fields are re-derived and
  validated; ``declared`` is True exactly when verbatim/unreconciled caller
  content is carried; ``unsupported`` steps fail closed. ``declared`` is never
  used to present unvalidated data as validated truth.
- Canonical serialization is STRICT JSON: ``allow_nan=False``, string-only
  mapping keys, finite numbers only, unsupported object types rejected. Semantic
  distinctness is not collapsed by coercion.
- Construction of :class:`UnrealRuntimeMapping` / :class:`UnrealRuntimeStepMapping`
  is SELF-VALIDATING via a single canonical validation path (provenance allowlist,
  source digest shape, render consistency, runtime authority consistency, digest
  binding). An invalid directly-constructed mapping FAILS CLOSED.

Semantic fidelity model: the existing Atlas runtime represents an M12 semantic
task as a SINGLE aggregate :class:`AtlasTaskDefinition` (one unreal_inspect
action) built by the M12.1 compiler. It has no per-fragment runtime operations.
Consequently M12.4's mapping is aggregate at the task level (``semantic_fidelity``
= ``"aggregate"``): the fragment identities / versions / dependencies are carried
in the compiled task metadata and in each step mapping, but the runtime does NOT
produce one independently executable operation per fragment. M12.4 therefore
never claims per-fragment executable fidelity; per-step meaning is preserved as
reconciled semantics for a future verifier (M12.5), not as distinct runtime
operations.

M12.5-deferred boundary: independent evidence verification is NOT implemented
here. The runtime snapshot never marks anything verified; the placeholder
evaluator is explicitly classified ``runtime_evaluator_kind = structural-placeholder``
and ``independently_verified = False`` so no future layer mistakes a declaration
for authoritative verification.
"""

from __future__ import annotations

import copy as _copy
import dataclasses
import hashlib
import json
import math
import numbers
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

from planning.m12.execution_plan import UnrealExecutionPlan
from planning.m12.fragments import UnrealProductionFragment
from planning.m12.fragments_registry import canonical_fragment
from planning.m12.semantic_task import (
    UnrealProductionTaskDefinition,
    UnrealSemanticTaskError,
    compile_unreal_semantic_task,
    compute_source_content_digest,
)
from planning.task_definition import AtlasTaskDefinition
from action_plan import ActionSpec
from planning.evidence_plan import EvidenceRequest
from planning.target_state import StateInvariant, TargetStateEvaluator

# Sentinel reason recorded on every step of a render-bearing plan to make the
# boundary explicit and audit-able while carrying no authorization material.
REQUIRES_EXISTING_RENDER_SUBMISSION_PATH = "requires-existing-render-submission-path"

# The single existing runtime tool that M12 non-render semantic tasks realize on
# as a task-level aggregate. M12.1's compiler emits one inspect action per
# composed task; the adapter records that tool as the aggregate target instead of
# inventing a new one.
EXISTING_RUNTIME_INSPECT_TOOL = "unreal_inspect"

# Adapter-owned provenance keys (authoritative adapter truth). A caller supplying
# any of these is REJECTED (no shadow/conflicting fields survive), even nested.
_ADAPTER_RESERVED_PROVENANCE_KEYS: FrozenSet[str] = frozenset(
    {
        "mapped_runtime_task_type",
        "recognized_render_plan",
        "semantic_fidelity",
        "source_task_digest",
        "runtime_task_digest",
        "declared",
        "reconciled",
        "runtime_evaluator_kind",
        "independently_verified",
    }
)

# R4-5: TYPED CLOSED PROVENANCE SCHEMA. Every accepted caller provenance field
# has an explicit name, exact type, and semantic meaning:
#   proposal_source: str — which proposal produced this plan/task.
#   source_task_version: int — the resolved source semantic task version.
#   note: str — caller free-form descriptive text (NON-authoritative; a plain
#               str only — nested/free-form structures are rejected).
#   fragment_id: str — the M12.3-DECLARED canonical fragment identity. This is
#               RECONCILED by the adapter (the canonical fragment wins); a
#               caller-forged value is overwritten, never trusted.
#   fragment_version: int — reconciled to the canonical fragment version.
#   target_state_contribution: list[str] — reconciled to the canonical
#               fragment's contributed invariant names.
# Unknown keys, nested undeclared structures, and free-form caller metadata are
# REJECTED (fail closed), not forwarded. Only the mapping-level adapter-owned
# keys (in _ADAPTER_RESERVED_PROVENANCE_KEYS) are the adapter's authoritative
# truth and a caller may never supply them.
_CALLER_PROVENANCE_SCHEMA: Dict[str, type] = {
    "proposal_source": str,
    "source_task_version": int,
    "note": str,
    "fragment_id": str,
    "fragment_version": int,
    "target_state_contribution": list,
}
# Adapter-owned keys are the MAPPING-level authoritative fields; a caller may
# never supply them (no shadow truth survives), even nested.
_ADAPTER_OWNED_KEYS: FrozenSet[str] = _ADAPTER_RESERVED_PROVENANCE_KEYS

# Closed allowlist of source-derived metadata keys that legitimately reach the
# runtime snapshot. Unknown source metadata keys are rejected.
_ALLOWED_SOURCE_METADATA_KEYS: FrozenSet[str] = frozenset(
    {
        "catalog_entry",
        "catalog_version",
        "fragments",
        "parameters",
        "unreal_digital_twin_id",
        "unreal_provenance",
        "unreal_semantic_dependencies",
        "unreal_semantic_intent",
        "unreal_semantic_task_class",
        "unreal_semantic_task_id",
        "unreal_semantic_task_version",
        "unreal_target_state",
    }
)

# Adapter-inserted disclosure fields placed in the runtime snapshot metadata so
# the mapping is unambiguous about what is authoritative vs declared vs deferred.
_ADAPTER_METADATA_DISCLOSURE_KEYS: FrozenSet[str] = frozenset(
    {
        "m12.4.evaluator_kind",
        "m12.4.independently_verified",
        "m12.4.declared",
    }
)

_MAX_DEPTH = 20

# ---------------------------------------------------------------------------
# Authority / security material model (closed allowlist + recursive scan).
# The CLOSED ALLOWLIST is the primary gate (unknown top-level provenance keys are
# rejected). The recursive authority-shape scan is defense-in-depth applied to
# structured VALUES (e.g. catalog `parameters`) so authority material hidden
# inside an otherwise-allowed container cannot survive.
# ---------------------------------------------------------------------------

_AUTHORITY_NORMALIZED_KEYS: FrozenSet[str] = frozenset(
    {
        "authorization", "authorizationid", "authorisation", "authorised",
        "authorized", "isauthorized", "isauthorised", "auth", "authid",
        "receipt", "receiptid", "receipthash",
        "nonce", "attemptnonce", "nonceid",
        "hmac", "hmackey", "hmacsecret",
        "apikey", "apitoken", "accesstoken", "accesstoken", "idtoken",
        "refreshtoken", "refreshtoken", "bearer", "bearertoken",
        "credential", "credentials", "password", "passwd",
        "secret", "clientsecret", "serversecret", "privatekey", "publickey",
        "signingkey", "session", "sessiontoken", "sessionid", "cookie",
        "jwt", "cert", "certificate",
        "recovery", "recoveryauthority", "retrycontroller", "scheduler", "retry",
        "protected", "protectedflag", "isprotected",
        "manifest", "manifestid", "artifact", "artifactid", "artifactmanifest",
        "attempt", "attemptid",
        "signature", "sig", "mac", "key", "grant", "capability", "approved",
        "claims", "scope", "permission", "principal", "token", "privatekey",
    }
)

_AUTHORITY_SUBSTRINGS: Tuple[str, ...] = (
    "authorization", "authorizationid", "authorised", "receipt", "nonce", "hmac",
    "credential", "password", "passwd", "secret", "bearer", "session", "jwt",
    "recovery", "retry", "schedul", "protected", "manifest", "artifact", "token",
    "apikey", "api_key", "auth", "privatekey", "signingkey", "cookie", "cert",
    "signature", "signing", "mac", "grant", "capability", "approved", "claims",
    "scope", "permission", "principal", "accesskey",
)

# Authority-shaped VALUE tokens: a string value containing these is rejected
# (defense against authority material hidden inside otherwise-allowed values).
_AUTHORITY_VALUE_TOKENS: Tuple[str, ...] = (
    "authorization_id", "hmac_key", "attempt_nonce", "receipt_id", "api_key",
    "secret", "signature", "BEGIN PRIVATE KEY", "bearer ", "password=",
)


def _normalize_non_separator(s: str) -> str:
    out = []
    for ch in s.lower().strip():
        out.append(ch) if ch.isalnum() else None
    return "".join(out)


def is_forbidden_authority_key(key: Any) -> bool:
    """Return True iff a key is authority/security material (alias/casing-trick
    invariant). Non-string keys are always forbidden (fail closed)."""
    if not isinstance(key, str):
        return True
    n = _normalize_non_separator(key)
    if n in _AUTHORITY_NORMALIZED_KEYS:
        return True
    return any(seg in n for seg in _AUTHORITY_SUBSTRINGS)


def _is_high_confidence_forbidden_key(key: Any) -> bool:
    """High-confidence authority-material key used for scanning COMPILED snapshot
    metadata (which contains legitimate M12 semantic words like ``capability``
    and ``scope`` as inspect query args). Returns True only for unambiguous
    credential/authority identifiers.

    Unlike :func:`is_forbidden_authority_key` (broad, used for the closed
    allowlist on caller provenance), this avoids rejecting legitimate M12
    semantic metadata by limiting itself to concrete credential identifiers.
    """
    if not isinstance(key, str):
        return True
    n = _normalize_non_separator(key)
    return n in _HIGH_CONFIDENCE_KEYS or any(seg in n for seg in _HIGH_CONFIDENCE_SUBSTRINGS)


_HIGH_CONFIDENCE_KEYS: FrozenSet[str] = frozenset(
    {
        "authorization", "authorizationid", "authorisation", "authorized",
        "isauthorized", "authid",
        "receipt", "receiptid", "receipthash",
        "nonce", "attemptnonce", "nonceid",
        "hmac", "hmackey", "hmacsecret",
        "apikey", "apitoken", "accesstoken", "idtoken", "refreshtoken",
        "bearer", "bearertoken",
        "credential", "credentials", "password", "passwd",
        "secret", "clientsecret", "serversecret", "privatekey", "publickey",
        "signingkey", "sessiontoken", "sessionid", "cookie", "jwt", "cert",
        "recoveryauthority", "retrycontroller", "protectedflag", "isprotected",
        "manifestid", "artifactid", "artifactmanifest", "attemptnonce",
        "signature", "sig", "mac", "grant", "approved", "claims", "accesskey",
    }
)

_HIGH_CONFIDENCE_SUBSTRINGS: Tuple[str, ...] = (
    "authorization", "authorized", "authid", "receipt", "nonce", "hmac",
    "credential", "password", "passwd", "secret", "bearer", "jwt", "cert",
    "sessiontoken", "recoveryauthority", "retrycontroller", "protectedflag",
    "manifestid", "artifactid", "attemptnonce", "signature", "signingkey",
    "accesskey", "privatekey",
)


def _is_value_forbidden(value: Any) -> bool:
    """Return True if a scalar string value contains authority-shaped material."""
    if not isinstance(value, str):
        return False
    low = value.lower()
    return any(tok.lower() in low for tok in _AUTHORITY_VALUE_TOKENS)


def _validate_strict_json_value(value: Any, owner: str, path: str, depth: int = 0,
                                *, reject_forbidden: bool,
                                high_confidence: bool = True) -> None:
    """Recursively validate a value is strict-JSON + (if requested) authority-free.

    Rejects: non-string mapping keys, non-finite floats, unsupported object types
    (e.g. Fraction), excessive depth, and (when reject_forbidden) any
    authority-shaped key or value token at any depth. ``high_confidence`` selects
    the vocabulary: high-confidence credentials only (safe for compiled-snapshot
    metadata that legitimately contains semantic words like ``capability``) vs the
    broad authority vocabulary (used for caller-supplied provenance already gated
    by the closed allowlist).
    """
    forbidden_check = _is_high_confidence_forbidden_key if high_confidence else is_forbidden_authority_key
    if depth > _MAX_DEPTH:
        raise UnrealRuntimeAdapterError(
            f"{owner}.{path}: nesting exceeds safety limit ({_MAX_DEPTH})"
        )
    if isinstance(value, (Mapping, MappingProxyType)):
        for k, v in value.items():
            if not isinstance(k, str):
                raise UnrealRuntimeAdapterError(
                    f"{owner}.{path}: mapping key must be a string, got "
                    f"{type(k).__name__}"
                )
            if reject_forbidden:
                if forbidden_check(k):
                    raise UnrealRuntimeAdapterError(
                        f"{owner}.{path}.{k!r} is forbidden authority material"
                    )
                if _is_value_forbidden(k):
                    raise UnrealRuntimeAdapterError(
                        f"{owner}.{path}.{k!r} is authority-shaped material"
                    )
            _validate_strict_json_value(
                v, owner, f"{path}.{k}", depth + 1, reject_forbidden=reject_forbidden,
                high_confidence=high_confidence,
            )
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _validate_strict_json_value(
                item, owner, f"{path}[{i}]", depth + 1, reject_forbidden=reject_forbidden,
                high_confidence=high_confidence,
            )
        return
    if value is None or isinstance(value, (bool, str)):
        if reject_forbidden and isinstance(value, str) and _is_value_forbidden(value):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{path}: value contains authority-shaped material"
            )
        return
    if type(value) is int:
        # Exact int only (bool and Integral subclasses such as numpy int are
        # excluded: bool is handled above; other Integral types are not part of
        # the strict JSON model).
        return
    if type(value) is float:
        if not math.isfinite(float(value)):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{path}: non-finite number {value!r} not allowed in "
                "strict canonical JSON"
            )
        return
    # R4-10: unsupported numeric types (Fraction, Decimal, numpy scalars, other
    # numbers.Real/Integral) are REJECTED structurally before serialization with
    # the declared canonical-contract error type, so json.dumps can never trip on
    # a value the strict model does not understand.
    raise UnrealRuntimeAdapterError(
        f"{owner}.{path}: unsupported value type {type(value).__name__} "
        "(strict JSON: int/float/bool/str/None only)"
    )
    raise UnrealRuntimeAdapterError(
        f"{owner}.{path}: unsupported value type {type(value).__name__} (strict JSON)"
    )


def _closed_allowlist_check(
    payload: Dict[str, Any],
    owner: str,
    *,
    allowed: FrozenSet[str],
    adapter_owned_ok: bool = True,
) -> None:
    """Enforce the CLOSED ALLOWLIST at the top level of a provenance/metadata dict.

    Any key that is not (a) in `allowed`, or (b) an adapter-owned/reserved key
    (when adapter_owned_ok) is rejected. Nesting is then validated recursively by
    the caller with the strict/authority walk.
    """
    reserved = _ADAPTER_RESERVED_PROVENANCE_KEYS if adapter_owned_ok else frozenset()
    for key in payload:
        if key in allowed or key in reserved:
            continue
        raise UnrealRuntimeAdapterError(
            f"{owner}.{key!r} is not an allowed provenance/metadata key "
            f"(closed allowlist)"
        )


def _freeze_json(value: Any) -> Any:
    """Deep-immutable, strict-JSON copy (dicts -> MappingProxyType, seqs -> tuple)."""
    if isinstance(value, (Mapping, MappingProxyType)):
        return MappingProxyType({k: _freeze_json(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(v) for v in value)
    return value


def _thaw_json(value: Any) -> Any:
    """Convert frozen structures back to plain dict/list for the serializer."""
    if isinstance(value, (Mapping, MappingProxyType)):
        return {k: _thaw_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(v) for v in value]
    return value


class UnrealRuntimeAdapterError(ValueError):
    """Raised when a semantic plan cannot be safely mapped to the runtime."""


def _check_token(value, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise UnrealRuntimeAdapterError(f"{field} must be a non-empty string")


def _check_tokens(values, field: str) -> None:
    if not isinstance(values, tuple):
        raise UnrealRuntimeAdapterError(f"{field} must be a tuple")
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise UnrealRuntimeAdapterError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise UnrealRuntimeAdapterError(f"{field} must not contain duplicates")


def _is_hex64(s: str) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


@dataclass(frozen=True)
class UnrealRuntimeStepMapping:
    """Immutable per-step mapping from one semantic step to the existing runtime.

    A step is *supported* only when there is a demonstrated existing Atlas
    runtime representation that already ingests it: the task-level aggregate
    ``unreal_inspect`` representation. Per-step semantic fields listed in
    ``_RECONCILED_FIELDS`` (required inputs, dependencies, target-state
    contributions, idempotence, fragment identity/version, preconditions,
    verification requirements) are re-derived from the CANONICAL fragment by the
    adapter and reconciled; a crafted plan cannot silently distort them.
    ``declared`` is True exactly when verbatim/unreconciled caller content is
    carried in this step's provenance. ``supported`` is False (and
    ``unsupported_reason`` set) for render-bound steps.

    It never carries authorization, receipt, or recovery material.
    """

    step_id: str
    semantic_operation: str
    supported: bool
    target_runtime_operation: str
    required_inputs: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()
    target_state_contributions: Tuple[str, ...] = ()
    idempotence: str = "unknown"
    capability_requirement: str = "inspect-only"
    fragment_id: Optional[str] = None
    fragment_version: Optional[int] = None
    preconditions: Tuple[str, ...] = ()
    verification_requirements: Tuple[str, ...] = ()
    unsupported_reason: Optional[str] = None
    declared: bool = False
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_token(self.step_id, "step_id")
        _check_token(self.semantic_operation, "semantic_operation")
        _check_tokens(self.required_inputs, "required_inputs")
        _check_tokens(self.dependencies, "dependencies")
        _check_tokens(self.target_state_contributions, "target_state_contributions")
        _check_tokens(self.preconditions, "preconditions")
        _check_tokens(self.verification_requirements, "verification_requirements")
        if not isinstance(self.supported, bool):
            raise UnrealRuntimeAdapterError("supported must be a bool")
        _check_token(self.target_runtime_operation, "target_runtime_operation")
        if self.idempotence not in ("idempotent", "non-idempotent", "unknown"):
            raise UnrealRuntimeAdapterError(
                f"step idempotence must be idempotent/non-idempotent/unknown, got "
                f"{self.idempotence!r}"
            )
        if not isinstance(self.capability_requirement, str) or not self.capability_requirement.strip():
            raise UnrealRuntimeAdapterError(
                "capability_requirement must be a non-empty string"
            )
        if self.fragment_version is not None and not isinstance(self.fragment_version, int):
            raise UnrealRuntimeAdapterError("fragment_version must be an int or None")
        if self.unsupported_reason is not None and not isinstance(
            self.unsupported_reason, str
        ):
            raise UnrealRuntimeAdapterError("unsupported_reason must be a str or None")
        # Typed closed provenance schema + authority/strict-JSON validation
        # (single canonical path, also run on direct construction) (R4-5).
        prov = _validate_caller_provenance(
            dict(self.provenance), f"step.provenance[{self.step_id!r}]"
        )
        object.__setattr__(self, "provenance", _freeze_json(prov))

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "semantic_operation": self.semantic_operation,
            "supported": self.supported,
            "target_runtime_operation": self.target_runtime_operation,
            "required_inputs": list(self.required_inputs),
            "dependencies": list(self.dependencies),
            "target_state_contributions": list(self.target_state_contributions),
            "idempotence": self.idempotence,
            "capability_requirement": self.capability_requirement,
            "fragment_id": self.fragment_id,
            "fragment_version": self.fragment_version,
            "preconditions": list(self.preconditions),
            "verification_requirements": list(self.verification_requirements),
            "unsupported_reason": self.unsupported_reason,
            "declared": self.declared,
            "provenance": _thaw_json(self.provenance),
        }


def compute_source_task_digest(source_task: UnrealProductionTaskDefinition) -> str:
    """Deterministic SHA-256 binding of the RESOLVED canonical source content.

    Delegates to the SINGLE M12-layer implementation
    :func:`planning.m12.semantic_task.compute_source_content_digest`, the same
    function M12.3 uses to produce the plan's immutable ``source_content_digest`.
    This guarantees the adapter's recomputation equals the plan's commitment.
    Raises ``UnrealRuntimeAdapterError`` on non-JSON data.
    """
    if not isinstance(source_task, UnrealProductionTaskDefinition):
        raise TypeError("source_task must be an UnrealProductionTaskDefinition")
    try:
        return compute_source_content_digest(source_task)
    except UnrealSemanticTaskError as exc:
        raise UnrealRuntimeAdapterError(str(exc)) from exc


@dataclass(frozen=True)
class UnrealRuntimeMapping:
    """Immutable result of mapping an M12.3 plan onto the existing runtime.

    Identity fields (plan id, source semantic task id/version, catalog version,
    digital-twin id) are preserved and never collapsed. ``source_task_digest``
    deterministically binds the resolved source content. ``render_plan`` /
    ``requires_existing_render_submission_path`` reflect the AUTHORITATIVE union
    of source-task class AND canonical fragment render semantics. ``can_execute``
    is always False.

    ``runtime_task_snapshot`` is an immutable, strict-JSON, self-describing
    snapshot of the EXISTING :class:`AtlasTaskDefinition`` (name, evidence,
    actions, allowed_action_tools, allow_writes, verify_after_action, metadata
    + evaluator disclosure). ``runtime_task_digest`` is its SHA-256 binding. The
    snapshot is the SOLE authoritative runtime-task representation; the mapping
    does NOT retain a hidden mutable backing object. ``materialize_runtime_task()``
    rebuilds the existing runtime object from the snapshot and asserts its digest
    matches before returning a fresh isolated copy.

    Construction is SELF-VALIDATING: ``__post_init__`` runs the single canonical
    validation path (closed-allowlist provenance, source digest shape, render
    consistency, runtime authority consistency, canonical-field consistency,
    digest binding). A directly-constructed invalid mapping FAILS CLOSED.

    The mapping never:
    - authorizes execution;
    - mints receipts / recovery authority / protected flags;
    - schedules, retries, reconstructs, or verifies;
    - submits, or fabricates, a render.
    """

    plan_id: str
    source_task_id: str
    source_task_version: int
    catalog_version: int
    digital_twin_id: str
    steps: Tuple[UnrealRuntimeStepMapping, ...]
    render_plan: bool
    requires_existing_render_submission_path: bool
    runtime_task_snapshot: Optional[MappingProxyType]
    runtime_task_digest: Optional[str]
    semantic_fidelity: str
    source_task_digest: str
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_token(self.plan_id, "plan_id")
        _check_token(self.source_task_id, "source_task_id")
        if not isinstance(self.source_task_version, int) or self.source_task_version < 1:
            raise UnrealRuntimeAdapterError("source_task_version must be a positive int")
        if not isinstance(self.catalog_version, int) or self.catalog_version < 1:
            raise UnrealRuntimeAdapterError("catalog_version must be a positive int")
        _check_token(self.digital_twin_id, "digital_twin_id")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise UnrealRuntimeAdapterError("runtime mapping must have at least one step")
        if any(not isinstance(s, UnrealRuntimeStepMapping) for s in self.steps):
            raise UnrealRuntimeAdapterError(
                "all runtime mapping steps must be UnrealRuntimeStepMapping"
            )
        _check_tokens(tuple(s.step_id for s in self.steps), "step_ids")
        if not isinstance(self.render_plan, bool):
            raise UnrealRuntimeAdapterError("render_plan must be a bool")
        if not isinstance(self.requires_existing_render_submission_path, bool):
            raise UnrealRuntimeAdapterError(
                "requires_existing_render_submission_path must be a bool"
            )
        # Render consistency: a render-bearing plan must set the boundary and have
        # NO runtime snapshot; a non-render plan must NOT set the boundary and MUST
        # have a snapshot.
        if self.render_plan != self.requires_existing_render_submission_path:
            raise UnrealRuntimeAdapterError(
                "render_plan and requires_existing_render_submission_path must agree"
            )
        if self.render_plan and self.runtime_task_snapshot is not None:
            raise UnrealRuntimeAdapterError(
                "a render-bearing mapping must not carry a runtime task snapshot"
            )
        if not self.render_plan and self.runtime_task_snapshot is None:
            raise UnrealRuntimeAdapterError(
                "a non-render mapping must carry a runtime task snapshot"
            )
        if self.runtime_task_snapshot is not None and not isinstance(
            self.runtime_task_snapshot, MappingProxyType
        ):
            raise UnrealRuntimeAdapterError(
                "runtime_task_snapshot must be a deep-frozen mapping or None"
            )
        if self.runtime_task_digest is not None and not isinstance(
            self.runtime_task_digest, str
        ):
            raise UnrealRuntimeAdapterError("runtime_task_digest must be a str or None")
        if self.semantic_fidelity not in ("aggregate", "unavailable"):
            raise UnrealRuntimeAdapterError(
                "semantic_fidelity must be 'aggregate' or 'unavailable'"
            )
        if self.render_plan and self.semantic_fidelity != "unavailable":
            raise UnrealRuntimeAdapterError(
                "render-bearing mapping must have semantic_fidelity 'unavailable'"
            )
        if not self.render_plan and self.semantic_fidelity != "aggregate":
            raise UnrealRuntimeAdapterError(
                "non-render mapping must have semantic_fidelity 'aggregate'"
            )
        if not _is_hex64(self.source_task_digest):
            raise UnrealRuntimeAdapterError(
                "source_task_digest must be a 64-char lowercase hex SHA-256"
            )
        # Runtime authority consistency on the snapshot.
        if self.runtime_task_snapshot is not None:
            tools = tuple(self.runtime_task_snapshot["allowed_action_tools"])
            if any(t != EXISTING_RUNTIME_INSPECT_TOOL for t in tools):
                raise UnrealRuntimeAdapterError(
                    "runtime snapshot permitted tools include non-inspect tool; "
                    "inspect-only contract violated"
                )
            actions = self.runtime_task_snapshot["actions"]
            if any(a["tool"] != EXISTING_RUNTIME_INSPECT_TOOL for a in actions):
                raise UnrealRuntimeAdapterError(
                    "runtime snapshot action tool exceeds inspect-only contract"
                )
            evidence = self.runtime_task_snapshot["evidence"]
            if any(e["tool"] != EXISTING_RUNTIME_INSPECT_TOOL for e in evidence):
                raise UnrealRuntimeAdapterError(
                    "runtime snapshot evidence tool exceeds inspect-only contract"
                )
            if self.runtime_task_snapshot["allow_writes"]:
                raise UnrealRuntimeAdapterError(
                    "runtime snapshot must not claim write authority under "
                    "inspect-only semantics"
                )
            # Digest binding: runtime_task_digest must equal digest of snapshot.
            snap_digest = _digest_of_jsonable(_thaw_json(self.runtime_task_snapshot))
            if self.runtime_task_digest != snap_digest:
                raise UnrealRuntimeAdapterError(
                    "runtime_task_digest does not bind the runtime task snapshot"
                )
            # R4-2/R4-11: single canonical path — a directly-constructed
            # mapping's snapshot metadata is subject to the SAME reserved-key,
            # recursive authority scan, and strict-JSON validation the factory
            # applies, so no snapshot-invalid state can be constructed directly.
            meta = dict(self.runtime_task_snapshot.get("metadata") or {})
            for mkey in meta:
                if mkey in _ADAPTER_RESERVED_PROVENANCE_KEYS:
                    raise UnrealRuntimeAdapterError(
                        f"runtime snapshot metadata contains adapter-owned key "
                        f"{mkey!r}; invalid snapshot state"
                    )
            _validate_strict_json_value(
                _thaw_json(self.runtime_task_snapshot),
                "runtime_task_snapshot", "<root>", reject_forbidden=True,
            )
        else:
            if self.runtime_task_digest is not None:
                raise UnrealRuntimeAdapterError(
                    "render-bearing mapping must not carry a runtime_task_digest"
                )
        if not isinstance(self.provenance, dict):
            raise UnrealRuntimeAdapterError("provenance must be a dict")
        # Closed allowlist for mapping provenance (allow caller-visible legit keys
        # plus adapter-owned keys), recursive authority + strict JSON walk.
        # Typed closed mapping-provenance validation (R4-5/R4-9). The single
        # canonical path accepts adapter-owned fields + typed caller fields and
        # rejects anything else (direct construction shares this path).
        prov = _validate_mapping_provenance(
            dict(self.provenance), "mapping.provenance"
        )
        object.__setattr__(self, "provenance", _freeze_json(prov))
        # Re-freeze snapshot to a fresh deep-frozen mapping (defensive; already
        # frozen at factory).
        if self.runtime_task_snapshot is not None:
            object.__setattr__(
                self, "runtime_task_snapshot", _freeze_json(dict(self.runtime_task_snapshot))
            )

    @property
    def can_execute(self) -> bool:
        """An adapter mapping is never an executor. Always False."""
        return False

    def materialize_runtime_task(self) -> Optional[AtlasTaskDefinition]:
        """Rebuild the existing runtime task SOLELY from the immutable snapshot.

        Returns a fresh, isolated deep copy (mutating it cannot affect the
        mapping). Rebuilds the placeholder (structural) evaluator from the
        snapshot's recorded invariant names, and asserts the rebuilt snapshot's
        digest equals ``runtime_task_digest`` before returning. Raises
        ``UnrealRuntimeAdapterError`` on any divergence.
        """
        snap = self.runtime_task_snapshot
        if snap is None:
            return None
        rt = _rebuild_atlas_task(snap)
        rebuilt_snap = _freeze_json(_atlas_to_snapshot(rt))
        if _digest_of_jsonable(_thaw_json(rebuilt_snap)) != self.runtime_task_digest:
            raise UnrealRuntimeAdapterError(
                "materialized runtime task diverges from the canonical snapshot digest"
            )
        return rt

    def to_json_compatible(self) -> Dict[str, Any]:
        rt_snap = _thaw_json(self.runtime_task_snapshot) if self.runtime_task_snapshot is not None else None
        return {
            "plan_id": self.plan_id,
            "source_task_id": self.source_task_id,
            "source_task_version": self.source_task_version,
            "catalog_version": self.catalog_version,
            "digital_twin_id": self.digital_twin_id,
            "source_task_digest": self.source_task_digest,
            "render_plan": self.render_plan,
            "requires_existing_render_submission_path": (
                self.requires_existing_render_submission_path
            ),
            "semantic_fidelity": self.semantic_fidelity,
            "runtime_task_present": self.runtime_task_snapshot is not None,
            "runtime_task_digest": self.runtime_task_digest,
            "runtime_task_snapshot": rt_snap,
            "steps": [s.to_json_compatible() for s in self.steps],
            "provenance": _thaw_json(self.provenance),
        }

    def canonical_json(self) -> str:
        """Deterministic STRICT-JSON canonical serialization (sorted keys, compact).

        ``allow_nan=False``; the snapshot and provenance are deep-frozen at
        construction, so mutating the caller's input afterward cannot change this
        output.
        """
        return json.dumps(
            self.to_json_compatible(), sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )


def _digest_of_jsonable(value: Any) -> str:
    _validate_strict_json_value(value, "digest", "<root>", reject_forbidden=False)
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                   allow_nan=False).encode("utf-8")
    ).hexdigest()


def _atlas_to_snapshot(rt: AtlasTaskDefinition) -> Dict[str, Any]:
    return {
        "name": rt.name,
        "evidence": [
            {"tool": e.tool, "arguments": _copy.deepcopy(e.arguments), "name": e.name}
            for e in rt.evidence
        ],
        "actions": [
            {
                "tool": a.tool,
                "arguments": _copy.deepcopy(a.arguments),
                "name": a.name,
                "requires_success": a.requires_success,
                "depends_on": list(a.dependency_names()),
            }
            for a in rt.actions
        ],
        "allowed_action_tools": sorted(rt.allowed_action_tools),
        "allow_writes": rt.allow_writes,
        "verify_after_action": rt.verify_after_action,
        "metadata": _copy.deepcopy(dict(rt.metadata or {})),
    }


def _rebuild_atlas_task(snap: MappingProxyType) -> AtlasTaskDefinition:
    """Rebuild an AtlasTaskDefinition strictly from a snapshot dict.

    Reconstructs a structural placeholder evaluator from the snapshot's
    ``metadata.unreal_target_state.invariant_names`` (deterministic; not
    independent verification). Classified as structural-placeholder /
    not-independently-verified so no future layer mistakes it for real
    verification (M12.5 boundary preserved).
    """
    snap_in = _thaw_json(snap) if not isinstance(snap, dict) else snap
    meta = dict(snap_in["metadata"] or {})
    invariant_names = []
    ts = meta.get("unreal_target_state")
    if isinstance(ts, dict):
        invariant_names = list(ts.get("invariant_names", []))
    invariants = [
        StateInvariant(
            name=name,
            predicate=lambda ev, _n=name: bool(
                isinstance(ev, dict) and ev.get(_n)
            ),
        )
        for name in invariant_names
    ]
    if not invariants:
        invariants = [
            StateInvariant(name="__no_invariants__", predicate=lambda ev: False)
        ]
    evidence = tuple(
        EvidenceRequest(
            tool=e["tool"], arguments=_copy.deepcopy(e["arguments"]), name=e["name"]
        )
        for e in snap_in["evidence"]
    )
    actions = tuple(
        ActionSpec(
            tool=a["tool"],
            arguments=_copy.deepcopy(a["arguments"]),
            name=a["name"],
            requires_success=a["requires_success"],
            depends_on=tuple(a["depends_on"]),
        )
        for a in snap_in["actions"]
    )
    return AtlasTaskDefinition(
        name=snap_in["name"],
        evidence=evidence,
        actions=actions,
        evaluator=TargetStateEvaluator(invariants),
        allowed_action_tools=set(snap_in["allowed_action_tools"]),
        allow_writes=bool(snap_in["allow_writes"]),
        verify_after_action=bool(snap_in["verify_after_action"]),
        metadata=meta,
    )


def _same_steps_as_task(plan: UnrealExecutionPlan, task: UnrealProductionTaskDefinition) -> bool:
    """The plan's ordered semantic operations must exactly match the source task's
    ordered fragment dependencies (this is how M12.3 builds a plan). Mismatch is
    fail-closed, so the adapter never maps a plan onto a different runtime."""
    return tuple(step.semantic_operation for step in plan.steps) == tuple(
        task.dependencies
    )


def _candidate_fragment(step_semantic_operation: str) -> Optional[UnrealProductionFragment]:
    try:
        return canonical_fragment(step_semantic_operation)
    except KeyError:
        return None


def _fragment_is_render_configured(fragment: UnrealProductionFragment) -> bool:
    """A canonical fragment is render-bearing if it is render-constrained or
    non-expandable to runtime actions (e.g. ``render_setup``)."""
    if fragment is None:
        return False
    if fragment.canonical_id == "render_setup":
        return True
    if bool(fragment.detail.get("render_execution_constrained")):
        return True
    return not fragment.expandable


def _explain_and_check_precondition(
    plan_step,
    fragment: UnrealProductionFragment,
) -> Optional[str]:
    expected_pre = tuple(sorted(set(fragment.requires)))
    actual_pre = tuple(sorted(set(plan_step.preconditions)))
    if actual_pre != expected_pre:
        return (
            f"step {plan_step.step_id!r} preconditions mismatch: plan declares "
            f"{actual_pre} but canonical fragment requires {expected_pre}"
        )
    expected_ver = tuple(sorted(set(fragment.contributed_invariant_names())))
    actual_ver = tuple(sorted(set(plan_step.verification_requirements)))
    if actual_ver != expected_ver:
        return (
            f"step {plan_step.step_id!r} verification_requirements mismatch: plan "
            f"declares {actual_ver} but canonical fragment contributes "
            f"{expected_ver}"
        )
    return None


def _reconcile_step_fidelity(
    step,
    fragment: UnrealProductionFragment,
    producer_to_step: Dict[str, str],
) -> Optional[str]:
    """Reconcile a plan step's claimed semantics against the canonical fragment.

    Returns an error message if any reconciled field is inconsistent, else None.
    The canonical fragment is the source of truth for required inputs,
    target-state contributions, idempotence, dependencies (prefix-only),
    preconditions, and verification requirements. This applies to EVERY mapped
    step, including render-bearing steps (no asymmetric bypass).

    CRITICAL (B5): every requirement the fragment declares must be resolved by an
    EARLIER producer step. An unresolved requirement is an error (never converted
    to an empty dependency set).
    """
    expected_inputs = tuple(sorted(set(fragment.inputs)))
    actual_inputs = tuple(sorted(set(step.required_inputs)))
    if actual_inputs != expected_inputs:
        return (
            f"step {step.step_id!r} required_inputs mismatch: plan may have been "
            f"tampered (expected {expected_inputs}, got {actual_inputs})"
        )

    expected_contrib = tuple(sorted(set(fragment.contributed_invariant_names())))
    actual_contrib = tuple(sorted(set(step.target_state_contributions)))
    if actual_contrib != expected_contrib:
        return (
            f"step {step.step_id!r} target_state_contributions mismatch: plan may "
            f"have been tampered (expected {expected_contrib}, got {actual_contrib})"
        )

    expected_idempotence = "idempotent" if fragment.idempotent else "non-idempotent"
    if step.idempotence != expected_idempotence:
        return (
            f"step {step.step_id!r} idempotence mismatch: plan declares "
            f"{step.idempotence!r} but canonical fragment is {expected_idempotence!r}"
        )

    # B5: every fragment requirement must be satisfied by an earlier producer.
    unresolved = [req for req in fragment.requires if req not in producer_to_step]
    if unresolved:
        return (
            f"step {step.step_id!r} has unresolved requirement(s) "
            f"{sorted(unresolved)} with no canonical producer step; failing closed "
            "(unresolved requirements must never degrade to an empty dependency)"
        )
    expected_deps = tuple(
        sorted(producer_to_step[req] for req in fragment.requires)
    )
    actual_deps = tuple(sorted(set(step.dependencies)))
    if actual_deps != expected_deps:
        return (
            f"step {step.step_id!r} dependencies mismatch: plan may have been "
            f"tampered (expected {expected_deps}, got {actual_deps})"
        )

    pre_reason = _explain_and_check_precondition(step, fragment)
    if pre_reason is not None:
        return pre_reason
    return None


# ---------------------------------------------------------------------------
# Map entry point
# ---------------------------------------------------------------------------


def map_unreal_execution_plan(
    plan: UnrealExecutionPlan,
    *,
    source_task: UnrealProductionTaskDefinition,
    catalog_version: Optional[int] = None,
    expected_source_task_digest: Optional[str] = None,
) -> UnrealRuntimeMapping:
    """Map a validated M12.3 execution plan onto the existing Atlas runtime.

    Args:
        plan: an already-validated :class:`UnrealExecutionPlan`.
        source_task: the validated :class:`UnrealProductionTaskDefinition` the
            plan was generated from (used to reuse the existing M12.1 compiler).
        catalog_version: catalog version. MUST equal ``plan.catalog_version`` and
            (when present in source metadata) the resolved source's catalog
            version; any mismatch fails closed.
        expected_source_task_digest: OPTIONAL redundant assertion (R5-2). The
            authoritative source binding is the plan's immutable
            ``source_content_digest`` (generated by M12.3 from the resolved source
            content). The adapter recomputes that digest from the supplied source
            and REQUIRES it to equal the plan's commitment; the caller-supplied
            expected digest, if present, must also agree. It NEVER establishes
            authority — omission is fine, and a mismatched/forged value cannot
            cause a substituted source to be accepted.

    Returns:
        a deterministic :class:`UnrealRuntimeMapping` (see class docstring).

    Raises:
        TypeError: if ``plan`` or ``source_task`` has the wrong type.
        UnrealRuntimeAdapterError: on any invariant violation (identity mismatch,
            render classification conflict across class/fragment/target-state
            axes, runtime action-authority violation, forbidden/un-allowed
            provenance, missing/malformed/conflicting source digest, unresolved
            requirement, catalog version conflict, etc.).
    """
    if not isinstance(plan, UnrealExecutionPlan):
        raise TypeError("plan must be an UnrealExecutionPlan")
    if not isinstance(source_task, UnrealProductionTaskDefinition):
        raise TypeError("source_task must be an UnrealProductionTaskDefinition")

    # --- Identity lock ---
    mismatch = []
    if plan.source_task_id != source_task.canonical_task_id:
        mismatch.append("source_task_id")
    if plan.source_task_version != source_task.task_version:
        mismatch.append("source_task_version")
    if plan.digital_twin_id != source_task.digital_twin_id:
        mismatch.append("digital_twin_id")
    if mismatch:
        raise UnrealRuntimeAdapterError(
            "plan identity does not match the provided source task on: "
            + ", ".join(mismatch)
        )
    if not _same_steps_as_task(plan, source_task):
        raise UnrealRuntimeAdapterError(
            "plan step operations do not match the source task's fragment "
            "dependencies"
        )

    # --- B3: closed-allowlist provenance (plan + steps), recursive authority
    # scan, strict JSON. Reject adapter-reserved keys (no shadow truth).
    clean_plan_provenance = _validate_caller_provenance(
        dict(plan.provenance or {}), "plan.provenance"
    )

    # --- M12.3-SOURCE-COMMITMENT BINDING (R5-2). The plan carries an immutable
    # source-content commitment (source_content_digest) generated by M12.3 from
    # the AUTHORITATIVE resolved source content. The adapter recomputes that
    # digest from the supplied source and REQUIRES it to equal the plan's
    # commitment, so a substituted same-identity source is REJECTED even if the
    # caller supplies a matching digest for the substituted source (PLAN_A +
    # SOURCE_B + DIGEST(SOURCE_B) must fail because PLAN_A's commitment is
    # DIGEST(SOURCE_A)). The caller-supplied expected digest, if present, is a
    # REDUNDANT assertion only and NEVER establishes authority.
    source_digest = compute_source_task_digest(source_task)
    if source_digest != plan.source_content_digest:
        raise UnrealRuntimeAdapterError(
            "source content digest recomputed from the supplied source does not "
            "match the plan's immutable source_content_digest; refusing to map a "
            "substituted/unbound source (PLAN_A + SOURCE_B + DIGEST(SOURCE_B) "
            "rejected)"
        )
    if expected_source_task_digest is not None:
        if not _is_hex64(expected_source_task_digest):
            raise UnrealRuntimeAdapterError(
                "expected_source_task_digest must be a 64-char lowercase hex "
                "SHA-256 of the resolved source content"
            )
        if expected_source_task_digest != source_digest:
            raise UnrealRuntimeAdapterError(
                "expected_source_task_digest does not match the digest recomputed "
                "from the authoritative resolved source content; refusing to map "
                "a substituted/unbound source"
            )

    # Plan's composed target-state must match the source's resolved target-state.
    plan_composed_invariants = set()
    for step in plan.steps:
        plan_composed_invariants.update(step.target_state_contributions)
    source_target_invariants = set(source_task.target_state.to_invariant_names())
    if plan_composed_invariants != source_target_invariants:
        raise UnrealRuntimeAdapterError(
            "plan's composed target-state contributions do not match the source "
            "task's resolved target-state invariants"
        )

    # --- Render classification from ALL authoritative axes (B2): the union of
    # source class semantics AND canonical fragment render semantics. Any
    # conflict fails closed.
    all_fragments = [_candidate_fragment(s.semantic_operation) for s in plan.steps]
    if any(f is None for f in all_fragments):
        bad = next(
            s.semantic_operation for s, f in zip(plan.steps, all_fragments) if f is None
        )
        raise UnrealRuntimeAdapterError(
            f"cannot map plan: semantic operation {bad!r} is not a known canonical "
            "fragment (fail closed)"
        )
    fragment_render = any(
        _fragment_is_render_configured(f) for f in all_fragments if f is not None
    )
    class_render = source_task.render_task
    target_state_render = bool(source_task.target_state.expects_render)
    # R4-3: render classification derives from EVERY authoritative M12 axis --
    # source task class, canonical fragment render semantics (render-constrained /
    # non-expandable fragments such as render_setup), AND target-state
    # ``expects_render``. Any authoritative render requirement routes to the
    # render boundary; CONFLICTING render vs non-render signals FAIL CLOSED.
    # Render class without a render fragment (e.g. artifact-validate) is the
    # documented benign direction: it still routes to the render boundary via
    # the class axis, preserving the existing M12.1-ir-divined boundary.
    if fragment_render and not class_render:
        raise UnrealRuntimeAdapterError(
            "render classification conflict: the plan's canonical fragments are "
            "render-configured (non-expandable / render_execution_constrained) "
            f"but the source task class {source_task.task_class!r} is "
            "non-render; refusing to route render semantics through the "
            "ordinary non-render runtime path"
        )
    if target_state_render != class_render:
        raise UnrealRuntimeAdapterError(
            f"render classification conflict: target-state expects_render="
            f"{target_state_render!r} disagrees with the source task class "
            f"render_task={class_render!r}; refusing to route conflicting render "
            "semantics"
        )
    if target_state_render and not (class_render or fragment_render):
        raise UnrealRuntimeAdapterError(
            "render classification conflict: source target state says "
            "expects_render=True but class and canonical fragment axes are "
            "non-render; refusing to route render semantics through the "
            "ordinary non-render runtime path"
        )
    require_render_boundary = bool(
        class_render or target_state_render or fragment_render
    )
    if plan.render_plan != require_render_boundary:
        raise UnrealRuntimeAdapterError(
            f"render_plan mismatch: plan declares render_plan={plan.render_plan!r} "
            f"but authoritative source classification is "
            f"{require_render_boundary!r}"
        )

    # --- Catalog version: ONE authoritative exact-int value (R4-8). The plan's
    # catalog_version is authoritative. A caller override or source metadata value
    # must be an EXACT int equal to it; type-coercion ambiguity (bool/float/str,
    # lossy int()) and conflicting nested representations FAIL CLOSED.
    if type(plan.catalog_version) is not int:
        raise UnrealRuntimeAdapterError(
            f"plan.catalog_version must be an exact int, got "
            f"{type(plan.catalog_version).__name__}"
        )
    if catalog_version is not None:
        if type(catalog_version) is not int:
            raise UnrealRuntimeAdapterError(
                "catalog_version override must be an exact int (no bool/float/str "
                "coercion)"
            )
        if catalog_version != plan.catalog_version:
            raise UnrealRuntimeAdapterError(
                f"catalog_version {catalog_version} conflicts with the plan's "
                f"authoritative {plan.catalog_version}"
            )
    source_meta_cv = None
    if isinstance(source_task.metadata, dict):
        source_meta_cv = source_task.metadata.get("catalog_version")
    if source_meta_cv is not None:
        if type(source_meta_cv) is not int:
            raise UnrealRuntimeAdapterError(
                f"source metadata catalog_version must be an exact int, got "
                f"{type(source_meta_cv).__name__} (no lossy coercion)"
            )
        if source_meta_cv != plan.catalog_version:
            raise UnrealRuntimeAdapterError(
                f"catalog_version conflict: plan says {plan.catalog_version} but "
                f"resolved source metadata says {source_meta_cv}"
            )
    used_catalog_version = plan.catalog_version

    # --- Per-step fidelity reconciliation (B5: unresolved requirements fail
    # closed). Prefix-only producer map.
    prefix_producers: Dict[str, str] = {}
    rendered_steps: list = []
    for index, step in enumerate(plan.steps):
        fragment = all_fragments[index]
        assert fragment is not None
        if step.idempotence == "unknown":
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: unknown idempotence (fail closed)"
            )
        if step.execution_capability_requirement != "inspect-only":
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: unsupported capability "
                f"requirement {step.execution_capability_requirement!r}"
            )
        if not require_render_boundary and not fragment.expandable:
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: canonical fragment "
                f"{fragment.canonical_id!r} is not expandable to runtime actions; "
                "fail closed (render-constrained step)"
            )
        fid_reason = _reconcile_step_fidelity(step, fragment, prefix_producers)
        if fid_reason is not None:
            raise UnrealRuntimeAdapterError(fid_reason)

        # Step provenance: typed closed schema (R4-5/R4-9). Caller may supply
        # any schema field (typed). The CANONICAL fragment identity/version and
        # target-state contributions are RECONCILED ADAPTER TRUTH: any caller-
        # forged value is OVERWRITTEN with the canonical value before being
        # carried — so a crafted fragment identity can never shadow the truth.
        step_prov_in = dict(step.provenance or {})
        step_provenance = _validate_caller_provenance(
            step_prov_in, f"step.provenance[{step.step_id!r}]"
        )
        # Overwrite the reconciled fields with canonical truth (adapter wins).
        step_provenance["fragment_id"] = fragment.canonical_id
        step_provenance["fragment_version"] = fragment.version
        step_provenance["target_state_contribution"] = list(
            sorted(set(fragment.contributed_invariant_names()))
        )
        # R4-9: `declared` is True only when caller-supplied NON-canonical
        # content (proposal_source/source_task_version/note) is carried
        # verbatim. Purely canonical reconciled fields never mark declared.
        declared = bool(
            set(step_prov_in)
            - {"fragment_id", "fragment_version", "target_state_contribution"}
        )

        if require_render_boundary:
            supported = False
            target_op = "<none>"
            reason = REQUIRES_EXISTING_RENDER_SUBMISSION_PATH
        else:
            supported = True
            target_op = EXISTING_RUNTIME_INSPECT_TOOL
            reason = None

        rendered_steps.append(
            UnrealRuntimeStepMapping(
                step_id=step.step_id,
                semantic_operation=step.semantic_operation,
                supported=supported,
                target_runtime_operation=target_op,
                required_inputs=tuple(sorted(set(step.required_inputs))),
                dependencies=tuple(sorted(set(step.dependencies))),
                target_state_contributions=tuple(
                    sorted(set(step.target_state_contributions))
                ),
                idempotence=step.idempotence,
                capability_requirement=step.execution_capability_requirement,
                fragment_id=fragment.canonical_id,
                fragment_version=fragment.version,
                preconditions=tuple(sorted(set(step.preconditions))),
                verification_requirements=tuple(
                    sorted(set(step.verification_requirements))
                ),
                unsupported_reason=reason,
                declared=declared,
                provenance=step_provenance,
            )
        )
        for produced in fragment.produces:
            prefix_producers.setdefault(produced, step.step_id)
    mapped_steps = tuple(rendered_steps)

    # --- Build the existing runtime representation for non-render plans, then
    # reconcile RUNTIME ACTION AUTHORITY (B1).
    runtime_task_snapshot: Optional[MappingProxyType] = None
    runtime_task_digest: Optional[str] = None
    semantic_fidelity = "unavailable"
    if not require_render_boundary:
        # R4-4: REJECT, DON'T REWRITE. An inspect-only mapping must come from a
        # semantically inspect-only source. If the source task declares any write
        # mutation (or its compiled runtime claims allow_writes), the adapter
        # REJECTS rather than silently downgrading the source's write intent.
        if source_task.allowed_mutations:
            raise UnrealRuntimeAdapterError(
                "source task declares write mutation(s) "
                f"{sorted(source_task.allowed_mutations)} under an inspect-only "
                "mapping; REJECTING the source's write intent (do not rewrite "
                "caller/source intent)"
            )
        compiled = compile_unreal_semantic_task(source_task)
        # B1: independently reconcile the compiled AtlasTaskDefinition against the
        # inspect-only contract. Any write/render tool or non-inspect action or
        # evidence tool FAILS CLOSED (we never merely zero allow_writes).
        compiled = _reconcile_runtime_authority(compiled)
        # B3: the source metadata reaches the runtime snapshot via the compiled
        # task. Enforce the source-metadata key allowlist AND recursively reject
        # authority-shaped keys/values anywhere in the metadata structure (e.g.
        # a catalog JSON `camera_slots` parameter carrying authorization fields).
        _closed_allowlist_check(
            dict(compiled.metadata or {}), "source.metadata",
            allowed=_ALLOWED_SOURCE_METADATA_KEYS,
            adapter_owned_ok=False,
        )
        _validate_strict_json_value(
            dict(compiled.metadata or {}), "source.metadata", "<root>",
            reject_forbidden=True,
        )
        # Deep-copy so callers mutating source/compile cannot affect the mapping.
        compiled = _copy.deepcopy(compiled)
        snapshot_mapping = _atlas_to_snapshot(compiled)
        # B3/B8: the assembled snapshot (metadata included) must be authority-free
        # strict JSON BEFORE freezing/digesting; fail closed otherwise.
        _validate_strict_json_value(
            snapshot_mapping, "runtime_task_snapshot", "<root>",
            reject_forbidden=True,
        )
        runtime_task_snapshot = _freeze_json(snapshot_mapping)  # type: ignore[assignment]
        runtime_task_digest = _digest_of_jsonable(_thaw_json(runtime_task_snapshot))
        semantic_fidelity = "aggregate"

    # --- Build mapping provenance (adapter-owned, closed, authoritative).
    provenance = dict(clean_plan_provenance)
    provenance["mapped_runtime_task_type"] = (
        "AtlasTaskDefinition" if not require_render_boundary else "unavailable"
    )
    provenance["recognized_render_plan"] = require_render_boundary
    provenance["semantic_fidelity"] = semantic_fidelity
    provenance["source_task_digest"] = source_digest
    provenance["runtime_task_digest"] = runtime_task_digest
    provenance["declared"] = False
    provenance["reconciled"] = True

    return UnrealRuntimeMapping(
        plan_id=plan.plan_id,
        source_task_id=plan.source_task_id,
        source_task_version=plan.source_task_version,
        catalog_version=used_catalog_version,
        digital_twin_id=plan.digital_twin_id,
        steps=mapped_steps,
        render_plan=require_render_boundary,
        requires_existing_render_submission_path=require_render_boundary,
        runtime_task_snapshot=runtime_task_snapshot,
        runtime_task_digest=runtime_task_digest,
        semantic_fidelity=semantic_fidelity,
        source_task_digest=source_digest,
        provenance=provenance,
    )


def _validate_caller_provenance(payload: Dict[str, Any], owner: str) -> Dict[str, Any]:
    """R4-5: TYPED CLOSED-SCHEMA validation of caller-provided provenance.

    Accepts ONLY the fields in ``_CALLER_PROVENANCE_SCHEMA``, each with its exact
    declared type. Rejects (fail closed, never strips-and-continues):
    - unknown keys,
    - adapter-owned keys (no shadow truth),
    - authority/security-shaped keys and values at any nesting,
    - NESTED undeclared structures and free-form caller metadata (a scalar field
      such as ``note`` must be a plain str; a dict/list is rejected rather than
      being promoted into trusted provenance).

    Returns a clean deep copy of the validated scalar fields.
    """
    real_owner = owner
    if not isinstance(payload, dict):
        raise UnrealRuntimeAdapterError(f"{owner} must be a dict")
    # Structural key gate: only schema fields, and no adapter-owned keys.
    for key in payload:
        if key in _ADAPTER_RESERVED_PROVENANCE_KEYS:
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is adapter-owned; caller shadow rejected"
            )
        if key in _ADAPTER_OWNED_KEYS:
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is adapter-owned; caller shadow rejected"
            )
        if key not in _CALLER_PROVENANCE_SCHEMA:
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is not an allowed provenance field (closed, "
                "typed schema)"
            )
        if is_forbidden_authority_key(key):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is forbidden authority material"
            )
        if _is_value_forbidden(key):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is authority-shaped material"
            )
    cleaned: Dict[str, Any] = {}
    for key, expected in _CALLER_PROVENANCE_SCHEMA.items():
        if key in payload:
            val = payload[key]
            if expected is list:
                # list-of-strings only (canonical reconciled field).
                if not isinstance(val, (list, tuple)) or any(
                    not isinstance(x, str) for x in val
                ):
                    raise UnrealRuntimeAdapterError(
                        f"{owner}.{key!r} must be a list of strings, got "
                        f"{type(val).__name__}"
                    )
                cleaned[key] = list(val)
            elif type(val) is not expected:
                raise UnrealRuntimeAdapterError(
                    f"{owner}.{key!r} must be of exact type "
                    f"{expected.__name__}, got {type(val).__name__} (no free-form "
                    "structures promoted into trusted provenance)"
                )
            else:
                cleaned[key] = val
    # Defense-in-depth authority scan over the (now scalar-only) values.
    _validate_strict_json_value(
        cleaned, owner, "<root>", reject_forbidden=True, high_confidence=False,
    )
    return cleaned


def _validate_mapping_provenance(payload: Dict[str, Any], owner: str) -> Dict[str, Any]:
    """Closed validation for a FULLY-ASSEMBLED mapping's provenance dict
    (R4-5, R4-9). Accepts exactly: the adapter-owned fields (validated as
    strict-JSON, adapter truth) plus the caller-visible typed schema fields
    (validated via the schema). Any other key is rejected (fail closed).

    Used by BOTH the factory (which assembles deterministic adapter fields) and
    ``__post_init__`` (direct construction), so one canonical path governs every
    provenance shape that can reach a mapping.
    """
    if not isinstance(payload, dict):
        raise UnrealRuntimeAdapterError(f"{owner} must be a dict")
    known = frozenset(
        set(_ADAPTER_RESERVED_PROVENANCE_KEYS) | set(_CALLER_PROVENANCE_SCHEMA)
    )
    for key in payload:
        if key not in known:
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is not an allowed mapping-provenance field "
                "(closed schema: adapter-owned or typed caller fields only)"
            )
        if is_forbidden_authority_key(key):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is forbidden authority material"
            )
    caller_part = {k: v for k, v in payload.items() if k in _CALLER_PROVENANCE_SCHEMA}
    adapter_part = {k: v for k, v in payload.items() if k in _ADAPTER_RESERVED_PROVENANCE_KEYS}
    _ = _validate_caller_provenance(caller_part, owner)
    _validate_strict_json_value(
        adapter_part, owner, "<root>", reject_forbidden=True, high_confidence=True,
    )
    return dict(payload)


def _reconcile_runtime_authority(compiled: AtlasTaskDefinition) -> AtlasTaskDefinition:
    """INDEPENDENTLY verify the compiled runtime task's authority against the
    M12.4 inspect-only contract. This is a REJECT, NOT a rewrite (R4-4):

    - ``allowed_action_tools`` must be exactly ``{unreal_inspect}``.
    - every action tool and evidence tool must be ``unreal_inspect``.
    - ``allow_writes`` must be False.

    On ANY violation raises ``UnrealRuntimeAdapterError`` (fail closed). It NEVER
    silently removes tools or clears write authority; a write-capable or
    render-capable compiled artifact is REJECTED rather than rewritten. A caller
    that supplied write intent is never silently downgraded to inspect-only.
    """
    allowed = set(compiled.allowed_action_tools)
    non_inspect_tools = allowed - {EXISTING_RUNTIME_INSPECT_TOOL}
    if non_inspect_tools:
        raise UnrealRuntimeAdapterError(
            "compiled runtime task permits non-inspect tool(s) "
            f"{sorted(non_inspect_tools)}; inspect-only contract violated"
        )
    emitted_tools = {a.tool for a in compiled.actions} | {e.tool for e in compiled.evidence}
    non_inspect_actions = sorted(emitted_tools - {EXISTING_RUNTIME_INSPECT_TOOL})
    if non_inspect_actions:
        raise UnrealRuntimeAdapterError(
            "compiled runtime actions/evidence use non-inspect tool(s) "
            f"{non_inspect_actions}; inspect-only contract violated"
        )
    if compiled.allow_writes:
        raise UnrealRuntimeAdapterError(
            "compiled runtime task claims write authority (allow_writes=True) "
            "under an inspect-only plan; REJECTING rather than rewriting the "
            "source's write intent"
        )
    return compiled


_RECONCILED_FIELDS: Tuple[str, ...] = (
    "required_inputs",
    "dependencies",
    "target_state_contributions",
    "idempotence",
    "fragment_id",
    "fragment_version",
    "preconditions",
    "verification_requirements",
    "capability_requirement",
)


__all__ = [
    "UnrealRuntimeAdapterError",
    "UnrealRuntimeStepMapping",
    "UnrealRuntimeMapping",
    "map_unreal_execution_plan",
    "compute_source_task_digest",
    "REQUIRES_EXISTING_RENDER_SUBMISSION_PATH",
    "EXISTING_RUNTIME_INSPECT_TOOL",
    "is_forbidden_authority_key",
]