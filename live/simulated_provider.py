"""Provider adapter protocol and simulated provider for Atlas Live.

External tracking and sensor systems (Chyron, Hawk-Eye, Second Spectrum, camera CV)
are adapted through this interface into canonical LiveObservationFrame batches.
"""

from dataclasses import dataclass
import math
from typing import Iterator, List, Optional, Protocol, Sequence, Tuple

from planning.digital_twin_spatial import SpatialPose, Vector3
from live.observation import EntityObservation, LiveObservationFrame


class LivePerceptionProvider(Protocol):
    """Protocol for observation providers feeding Atlas Live."""

    @property
    def source_id(self) -> str:
        ...

    def poll_frame(self) -> Optional[LiveObservationFrame]:
        """Return the next observation frame, or None if no new frame is available."""
        ...


class SimulatedSoccerStreamProvider:
    """Deterministic simulated observation provider.

    Simulates a player approaching a stationary ball and striking it.
    Can inject latency, drops, confidence degradation, or jitter if configured.
    """

    def __init__(
        self,
        source_id: str = "sim-provider-01",
        frame_rate_hz: float = 50.0,
        player_id: str = "player-09",
        ball_id: str = "ball",
    ) -> None:
        self._source_id: str = source_id
        self._dt_ns: int = int(1e9 / frame_rate_hz)
        self._player_id: str = player_id
        self._ball_id: str = ball_id
        self._current_sequence: int = 0
        self._current_timestamp_ns: int = 0
        self.is_connected: bool = True

    @property
    def source_id(self) -> str:
        return self._source_id

    def generate_raw_frame(self, step_index: int) -> "RawPerceptionFrame":
        """Generate a RawPerceptionFrame before perception adapter normalization."""
        from live.perception_adapter import RawEntityMeasurement, RawPerceptionFrame

        self._current_sequence += 1
        self._current_timestamp_ns += self._dt_ns
        dt_s = self._dt_ns / 1e9

        measurements = []
        if step_index < 10:
            player_x = 5.0 + step_index * 0.5
            measurements.append(RawEntityMeasurement(
                entity_id=self._player_id,
                x=player_x, y=0.0, z=0.0,
                vx=5.0, vy=0.0, vz=0.0,
                confidence=0.95,
            ))
            measurements.append(RawEntityMeasurement(
                entity_id=self._ball_id,
                x=10.0, y=0.0, z=0.1,
                vx=0.0, vy=0.0, vz=0.0,
                confidence=0.98,
            ))
        elif step_index == 10:
            measurements.append(RawEntityMeasurement(
                entity_id=self._player_id,
                x=10.0, y=0.0, z=0.0,
                vx=5.0, vy=0.0, vz=0.0,
                confidence=0.95,
            ))
            measurements.append(RawEntityMeasurement(
                entity_id=self._ball_id,
                x=10.0, y=0.0, z=0.1,
                vx=25.0, vy=5.0, vz=2.0,
                confidence=0.98,
            ))
        else:
            post_steps = step_index - 10
            measurements.append(RawEntityMeasurement(
                entity_id=self._player_id,
                x=10.0 + post_steps * 0.1, y=0.0, z=0.0,
                vx=1.0, vy=0.0, vz=0.0,
                confidence=0.95,
            ))
            ball_x = 10.0 + post_steps * 25.0 * dt_s
            ball_y = 0.0 + post_steps * 5.0 * dt_s
            ball_z = 0.1 + post_steps * 2.0 * dt_s
            measurements.append(RawEntityMeasurement(
                entity_id=self._ball_id,
                x=ball_x, y=ball_y, z=ball_z,
                vx=25.0, vy=5.0, vz=2.0,
                confidence=0.98,
            ))

        return RawPerceptionFrame(
            source_id=self.source_id,
            sequence_number=self._current_sequence,
            sensor_timestamp_ns=self._current_timestamp_ns,
            measurements=tuple(measurements),
            attributes=(("provider", "simulated_soccer"),),
        )

    def generate_strike_scenario(self, total_frames: int = 20) -> Iterator[LiveObservationFrame]:
        """Generate a sequence of frames modeling a run-up and strike.

        Frames 1-10: Player runs toward stationary ball at (10, 0, 0).
                     Ball is at (10, 0, 0), velocity (0, 0, 0).
        Frame 10: Player contacts ball at (10, 0, 0).
        Frames 11-20: Ball accelerates rapidly to (25, 5, 1) with high velocity.
                      Player decelerates.
        """
        for i in range(1, total_frames + 1):
            frame = self.generate_next_frame(step_index=i)
            yield frame

    def generate_next_frame(self, step_index: int) -> LiveObservationFrame:
        self._current_sequence += 1
        self._current_timestamp_ns += self._dt_ns

        # Scenario geometry:
        # Stationary ball at x=10.0, y=0.0, z=0.1
        # Player starts at x=5.0, y=0.0, z=0.0, runs at 5 m/s toward ball (+x)
        # At step 10 (t = 10 * 0.02s = 0.2s), player reaches ball: x = 10.0
        # Ball is struck at step 10:
        # From step 11 onwards, ball velocity jumps to (25.0, 5.0, 2.0) m/s
        dt_s = self._dt_ns / 1e9

        if step_index < 10:
            player_x = 5.0 + step_index * 0.5  # approaches x=10
            player_pose = SpatialPose("atlas-field", Vector3(player_x, 0.0, 0.0))
            player_vel = Vector3(5.0, 0.0, 0.0)

            ball_pose = SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.1))
            ball_vel = Vector3(0.0, 0.0, 0.0)
        elif step_index == 10:
            # Contact frame
            player_pose = SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.0))
            player_vel = Vector3(5.0, 0.0, 0.0)

            # Ball gets high velocity on strike frame
            ball_pose = SpatialPose("atlas-field", Vector3(10.0, 0.0, 0.1))
            ball_vel = Vector3(25.0, 5.0, 2.0)
        else:
            # Post-strike trajectory
            post_steps = step_index - 10
            player_pose = SpatialPose("atlas-field", Vector3(10.0 + post_steps * 0.1, 0.0, 0.0))
            player_vel = Vector3(1.0, 0.0, 0.0)

            ball_x = 10.0 + post_steps * 25.0 * dt_s
            ball_y = 0.0 + post_steps * 5.0 * dt_s
            ball_z = max(0.0, 0.1 + post_steps * 2.0 * dt_s - 0.5 * 9.81 * ((post_steps * dt_s) ** 2))
            ball_pose = SpatialPose("atlas-field", Vector3(ball_x, ball_y, ball_z))
            ball_vel = Vector3(25.0, 5.0, 2.0 - 9.81 * (post_steps * dt_s))

        entities = (
            EntityObservation(
                entity_id=self._player_id,
                pose=player_pose,
                velocity=player_vel,
                confidence=0.98,
                attributes=(("role", "striker"),),
            ),
            EntityObservation(
                entity_id=self._ball_id,
                pose=ball_pose,
                velocity=ball_vel,
                confidence=0.99,
                attributes=(("type", "match_ball"),),
            ),
        )

        return LiveObservationFrame(
            source_id=self._source_id,
            sequence_number=self._current_sequence,
            timestamp_ns=self._current_timestamp_ns,
            entities=entities,
            frame_attributes=(("match_phase", "in_play"),),
        )
