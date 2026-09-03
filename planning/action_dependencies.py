"""Validation for declarative Atlas action dependencies."""

from typing import Dict, Iterable, List, Set

from planning.action_plan import ActionSpec


class ActionDependencyError(ValueError):
    """Raised when an action dependency graph is unsafe or inconsistent."""


def validate_action_dependencies(
    actions: List[ActionSpec],
    *,
    satisfied_dependencies: Iterable[str] = (),
) -> None:
    """Validate a serial, dependency-aware action sequence.

    ``satisfied_dependencies`` represents prerequisites proven complete by a
    prior authorized continuation. Those inherited prerequisites are never
    executed again; they only satisfy references from replacement actions.
    """
    if not isinstance(actions, list):
        raise TypeError("actions must be a list of ActionSpec objects")
    if any(not isinstance(action, ActionSpec) for action in actions):
        raise TypeError("actions must contain only ActionSpec objects")
    inherited = {str(name).strip() for name in satisfied_dependencies}
    if any(not name for name in inherited):
        raise ActionDependencyError("satisfied dependency names must not be empty")

    has_dependencies = any(action.dependency_names() for action in actions)
    names: Dict[str, int] = {}
    name_to_action: Dict[str, ActionSpec] = {}
    duplicates: Set[str] = set()
    for index, action in enumerate(actions):
        name = (action.name or action.tool).strip()
        if not name:
            raise ActionDependencyError("every action must have a non-empty name or tool")
        if name in names:
            duplicates.add(name)
        else:
            names[name] = index
            name_to_action[name] = action

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
            if dependency in inherited:
                continue
            dependency_index = names.get(dependency)
            if dependency_index is None:
                raise ActionDependencyError(
                    f"action {index} depends on unknown action: {dependency}"
                )
            if dependency_index >= index:
                raise ActionDependencyError(
                    f"action {index} depends on a later action: {dependency}"
                )
            if not name_to_action[dependency].requires_success:
                raise ActionDependencyError(
                    f"action {index} depends on action that does not require success: {dependency}"
                )

    graph: Dict[str, Set[str]] = {
        (action.name or action.tool).strip(): {
            dependency for dependency in action.dependency_names() if dependency not in inherited
        }
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
