"""M12.4 semantic -> existing Atlas/Unreal runtime adapter (narrow bridge).

M12.4 is an ADAPTER, never a new authority. It consumes a validated
:class:`UnrealExecutionPlan` (M12.3) together with the validated source
:class:`UnrealProductionTaskDefinition` (M12.1) and produces an immutable
:class:`UnrealRuntimeMapping` describing exactly how each semantic step maps onto
the EXISTING Atlas runtime representation (an :class:`AtlasTaskDefinition` via
the existing M12.1 compile boundary).

Critical invariants (enforced by construction, not by convention):

- It does NOT authorize, execute, schedule, retry, recover, persist, mint receipts,
  produce evidence manifests, or verify anything. ``can_execute`` is always False.
- It does NOT import or reach any M4-M10 production-authority module (render
  submission, recovery coordinator, receipt/store, evidence, job store/record).
- It does NOT create a second runtime, scheduler, retry, persistence, receipt,
  recovery, or evidence authority. M12.4 reuses the existing M12.1 compiler to
  produce the existing :class:`AtlasTaskDefinition` runtime representation.
- Render-bearing plans are recognized from the AUTHORITATIVE source task
  classification (never from a caller-supplied plan flag) and produce a
  STRUCTURED mapping that declares
  ``requires_existing_render_submission_path=True`` and NO runtime task. M12.4
  does not fabricate render authorization and does not submit MRQ.
- Unsupported steps / unknown idempotence / unsupported capability requirements
  fail closed (raise ``UnrealRuntimeAdapterError``).
- Authority/security material (authorization IDs, receipts, HMAC, credentials,
  protected flags, recovery/artifact authority, scheduler/retry directives,
  session/jwt/bearer/token/secret material) appearing ANYWHERE in the accepted
  provenance structure (nested mappings/sequences, any casing, any alias) is
  REJECTED, never silently forwarded.
- Step semantics (required inputs, dependencies, target-state contributions,
  idempotence, fragment identity/version, preconditions, verification
  requirements) are re-derived from the CANONICAL fragment and reconciled with
  the plan for EVERY mapped step, including render-bearing steps (no asymmetric
  bypass); any inconsistency fails closed. Fields that are intentionally only
  declared (not reconciled) are explicitly classified as such.
- The runtime representation honors the plan's semantic capability: an
  inspect-only plan never emits a write-capable ``AtlasTaskDefinition``.
- The mapping exposes an immutable canonical snapshot of the embedded runtime
  task (NOT a mutable ``AtlasTaskDefinition`` handle). Post-construction mutation
  is impossible or isolated; ``allowed_action_tools`` cannot gain ``unreal_render``
  after construction, and metadata cannot be altered to change semantics.
- The mapping is deterministic and the provenance/runtime-task structures are
  JSON-serializable end to end (nested immutable proxies thaw inside the
  canonical serializer): identical plan + identical source task produce
  identical canonical JSON.

Semantic fidelity model: the existing Atlas runtime represents an M12 semantic
task as a SINGLE aggregate :class:`AtlasTaskDefinition` (one unreal_inspect
action) built by the M12.1 compiler. It has no per-fragment runtime operations.
Consequently M12.4's mapping is aggregate at the task level (``semantic_fidelity``
= ``"aggregate"``): the fragment identities / versions / dependencies are carried
in the compiled task metadata and in each step mapping, but the runtime does NOT
produce one independently executable operation per fragment. M12.4 therefore
never claims per-fragment executable fidelity to the runtime; per-step meaning is
preserved as declared semantics for a future verifier (M12.5), not as distinct
runtime operations. If a step's semantic operation is not a known canonical
fragment (or cannot be represented at aggregate level), the mapping fails closed.

Declared-vs-validated contract: every step field under ``_RECONCILED_FIELDS`` is
reconciled against the canonical fragment (validated truth). Any plan step field
the adapter does NOT reconcile is either (a) carried verbatim and clearly marked
``declared=True`` in the step mapping (never represented as validated runtime
truth), or (b) dropped with an explicit note. Nothing declared is ever presented
as authoritative.
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
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from planning.m12.execution_plan import UnrealExecutionPlan
from planning.m12.fragments import UnrealProductionFragment
from planning.m12.fragments_registry import canonical_fragment
from planning.m12.semantic_task import (
    UnrealProductionTaskDefinition,
    compile_unreal_semantic_task,
)
from planning.task_definition import AtlasTaskDefinition

# Sentinel reason recorded on every step of a render-bearing plan to make the
# boundary explicit and audit-able while carrying no authorization material.
REQUIRES_EXISTING_RENDER_SUBMISSION_PATH = "requires-existing-render-submission-path"

# The single existing runtime tool that M12 non-render semantic tasks realize on
# as a task-level aggregate. M12.1's compiler emits one inspect action per
# composed task; the adapter records that tool as the aggregate target instead of
# inventing a new one.
EXISTING_RUNTIME_INSPECT_TOOL = "unreal_inspect"
# Adapter-owned provenance keys. These encode adapter-computed truth. A caller
# supplying any of these is REJECTED (no shadow/conflicting fields survive).
_ADAPTER_RESERVED_PROVENANCE_KEYS: FrozenSet[str] = frozenset(
    {
        "mapped_runtime_task_type",
        "recognized_render_plan",
        "semantic_fidelity",
        "source_task_digest",
        "runtime_task_digest",
        "declared",
    }
)
# Step fields that are reconciled against the canonical fragment.
_RECONCILED_FIELDS: Tuple[str, ...] = (
    "required_inputs",
    "dependencies",
    "target_state_contributions",
    "idempotence",
    "fragment_id",
    "fragment_version",
    "preconditions",
    "verification_requirements",
)

# ---------------------------------------------------------------------------
# Forbidden authority/security material. The adapter recursively validates every
# key in the accepted provenance structure, normalizing casing/separators so
# aliases (apiKey/apikey/API_KEY), casing variants, and nested placements are all
# rejected. This is fail-closed: forbidden material is REJECTED, never stripped
# and continued.
# ---------------------------------------------------------------------------

# Normalized authority/credential alias vocabulary (lowercased, separators
# removed). A key that normalizes to one of these (e.g. api_key / apikey /
# APIKey / api-key) is rejected anywhere in the structure.
_AUTHORITY_NORMALIZED_KEYS: FrozenSet[str] = frozenset(
    {
        "authorization",
        "authorizationid",
        "authorisation",
        "authorised",
        "authorized",
        "isauthorized",
        "isauthorised",
        "auth",
        "authid",
        "receipt",
        "receiptid",
        "receipthash",
        "nonce",
        "attemptnonce",
        "nonceid",
        "hmac",
        "hmackey",
        "hmacsecret",
        "apikey",
        "apitoken",
        "access_token",
        "accesstoken",
        "idtoken",
        "refreshtoken",
        "refreshtoken",
        "bearer",
        "bearertoken",
        "credential",
        "credentials",
        "password",
        "passwd",
        "secret",
        "clientsecret",
        "serversecret",
        "privatekey",
        "publickey",
        "signingkey",
        "session",
        "sessiontoken",
        "sessionid",
        "cookie",
        "jwt",
        "cert",
        "certificate",
        "recovery",
        "recoveryauthority",
        "retrycontroller",
        "scheduler",
        "retry",
        "protected",
        "protectedflag",
        "isprotected",
        "manifest",
        "manifestid",
        "artifact",
        "artifactid",
        "artifactmanifest",
        "attempt",
        "attemptid",
    }
)

# Substring triggers (normalized). A normalized key CONTAINING any of these is
# rejected. Kept broad for credentials/security so aliases and compound keys
# (e.g. "my_authorization_token") are caught.
_AUTHORITY_SUBSTRINGS: Tuple[str, ...] = (
    "authorization",
    "authorizationid",
    "authorised",
    "receipt",
    "nonce",
    "hmac",
    "credential",
    "password",
    "passwd",
    "secret",
    "bearer",
    "session",
    "jwt",
    "recovery",
    "retry",
    "schedul",
    "protected",
    "manifest",
    "artifact",
    "token",
    "apikey",
    "api_key",
    "auth",
    "privatekey",
    "signingkey",
    "cookie",
    "cert",
)


def _normalize_authority_key(key: Any) -> str:
    """Lowercase and strip common separators for alias/casing-invariant match.

    ``api_key``, ``api-key``, ``APIKey``, ``apikey`` all normalize to ``apikey``.
    ``is_authorized`` / ``IS_AUTHORIZED`` / ``IsAuthorized`` → ``isauthorized``.
    """
    if not isinstance(key, str):
        return ""
    s = key.lower().strip()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def is_forbidden_authority_key(key: Any) -> bool:
    """Return True iff a provenance key is authority/security material.

    Recursively safe to call on nested-provenance keys. Normalizes casing and
    separators so aliases (apiKey/apikey/API_KEY), casing tricks
    (IS_AUTHORIZED / IsAuthorized), and compound credential keys are all caught.
    Non-string keys are always treated as forbidden (fail closed).
    """
    if not isinstance(key, str):
        return True
    n = _normalize_authority_key(key)
    if n in _AUTHORITY_NORMALIZED_KEYS:
        return True
    return any(seg in n for seg in _AUTHORITY_SUBSTRINGS)


def _is_json_scalar(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)) or isinstance(value, numbers.Integral):
        return True
    if isinstance(value, numbers.Real):
        # Reject non-finite floats so canonical JSON is strict/portable.
        return math.isfinite(float(value))
    return False


def _validate_provenance_value(value: Any, owner: str, path: str, depth: int = 0) -> None:
    """Recursively validate a provenance value for authority material.

    Walks mappings and sequences; rejects (a) any forbidden/authority-like key at
    any depth, (b) non-string mapping keys, (c) unsupported object types, and
    (d) pathologically deep nesting. Never strips-and-continues: it raises.
    """
    if depth > 16:
        raise UnrealRuntimeAdapterError(
            f"{owner}.{path}: provenance nesting exceeds safety limit (possible cycle)"
        )
    if isinstance(value, (Mapping, MappingProxyType)):
        for k, v in value.items():
            if not isinstance(k, str):
                raise UnrealRuntimeAdapterError(
                    f"{owner}.{path}: provenance mapping key must be a string, got "
                    f"{type(k).__name__}"
                )
            if is_forbidden_authority_key(k):
                raise UnrealRuntimeAdapterError(
                    f"{owner}.{path}.{k!r} is forbidden authority/security material; "
                    "rejecting rather than forwarding it into the runtime mapping"
                )
            _validate_provenance_value(v, owner, f"{path}.{k}", depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _validate_provenance_value(item, owner, f"{path}[{i}]", depth + 1)
        return
    if not _is_json_scalar(value):
        raise UnrealRuntimeAdapterError(
            f"{owner}.{path}: unsupported provenance value type "
            f"{type(value).__name__} (must be JSON-serializable scalar, mapping, "
            "or sequence)"
        )


def _validate_provenance(payload: Any, owner: str, *, reserved: FrozenSet[str]) -> Dict[str, Any]:
    """Validate and return a provenance dict.

    Recursively rejects authority/security material anywhere in the accepted
    structure and rejects any adapter-reserved key (caller cannot shadow adapter
    truth). Never silently strips malicious material.
    """
    if not isinstance(payload, dict):
        raise UnrealRuntimeAdapterError(f"{owner} must be a dict")
    for key in payload:
        if key in reserved:
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is an adapter-owned field; caller-supplied "
                "shadow values are rejected"
            )
        if is_forbidden_authority_key(key):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is forbidden authority/security material; "
                "rejecting rather than forwarding it"
            )
        _validate_provenance_value(payload[key], owner, str(key), 1)
    return dict(payload)


def _freeze_json(value: Any) -> Any:
    """Return a deeply immutable, JSON-model copy (dicts -> MappingProxyType,
    sequences -> tuple, scalars unchanged)."""
    if isinstance(value, (Mapping, MappingProxyType)):
        return MappingProxyType({k: _freeze_json(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(v) for v in value)
    return value


def _thaw_json(value: Any) -> Any:
    """Recursively convert immutable/frozen structures back to JSON-safe plain
    dict/list so the canonical serializer never hits a MappingProxyType."""
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
        # Deep-freeze provenance (immutability of the mapping's canonical view).
        object.__setattr__(self, "provenance", _freeze_json(self.provenance))

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

    Covers the semantic task identity, version, digital-twin id, target state,
    dependencies, evidence, actions, allowed tools/mutations, and resolved
    catalog metadata (parameters, fragments). Two same-identity tasks with
    different resolved content produce different digests; the adapter binds this
    digest so substitution is detectable and (when embedded) rejected.
    """
    if not isinstance(source_task, UnrealProductionTaskDefinition):
        raise TypeError("source_task must be an UnrealProductionTaskDefinition")
    payload = source_task.to_json_compatible()
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UnrealRuntimeMapping:
    """Immutable result of mapping an M12.3 plan onto the existing runtime.

    Identity fields (plan id, source semantic task id/version, catalog version,
    digital-twin id) are preserved and never collapsed. ``source_task_digest``
    deterministically binds the resolved source content. ``render_plan`` /
    ``requires_existing_render_submission_path`` reflect the AUTHORITATIVE source
    task classification. ``can_execute`` is always False.

    ``runtime_task_snapshot`` is an immutable, JSON-serializable snapshot of the
    EXISTING :class:`AtlasTaskDefinition`` (name, evidence, actions,
    allowed_action_tools, allow_writes, verify_after_action, metadata).
    ``runtime_task_digest`` is its SHA-256 binding. The mapping does NOT expose a
    mutable ``AtlasTaskDefinition`` handle: callers use
    ``materialize_runtime_task()`` to obtain a fresh isolated deep copy, so
    post-construction mutation cannot invalidate the mapping's trust/audit
    invariant, and ``allowed_action_tools`` cannot gain ``unreal_render`` in the
    mapping's canonical view. ``runtime_task_snapshot`` is None for render-bound
    plans (no runtime representation is fabricated).

    ``semantic_fidelity`` explicitly records how the plan's semantics are
    represented by the existing runtime: ``"aggregate"`` (non-render tasks are
    represented as ONE task-level AtlasTaskDefinition + per-step reconciled
    semantics; the runtime has no per-fragment operations) or ``"unavailable"``
    (render-bearing plans are not represented at all).

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
        if self.runtime_task_snapshot is not None and not isinstance(
            self.runtime_task_snapshot, MappingProxyType
        ):
            raise UnrealRuntimeAdapterError(
                "runtime_task_snapshot must be a deep-frozen mapping or None"
            )
        if self.runtime_task_digest is not None and not isinstance(
            self.runtime_task_digest, str
        ):
            raise UnrealRuntimeAdapterError(
                "runtime_task_digest must be a str or None"
            )
        if self.semantic_fidelity not in ("aggregate", "unavailable"):
            raise UnrealRuntimeAdapterError(
                "semantic_fidelity must be 'aggregate' or 'unavailable'"
            )
        _check_token(self.source_task_digest, "source_task_digest")
        if not isinstance(self.provenance, dict):
            raise UnrealRuntimeAdapterError("provenance must be a dict")
        # Deep-freeze provenance (immutability of the mapping's canonical view).
        object.__setattr__(self, "provenance", _freeze_json(self.provenance))
        if self.runtime_task_snapshot is not None:
            object.__setattr__(
                self, "runtime_task_snapshot", _freeze_json(dict(self.runtime_task_snapshot))
            )

    @property
    def can_execute(self) -> bool:
        """An adapter mapping is never an executor. Always False."""
        return False

    def materialize_runtime_task(self) -> Optional[AtlasTaskDefinition]:
        """Return a FRESH, isolated deep copy of the runtime task, or None.

        Because a fresh deep copy is returned each call, mutating the result
        (allowed_action_tools, metadata, ...) can never affect this mapping's
        canonical snapshot or digest. Callers that mutate the returned copy are
        mutating only their own copy.
        """
        stored = getattr(self, "_materialized_runtime_task", None)
        if stored is None:
            return None
        return _copy.deepcopy(stored)

    def to_json_compatible(self) -> Dict[str, Any]:
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
            "runtime_task_snapshot": (
                _thaw_json(self.runtime_task_snapshot)
                if self.runtime_task_snapshot is not None
                else None
            ),
            "steps": [s.to_json_compatible() for s in self.steps],
            "provenance": _thaw_json(self.provenance),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical serialization (sorted keys, compact).

        The provenance and runtime-task snapshot are deep-frozen at construction,
        so mutating the caller's input afterward cannot change this output.
        """
        return json.dumps(
            self.to_json_compatible(), sort_keys=True, separators=(",", ":")
        )


