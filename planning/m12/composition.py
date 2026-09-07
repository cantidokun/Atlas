"""M12.2 deterministic fragment composition into an ordered semantic plan.

Composition is a pure planning/constitution concern. It does NOT schedule,
authorize, or execute anything. It orders fragments deterministically, detects
conflicts/cycles/missing dependencies, and merges target-state contributions —
while preserving the requested semantic meaning without hidden mutation.

Result :class:`UnrealComposedTaskPlan` is a normalized, ordered semantic task plan
that (for non-render classes) compiles through the existing M12.1 compiler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from planning.m12.fragments import UnrealProductionFragment
from planning.m12.target_state import UnrealTargetStateSpec, target_state_spec


class FragmentCompositionError(ValueError):
    """Raised when fragment composition cannot produce a deterministic plan."""


def compose_fragments(
    fragments: Sequence[UnrealProductionFragment],
    *,
    requested_invariants: Iterable[str] = (),
    description: str = "Composed Unreal semantic production task.",
) -> "UnrealComposedTaskPlan":
    """Deterministically order and compose fragments into a semantic plan.

    Raises:
        FragmentCompositionError: on missing dependency, cycle, duplicate
            incompatible fragment, or conflicting target-state invariant.
    """
    if not isinstance(fragments, (list, tuple)) or not fragments:
        raise FragmentCompositionError("at least one fragment is required")
    frags: List[UnrealProductionFragment] = list(fragments)
    if any(not isinstance(f, UnrealProductionFragment) for f in frags):
        raise FragmentCompositionError("all fragments must be UnrealProductionFragment instances")
    if len({f.canonical_id for f in frags}) != len(frags):
        raise FragmentCompositionError("duplicate fragment canonical_id is not permitted")

    # Topological order (Kahn). A requirement is a semantic dependency.
    order: List[UnrealProductionFragment] = []
    remaining = list(frags)
    available_produces: set = set()
    while remaining:
        progressed = False
        for fragment in remaining:
            deps = set(fragment.requires)
            if deps.issubset(available_produces):
                order.append(fragment)
                available_produces.update(fragment.produces)
                remaining.remove(fragment)
                progressed = True
                break
        if not progressed:
            unresolved = [f.canonical_id for f in remaining]
            raise FragmentCompositionError(
                f"fragment dependency cycle or missing dependency among: "
                f"{sorted(unresolved)}"
            )

    # Merge target-state invariants, detecting conflicts.
    all_invariants: List[str] = list(requested_invariants or [])
    for fragment in order:
        for inv in fragment.contributed_invariant_names():
            if inv in all_invariants:
                # Idempotent re-contribution is fine; non-idempotent is a conflict.
                if not fragment.idempotent:
                    raise FragmentCompositionError(
                        f"non-idempotent fragment {fragment.canonical_id!r} "
                        f"re-contributes target-state invariant {inv!r}"
                    )
                continue
            all_invariants.append(inv)

    fragment_ids = tuple(f.canonical_id for f in order)
    return UnrealComposedTaskPlan(
        fragments=tuple(order),
        fragment_ids=fragment_ids,
        target_state=target_state_spec(
            description=description,
            invariant_names=all_invariants,
        ),
    )


@dataclass(frozen=True)
class UnrealComposedTaskPlan:
    """Ordered, validated composition of fragments into a semantic plan.

    Holds the ordered fragments, the canonical fragment id sequence, and the
    merged target-state spec. It is a planning artifact only.
    """

    fragments: Tuple[UnrealProductionFragment, ...]
    fragment_ids: Tuple[str, ...]
    target_state: UnrealTargetStateSpec

    def __post_init__(self) -> None:
        if not isinstance(self.fragments, tuple) or not self.fragments:
            raise FragmentCompositionError("composed plan must hold at least one fragment")
        if not isinstance(self.fragment_ids, tuple):
            raise FragmentCompositionError("fragment_ids must be a tuple")
        if not isinstance(self.target_state, UnrealTargetStateSpec):
            raise FragmentCompositionError("target_state must be an UnrealTargetStateSpec")

    @property
    def ordered_fragment_ids(self) -> Tuple[str, ...]:
        """Canonical ordered fragment ids (the composition order)."""
        return self.fragment_ids

    def to_json_compatible(self) -> Dict[str, Any]:
        """Stable, language-neutral serialization."""
        return {
            "fragments": [f.to_json_compatible() for f in self.fragments],
            "fragment_ids": list(self.fragment_ids),
            "target_state": self.target_state.to_json_compatible(),
        }