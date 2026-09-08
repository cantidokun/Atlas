"""M12 Unreal semantic production-task contract + normalization/compile boundary.

This is the foundational M12.1 layer. It defines:

- :class:`UnrealProductionTaskDefinition`: an immutable, validated semantic
  production-task contract that is independent of low-level Unreal transport
  detail.
- :func:`normalize_unreal_semantic_request`: deterministic normalization from a
  raw semantic request into canonical form, fail-closed on malformed/ambiguous
  or unsupported input.
- :func:`compile_unreal_semantic_task`: a narrow compiler that maps a validated
  semantic task onto the existing
  :class:`planning.task_definition.AtlasTaskDefinition` representation.

Critical invariant: nothing in this module authorizes execution, mints receipts,
grants recovery authority, sets protected flags, or introduces a scheduler/retry
authority. Model-provided authorization material is never trusted. Those
authorities remain entirely in the existing M4-M10 machinery.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from action_plan import ActionSpec
from planning.action_dependencies import validate_action_dependencies
from planning.evidence_plan import EvidenceRequest
from planning.m12.target_state import (
    UnrealTargetStateSpec,
    target_state_metadata,
    target_state_spec,
)
from planning.m12.task_classes import (
    UNREAL_RENDER_TASK_CLASSES,
    UNREAL_TASK_CLASS_INTENT,
    is_render_task_class,
    validate_task_class,
)
from planning.task_definition import AtlasTaskDefinition
from planning.target_state import StateInvariant, TargetStateEvaluator

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnrealSemanticTaskError(ValueError):
    """Base error for M12 semantic-task contract/normalization failures."""


class UnsupportedCompileMappingError(UnrealSemanticTaskError):
    """Raised when a semantic task cannot safely map to the existing runtime."""


class UnauthorizedSemanticFieldError(UnrealSemanticTaskError):
    """Raised when a request attempts to smuggle authority material into semantics."""


# ---------------------------------------------------------------------------
# Authority material that the semantic layer must NEVER accept, carry, or emit.
# The semantic layer is proposal/description only; any of these appearing in an
# in-bound request is treated as a fail-closed rejection (never trusted, never
# forwarded).
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
    }
)

# Canonical top-level keys accepted in a raw semantic request.
_RAW_TASK_KEYS: FrozenSet[str] = frozenset(
    {
        "canonical_task_id",
        "task_class",
        "digital_twin_id",
        "task_name",
        "task_version",
        "intent",
        "target_state",
        "allowed_mutations",
        "dependencies",
        "evidence",
        "actions",
        "allowed_action_tools",
        "provenance",
        "metadata",
    }
)


def _require_plain_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise UnrealSemanticTaskError(
            f"{field} must be a string, got {type(value).__name__}"
        )
    stripped = value.strip()
    if not stripped:
        raise UnrealSemanticTaskError(f"{field} must not be empty")
    return stripped


def _normalize_identifier(value: Any, field: str) -> str:
    """Normalize a canonical identifier atom (case-sensitive, stripped)."""
    stripped = _require_plain_string(value, field)
    if any(ch.isspace() for ch in stripped):
        raise UnrealSemanticTaskError(
            f"{field} must be a single canonical token without whitespace: {stripped!r}"
        )
    return stripped


# ---------------------------------------------------------------------------
# Semantic task contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnrealProductionTaskDefinition:
    """Immutable, validated semantic Unreal production-task contract.

    Represents semantic intent only. It is independent of low-level Unreal
    transport detail and carries no execution/authority semantics. Compilation to
    the existing :class:`AtlasTaskDefinition` runtime is done separately by
    :func:`compile_unreal_semantic_task`.
    """

    canonical_task_id: str
    task_class: str
    digital_twin_id: str
    task_version: int
    intent: str
    target_state: UnrealTargetStateSpec
    evidence: Tuple[EvidenceRequest, ...]
    actions: Tuple[ActionSpec, ...]
    allowed_action_tools: FrozenSet[str]
    allowed_mutations: FrozenSet[str] = frozenset()
    dependencies: Tuple[str, ...] = ()
    task_name: str = ""
    provenance: Dict[str, Any] = None  # type: ignore[assignment]
    metadata: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Canonical task identity.
        object.__setattr__(self, "canonical_task_id", _normalize_identifier(
            self.canonical_task_id, "canonical_task_id"
        ))
        # Task type (constrained taxonomy; fail closed on unsupported/reserved).
        try:
            task_class = validate_task_class(self.task_class)
        except ValueError as exc:
            raise UnrealSemanticTaskError(str(exc)) from exc
        object.__setattr__(self, "task_class", task_class)
        # Canonical digital-twin identity.
        object.__setattr__(self, "digital_twin_id", _normalize_identifier(
            self.digital_twin_id, "digital_twin_id"
        ))
        # Schema/version identity.
        if not isinstance(self.task_version, int):
            raise UnrealSemanticTaskError(
                f"task_version must be an int, got {type(self.task_version).__name__}"
            )
        if self.task_version < 1:
            raise UnrealSemanticTaskError("task_version must be >= 1")
        # Requested intent.
        object.__setattr__(self, "intent", _require_plain_string(self.intent, "intent"))

        # Target state / invariants.
        if not isinstance(self.target_state, UnrealTargetStateSpec):
            raise UnrealSemanticTaskError(
                "target_state must be an UnrealTargetStateSpec"
            )
        # A render-bearing task class must declare a render-expectant target state.
        if is_render_task_class(self.task_class) and not self.target_state.expects_render:
            raise UnrealSemanticTaskError(
                f"task class {self.task_class!r} must declare expects_render=True "
                "in its target state"
            )
        # A non-render task class must NOT declare expects_render.
        if not is_render_task_class(self.task_class) and self.target_state.expects_render:
            raise UnrealSemanticTaskError(
                f"task class {self.task_class!r} must declare expects_render=False"
            )

        # Evidence / actions must be present and well-formed.
        if not self.evidence:
            raise UnrealSemanticTaskError(
                "a semantic task must define at least one evidence request"
            )
        if not self.actions:
            raise UnrealSemanticTaskError(
                "a semantic task must define at least one action"
            )
        if not self.allowed_action_tools:
            raise UnrealSemanticTaskError(
                "a semantic task must define allowed action tools"
            )
        if any(not isinstance(req, EvidenceRequest) for req in self.evidence):
            raise UnrealSemanticTaskError("evidence must contain EvidenceRequest instances")
        if any(not isinstance(act, ActionSpec) for act in self.actions):
            raise UnrealSemanticTaskError("actions must contain ActionSpec instances")
        # Constrain actions to allowed tools (mirrors AtlasTaskDefinition).
        action_tools = {action.tool for action in self.actions}
        unknown = action_tools - set(self.allowed_action_tools)
        if unknown:
            raise UnrealSemanticTaskError(
                f"actions use unauthorized tools: {sorted(unknown)}"
            )
        # Dependency graph must be well-formed.
        try:
            validate_action_dependencies(list(self.actions))
        except Exception as exc:  # pragma: no cover - re-raised with context
            raise UnrealSemanticTaskError(f"invalid action dependencies: {exc}") from exc

        # Allowed mutations (mutation scope) must be non-empty tokens.
        if not isinstance(self.allowed_mutations, frozenset) or any(
            not isinstance(m, str) or not m.strip() for m in self.allowed_mutations
        ):
            raise UnrealSemanticTaskError(
                "allowed_mutations must be a frozenset of non-empty strings"
            )
        if not isinstance(self.dependencies, tuple) or any(
            not isinstance(d, str) or not d.strip() for d in self.dependencies
        ):
            raise UnrealSemanticTaskError(
                "dependencies must be a tuple of non-empty strings"
            )
        # Provenance / metadata are opaque dicts (fail closed on non-dict).
        if self.provenance is not None and not isinstance(self.provenance, dict):
            raise UnrealSemanticTaskError("provenance must be a dict or None")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise UnrealSemanticTaskError("metadata must be a dict or None")
        # The semantic layer must NEVER carry authority material in provenance or
        # metadata (belt-and-braces; normalization already rejects it, but the
        # dataclass keeps the invariant even for direct construction).
        for owner, payload in (
            ("provenance", self.provenance or {}),
            ("metadata", self.metadata or {}),
        ):
            for key in payload:
                if key in _FORBIDDEN_AUTHORITY_KEYS or any(
                    seg in key.lower()
                    for seg in ("authorization", "receipt", "artifact", "manifest", "hmac", "nonce", "api_key")
                ):
                    raise UnauthorizedSemanticFieldError(
                        f"field {owner}.{key!r} is forbidden authority material; "
                        "the semantic layer must not carry it"
                    )

    # -- canonical / identity -------------------------------------------------

    @property
    def render_task(self) -> bool:
        return is_render_task_class(self.task_class)

    # -- serialization --------------------------------------------------------

    def to_json_compatible(self) -> Dict[str, Any]:
        """Stable, deterministic, language-neutral serialization.

        Independent of Python object identity; no authority material is emitted.
        """
        provenance = dict(self.provenance or {})
        provenance.setdefault("canonical_digital_twin_id", self.digital_twin_id)
        provenance.setdefault("semantic_task_class", self.task_class)
        provenance.setdefault("semantic_task_version", self.task_version)
        metadata = dict(self.metadata or {})
        metadata.update(target_state_metadata(self.target_state))
        return {
            "canonical_task_id": self.canonical_task_id,
            "task_class": self.task_class,
            "digital_twin_id": self.digital_twin_id,
            "task_version": self.task_version,
            "intent": self.intent,
            "task_name": self.task_name,
            "target_state": self.target_state.to_json_compatible(),
            "allowed_mutations": sorted(self.allowed_mutations),
            "dependencies": list(self.dependencies),
            "evidence": [
                {
                    "tool": request.tool,
                    "arguments": deepcopy(request.arguments),
                    "name": request.name,
                }
                for request in self.evidence
            ],
            "actions": [
                {
                    "tool": action.tool,
                    "arguments": deepcopy(action.arguments),
                    "name": action.name,
                    "requires_success": action.requires_success,
                    "depends_on": list(action.dependency_names()),
                }
                for action in self.actions
            ],
            "allowed_action_tools": sorted(self.allowed_action_tools),
            "provenance": deepcopy(provenance),
            "metadata": deepcopy(metadata),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical JSON (sorted keys, compact separators)."""
        return json.dumps(
            self.to_json_compatible(), sort_keys=True, separators=(",", ":")
        )

    def snapshot(self) -> Dict[str, Any]:
        """Public snapshot (alias of the JSON-compatible form)."""
        return self.to_json_compatible()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize_target_state(raw: Any) -> UnrealTargetStateSpec:
    if raw is None:
        raise UnrealSemanticTaskError("target_state is required")
    if not isinstance(raw, dict):
        raise UnrealSemanticTaskError("target_state must be a dict")
    description = _require_plain_string(raw.get("description", ""), "target_state.description")
    invariant_names = raw.get("invariant_names", ())
    if not isinstance(invariant_names, (list, tuple)):
        raise UnrealSemanticTaskError("target_state.invariant_names must be a list/tuple")
    expects_render = raw.get("expects_render", False)
    if not isinstance(expects_render, bool):
        raise UnrealSemanticTaskError("target_state.expects_render must be a bool")
    return target_state_spec(
        description=description,
        invariant_names=[
            _require_plain_string(n, "target_state.invariant name")
            for n in invariant_names
        ],
        expects_render=expects_render,
    )