def _same_steps_as_task(plan: UnrealExecutionPlan, task: UnrealProductionTaskDefinition) -> bool:
    """The plan's ordered semantic operations must exactly match the source task's
    ordered fragment dependencies (this is how M12.3 builds a plan). Mismatch is
    fail-closed, so the adapter never maps a plan onto a different runtime.""" 
    return tuple(step.semantic_operation for step in plan.steps) == tuple(
        task.dependencies
    )


def _candidate_fragment(step_semantic_operation: str) -> Optional[UnrealProductionFragment]:
    """Resolve the canonical fragment for a semantic operation, or None if the
    operation is not a known canonical fragment (unknown -> fail closed)."""
    try:
        return canonical_fragment(step_semantic_operation)
    except KeyError:
        return None


def _prefix_producer_map(steps):
    """Reconstruct the prefix-only producer->step map, mirroring M12.3's
    generator: a requirement only resolves to producers among EARLIER steps.

    A forward-only producer map would let an attacker declare a dependency on a
    future step; the prefix map means unresolved/forward requirements yield no
    producer entry, so any plan claiming such a dependency fails closed.
    """
    producer_to_step: Dict[str, str] = {}
    for step in steps:
        frag = _candidate_fragment(step.semantic_operation)
        if frag is not None:
            for produced in frag.produces:
                producer_to_step.setdefault(produced, step.step_id)
    return producer_to_step


