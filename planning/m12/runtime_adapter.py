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
- Render-bearing plans are recognized and produce a STRUCTURED mapping that
  declares "requires existing render authorization/submission path" with
  ``requires_existing_render_submission_path=True`` and NO runtime task. M12.4
  does not fabricate render authorization and does not submit MRQ.
- Unsupported steps / unknown idempotence / unsupported capability requirements
  fail closed (raise ``UnrealRuntimeAdapterError``).
- The mapping is deterministic: identical plan + identical source task produce
  identical canonical JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from planning.m12.execution_plan import UnrealExecutionPlan
from planning.m12.semantic_task import (
    UnrealProductionTaskDefinition,
    compile_unreal_semantic_task,
)
from planning.task_definition import AtlasTaskDefinition

# Sentinel reason recorded on every step of a render-bearing plan to make the
# boundary explicit and audit-able while carrying no authorization material.
REQUIRES_EXISTING_RENDER_SUBMISSION_PATH = "requires-existing-render-submission-path"

# The single existing runtime tool that M12 non-render semantic steps realize on.
# M12.1's compiler emits exactly one inspect action per composed task; the
# adapter records that tool as the target instead of inventing a new one.
EXISTING_RUNTIME_INSPECT_TOOL = "unreal_inspect"


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
    runtime operation that already ingests it (the M12.1 inspect tool for
    non-render semantic steps). Unsupported steps are recorded with
    ``supported=False`` and a non-empty ``unsupported_reason`` (fail closed).
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
    unsupported_reason: Optional[str] = None

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
        if self.unsupported_reason is not None and not isinstance(
            self.unsupported_reason, str
        ):
            raise UnrealRuntimeAdapterError("unsupported_reason must be a str or None")

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
            "unsupported_reason": self.unsupported_reason,
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
        if not isinstance(self.provenance, dict):
            raise UnrealRuntimeAdapterError("provenance must be a dict")

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
            "runtime_task_present": self.runtime_task is not None,
            "steps": [s.to_json_compatible() for s in self.steps],
            "provenance": dict(self.provenance),
        }

    def canonical_json(self) -> str:
        """Deterministic canonical serialization (sorted keys, compact)."""
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
        compiler (M12.4 does not construct a new runtime). For a render-bearing
        plan it yields ``runtime_task=None`` and
        ``requires_existing_render_submission_path=True`` without manufacturing
        authorization or a runtime task.

    Raises:
        TypeError: if ``plan`` or ``source_task`` has the wrong type.
        UnrealRuntimeAdapterError: if the plan's identity does not match the
            source task, a supported step declares unknown idempotence, an
            unsupported capability is requested, or the mapping is ambiguous.
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

    used_catalog_version = catalog_version if catalog_version is not None else plan.catalog_version

    # Every semantic step must have a demonstrated existing runtime equivalent.
    # For non-render tasks, M12.1 compiled the task into an AtlasTaskDefinition
    # whose single real action is "unreal_inspect"; we record that as the target
    # runtime operation. Render-bearing plans cannot be represented this way and
    # are kept as an explicit requires-existing-render-submission-path boundary.
    require_render_boundary = plan.render_plan

    mapped_steps: Tuple[UnrealRuntimeStepMapping, ...] = ()
    if not require_render_boundary:
        rendered_steps = []
        for step in plan.steps:
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
            rendered_steps.append(
                UnrealRuntimeStepMapping(
                    step_id=step.step_id,
                    semantic_operation=step.semantic_operation,
                    supported=True,
                    target_runtime_operation=EXISTING_RUNTIME_INSPECT_TOOL,
                    required_inputs=step.required_inputs,
                    dependencies=step.dependencies,
                    target_state_contributions=step.target_state_contributions,
                    idempotence=step.idempotence,
                    capability_requirement=step.execution_capability_requirement,
                    unsupported_reason=None,
                )
            )
        mapped_steps = tuple(rendered_steps)
    else:
        # Render-bearing plan: never translate into a runtime task, never
        # fabricate a render submission. Record the boundary on each step.
        mapped_steps = tuple(
            UnrealRuntimeStepMapping(
                step_id=step.step_id,
                semantic_operation=step.semantic_operation,
                supported=False,
                target_runtime_operation="<none>",
                required_inputs=step.required_inputs,
                dependencies=step.dependencies,
                target_state_contributions=step.target_state_contributions,
                idempotence=step.idempotence,
                capability_requirement=step.execution_capability_requirement,
                unsupported_reason=REQUIRES_EXISTING_RENDER_SUBMISSION_PATH,
            )
            for step in plan.steps
        )

    # Build the existing runtime representation ONLY for non-render plans, by
    # reusing the existing M12.1 compiler (it already rejects render-bearing
    # plans). For render plans we do not reach it at all.
    runtime_task: Optional[AtlasTaskDefinition] = None
    if not require_render_boundary:
        runtime_task = compile_unreal_semantic_task(source_task)

    provenance = dict(plan.provenance or {})
    provenance.setdefault("mapped_runtime_task_type", "AtlasTaskDefinition" if not require_render_boundary else "unavailable")
    provenance.setdefault("recognized_render_plan", require_render_boundary)

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
        provenance=provenance,
    )


__all__ = [
    "UnrealRuntimeAdapterError",
    "UnrealRuntimeStepMapping",
    "UnrealRuntimeMapping",
    "map_unreal_execution_plan",
    "REQUIRES_EXISTING_RENDER_SUBMISSION_PATH",
    "EXISTING_RUNTIME_INSPECT_TOOL",
]