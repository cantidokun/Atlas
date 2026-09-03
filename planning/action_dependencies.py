"""Validation for declarative Atlas action dependencies."""

from typing import Dict, List, Set

from planning.action_plan import ActionSpec


class ActionDependencyError(ValueError):
    """Raised when an action dependency graph is unsafe or inconsistent."""


def validate_action_dependencies(actions: List[ActionSpec]) -> None:
    """Validate a serial, dependency-aware action sequence.

    The action list remains the execution and authorization order. Dependencies
    may constrain that order but never reorder it or introduce parallelism.
    """
    if not isinstance(actions, list):
        raise TypeError("actions must be a list of ActionSpec objects")
    if any(not isinstance(action, ActionSpec) for action in actions):
        raise TypeError("actions must contain only ActionSpec objects")

    names: Dict[str, int] = {}
    for index, action in enumerate(actions):
        name = (action.name or action.tool).strip()
        if not name:
            raise ActionDependencyError("every action must have a non-empty name or tool")
        if name in names:
            raise ActionDependencyError(f"duplicate action name: {name}")
        names[name] = index

    for index, action in enumerate(actions):
        dependencies = action.dependency_names()
        if len(dependencies) != len(set(dependencies)):
            raise ActionDependencyError(f"action {index} declares duplicate dependencies")
        for dependency in dependencies:
            if not dependency:
                raise ActionDependencyError(f"action {index} declares an empty dependency")
            if dependency == (action.name or action.tool).strip():
                raise ActionDependencyError(f"action {index} cannot depend on itself")
            dependency_index = names.get(dependency)
            if dependency_index is None:
                raise ActionDependencyError(f"action {index} depends on unknown action: {dependency}")
            if dependency_index >= index:
                raise ActionDependencyError(
                    f"action {index} depends on a later action: {dependency}"
                )

    # The positional rule above establishes an acyclic topological order. Keep
    # an explicit traversal here so future extensions cannot accidentally
    # weaken cycle detection by changing the validation strategy.
    graph: Dict[str, Set[str]] = {
        (action.name or action.tool).strip(): set(action.dependency_names())
        for action in actions
    }
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ActionDependencyError(f"cyclic action dependency: {name}")
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)
