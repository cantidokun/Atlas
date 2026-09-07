"""M12.2 reusable Unreal semantic production fragments.

A fragment is a reusable *semantic production capability* — NOT a low-level
Unreal command. Fragments express what a piece of the soccer production needs to
establish (its produced semantic requirements, target-state contributions,
dependencies, and idempotence expectation) without granting any execution,
authorization, scheduling, or recovery authority.

Fragment types are deliberately concrete and soccer-production-scoped:
scene_setup, environment_setup, camera_setup, lighting_setup, sequence_setup,
render_setup. Render execution mapping stays constrained (M12.1 rejects
render-bearing compile); fragments only express semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class UnrealProductionFragment:
    """An immutable, reusable semantic production fragment.

    Fields:
        canonical_id: stable, canonical fragment identifier (no whitespace).
        version: positive int fragment schema version.
        label: human-readable semantic description (intent only).
        inputs: canonical names of the semantic inputs this fragment consumes.
        produces: canonical names of the semantic requirements this fragment
            establishes (post-condition capabilities).
        requires: canonical names of semantic requirements that MUST already be
            established (dependencies) for this fragment to be valid. This is a
            *planning* dependency, not a scheduling authority.
        contributes_invariants: target-state invariant names this fragment adds
            to the composed task target state.
        idempotent: whether re-applying the fragment when its target state is
            already reached is a no-op (composition may deduplicate it).
        expandable: whether the fragment can be expanded to M12.1 actions.
        detail: opaque, validated configuration details (engine-neutral).
    """

    canonical_id: str
    version: int
    label: str
    inputs: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()
    requires: Tuple[str, ...] = ()
    contributes_invariants: Tuple[str, ...] = ()
    idempotent: bool = True
    expandable: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_id, str) or not self.canonical_id.strip():
            raise ValueError("fragment canonical_id must be a non-empty string")
        if any(ch.isspace() for ch in self.canonical_id):
            raise ValueError(
                f"fragment canonical_id must be a single token without whitespace: "
                f"{self.canonical_id!r}"
            )
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ValueError("fragment version must be a positive integer")
        _check_tokens(self.inputs, "inputs")
        _check_tokens(self.produces, "produces")
        _check_tokens(self.requires, "requires")
        _check_tokens(self.contributes_invariants, "contributes_invariants")
        # A fragment that contributes no target-state invariant and produces no
        # requirement is semantically empty; fail closed.
        if not self.produces and not self.contributes_invariants:
            raise ValueError(
                f"fragment {self.canonical_id!r} must produce a requirement or "
                "contribute at least one target-state invariant"
            )
        if not isinstance(self.idempotent, bool):
            raise ValueError("fragment idempotent must be a bool")
        if not isinstance(self.expandable, bool):
            raise ValueError("fragment expandable must be a bool")
        if not isinstance(self.detail, dict):
            raise ValueError("fragment detail must be a dict")

    def dependency_names(self) -> Tuple[str, ...]:
        """Canonical sorted tuple of dependency requirement names."""
        return tuple(sorted(set(self.requires)))

    def contributed_invariant_names(self) -> Tuple[str, ...]:
        return tuple(sorted(set(self.contributes_invariants)))

    def to_json_compatible(self) -> Dict[str, Any]:
        """Stable, language-neutral serialization (C++/wire friendly)."""
        return {
            "canonical_id": self.canonical_id,
            "version": self.version,
            "label": self.label,
            "inputs": list(self.inputs),
            "produces": list(self.produces),
            "requires": list(self.requires),
            "contributes_invariants": list(self.contributed_invariant_names()),
            "idempotent": self.idempotent,
            "expandable": self.expandable,
            "detail": dict(self.detail),
        }


def _check_tokens(values: Tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"fragment {field_name} must be a tuple")
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"fragment {field_name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"fragment {field_name} must not contain duplicates")