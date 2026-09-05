"""Deterministic event engine and event definitions for Atlas Live.

Events represent derived temporal interpretations of physical interactions in the
World-State (e.g. ball strike, possession change, goal line cross).
Events are NOT raw observations and are NOT predictions.
"""

from dataclasses import dataclass
from enum import Enum
import math
import time
from types import MappingProxyType
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from planning.digital_twin_spatial import Vector3
from live.observation import _freeze, _thaw
from live.world_state import LiveWorldState


class EventType(str, Enum):
    BALL_STRIKE = "ball_strike"
    POSSESSION_CHANGE = "possession_change"
    SHOT_ON_TARGET = "shot_on_target"
    BALL_OUT_OF_BOUNDS = "ball_out_of_bounds"


@dataclass(frozen=True)
class LiveEvent:
    """An immutable, derived event recognized by Atlas from World-State transitions."""

    event_id: str
    event_type: EventType
    timestamp_ns: int
    source_sequence: int
    entity_ids: Tuple[str, ...]
    confidence: float
    intensity: float = 0.0
    location: Optional[Vector3] = None
    direction: Optional[Vector3] = None
    metadata: Optional[Mapping[str, Any]] = None
    detected_at_ns: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be an instance of EventType")
        if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        if not isinstance(self.source_sequence, int) or isinstance(self.source_sequence, bool) or self.source_sequence < 1:
            raise ValueError("source_sequence must be a positive integer")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise TypeError("confidence must be a float between 0.0 and 1.0")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.intensity, (int, float)) or isinstance(self.intensity, bool):
            raise TypeError("intensity must be a float between 0.0 and 1.0")
        if not 0.0 <= float(self.intensity) <= 1.0:
            raise ValueError("intensity must be between 0.0 and 1.0")
        clean_entities = tuple(e.strip() for e in self.entity_ids if e.strip())
        if not clean_entities:
            raise ValueError("entity_ids must contain at least one non-empty entity id")
        object.__setattr__(self, "entity_ids", clean_entities)
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "intensity", float(self.intensity))
        if self.detected_at_ns is not None:
            if not isinstance(self.detected_at_ns, int) or isinstance(self.detected_at_ns, bool) or self.detected_at_ns < 0:
                raise ValueError("detected_at_ns must be a non-negative integer when provided")
        if self.metadata is not None:
            if not isinstance(self.metadata, Mapping):
                raise TypeError("metadata must be a mapping when provided")
            object.__setattr__(self, "metadata", _freeze(self.metadata))

    def metadata_snapshot(self) -> Mapping[str, Any]:
        return _thaw(self.metadata or {})


class LiveEventEngine:
    """Deterministic, rule-based event detector evaluating World-State history.

    Operates in the critical high-frequency loop without LLM calls.
    Evaluates kinematic state transitions (e.g., ball acceleration inflection coupled with
    proximity to a player entity) to detect BALL_STRIKE and similar physical events.
    """

    def __init__(
        self,
        ball_entity_id: str = "ball",
        proximity_threshold_m: float = 1.5,
        acceleration_threshold_m_s2: float = 15.0,
    ) -> None:
        self.ball_entity_id: str = ball_entity_id.strip()
        self.proximity_threshold_m: float = proximity_threshold_m
        self.acceleration_threshold_m_s2: float = acceleration_threshold_m_s2
        self._event_counter: int = 0

    def evaluate(self, current_state: LiveWorldState, prior_state: Optional[LiveWorldState]) -> Sequence[LiveEvent]:
        """Detect events between prior_state and current_state."""
        if prior_state is None:
            return ()

        events: List[LiveEvent] = []

        # Check for Ball Strike
        strike_event = self._detect_ball_strike(current_state, prior_state)
        if strike_event is not None:
            events.append(strike_event)

        return tuple(events)

    def _detect_ball_strike(self, current: LiveWorldState, prior: LiveWorldState) -> Optional[LiveEvent]:
        # Both states must contain fresh, actively observed ball entities
        if not current.has_entity(self.ball_entity_id, only_fresh=True) or not prior.has_entity(self.ball_entity_id, only_fresh=True):
            return None

        ball_curr = current.entity(self.ball_entity_id)
        ball_prev = prior.entity(self.ball_entity_id)

        if not ball_curr.is_observed or not ball_prev.is_observed:
            return None

        if ball_curr.pose is None or ball_prev.pose is None:
            return None
        if ball_curr.velocity is None or ball_prev.velocity is None:
            return None

        dt_s = (current.timestamp_ns - prior.timestamp_ns) / 1e9
        if dt_s <= 0.0:
            return None

        # Compute ball acceleration magnitude
        dvx = ball_curr.velocity.x - ball_prev.velocity.x
        dvy = ball_curr.velocity.y - ball_prev.velocity.y
        dvz = ball_curr.velocity.z - ball_prev.velocity.z
        accel_magnitude = math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz) / dt_s

        if accel_magnitude < self.acceleration_threshold_m_s2:
            return None

        # Check proximity to any player entity in current state
        ball_pos = ball_curr.pose.position
        closest_player_id: Optional[str] = None
        min_distance = float("inf")

        for entity in current.entities:
            if entity.entity_id == self.ball_entity_id or entity.pose is None:
                continue
            # Stale player entities must not trigger kinematic events
            if not entity.is_observed:
                continue
            dx = entity.pose.position.x - ball_pos.x
            dy = entity.pose.position.y - ball_pos.y
            dz = entity.pose.position.z - ball_pos.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < min_distance:
                min_distance = dist
                closest_player_id = entity.entity_id

        if closest_player_id is not None and min_distance <= self.proximity_threshold_m:
            self._event_counter += 1
            # Intensity normalized [0.0, 1.0] based on acceleration
            norm_intensity = min(1.0, max(0.1, accel_magnitude / (self.acceleration_threshold_m_s2 * 4.0)))
            confidence = min(1.0, ball_curr.confidence * current.entity(closest_player_id).confidence)

            # Travel direction unit vector
            vel_mag = math.sqrt(ball_curr.velocity.x ** 2 + ball_curr.velocity.y ** 2 + ball_curr.velocity.z ** 2)
            direction = (
                Vector3(
                    ball_curr.velocity.x / vel_mag,
                    ball_curr.velocity.y / vel_mag,
                    ball_curr.velocity.z / vel_mag,
                )
                if vel_mag > 0.001
                else None
            )

            return LiveEvent(
                event_id=f"evt-strike-{self._event_counter:04d}",
                event_type=EventType.BALL_STRIKE,
                timestamp_ns=current.timestamp_ns,
                source_sequence=current.sequence_number,
                entity_ids=(closest_player_id, self.ball_entity_id),
                confidence=confidence,
                intensity=norm_intensity,
                location=ball_pos,
                direction=direction,
                metadata={"accel_m_s2": accel_magnitude, "distance_m": min_distance},
                detected_at_ns=time.perf_counter_ns(),
            )

        return None
