"""Recovery boundary for interrupted authorization-bound Blender writes."""

from typing import Any, Callable, Mapping, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal, _digest
from planning.blender_write_authorization import BlenderWriteAuthorization


RecoveryVerifier = Callable[[ActionSpec, Mapping[str, Any]], Tuple[bool, Mapping[str, Any]]]


class BlenderExecutionRecovery:
    """Reconcile journaled STARTED executions without replaying Blender writes."""

    def __init__(self, journal: SQLiteBlenderExecutionJournal) -> None:
        if not isinstance(journal, SQLiteBlenderExecutionJournal):
            raise TypeError("journal must be SQLiteBlenderExecutionJournal")
        self._journal = journal

    def _restore(self, record: Mapping[str, Any]) -> Tuple[ActionSpec, BlenderWriteAuthorization]:
        """Reconstruct an execution envelope only after validating its persisted identity."""
        arguments = record.get("arguments")
        snapshot = record.get("authorization")
        if not isinstance(arguments, dict):
            raise RuntimeError("journaled execution is missing persisted arguments")
        if not isinstance(snapshot, dict):
            raise RuntimeError("journaled execution is missing authorization snapshot")
        action = ActionSpec(tool=record["tool"], arguments=arguments)
        if record["arguments_digest"] != _digest(action.arguments):
            raise RuntimeError("journaled execution arguments digest is invalid")
        authorization = BlenderWriteAuthorization.restore(action, snapshot)
        if authorization.authorization_id != record["authorization_id"]:
            raise RuntimeError("journaled execution authorization identity is invalid")
        if not authorization.matches(action):
            raise RuntimeError("restored authorization does not match journaled action")
        return action, authorization

    def reconcile_record(self, authorization_id: str, verifier: RecoveryVerifier) -> Mapping[str, Any]:
        """Recover directly from a durable journal record; never replay the write."""
        if not callable(verifier):
            raise TypeError("verifier must be callable")
        record = self._journal.get(authorization_id)
        if record is None:
            raise RuntimeError("no journaled execution exists for authorization")
        if record["status"] != "STARTED":
            raise RuntimeError("journaled execution is not interrupted")
        action, authorization = self._restore(record)
        return self.reconcile(action, authorization, verifier)

    def reconcile(self, action: ActionSpec, authorization: BlenderWriteAuthorization, verifier: RecoveryVerifier) -> Mapping[str, Any]:
        """Resolve an interrupted execution from authoritative Blender state."""
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be a BlenderWriteAuthorization")
        if not callable(verifier):
            raise TypeError("verifier must be callable")
        if not authorization.matches(action):
            raise ValueError("authorization does not match action")
        record = self._journal.get(authorization.authorization_id)
        if record is None:
            raise RuntimeError("no journaled execution exists for authorization")
        if record["status"] != "STARTED":
            raise RuntimeError("journaled execution is not interrupted")
        if record["tool"] != action.tool:
            raise RuntimeError("journaled execution tool does not match action")
        if record["arguments_digest"] != _digest(action.arguments):
            raise RuntimeError("journaled execution arguments do not match action")
        verified, details = verifier(action, record)
        if not isinstance(verified, bool):
            raise TypeError("recovery verifier must return a bool verification result")
        if not isinstance(details, Mapping):
            raise TypeError("recovery verifier must return a mapping of details")
        if verified:
            self._journal.complete(authorization, None, "VERIFIED")
            return {"status": "VERIFIED", "recovered": True, **dict(details)}
        self._journal.complete(authorization, None, "BLOCKED")
        return {"status": "BLOCKED", "recovered": False, **dict(details)}
