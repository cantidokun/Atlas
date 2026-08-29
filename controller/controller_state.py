"""State-aware controller primitives for authorized Blender modifications."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

TARGET_MIDPOINT = [0.0, 0.0, 0.0]
_LOCATION_PRECISION = 10


def _is_vec3(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _subtract(a: List[float], b: List[float]) -> List[float]:
    return [round(a[index] - b[index], _LOCATION_PRECISION) for index in range(3)]


def _location_key(value: Any) -> tuple:
    if not _is_vec3(value):
        raise ValueError("Location must be a 3-value numeric vector.")
    return tuple(round(float(item), _LOCATION_PRECISION) for item in value)


def _same_location(a: Any, b: Any) -> bool:
    return _is_vec3(a) and _is_vec3(b) and _location_key(a) == _location_key(b)


@dataclass
class ControllerState:
    """Deterministic state for the current authorized midpoint task."""
    file_name: str
    object_a_name: str
    object_b_name: str
    before: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None
    writes: List[Dict[str, Any]] = field(default_factory=list)
    after: Optional[Dict[str, Any]] = None
    write_retry_pending: bool = field(default=False, repr=False)
    recovery_reconciled: bool = field(default=False, repr=False)

    @property
    def phase(self) -> str:
        if self.after is not None:
            return "AFTER"
        if self.writes:
            return "WRITE"
        if self.target is not None:
            return "TARGET"
        if self.before is not None:
            return "BEFORE"
        return "EMPTY"

    @property
    def complete(self) -> bool:
        return self.before is not None and self.target is not None and not required_moves(self) and self.after is not None and (after_matches_target(self) or (self.recovery_reconciled and _writes_match_relationship(self, self.after)))


def establish_target(state: ControllerState, relationship: Dict[str, Any]) -> Dict[str, Any]:
    midpoint = relationship.get("midpoint")
    object_a = relationship.get("object_a", {})
    object_b = relationship.get("object_b", {})
    location_a = object_a.get("location")
    location_b = object_b.get("location")
    if not (_is_vec3(midpoint) and _is_vec3(location_a) and _is_vec3(location_b)):
        raise ValueError("Relationship evidence is missing a complete midpoint or object location.")
    if object_a.get("name") != state.object_a_name or object_b.get("name") != state.object_b_name:
        raise ValueError("BEFORE evidence does not match the authorized objects.")
    adjustment = _subtract(list(TARGET_MIDPOINT), list(midpoint))
    state.target = {"midpoint": TARGET_MIDPOINT.copy(), "adjustment": adjustment, "object_a_location": _subtract(list(location_a), list(midpoint)), "object_b_location": _subtract(list(location_b), list(midpoint))}
    state.write_retry_pending = False
    state.recovery_reconciled = False
    return deepcopy(state.target)


def record_before(state: ControllerState, relationship: Dict[str, Any]) -> None:
    if state.before is not None:
        raise ValueError("BEFORE state has already been established.")
    state.before = deepcopy(relationship)
    establish_target(state, relationship)


def record_write(state: ControllerState, object_name: str, location: List[float], result: Dict[str, Any]) -> None:
    if result.get("status") != "moved":
        return
    if object_name not in {state.object_a_name, state.object_b_name}:
        raise ValueError("Write targeted an object outside the authorized task state.")
    state.write_retry_pending = False
    state.recovery_reconciled = False
    state.writes.append({"object_name": object_name, "location": deepcopy(location), "result": deepcopy(result)})


def required_moves(state: ControllerState) -> List[Dict[str, Any]]:
    if state.before is None or state.target is None:
        return []
    required = [(state.object_a_name, state.target["object_a_location"]), (state.object_b_name, state.target["object_b_location"])]
    completed = {(write["object_name"], _location_key(write["location"])) for write in state.writes}
    return [{"tool": "move_object", "arguments": {"file_name": state.file_name, "object_name": name, "location": location}} for name, location in required if (name, _location_key(location)) not in completed]


def _relationship_matches_target(state: ControllerState, relationship: Optional[Dict[str, Any]]) -> bool:
    if relationship is None or state.target is None:
        return False
    object_a = relationship.get("object_a", {})
    object_b = relationship.get("object_b", {})
    return object_a.get("name") == state.object_a_name and object_b.get("name") == state.object_b_name and _same_location(object_a.get("location"), state.target.get("object_a_location")) and _same_location(object_b.get("location"), state.target.get("object_b_location")) and _same_location(relationship.get("midpoint"), state.target.get("midpoint"))


def after_matches_target(state: ControllerState) -> bool:
    return _relationship_matches_target(state, state.after)


def _writes_match_relationship(state: ControllerState, relationship: Optional[Dict[str, Any]]) -> bool:
    if not state.writes or relationship is None:
        return False
    object_a = relationship.get("object_a", {})
    object_b = relationship.get("object_b", {})
    for write in state.writes:
        name = write.get("object_name")
        location = write.get("location")
        observed = object_a if name == state.object_a_name else object_b if name == state.object_b_name else None
        if observed is None or observed.get("name") != name or not _same_location(observed.get("location"), location):
            return False
    return True


def next_required_action(state: ControllerState) -> Dict[str, Any]:
    if state.before is None:
        return {"kind": "evidence", "tool": "inspect_object_relationship", "arguments": {"file_name": state.file_name, "object1_name": state.object_a_name, "object2_name": state.object_b_name}}
    pending = required_moves(state)
    if pending:
        state.write_retry_pending = True
        return {"kind": "write", **pending[0]}
    if state.after is None or not after_matches_target(state):
        return {"kind": "verification", "tool": "inspect_object_relationship", "arguments": {"file_name": state.file_name, "object1_name": state.object_a_name, "object2_name": state.object_b_name}}
    return {"kind": "complete"}


def record_after(state: ControllerState, relationship: Dict[str, Any]) -> bool:
    """Accept fresh evidence only when it proves the exact authorized target."""
    if not isinstance(relationship, dict):
        raise ValueError("AFTER evidence must be an object.")
    if not state.writes and state.target is None:
        raise ValueError("AFTER evidence has no established target or write state.")
    if not after_matches_target_with(state, relationship):
        raise ValueError("AFTER evidence does not prove the authorized target state.")
    state.after = deepcopy(relationship)
    state.recovery_reconciled = False
    return True


def after_matches_target_with(state: ControllerState, relationship: Dict[str, Any]) -> bool:
    return _relationship_matches_target(state, relationship)


def record_reconciled_after(state: ControllerState, relationship: Dict[str, Any]) -> None:
    """Record fresh recovery evidence that proves every successful recorded write."""
    if not _writes_match_relationship(state, relationship):
        raise ValueError("AFTER evidence does not prove the recorded write state.")
    state.after = deepcopy(relationship)
    state.recovery_reconciled = True