def _normalize_evidence(raw: Any) -> Tuple[EvidenceRequest, ...]:
    if not isinstance(raw, list):
        raise UnrealSemanticTaskError("evidence must be a list")
    requests: list[EvidenceRequest] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise UnrealSemanticTaskError("each evidence entry must be a dict")
        tool = _require_plain_string(entry.get("tool", ""), "evidence.tool")
        arguments = entry.get("arguments", {})
        if not isinstance(arguments, dict):
            raise UnrealSemanticTaskError("evidence.arguments must be a dict")
        name = entry.get("name", "")
        if name is not None and not isinstance(name, str):
            raise UnrealSemanticTaskError("evidence.name must be a string")
        requests.append(
            EvidenceRequest(tool=tool, arguments=deepcopy(arguments), name=name or "")
        )
    if not requests:
        raise UnrealSemanticTaskError("evidence must not be empty")
    return tuple(requests)


def _normalize_actions(raw: Any) -> Tuple[ActionSpec, ...]:
    if not isinstance(raw, list):
        raise UnrealSemanticTaskError("actions must be a list")
    specs: list[ActionSpec] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise UnrealSemanticTaskError("each action entry must be a dict")
        tool = _require_plain_string(entry.get("tool", ""), "action.tool")
        arguments = entry.get("arguments", {})
        if not isinstance(arguments, dict):
            raise UnrealSemanticTaskError("action.arguments must be a dict")
        name = entry.get("name", "")
        requires_success = entry.get("requires_success", True)
        if not isinstance(requires_success, bool):
            raise UnrealSemanticTaskError("action.requires_success must be a bool")
        depends_on = entry.get("depends_on", ())
        if not isinstance(depends_on, (list, tuple)):
            raise UnrealSemanticTaskError("action.depends_on must be a list/tuple")
        specs.append(
            ActionSpec(
                tool=tool,
                arguments=deepcopy(arguments),
                name=name or "",
                requires_success=requires_success,
                depends_on=tuple(depends_on),
            )
        )
    if not specs:
        raise UnrealSemanticTaskError("actions must not be empty")
    return tuple(specs)


