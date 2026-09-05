"""Production intent and downstream consumer interfaces for Atlas Live.

Production intent represents what Atlas Live wants downstream presentation or game engine
environments (such as Unreal Engine) to execute in response to recognized live events
or world states.

It separates:
1. What happened (Event)
2. What Atlas wants produced (ProductionIntent)
3. How transport delivers it (ProductionIntentEnvelope & LiveTransportChannel)
4. How Unreal executes it (Downstream Consumer)
"""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import time
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from planning.digital_twin_spatial import Vector3
from live.observation import _freeze, _thaw
from live.event_engine import LiveEvent


class ProductionTreatment(str, Enum):
    IMPACT_ACCENT = "impact_accent"
    SPEED_TRAIL = "speed_trail"
    BALL_HIGHLIGHT = "ball_highlight"
    PLAYER_CARD = "player_card"
    CINEMATIC_PUNCH = "cinematic_punch"
    IMPACT_FRAME = "impact_frame"


@dataclass(frozen=True)
class ProductionIntent:
    """An explicit, engine-neutral request from Atlas Live to produce a live visual treatment."""

    intent_id: str
    treatment: ProductionTreatment
    source_event_id: str
    target_entity_ids: Tuple[str, ...]
    intensity: float
    duration_ms: int
    timestamp_ns: int
    origin: Optional[Vector3] = None
    direction: Optional[Vector3] = None
    parameters: Optional[Mapping[str, Any]] = None
    created_at_ns: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("intent_id must be a non-empty string")
        if not isinstance(self.treatment, ProductionTreatment):
            raise TypeError("treatment must be an instance of ProductionTreatment")
        if not isinstance(self.source_event_id, str) or not self.source_event_id.strip():
            raise ValueError("source_event_id must be a non-empty string")
        if not isinstance(self.intensity, (int, float)) or isinstance(self.intensity, bool):
            raise TypeError("intensity must be a float between 0.0 and 1.0")
        if not 0.0 <= float(self.intensity) <= 1.0:
            raise ValueError("intensity must be between 0.0 and 1.0")
        if not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool) or self.duration_ms < 0:
            raise ValueError("duration_ms must be a non-negative integer")
        if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        clean_entities = tuple(e.strip() for e in self.target_entity_ids if e.strip())
        if not clean_entities:
            raise ValueError("target_entity_ids must contain at least one non-empty entity id")
        object.__setattr__(self, "target_entity_ids", clean_entities)
        object.__setattr__(self, "intensity", float(self.intensity))
        if self.created_at_ns is not None:
            if not isinstance(self.created_at_ns, int) or isinstance(self.created_at_ns, bool) or self.created_at_ns < 0:
                raise ValueError("created_at_ns must be a non-negative integer when provided")
        if self.parameters is not None:
            if not isinstance(self.parameters, Mapping):
                raise TypeError("parameters must be a mapping when provided")
            object.__setattr__(self, "parameters", _freeze(self.parameters))

    def parameters_snapshot(self) -> Mapping[str, Any]:
        return _thaw(self.parameters or {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable canonical dict."""
        return {
            "intent_id": self.intent_id,
            "treatment": self.treatment.value,
            "source_event_id": self.source_event_id,
            "target_entity_ids": list(self.target_entity_ids),
            "intensity": self.intensity,
            "duration_ms": self.duration_ms,
            "timestamp_ns": self.timestamp_ns,
            "origin": (
                {"x": self.origin.x, "y": self.origin.y, "z": self.origin.z}
                if self.origin is not None
                else None
            ),
            "direction": (
                {"x": self.direction.x, "y": self.direction.y, "z": self.direction.z}
                if self.direction is not None
                else None
            ),
            "parameters": self.parameters_snapshot(),
            "created_at_ns": self.created_at_ns,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProductionIntent":
        """Construct ProductionIntent from a validated mapping."""
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        treatment = ProductionTreatment(data["treatment"])
        origin_data = data.get("origin")
        origin = Vector3(origin_data["x"], origin_data["y"], origin_data["z"]) if origin_data else None
        dir_data = data.get("direction")
        direction = Vector3(dir_data["x"], dir_data["y"], dir_data["z"]) if dir_data else None

        return cls(
            intent_id=data["intent_id"],
            treatment=treatment,
            source_event_id=data["source_event_id"],
            target_entity_ids=tuple(data["target_entity_ids"]),
            intensity=data["intensity"],
            duration_ms=data["duration_ms"],
            timestamp_ns=data["timestamp_ns"],
            origin=origin,
            direction=direction,
            parameters=data.get("parameters"),
            created_at_ns=data.get("created_at_ns"),
        )


@dataclass(frozen=True)
class ProductionIntentEnvelope:
    """Transport-neutral framing for delivering ProductionIntent across process/network boundaries.

    Provides monotonic sequencing, content hashing (digest), and delivery tracking.
    """

    sequence_number: int
    intent: ProductionIntent
    sent_at_ns: int
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence_number, int) or isinstance(self.sequence_number, bool) or self.sequence_number < 1:
            raise ValueError("sequence_number must be a positive integer")
        if not isinstance(self.intent, ProductionIntent):
            raise TypeError("intent must be an instance of ProductionIntent")
        if not isinstance(self.sent_at_ns, int) or isinstance(self.sent_at_ns, bool) or self.sent_at_ns < 0:
            raise ValueError("sent_at_ns must be a non-negative integer")
        if not isinstance(self.digest, str) or not self.digest.strip():
            raise ValueError("digest must be a non-empty hex string")

    @classmethod
    def create(cls, sequence_number: int, intent: ProductionIntent, sent_at_ns: int) -> "ProductionIntentEnvelope":
        """Create an envelope with an authoritative deterministic digest."""
        payload_bytes = json.dumps(intent.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        header = f"{sequence_number}:{sent_at_ns}:".encode("utf-8")
        digest = hashlib.sha256(header + payload_bytes).hexdigest()
        return cls(
            sequence_number=sequence_number,
            intent=intent,
            sent_at_ns=sent_at_ns,
            digest=digest,
        )

    def verify_digest(self) -> bool:
        """Verify that the envelope content has not been corrupted or tampered with."""
        payload_bytes = json.dumps(self.intent.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        header = f"{self.sequence_number}:{self.sent_at_ns}:".encode("utf-8")
        expected = hashlib.sha256(header + payload_bytes).hexdigest()
        return self.digest == expected


class LiveProductionDecisionLayer:
    """Maps recognized events to production intents based on configured rules or prepared capabilities.

    Operates deterministically without per-frame LLM invocation.
    """

    def __init__(self, min_confidence_threshold: float = 0.5) -> None:
        self.min_confidence_threshold: float = min_confidence_threshold
        self._intent_counter: int = 0

    def evaluate(self, event: LiveEvent) -> Optional[ProductionIntent]:
        """Convert a recognized LiveEvent into an actionable ProductionIntent."""
        if not isinstance(event, LiveEvent):
            raise TypeError("event must be a LiveEvent")

        # Confidence gate
        if event.confidence < self.min_confidence_threshold:
            return None

        self._intent_counter += 1
        intent_id = f"intent-{self._intent_counter:04d}"

        # Deterministic mapping based on event type
        if event.event_type.value == "ball_strike":
            # For ball strike, map to IMPACT_ACCENT
            duration_ms = int(100 + event.intensity * 200)  # 100ms - 300ms
            return ProductionIntent(
                intent_id=intent_id,
                treatment=ProductionTreatment.IMPACT_ACCENT,
                source_event_id=event.event_id,
                target_entity_ids=event.entity_ids,
                intensity=event.intensity,
                duration_ms=duration_ms,
                timestamp_ns=event.timestamp_ns,
                origin=event.location,
                direction=event.direction,
                parameters={"preset": "strike_flash_v1"},
                created_at_ns=time.perf_counter_ns(),
            )

        return None
