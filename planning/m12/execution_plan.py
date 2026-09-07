"""M12.3 deterministic semantic execution-plan boundary.

M12.3 is a PLAN, not an executor. It converts an M12.1 semantic task contract and
its M12.2 composed fragment ordering into an immutable, language-neutral
execution plan: ordered steps, semantic preconditions, dependency relationships,
target-state contributions, verification requirements, idempotence, and
provenance.

It does NOT schedule, authorize, execute, verify, or mint anything. Preconditions
and verification requirements are descriptive declarations a future verifier/
executor may consume; creating a plan marks NOTHING verified and grants NO
authority. Future M12.4 will consume this plan and map approved semantic
operations onto the existing trusted Atlas runtime — that adapter is NOT
implemented here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from planning.m12.fragments import UnrealProductionFragment
from planning.m12.fragments_registry import canonical_fragment
from planning.m12.semantic_task import UnrealProductionTaskDefinition

Idempotence = str  # "idempotent" | "non-idempotent" | "unknown"


class UnrealExecutionPlanError(ValueError):
    """Raised when execution-plan construction cannot be deterministic/safe."""


def _check_token(value, field_and: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise UnrealExecutionPlanError(f"{field_and} must be a non-empty string")


def _check_tokens(values, field: str) -> None:
    if not isinstance(values, tuple):
        raise UnrealExecutionPlanError(f"{field} must be a tuple")
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise UnrealExecutionPlanError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise UnrealExecutionPlanError(f"{field} must not contain duplicates")


@dataclass(frozen=True)
class UnrealExecutionPlanStep:
    """One immutable step in a semantic execution plan.

    A step is a semantic operation description, not an Atlas authorization and
    not an Unreal transport payload.
    """

    step_id: str
    semantic_operation: str
    required_inputs: Tuple[str, ...] = ()
    preconditions: Tuple[str, ...] = ()
    target_state_contributions: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()
    idempotence: Idempotence = "unknown"
    verification_requirements: Tuple[str, ...] = ()
    execution_capability_requirement: str = "inspect-only"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _check_token(self.step_id, "step_id")
        _check_token(self.semantic_operation, "semantic_operation")
        _check_tokens(self.required_inputs, "required_inputs")
        _check_tokens(self.preconditions, "preconditions")
        _check_tokens(self.target_state_contributions, "target_state_contributions")
        _check_tokens(self.dependencies, "dependencies")
        if self.idempotence not in ("idempotent", "non-idempotent", "unknown"):
            raise UnrealExecutionPlanError(
                f"step idempotence must be idempotent/non-idempotent/unknown, got "
                f"{self.idempotence!r}"
            )
        _check_tokens(self.verification_requirements, "verification_requirements")
        if (
            not isinstance(self.execution_capability_requirement, str)
            or not self.execution_capability_requirement.strip()
        ):
            raise UnrealExecutionPlanError(
                "execution_capability_requirement must be a non-empty string"
            )
        if not isinstance(self.provenance, dict):
            raise UnrealExecutionPlanError("step provenance must be a dict")

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "semantic_operation": self.semantic_operation,
            "required_inputs": list(self.required_inputs),
            "preconditions": list(self.preconditions),
            "target_state_contributions": list(self.target_state_contributions),
            "dependencies": list(self.dependencies),
            "idempotence": self.idempotence,
            "verification_requirements": list(self.verification_requirements),
            "execution_capability_requirement": self.execution_capability_requirement,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class UnrealExecutionPlan:
    """Immutable, language-neutral semantic execution plan.

    Describes canonical plan id, source semantic task, catalog version,
    digital-twin identity, ordered steps, render-bearing classification, and
    provenance. It is a plan only: no execution, authorization, verification,
    receipt, or recovery authority.
    """

    plan_id: str
    source_task_id: str
    source_task_version: int
    catalog_version: int
    digital_twin_id: str
    steps: Tuple[UnrealExecutionPlanStep, ...]
    provenance: Dict[str, Any] = field(default_factory=dict)
    render_plan: bool = False

    def __post_init__(self) -> None:
        _check_token(self.plan_id, "plan_id")
        _check_token(self.source_task_id, "source_task_id")
        if not isinstance(self.source_task_version, int) or self.source_task_version < 1:
            raise UnrealExecutionPlanError("source_task_version must be a positive int")
        if not isinstance(self.catalog_version, int) or self.catalog_version < 1:
            raise UnrealExecutionPlanError("catalog_version must be a positive int")
        _check_token(self.digital_twin_id, "digital_twin_id")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise UnrealExecutionPlanError("execution plan must have at least one step")
        if any(not isinstance(s, UnrealExecutionPlanStep) for s in self.steps):
            raise UnrealExecutionPlanError("all plan steps must be UnrealExecutionPlanStep")
        _check_tokens(self.ordered_step_ids(), "step_ids")
        if not isinstance(self.provenance, dict):
            raise UnrealExecutionPlanError("plan provenance must be a dict")
        if not isinstance(self.render_plan, bool):
            raise UnrealExecutionPlanError("render_plan must be a bool")

    @property
    def can_execute(self) -> bool:
        """A semantic execution plan is a plan, not an executor. Always False."""
        return False

    def has_render_step(self) -> bool:
        """True iff this is a plan for an authoritatively render-bearing task.

        Mirrors the authoritative render-bearing classification carried onto the
        plan at generation time (the source task's ``render_task`` flag), so it
        is True for every render-bearing semantic class (render-execute,
        artifact-validate). A render plan DESCRIBES render intent; it does NOT
        authorize or execute a render.
        """
        return self.render_plan

    def ordered_step_ids(self) -> Tuple[str, ...]:
        return tuple(s.step_id for s in self.steps)

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_task_id": self.source_task_id,
            "source_task_version": self.source_task_version,
            "catalog_version": self.catalog_version,
            "digital_twin_id": self.digital_twin_id,
            "render_plan": self.render_plan,
            "steps": [s.to_json_compatible() for s in self.steps],
            "provenance": dict(self.provenance),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical serialization (sorted keys, compact)."""
        return json.dumps(
            self.to_json_compatible(), sort_keys=True, separators=(",", ":")
        )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _deterministic_step_id(source_task_id: str, operation: str, index: int) -> str:
    return f"{source_task_id}:{operation}:{index:03d}"


def _lookup_fragment(fragment_id: str) -> Optional[UnrealProductionFragment]:
    try:
        return canonical_fragment(fragment_id)
    except KeyError:
        return None


def _fragment_idempotence(fragment_id: str) -> Idempotence:
    frag = _lookup_fragment(fragment_id)
    if frag is None:
        return "unknown"
    return "idempotent" if frag.idempotent else "non-idempotent"


def _build_plan_id(
    source_task_id: str,
    source_task_version: int,
    fragment_ids: Tuple[str, ...],
) -> str:
    deps = "|".join(fragment_ids)
    return f"plan:{source_task_id}:{source_task_version}:{deps}"


def generate_execution_plan(
    task: UnrealProductionTaskDefinition,
    *,
    catalog_version: int = 1,
) -> UnrealExecutionPlan:
    """Deterministically generate an execution plan for a resolved semantic task.

    Uses the task's ordered fragment dependencies (``task.dependencies``) and the
    resolved target state. Identical semantic input yields canonical-equivalent
    output. No authorization, side effect, or execution occurs.

    The plan's render-bearing classification (``render_plan``) is carried from the
    task's authoritative ``render_task`` flag, so every render-bearing semantic
    class (render-execute, artifact-validate) yields a plan with
    ``render_plan=True``.
    """
    if not isinstance(task, UnrealProductionTaskDefinition):
        raise TypeError("task must be an UnrealProductionTaskDefinition")

    fragment_ids = tuple(task.dependencies)
    if not fragment_ids:
        raise UnrealExecutionPlanError(
            "cannot generate execution plan: semantic task has no fragment dependencies"
        )

    steps: List[UnrealExecutionPlanStep] = []
    # Map a produced requirement NAME -> deterministic step id, so a later
    # fragment's `requires` can be resolved to explicit step dependencies.
    producer_to_step: Dict[str, str] = {}

    for index, fragment_id in enumerate(fragment_ids):
        fragment = _lookup_fragment(fragment_id)
        step_id = _deterministic_step_id(task.canonical_task_id, fragment_id, index)

        if fragment is not None:
            preconditions = tuple(sorted(fragment.requires))
            contributions = tuple(fragment.contributed_invariant_names())
            inputs = tuple(fragment.inputs)
            # Map each required requirement name to the step that produces it
            # (only among previously ordered fragments; unknown -> empty deps,
            # i.e. precondition unmet -> fail-closed by the consumer).
            deps = tuple(
                producer_to_step.get(req)
                for req in fragment.requires
                if req in producer_to_step
            )
        else:
            # Unknown fragment: represent conservatively (fail-closed idempotence).
            preconditions = ()
            contributions = ()
            inputs = ()
            deps = ()

        steps.append(
            UnrealExecutionPlanStep(
                step_id=step_id,
                semantic_operation=fragment_id,
                required_inputs=inputs,
                preconditions=preconditions,
                target_state_contributions=contributions,
                dependencies=tuple(sorted(set(d for d in deps if d is not None))),
                idempotence=_fragment_idempotence(fragment_id),
                verification_requirements=contributions,
                execution_capability_requirement="inspect-only",
                provenance={
                    "fragment_id": fragment_id,
                    "fragment_version": fragment.version if fragment is not None else "unknown",
                    "target_state_contribution": list(contributions),
                },
            )
        )
        if fragment is not None:
            # This step produces these requirement names for downstream steps.
            for produced in fragment.produces:
                producer_to_step[produced] = step_id

    plan_provenance = dict(task.provenance or {})
    plan_provenance.setdefault("source_task_version", task.task_version)
    return UnrealExecutionPlan(
        plan_id=_build_plan_id(
            task.canonical_task_id, task.task_version, fragment_ids
        ),
        source_task_id=task.canonical_task_id,
        source_task_version=task.task_version,
        catalog_version=catalog_version,
        digital_twin_id=task.digital_twin_id,
        steps=tuple(steps),
        provenance=plan_provenance,
        render_plan=task.render_task,
    )


__all__ = [
    "Idempotence",
    "UnrealExecutionPlanError",
    "UnrealExecutionPlanStep",
    "UnrealExecutionPlan",
    "generate_execution_plan",
]