def _normalize_string_tuple(value: Any, field: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise UnrealSemanticTaskError(f"{field} must be a list/tuple")
    return tuple(
        _require_plain_string(item, field) for item in value
    )


def normalize_unreal_semantic_request(raw: Dict[str, Any]) -> UnrealProductionTaskDefinition:
    """Deterministically normalize a semantic task request into canonical form.

    Fail-closed on malformed, ambiguous, or unsupported input and on ANY attempt
    to smuggle authority material (authorization/receipt/nonce/HMAC/credential)
    into the semantic request. Never trusts model-provided authorization material.
    """
    if not isinstance(raw, dict):
        raise UnrealSemanticTaskError("semantic request must be a dict")
    # Reject authority material present at the top level BEFORE the unknown-field
    # check so a smuggled authorization/receipt key is never reported merely as
    # an unseen field (and never reaches any other path).
    for key in raw:
        if key in _FORBIDDEN_AUTHORITY_KEYS or any(
            seg in key.lower()
            for seg in ("authorization", "receipt", "artifact", "manifest", "hmac", "nonce", "api_key")
        ):
            raise UnauthorizedSemanticFieldError(
                f"field {key!r} is forbidden authority material"
            )
    unknown = set(raw) - set(_RAW_TASK_KEYS)
    if unknown:
        raise UnrealSemanticTaskError(
            f"unsupported semantic request fields: {sorted(unknown)}"
        )

    target_state = _normalize_target_state(raw.get("target_state"))
    evidence = _normalize_evidence(raw.get("evidence", []))
    actions = _normalize_actions(raw.get("actions", []))
    allowed_action_tools = frozenset(
        _require_plain_string(tool, "allowed_action_tools")
        for tool in raw.get("allowed_action_tools", ())
    )
    allowed_mutations = frozenset(
        _require_plain_string(mut, "allowed_mutations")
        for mut in raw.get("allowed_mutations", ())
    )
    dependencies = _normalize_string_tuple(raw.get("dependencies"), "dependencies")

    provenance_raw = raw.get("provenance") or {}
    metadata_raw = raw.get("metadata") or {}
    for owner, payload in (
        ("provenance", provenance_raw),
        ("metadata", metadata_raw),
    ):
        if not isinstance(payload, dict):
            raise UnrealSemanticTaskError(f"{owner} must be a dict")
        for key in payload:
            if key in _FORBIDDEN_AUTHORITY_KEYS or any(
                seg in key.lower()
                for seg in ("authorization", "receipt", "artifact", "manifest", "hmac", "nonce", "api_key")
            ):
                raise UnauthorizedSemanticFieldError(
                    f"field {owner}.{key!r} is forbidden authority material"
                )

    task_class = _require_plain_string(raw.get("task_class", ""), "task_class")
    try:
        validate_task_class(task_class)
    except ValueError as exc:
        raise UnrealSemanticTaskError(str(exc)) from exc
    return UnrealProductionTaskDefinition(
        canonical_task_id=_require_plain_string(
                raw.get("canonical_task_id", ""), "canonical_task_id"
            ),
            task_class=task_class,
        digital_twin_id=_require_plain_string(
            raw.get("digital_twin_id", ""), "digital_twin_id"
        ),
        task_version=raw.get("task_version", 1),
        intent=_require_plain_string(raw.get("intent", ""), "intent"),
        task_name=raw.get("task_name", ""),
        target_state=target_state,
        allowed_mutations=allowed_mutations,
        dependencies=dependencies,
        evidence=evidence,
        actions=actions,
        allowed_action_tools=allowed_action_tools,
        provenance=deepcopy(provenance_raw),
        metadata=deepcopy(metadata_raw),
    )


# ---------------------------------------------------------------------------
# Compile boundary
# ---------------------------------------------------------------------------


def _build_default_evaluator(task: UnrealProductionTaskDefinition) -> TargetStateEvaluator:
    """Build a deterministic, structural target-state evaluator for M12.1.

    This is a *placeholder* evaluator, not an independent verifier: it treats the
    evidence mapping as satisfied only when every declared invariant name is
    present-and-Truthy in the supplied evidence dict. Real independent verification
    (which must not trust self-reported evidence) is deliberately deferred to M12.5
    and wired through the existing evidence machinery. This keeps compilation
    structurally complete without fabricating a verification authority here.
    """
    invariants = [
        StateInvariant(
            name=name,
            predicate=lambda evidence, _n=name: bool(
                isinstance(evidence, dict) and evidence.get(_n)
            ),
        )
        for name in task.target_state.to_invariant_names()
    ]
    if not invariants:
        # No declared invariants: nothing observable to verify -> fail closed.
        invariants = [
            StateInvariant(
                name="__no_invariants__",
                predicate=lambda evidence: False,
            )
        ]
    return TargetStateEvaluator(invariants)


def compile_unreal_semantic_task(
    task: UnrealProductionTaskDefinition,
    *,
    evaluator: Optional[TargetStateEvaluator] = None,
) -> AtlasTaskDefinition:
    """Compile a validated semantic task onto the existing Atlas task runtime.

    This is a NARROW boundary: it produces an existing
    :class:`AtlasTaskDefinition` and carries the Unreal semantic provenance
    through ``metadata``. It does NOT create a second runtime, does not authorize
    execution, and does not mint receipts/artifact manifests. Render-bearing tasks
    are rejected here because their safe mapping requires the existing
    render-submission machinery, which is out of scope for the semantic compile
    boundary (deferred until the contract is proven independently).
    """
    if not isinstance(task, UnrealProductionTaskDefinition):
        raise TypeError("task must be an UnrealProductionTaskDefinition")
    if task.render_task:
        raise UnsupportedCompileMappingError(
            f"cannot compile render-bearing task class {task.task_class!r} through "
            "the semantic boundary without the existing render-submission machinery; "
            "runtime mapping is deferred"
        )

    atlas_metadata: Dict[str, Any] = dict(task.metadata or {})
    atlas_metadata.update(
        {
            "unreal_semantic_task_id": task.canonical_task_id,
            "unreal_semantic_task_class": task.task_class,
            "unreal_digital_twin_id": task.digital_twin_id,
            "unreal_semantic_task_version": task.task_version,
            "unreal_semantic_intent": task.intent,
        }
    )
    atlas_metadata.update(target_state_metadata(task.target_state))
    if task.dependencies:
        atlas_metadata["unreal_semantic_dependencies"] = list(task.dependencies)
    atlas_metadata["unreal_provenance"] = deepcopy(task.provenance or {})

    used_evaluator = evaluator if evaluator is not None else _build_default_evaluator(task)

    return AtlasTaskDefinition(
        name=task.task_name or f"{task.task_class}:{task.canonical_task_id}",
        evidence=task.evidence,
        actions=task.actions,
        evaluator=used_evaluator,
        allowed_action_tools=set(task.allowed_action_tools),
        allow_writes=bool(task.allowed_mutations),
        verify_after_action=True,
        metadata=atlas_metadata,
    )


__all__ = [
    "UnrealProductionTaskDefinition",
    "UnrealSemanticTaskError",
    "UnsupportedCompileMappingError",
    "UnauthorizedSemanticFieldError",
    "normalize_unreal_semantic_request",
    "compile_unreal_semantic_task",
    "UNREAL_TASK_CLASS_INTENT",
    "UNREAL_RENDER_TASK_CLASSES",
]