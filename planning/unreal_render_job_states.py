"""Normative lifecycle and recovery state model for Atlas Unreal render recovery.

Defined by docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md.
"""

from __future__ import annotations

from enum import Enum


class RenderJobLifecycleState(str, Enum):
    """Normative lifecycle states for one Atlas execution attempt.
    
    Terminal states MUST never regress:
    - FINALIZED
    - FAILED
    - ORPHANED
    - ORPHANED_ARTIFACTS_PRESENT
    - RECOVERY_FAILED
    - RECORD_CORRUPT
    """

    PENDING_SUBMISSION = "PENDING_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    RENDERING = "RENDERING"
    COMPLETED_UNVERIFIED = "COMPLETED_UNVERIFIED"
    VERIFIED = "VERIFIED"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"
    ORPHANED = "ORPHANED"
    ORPHANED_ARTIFACTS_PRESENT = "ORPHANED_ARTIFACTS_PRESENT"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    RECORD_CORRUPT = "RECORD_CORRUPT"


TERMINAL_LIFECYCLE_STATES: frozenset[RenderJobLifecycleState] = frozenset({
    RenderJobLifecycleState.FINALIZED,
    RenderJobLifecycleState.FAILED,
    RenderJobLifecycleState.ORPHANED,
    RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
    RenderJobLifecycleState.RECOVERY_FAILED,
    RenderJobLifecycleState.RECORD_CORRUPT,
})


class RenderJobRecoveryStatus(str, Enum):
    """Operational status during recovery tracking and reconciliation passes.
    
    This is distinct from lifecycle state: transport unavailability or waiting
    must not mutate execution lifecycle state.
    """

    NONE = "NONE"
    WAITING_FOR_ENGINE = "WAITING_FOR_ENGINE"
    WAITING_FOR_ENGINE_QUIESCENCE = "WAITING_FOR_ENGINE_QUIESCENCE"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    RECONCILING = "RECONCILING"
    RESOLVED = "RESOLVED"
    EXHAUSTED = "EXHAUSTED"
