"""Single admission boundary for autonomous Blender writes."""

from typing import Any, Mapping

from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery, RecoveryVerifier
from planning.blender_live_write_gate import BlenderLiveWriteGate
from planning.blender_startup_reconciliation import BlenderStartupReconciliation


class BlenderAutonomousAdmission:
    """Own runtime readiness and delegate authorized writes to the proven live gate."""

    def __init__(self, write_gate: BlenderLiveWriteGate, journal: SQLiteBlenderExecutionJournal, recovery: BlenderExecutionRecovery) -> None:
        if not isinstance(write_gate, BlenderLiveWriteGate):
            raise TypeError("write_gate must be BlenderLiveWriteGate")
        if not isinstance(journal, SQLiteBlenderExecutionJournal):
            raise TypeError("journal must be SQLiteBlenderExecutionJournal")
        if write_gate.execution_journal is not journal:
            raise ValueError("autonomous admission requires the write gate to use the supplied durable execution journal")
        self._write_gate = write_gate
        self._startup = BlenderStartupReconciliation(journal, recovery)

    @property
    def ready(self) -> bool:
        return self._startup.ready

    def startup(self, verifier: RecoveryVerifier) -> list[Mapping[str, Any]]:
        """Reconcile interrupted work and unlock autonomous execution only on success."""
        return self._startup.reconcile(verifier)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Admit autonomous execution only after successful startup reconciliation."""
        self._startup.require_ready()
        return self._write_gate.execute(*args, **kwargs)
