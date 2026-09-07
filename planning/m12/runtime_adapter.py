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
  protected flags, recovery/artifact authority, scheduler/retry directives)
  appearing in plan provenance is REJECTED, never silently forwarded.
- Step semantics (required inputs, dependencies, target-state contributions,
  idempotence, fragment identity/version) are re-derived from the CANONICAL
  fragment and reconciled with the plan; any inconsistency fails closed.
- The runtime representation honors the plan's semantic capability: an
  inspect-only plan never emits a write-capable ``AtlasTaskDefinition``.
- The mapping is deterministic: identical plan + identical source task produce
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
"""

from __future__ import annotations

import dataclasses
import json
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

# Authoritative render-bearing classification passed through from the source
# task must match the plan's classification; mismatch fails closed.
_AUTHORITATIVE_RENDER_DERIVED = "authoritative-source-task"


class UnrealRuntimeAdapterError(ValueError):
    """Raised when a semantic plan cannot be safely mapped to the runtime."""


# ---------------------------------------------------------------------------
# Forbidden authority/security material (mirrors M12.1 semantic_task.py).
# The adapter independently rejects these because a crafted plan object can be
# constructed directly, bypassing M12.1's normalize-boundary vetting.
# ---------------------------------------------------------------------------
_FORBIDDEN_AUTHORITY_KEYS: FrozenSet[str] = frozenset(
    {
        "authorization_id",
        "authorization",
        "receipt",
        "receipt_id",
        "artifact_id",
        "manifest_id",
        "recovery_authority",
        "scheduler",
        "retry_controller",
        "nonce",
        "attempt_nonce",
        "hmac",
        "hmac_key",
        "api_key",
        "credential",
        "protected",
        "protected_flag",
        "is_authorized",
        "authorized",
    }
)

_FORBIDDEN_AUTHORITY_SUBSTRINGS: Tuple[str, ...] = (
    "authorization",
    "receipt",
    "artifact",
    "manifest",
    "hmac",
    "nonce",
    "api_key",
    "credential",
    "recovery_authority",
    "protected",
    "scheduler",
    "retry",
)


def is_forbidden_authority_key(key: str) -> bool:
    """Return True iff a provenance key is authority/security material.

    Uses the same exact-set + substring heuristic as M12.1's semantic_task so a
    smuggled authorization/receipt/credential key is rejected at the adapter
    boundary rather than forwarded into the runtime mapping.
    """
    if not isinstance(key, str):
        return True
    lowered = key.lower()
    return key in _FORBIDDEN_AUTHORITY_KEYS or any(
        seg in lowered for seg in _FORBIDDEN_AUTHORITY_SUBSTRINGS
    )


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


def _deep_freeze(value: Any) -> Any:
    """Return a deep-immutable, JSON-compatible copy (freeze dicts -> proxies,
    lists/tuples -> tuples, recursively)."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v) for v in value)
    return value


def _validate_provenance(payload: Any, owner: str) -> Dict[str, Any]:
    """Validate a provenance dict, rejecting authority/security material.

    Raises:
        UnrealRuntimeAdapterError: if the payload is not a dict, or if any key is
            forbidden authority/security material (never silently dropped).
    """
    if not isinstance(payload, dict):
        raise UnrealRuntimeAdapterError(f"{owner} must be a dict")
    for key in payload:
        if is_forbidden_authority_key(key):
            raise UnrealRuntimeAdapterError(
                f"{owner}.{key!r} is forbidden authority/security material; "
                "rejecting rather than forwarding it into the runtime mapping"
            )
    return dict(payload)