def _explain_and_check_precondition(
    plan_step,
    fragment: UnrealProductionFragment,
) -> Optional[str]:
    """Reconcile the plan step's preconditions + verification requirements.

    M12.3 sets preconditions = sorted(fragment.requires) (raw requirement names)
    and verification_requirements = sorted(contributed_invariant_names()). We
    re-derive both and reject divergence so a plan cannot drop/forge them.
    """
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

    # Dependencies: expected = the producer steps (EARLIER in order, prefix map)
    # that satisfy each requirement name, exactly as M12.3's generator resolves.
    expected_deps = tuple(
        sorted(
            {
                producer_to_step[req]
                for req in fragment.requires
                if req in producer_to_step
            }
        )
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


def _digest_of_jsonable(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()



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
        catalog_version: catalog version override. Defaults to ``plan.catalog_version``.
        expected_source_task_digest: if provided, the resolved source content
            must produce exactly this digest; any mismatch is rejected. This is
            the M12.4 enforcement point for same-identity/different-content
            substitution (the plan itself, generated by M12.3, does not carry the
            resolved parameters; callers that hold an expected digest pass it
            here). When omitted, the mapping still computes and records the
            authoritative ``source_task_digest`` for downstream verification.

    Returns:
        a deterministic :class:`UnrealRuntimeMapping`. See the class docstring for
        the exact contract (immutable snapshot, no mutable AtlasTaskDefinition
        handle, source digest binding, ...).

    Raises:
        TypeError: if ``plan`` or ``source_task`` has the wrong type.
        UnrealRuntimeAdapterError: if the plan's identity does not match the
            source task; a supported step mismatches the canonical fragment
            (inputs/dependencies/target-state/idempotence/preconditions/
            verification requirements); forbidden authority material appears
            anywhere in plan/step provenance; a caller supplies an adapter-owned
            provenance key; render classification is inconsistent with the
            authoritative source task; an unsupported capability or unknown
            idempotence is requested; source content is inconsistent with the
            plan's resolved target state; or the mapping is otherwise ambiguous.
    """
    if not isinstance(plan, UnrealExecutionPlan):
        raise TypeError("plan must be an UnrealExecutionPlan")
    if not isinstance(source_task, UnrealProductionTaskDefinition):
        raise TypeError("source_task must be an UnrealProductionTaskDefinition")

    # Identity lock: mapping is only allowed for the exact semantic task the plan
    # was generated from (task id/version/twin). This prevents attaching runtime
    # to a different task CLASS.
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

    # Fix 1: recursive authority/security material rejection in plan provenance
    # (deny nested/casing/alias credentials). Preserve legitimate provenance.
    clean_plan_provenance = _validate_provenance(
        dict(plan.provenance or {}),
        "plan.provenance",
        reserved=_ADAPTER_RESERVED_PROVENANCE_KEYS,
    )

    # Fix 4: bind the resolved source content. A caller-supplied source_task
    # that shares the plan's class/version/twin but differs in resolved content
    # (e.g. different parameters/target-state) yields a different digest.
    source_digest = compute_source_task_digest(source_task)
    if (
        expected_source_task_digest is not None
        and expected_source_task_digest != source_digest
    ):
        raise UnrealRuntimeAdapterError(
            "expected_source_task_digest does not match the provided source task "
            "resolved content; refusing to map a substituted source "
            f"(expected {expected_source_task_digest[:16]}..., got {source_digest[:16]}...)"
        )
    embedded_digest = clean_plan_provenance.get("source_task_digest")
    if embedded_digest is not None and embedded_digest != source_digest:
        raise UnrealRuntimeAdapterError(
            "plan provenance carries a source_task_digest that does not match the "
            "provided source task resolved content; refusing to map a substituted "
            "source"
        )

    # Fix 5/4: verify plan's resolved target-state against the source task's
    # target-state invariants (another same-identity/different-content detector).
    plan_composed_invariants = set()
    for step in plan.steps:
        plan_composed_invariants.update(step.target_state_contributions)
    source_target_invariants = set(source_task.target_state.to_invariant_names())
    if plan_composed_invariants != source_target_invariants:
        raise UnrealRuntimeAdapterError(
            "plan's composed target-state contributions do not match the source "
            "task's resolved target-state invariants; failing closed on "
            "substituted/inconsistent source content"
        )

    # Fix 5: render classification must be reconciled with the authoritative
    # source task. A caller must not be able to understate or overstate
    # render-bearing status; fail closed on any mismatch.
    authoritative_render = source_task.render_task
    if plan.render_plan != authoritative_render:
        raise UnrealRuntimeAdapterError(
            f"render_plan mismatch: plan declares render_plan={plan.render_plan!r} "
            f"but the authoritative source task class "
            f"{source_task.task_class!r} is render-bearing={authoritative_render!r}; "
            "failing closed rather than trusting the plan flag"
        )
    require_render_boundary = authoritative_render

    used_catalog_version = catalog_version if catalog_version is not None else plan.catalog_version

    # Step fidelity: re-derive critical semantics from the canonical fragments so
    # a crafted plan cannot silently distort inputs/dependencies/target-state/
    # idempotence/preconditions/verification requirements while mapping. Applied
    # to EVERY step, including render-bearing ones (no asymmetric bypass).
    # NOTE: prefix-only producer map; forward dependencies fail closed.
    # Reconstruct the prefix map by walking steps in order and only counting
    # producers strictly before the current step.
    all_fragments = [_candidate_fragment(s.semantic_operation) for s in plan.steps]

    mapped_steps: Tuple[UnrealRuntimeStepMapping, ...] = ()
    prefix_producers: Dict[str, str] = {}
    rendered_steps: list = []
    for index, step in enumerate(plan.steps):
        fragment = all_fragments[index]
        if fragment is None:
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: semantic operation "
                f"{step.semantic_operation!r} is not a known canonical fragment "
                "(fail closed)"
            )
        if step.idempotence == "unknown":
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: unknown idempotence (fail closed)"
            )
        if step.execution_capability_requirement != "inspect-only":
            raise UnrealRuntimeAdapterError(
                f"cannot map step {step.step_id!r}: unsupported capability "
                f"requirement {step.execution_capability_requirement!r} (only "
                f"'inspect-only' is representable in the existing runtime)"
            )
        fid_reason = _reconcile_step_fidelity(step, fragment, prefix_producers)
        if fid_reason is not None:
            raise UnrealRuntimeAdapterError(fid_reason)

        # Validate step provenance recursively and reject adapter-owned shadow keys.
        step_provenance = _validate_provenance(
            dict(step.provenance or {}),
            f"step.provenance[{step.step_id!r}]",
            reserved=_ADAPTER_RESERVED_PROVENANCE_KEYS,
        )
        # Overwrite M12.3-declared fragment identity/version with canonical truth so a
        # crafted plan cannot seed a conflicting fragment identity that survives.
        step_provenance["fragment_id"] = fragment.canonical_id
        step_provenance["fragment_version"] = fragment.version

        if require_render_boundary:
            supported = False
            target_op = "<none>"
            reason = REQUIRES_EXISTING_RENDER_SUBMISSION_PATH
            declared = False
        else:
            supported = True
            target_op = EXISTING_RUNTIME_INSPECT_TOOL
            reason = None
            declared = False

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
        # After processing this step, add its produced requirements to the prefix
        # map so a LATER step may depend on them.
        for produced in fragment.produces:
            prefix_producers.setdefault(produced, step.step_id)
    mapped_steps = tuple(rendered_steps)

    # Build the existing runtime representation ONLY for non-render plans, via
    # the existing M12.1 compiler (it already rejects render-bearing plans). For
    # render plans we do not reach it at all. The mapping keeps ONLY an immutable
    # snapshot + digest of the runtime task; a mutable AtlasTaskDefinition is not
    # exposed (callers materialize a fresh isolated copy).
    runtime_task_snapshot: Optional[MappingProxyType] = None
    runtime_task_digest: Optional[str] = None
    semantic_fidelity = "unavailable"
    _materialized: Optional[AtlasTaskDefinition] = None
    if not require_render_boundary:
        compiled = compile_unreal_semantic_task(source_task)
        # Fix 2: reconcile write authority with the plan's inspect-only
        # capability. An all-inspect-only semantic plan must not emit a
        # write-capable AtlasTaskDefinition. The existing field (allow_writes) is
        # re-derived consistently; no new authority field is invented.
        all_inspect_only = all(
            s.execution_capability_requirement == "inspect-only" for s in plan.steps
        )
        if all_inspect_only and compiled.allow_writes:
            compiled = dataclasses.replace(compiled, allow_writes=False)
        # Deep-copy so post-construction mutation of the caller's/source object
        # cannot affect the mapping's snapshot/digest.
        _materialized = _copy.deepcopy(compiled)
        snapshot_mapping = {
            "name": _materialized.name,
            "evidence": [
                {"tool": e.tool, "arguments": _copy.deepcopy(e.arguments), "name": e.name}
                for e in _materialized.evidence
            ],
            "actions": [
                {
                    "tool": a.tool,
                    "arguments": _copy.deepcopy(a.arguments),
                    "name": a.name,
                    "requires_success": a.requires_success,
                    "depends_on": list(a.dependency_names()),
                }
                for a in _materialized.actions
            ],
            "allowed_action_tools": sorted(_materialized.allowed_action_tools),
            "allow_writes": _materialized.allow_writes,
            "verify_after_action": _materialized.verify_after_action,
            "metadata": _copy.deepcopy(_materialized.metadata or {}),
        }
        runtime_task_snapshot = _freeze_json(snapshot_mapping)  # type: ignore[assignment]
        runtime_task_digest = _digest_of_jsonable(_thaw_json(runtime_task_snapshot))
        semantic_fidelity = "aggregate"

    provenance = dict(clean_plan_provenance)
    # Fix 5: adapter-owned provenance keys are authoritative (direct assignment,
    # not setdefault, and caller-supplied shadow values already rejected).
    provenance["mapped_runtime_task_type"] = (
        "AtlasTaskDefinition" if not require_render_boundary else "unavailable"
    )
    provenance["recognized_render_plan"] = require_render_boundary
    provenance["semantic_fidelity"] = semantic_fidelity
    provenance["source_task_digest"] = source_digest
    provenance["runtime_task_digest"] = runtime_task_digest
    provenance["declared"] = False

    mapping = UnrealRuntimeMapping(
        plan_id=plan.plan_id,
        source_task_id=plan.source_task_id,
        source_task_version=plan.source_task_version,
        catalog_version=used_catalog_version,
        digital_twin_id=plan.digital_twin_id,
        steps=mapped_steps,
        render_plan=plan.render_plan,
        requires_existing_render_submission_path=require_render_boundary,
        runtime_task_snapshot=runtime_task_snapshot,
        runtime_task_digest=runtime_task_digest,
        semantic_fidelity=semantic_fidelity,
        source_task_digest=source_digest,
        provenance=provenance,
    )
    # Attach a private deep copy for materialize_runtime_task isolation.
    mapping.__dict__["_materialized_runtime_task"] = _materialized
    return mapping


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