"""Photogrammetry-to-Atlas intake boundary.

Photogrammetry creates an initial reconstruction; it does not become the
canonical Digital Twin automatically. This contract records the reconstruction
as an observed input that can be analyzed, cleaned, and validated before a
canonical Atlas revision is established.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IntakeState(str, Enum):
    RECEIVED = "received"
    ANALYZING = "analyzing"
    NEEDS_CLEANUP = "needs_cleanup"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReconstructionIntake:
    intake_id: str
    twin_candidate_id: str
    source_id: str
    software: str
    reconstruction_id: str
    state: IntakeState = IntakeState.RECEIVED
    source_fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        for name, value in (
            ("intake_id", self.intake_id),
            ("twin_candidate_id", self.twin_candidate_id),
            ("source_id", self.source_id),
            ("software", self.software),
            ("reconstruction_id", self.reconstruction_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")


def create_reconstruction_intake(
    intake_id: str,
    twin_candidate_id: str,
    source_id: str,
    software: str,
    reconstruction_id: str,
    source_fingerprint: Optional[str] = None,
) -> ReconstructionIntake:
    """Register an external reconstruction without promoting it to canonical state."""
    return ReconstructionIntake(
        intake_id=intake_id,
        twin_candidate_id=twin_candidate_id,
        source_id=source_id,
        software=software,
        reconstruction_id=reconstruction_id,
        source_fingerprint=source_fingerprint,
    )