@dataclass(frozen=True)
class UnrealRuntimeStepMapping:
    """Immutable per-step mapping from one semantic step to the existing runtime.

    A step is *supported* only when there is a demonstrated existing Atlas
    runtime representation that already ingests it: the task-level aggregate
    ``unreal_inspect`` representation. Per-step semantic fields (required inputs,
    dependencies, target-state contributions, idempotence, capability, fragment
    identity/version) are re-derived from the CANONICAL fragment by the adapter
    and are immutable here; a crafted plan cannot silently distort them.

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
    unsupported_reason: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_token(self.step_id, "step_id")
        _check_token(self.semantic_operation, "semantic_operation")
        _check_tokens(self.required_inputs, "required_inputs")
        _check_tokens(self.dependencies, "dependencies")
        _check_tokens(self.target_state_contributions, "target_state_contributions")
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
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))

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
            "unsupported_reason": self.unsupported_reason,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class UnrealRuntimeMapping:
    """Immutable result of mapping an M12.3 plan onto the existing runtime.

    Identity fields (plan id, source semantic task id/version, catalog version,
    digital-twin id) are preserved and never collapsed. ``runtime_task`` holds
    the EXISTING :class:`AtlasTaskDefinition`` (for supported non-render plans)
    or ``None`` for render-bearing plans. ``can_execute`` is always False.

    The mapping never:
    - authorizes execution;
    - mints receipts / recovery authority / protected flags;
    - schedules, retries, reconstructs, or verifies;
    - submits, or fabricates, a render.

    ``semantic_fidelity`` explicitly records how the plan's semantics are
    represented by the existing runtime: ``"aggregate"`` (non-render tasks are
    represented as ONE task-level AtlasTaskDefinition + per-step declared
    semantics; the runtime has no per-fragment operations) or ``"unavailable"``
    (render-bearing plans are not represented at all).

    ``runtime_task.allow_writes`` is reconciled to the plan's capability: an
    all-inspect-only plan never emits a write-capable runtime representation.
    """

    plan_id: str
    source_task_id: str
    source_task_version: int
    catalog_version: int
    digital_twin_id: str
    steps: Tuple[UnrealRuntimeStepMapping, ...]
    render_plan: bool
    requires_existing_render_submission_path: bool
    runtime_task: Optional[AtlasTaskDefinition]
    semantic_fidelity: str
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
        if self.runtime_task is not None and not isinstance(
            self.runtime_task, AtlasTaskDefinition
        ):
            raise UnrealRuntimeAdapterError(
                "runtime_task must be an AtlasTaskDefinition or None"
            )
        if self.semantic_fidelity not in ("aggregate", "unavailable"):
            raise UnrealRuntimeAdapterError(
                "semantic_fidelity must be 'aggregate' or 'unavailable'"
            )
        if not isinstance(self.provenance, dict):
            raise UnrealRuntimeAdapterError("provenance must be a dict")
        # Deep-freeze provenance (immutability of the mapping's canonical view).
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))

    @property
    def can_execute(self) -> bool:
        """An adapter mapping is never an executor. Always False."""
        return False

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_task_id": self.source_task_id,
            "source_task_version": self.source_task_version,
            "catalog_version": self.catalog_version,
            "digital_twin_id": self.digital_twin_id,
            "render_plan": self.render_plan,
            "requires_existing_render_submission_path": (
                self.requires_existing_render_submission_path
            ),
            "semantic_fidelity": self.semantic_fidelity,
            "runtime_task_present": self.runtime_task is not None,
            "steps": [s.to_json_compatible() for s in self.steps],
            "provenance": dict(self.provenance),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical serialization (sorted keys, compact).

        The provenance view is deep-frozen at construction, so mutating the
        caller's input afterward cannot change this output.
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


def _build_producer_to_step(
    steps,
) -> Dict[str, str]:
    """Reconstruct the producer->step-id map exactly as M12.3's generator does.

    Processed in order so a later requirement only resolves to producers among
    earlier steps.
    """
    producer_to_step: Dict[str, str] = {}
    for step in steps:
        frag = _candidate_fragment(step.semantic_operation)
        if frag is not None:
            for produced in frag.produces:
                producer_to_step[produced] = step.step_id
    return producer_to_step


def _reconcile_step_fidelity(
    step,
    fragment: UnrealProductionFragment,
    producer_to_step: Dict[str, str],
) -> Optional[str]:
    """Reconcile a plan step's claimed semantics against the canonical fragment.

    Returns an error message if any field is inconsistent, else None. This makes
    the adapter independent of a crafted/adversarial plan's mutable contents: the
    canonical fragment is the source of truth for required inputs,
    target-state contributions, idempotence, and dependencies.
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

    # Dependencies: expected = the producer steps (earlier in order) that satisfy
    # each requirement name, exactly as M12.3's generator resolves them.
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
    return None


def map_unreal_execution_plan(
    plan: UnrealExecutionPlan,
    *,
    source_task: UnrealProductionTaskDefinition,
    catalog_version: Optional[int] = None,
) -> UnrealRuntimeMapping:
    """Map a validated M12.3 execution plan onto the existing Atlas runtime.

    Args:
        plan: an already-validated :class:`UnrealExecutionPlan`.
        source_task: the validated :class:`UnrealProductionTaskDefinition` the
            plan was generated from (used to reuse the existing M12.1 compiler).
        catalog_version: catalog version override. Defaults to ``plan.catalog_version``.

    Returns:
        a deterministic :class:`UnrealRuntimeMapping`. For a non-render plan it
        wraps the existing :class:`AtlasTaskDefinition` produced by M12.1's
        compiler (M12.4 does not construct a new runtime), with the runtime's
        write authority reconciled to the plan's inspect-only capability. For a
        render-bearing plan it yields ``runtime_task=None`` and
        ``requires_existing_render_submission_path=True`` without manufacturing
        authorization or a runtime task.

    Raises:
        TypeError: if ``plan`` or ``source_task`` has the wrong type.
        UnrealRuntimeAdapterError: if the plan's identity does not match the
            source task; a supported step mismatches the canonical fragment
            (inputs/dependencies/target-state/idempotence); forbidden authority
            material appears in plan provenance; render classification is
            inconsistent with the authoritative source task; an unsupported
            capability or unknown idempotence is requested; or the mapping is
            otherwise ambiguous.
    """
    if not isinstance(plan, UnrealExecutionPlan):
        raise TypeError("plan must be an UnrealExecutionPlan")
    if not isinstance(source_task, UnrealProductionTaskDefinition):
        raise TypeError("source_task must be an UnrealProductionTaskDefinition")

    # Identity lock: mapping is only allowed for the exact semantic task the plan
    # was generated from. This prevents attaching a runtime representation to a
    # foreign plan (fail-closed identity preservation).
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

    # Fix 1: reject authority/security material smuggled via plan provenance
    # (a crafted plan can bypass M12.1's normalize vetting). Preserve legitimate
    # provenance.
    clean_plan_provenance = _validate_provenance(dict(plan.provenance or {}), "plan.provenance")

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
    # idempotence while still mapping.
    producer_to_step = _build_producer_to_step(plan.steps)

    mapped_steps: Tuple[UnrealRuntimeStepMapping, ...] = ()
    if not require_render_boundary:
        rendered_steps = []
        for step in plan.steps:
            fragment = _candidate_fragment(step.semantic_operation)
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
            fid_reason = _reconcile_step_fidelity(step, fragment, producer_to_step)
            if fid_reason is not None:
                raise UnrealRuntimeAdapterError(fid_reason)

            step_provenance = dict(step.provenance or {})
            _validate_provenance(step_provenance, f"step.provenance[{step.step_id!r}]")
            step_provenance.setdefault("fragment_id", fragment.canonical_id)
            step_provenance.setdefault("fragment_version", fragment.version)
            rendered_steps.append(
                UnrealRuntimeStepMapping(
                    step_id=step.step_id,
                    semantic_operation=step.semantic_operation,
                    supported=True,
                    target_runtime_operation=EXISTING_RUNTIME_INSPECT_TOOL,
                    required_inputs=tuple(sorted(set(step.required_inputs))),
                    dependencies=tuple(sorted(set(step.dependencies))),
                    target_state_contributions=tuple(
                        sorted(set(step.target_state_contributions))
                    ),
                    idempotence=step.idempotence,
                    capability_requirement=step.execution_capability_requirement,
                    fragment_id=fragment.canonical_id,
                    fragment_version=fragment.version,
                    unsupported_reason=None,
                    provenance=step_provenance,
                )
            )
        mapped_steps = tuple(rendered_steps)
    else:
        # Render-bearing plan: never translate into a runtime task, never
        # fabricate a render submission. Record the boundary on each step.
        render_steps = []
        for step in plan.steps:
            fragment = _candidate_fragment(step.semantic_operation)
            step_provenance = dict(step.provenance or {})
            _validate_provenance(step_provenance, f"step.provenance[{step.step_id!r}]")
            render_steps.append(
                UnrealRuntimeStepMapping(
                    step_id=step.step_id,
                    semantic_operation=step.semantic_operation,
                    supported=False,
                    target_runtime_operation="<none>",
                    required_inputs=tuple(sorted(set(step.required_inputs))),
                    dependencies=tuple(sorted(set(step.dependencies))),
                    target_state_contributions=tuple(
                        sorted(set(step.target_state_contributions))
                    ),
                    idempotence=step.idempotence,
                    capability_requirement=step.execution_capability_requirement,
                    fragment_id=fragment.canonical_id if fragment is not None else None,
                    fragment_version=fragment.version if fragment is not None else None,
                    unsupported_reason=REQUIRES_EXISTING_RENDER_SUBMISSION_PATH,
                    provenance=step_provenance,
                )
            )
        mapped_steps = tuple(render_steps)

    # Build the existing runtime representation ONLY for non-render plans, by
    # reusing the existing M12.1 compiler (it already rejects render-bearing
    # plans). For render plans we do not reach it at all.
    runtime_task: Optional[AtlasTaskDefinition] = None
    semantic_fidelity = "unavailable"
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
            runtime_task = dataclasses.replace(compiled, allow_writes=False)
        else:
            runtime_task = compiled
        semantic_fidelity = "aggregate"

    provenance = dict(clean_plan_provenance)
    provenance.setdefault("mapped_runtime_task_type", "AtlasTaskDefinition" if not require_render_boundary else "unavailable")
    provenance.setdefault("recognized_render_plan", require_render_boundary)
    provenance["semantic_fidelity"] = semantic_fidelity

    return UnrealRuntimeMapping(
        plan_id=plan.plan_id,
        source_task_id=plan.source_task_id,
        source_task_version=plan.source_task_version,
        catalog_version=used_catalog_version,
        digital_twin_id=plan.digital_twin_id,
        steps=mapped_steps,
        render_plan=plan.render_plan,
        requires_existing_render_submission_path=require_render_boundary,
        runtime_task=runtime_task,
        semantic_fidelity=semantic_fidelity,
        provenance=provenance,
    )


__all__ = [
    "UnrealRuntimeAdapterError",
    "UnrealRuntimeStepMapping",
    "UnrealRuntimeMapping",
    "map_unreal_execution_plan",
    "REQUIRES_EXISTING_RENDER_SUBMISSION_PATH",
    "EXISTING_RUNTIME_INSPECT_TOOL",
    "is_forbidden_authority_key",
]