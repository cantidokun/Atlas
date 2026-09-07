"""M12 Unreal target-state representation (foundation only).

``UnrealTargetStateSpec`` is a *data-only*, language-neutral descriptor of the
requested target state for a semantic Unreal task. It is deliberately NOT a
second evidence system: it does not record evidence, verify evidence, or issue
verification claims. It only *expresses* the invariants that an independent
verifier (future, M12.5) is expected to check.

M12.1 does not implement independent verification. The spec supports composing
with the existing :class:`planning.target_state.TargetStateEvaluator` at a later
milestone without changing the semantic contract (see ``to_invariant_names`` and
the fail-closed evaluator factory in :mod:`planning.m12.semantic_task`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Tuple


@dataclass(frozen=True)
class UnrealTargetStateSpec:
    """Immutable descriptor of the requested target state for a semantic task.

    Fields:
        description: human-readable statement of the expected result (intent only).
        invariant_names: canonical names of the state invariants that must all
            hold for the target to be considered reached. These are *labels* for a
            future independent verifier; they carry no verification authority.
        expects_render: whether completing this target state necessarily involves
            an Atlas render-job submission (render-bearing task).
    """

    description: str
    invariant_names: FrozenSet[str] = frozenset()
    expects_render: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("target-state description must be a non-empty string")
        if not isinstance(self.invariant_names, frozenset):
            raise ValueError("invariant_names must be a frozenset of strings")
        if any(not isinstance(n, str) or not n.strip() for n in self.invariant_names):
            raise ValueError("invariant names must be non-empty strings")
        if not isinstance(self.expects_render, bool):
            raise ValueError("expects_render must be a bool")

    def to_invariant_names(self) -> Tuple[str, ...]:
        """Return the canonical invariant name tuple (stable, sorted)."""
        return tuple(sorted(self.invariant_names))

    def to_json_compatible(self) -> Dict[str, Any]:
        """Stable, language-neutral serialization for C++/wire interoperability.

        Deterministic and independent of Python object identity.
        """
        return {
            "description": self.description,
            "invariant_names": list(self.to_invariant_names()),
            "expects_render": self.expects_render,
        }


def target_state_spec(
    *,
    description: str,
    invariant_names=(),
    expects_render: bool = False,
) -> UnrealTargetStateSpec:
    """Convenience constructor that normalizes an iterable into a frozenset.

    Raises:
        ValueError: on anything the frozen dataclass rejects.
    """
    return UnrealTargetStateSpec(
        description=description,
        invariant_names=frozenset(invariant_names),
        expects_render=expects_render,
    )


_UNREAL_TARGET_STATE_META_KEY = "unreal_target_state"


def target_state_metadata(spec: UnrealTargetStateSpec) -> Dict[str, Any]:
    """Emit the target-state spec as deterministic metadata for a compiled task.

    This is a *carrier* for forward provenance; it grants no execution/verification
    authority. It lets a future independent verifier (M12.5) read the expected
    invariants from the compiled Atlas task without re-deriving them from a live
    model.
    """
    return {_UNREAL_TARGET_STATE_META_KEY: spec.to_json_compatible()}