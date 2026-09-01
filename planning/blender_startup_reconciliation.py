"""Startup reconciliation gate for autonomous Blender execution."""

from typing import Any, Mapping

from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_execution_recovery import BlenderExecutionRecovery, RecoveryVerifier


class BlenderStartupReconciliation:
    """Reconcile interrupted writes before admitting autonomous execution."""

    def __init__(self, journal: SQLiteBlenderExecutionJournal, recovery: BlenderExecutionRecovery) -> None:
        if not isinstance(journal, SQLiteBlenderExecutionJournal):
            raise TypeError("journal must be SQLiteBlenderExecutionJournal")
        if not isinstance(recovery, BlenderExecutionRecovery):
            raise TypeError("recovery must be BlenderExecutionRecovery")
        self._journal = journal
        self._recovery = recovery
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def reconcile(self, verifier: RecoveryVerifier) -> list[Mapping[str, Any]]:
        """Reconcile every unresolved execution; readiness requires every result to be VERIFIED."""
        if not callable(verifier):
            raise TypeError("verifier must be callable")
        self._ready = False
        results = []
        for record in self._journal.list_unresolved():
            result = self._recovery.reconcile_record(record["authorization_id"], verifier)
            results.append(result)
        self._ready = bool(all(result.get("status") == "VERIFIED" for result in results))
        return results

    def require_ready(self) -> None:
        """Reject autonomous write admission until startup reconciliation succeeds."""
        if not self._ready:
            raise RuntimeError("autonomous Blender execution is locked pending startup reconciliation")
