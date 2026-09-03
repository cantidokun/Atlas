"""Validation for declarative Atlas action dependencies."""

from typing import Dict, List, Set

from planning.action_plan import ActionSpec


class ActionDependencyError(ValueError):
    """Raised when an action dependency graph is unsafe or inconsistent."""


def validate_action_dependencies(actions: List[ActionSpec]) -> None:
    """Validate a serial, dependency-aware action sequence.

    The action list remains the execution and authorization order. Dependencies
    may constrain that order but never reorder it or introduce parallelism.

    Dependency-free legacy action lists are accepted unchanged. Once a task
    declares dependencies, action names must be unique so dependency references
    are deterministic.
    """
    if not isinstance(actions, list):
        raise TypeError("actions must be a list of ActionSpec objects")
    if any(not isinstance(action, ActionSpec) for action in actions):
        raise TypeError("actions must contain only ActionSpec objects")

    has_dependencies = any(action.dependency_names() for action in actions)
    names: Dict[str, int] = {}
    duplicates: Set[str] = set()
    for index, action in enumerate(actions):
        name = (action.name or action.tool).strip()
        if not name:
            raise ActionDependencyError("every action must have a non-empty name or tool")
        if name in names:
            duplicates.add(name)
        else:
            names[name] = index

    if has_dependencies and duplicates:
        raise ActionDependencyError(
            f"dependency-bearing action plan has ambiguous names: {sorted(duplicates)}"
        )

    if not has_dependencies:
        return

    for index, action in enumerate(actions):
        dependencies = action.dependency_names()
        if len(dependencies) != len(set(dependencies)):
            raise ActionDependencyError(f"action {index} declares duplicate dependencies")
        action_name = (action.name or action.tool).strip()
        for dependency in dependencies:
            if not dependency:
                raise ActionDependencyError(f"action {index} declares an empty dependency")
            if dependency == action_name:
                raise ActionDependencyError(f"action {index} cannot depend on itself")
            dependency_index = names.get(dependency)
            if dependency_index is None:
                raise ActionDependencyError(f"action {index} depends on unknown action: {dependency}")
            if dependency_index >= index:
                raise ActionDependencyError(
                    f"action {index} depends on a later action: {dependency}"
                )

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
