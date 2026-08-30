"""Recovery boundary for interrupted authorization-bound Blender writes."""

from typing import Any, Callable, Mapping, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_write_authorization import BlenderWriteAuthorization


RecoveryVerifier = Callable[[ActionSpec, Mapping[str, Any]], Tuple[bool, Mapping[str, Any]]]


class BlenderExecutionRecovery:
    """Reconcile journaled STARTED executions without replaying Blender writes."""

    def __init__(self, journal: SQLiteBlenderExecutionJournal) -> None:
        if not isinstance(journal, SQLiteBlenderExecutionJournal):
            raise TypeError("journal must be SQLiteBlenderExecutionJournal")
        self._journal = journal

    def reconcile(
        self,
        action: ActionSpec,
        authorization: BlenderWriteAuthorization,
        verifier: RecoveryVerifier,
    ) -> Mapping[str, Any]:
        """Resolve an interrupted execution from authoritative Blender state.

        Recovery never calls the Blender write executor. A STARTED journal row is
        first matched to the original authorization/tool/arguments identity; the
        caller's verifier then decides whether the scene already reflects the
        requested action. A positive decision closes the journal as VERIFIED.
        """
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
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
