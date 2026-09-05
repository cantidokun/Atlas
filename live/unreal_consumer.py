"""Unreal Live adapter interfaces and mock execution sinks.

This module sits on the execution side of the transport boundary.
It receives ProductionIntents via transport delivery and prepares or dispatches
them to Unreal Engine subsystems (e.g. Niagara VFX, Sequencer, Movie Render Queue).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from live.production_intent import ProductionIntent, ProductionTreatment
from live.transport import LiveProductionConsumer


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class UnrealEffectDispatch:
    """Unreal-side representation of an accepted production intent mapped to an engine asset/preset."""

    dispatch_id: str
    intent_id: str
    target_unreal_preset: str
    duration_frames: int
    status: ExecutionStatus


class MockUnrealLiveConsumer:
    """Mock execution consumer modeling Unreal Engine's Live VFX / cinematic dispatch queue."""

    PRESET_MAP: Dict[ProductionTreatment, str] = {
        ProductionTreatment.IMPACT_ACCENT: "NS_LiveSoccer_BallStrike_Burst",
        ProductionTreatment.SPEED_TRAIL: "NS_LiveSoccer_BallTrail_Ribbon",
        ProductionTreatment.BALL_HIGHLIGHT: "MI_LiveSoccer_BallGlow_Overlay",
        ProductionTreatment.PLAYER_CARD: "WBP_LiveSoccer_PlayerHUD",
        ProductionTreatment.CINEMATIC_PUNCH: "LS_LiveSoccer_CinematicPunch",
        ProductionTreatment.IMPACT_FRAME: "PP_LiveSoccer_ImpactFrame",
    }

    def __init__(self, fps: float = 60.0) -> None:
        self.fps = fps
        self.is_connected = True
        self.received_intents: List[ProductionIntent] = []
        self.dispatches: List[UnrealEffectDispatch] = []
        self._dispatch_counter = 0

    def consume(self, intent: ProductionIntent) -> bool:
        if not self.is_connected:
            return False

        self.received_intents.append(intent)
        self._dispatch_counter += 1

        # Map intent treatment to Unreal preset
        preset = self.PRESET_MAP.get(intent.treatment, "NS_LiveSoccer_Default")
        frames = max(1, int((intent.duration_ms / 1000.0) * self.fps))

        dispatch = UnrealEffectDispatch(
            dispatch_id=f"ue-disp-{self._dispatch_counter:04d}",
            intent_id=intent.intent_id,
            target_unreal_preset=preset,
            duration_frames=frames,
            status=ExecutionStatus.QUEUED,
        )
        self.dispatches.append(dispatch)
        return True
