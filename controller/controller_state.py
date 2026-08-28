"""State-aware controller primitives for authorized Blender modifications."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


TARGET_MIDPOINT = [0.0, 0.0, 0.0]
_LOCATION_PRECISION = 10


def _is_vec3(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    )


def _subtract(a: List[float], b: List[float]) -> List[float]:
    return [round(a[index] - b[index], _LOCATION_PRECISION) for index in range(3)]


def _location_key(value: Any) -> tuple:
    """Create a stable, hashable key for Blender XYZ coordinates."""
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
        return (
            self.before is not None
            and self.target is not None
            and not required_moves(self)
            and self.after is not None
            and after_matches_target(self)
        )


def establish_target(state: ControllerState, relationship: Dict[str, Any]) -> Dict[str, Any]:
    """Build the exact target from measured BEFORE evidence."""
    midpoint = relationship.get("midpoint")
    object_a = relationship.get("object_a", {})
    object_b = relationship.get("object_b", {})
    location_a = object_a.get("location")
    location_b = object_b.get("location")

    if not (_is_vec3(midpoint) and _is_vec3(location_a) and _is_vec3(location_b)):
        raise ValueError("Relationship evidence is missing a complete midpoint or object location.")

    if object_a.get("name") != state.object_a_name:
        raise ValueError("BEFORE evidence does not match object A.")

    if object_b.get("name") != state.object_b_name:
        raise ValueError("BEFORE evidence does not match object B.")

    adjustment = _subtract(list(TARGET_MIDPOINT), list(midpoint))

    state.target = {
        "midpoint": TARGET_MIDPOINT.copy(),
        "adjustment": adjustment,
        "object_a_location": _subtract(list(location_a), list(midpoint)),
        "object_b_location": _subtract(list(location_b), list(midpoint)),
    }

    return state.target


def record_before(state: ControllerState, relationship: Dict[str, Any]) -> None:
    """Record the authoritative BEFORE snapshot and calculate TARGET."""
    if state.before is not None:
        raise ValueError("BEFORE state has already been established.")

    state.before = relationship
    establish_target(state, relationship)


def record_write(
    state: ControllerState,
    object_name: str,
    location: List[float],
    result: Dict[str, Any],
) -> None:
    """Record only a successful authorized move."""
    if result.get("status") != "moved":
        return

    if object_name not in {state.object_a_name, state.object_b_name}:
        raise ValueError("Write targeted an object outside the authorized task state.")

    state.writes.append(
        {
            "object_name": object_name,
            "location": list(location),
            "result": result,
        }
    )


def required_moves(state: ControllerState) -> List[Dict[str, Any]]:
    """Return every target move that has not yet successfully executed."""
    if state.before is None or state.target is None:
        return []

    required = [
        (state.object_a_name, state.target["object_a_location"]),
        (state.object_b_name, state.target["object_b_location"]),
    ]

    completed = {
        (write["object_name"], _location_key(write["location"]))
        for write in state.writes
    }

    return [
        {
            "tool": "move_object",
            "arguments": {
                "file_name": state.file_name,
                "object_name": object_name,
                "location": location,
            },
        }
        for object_name, location in required
        if (object_name, _location_key(location)) not in completed
    ]


def after_matches_target(state: ControllerState) -> bool:
    """Require independent AFTER evidence to match every authorized target."""
    if state.after is None or state.target is None:
        return False

    object_a = state.after.get("object_a", {})
    object_b = state.after.get("object_b", {})

    return (
        _same_location(object_a.get("location"), state.target.get("object_a_location"))
        and _same_location(object_b.get("location"), state.target.get("object_b_location"))
        and _same_location(state.after.get("midpoint"), TARGET_MIDPOINT)
    )


def next_required_action(state: ControllerState) -> Dict[str, Any]:
    """Return the next deterministic gate without performing it."""
    if state.before is None:
        return {
            "kind": "evidence",
            "tool": "inspect_object_relationship",
            "arguments": {
                "file_name": state.file_name,
                "object1_name": state.object_a_name,
                "object2_name": state.object_b_name,
            },
        }

    pending_moves = required_moves(state)
    if pending_moves:
        return {"kind": "write", **pending_moves[0]}

    if state.after is None:
        return {
            "kind": "verification",
            "tool": "inspect_object_relationship",
            "arguments": {
                "file_name": state.file_name,
                "object1_name": state.object_a_name,
                "object2_name": state.object_b_name,
            },
        }

    if state.complete:
        return {"kind": "complete"}

    return {
        "kind": "verification",
        "tool": "inspect_object_relationship",
        "arguments": {
            "file_name": state.file_name,
            "object1_name": state.object_a_name,
            "object2_name": state.object_b_name,
        },
    }


def record_after(state: ControllerState, relationship: Dict[str, Any]) -> None:
    """Record independent AFTER verification after all required writes."""
    if required_moves(state):
        raise ValueError("Cannot establish AFTER state while authorized writes remain outstanding.")

    if not state.writes:
        raise ValueError("Cannot establish AFTER state before a successful write.")

    state.after = relationship
