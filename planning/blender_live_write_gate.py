"""Final pre-live gate for one authorized Blender write."""
from typing import Any, Callable, Mapping, Optional, Tuple

from planning.action_plan import ActionSpec
from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.blender_execution_journal import SQLiteBlenderExecutionJournal
from planning.blender_live_write_result import BlenderLiveWriteOutcome
from planning.blender_write_authorization import BlenderWriteAuthorization
from planning.blender_write_authorization_ledger import BlenderWriteAuthorizationLedger

AuthoritativeVerifier = Callable[[ActionSpec, Any], Tuple[bool, Mapping[str, Any]]]


class BlenderLiveWriteGate:
    """Execute one authorization-bound Blender write and verify authoritative state."""

    def __init__(self, boundary: BlenderExecutionBoundary, verifier: Optional[AuthoritativeVerifier] = None, authorization_ledger: Optional[BlenderWriteAuthorizationLedger] = None, execution_journal: Optional[SQLiteBlenderExecutionJournal] = None) -> None:
        self._boundary = boundary
        self._verifier = verifier
        self._authorization_ledger = authorization_ledger
        self._execution_journal = execution_journal

    @property
    def execution_journal(self) -> Optional[SQLiteBlenderExecutionJournal]:
        return self._execution_journal

    def execute(self, action: ActionSpec, authorization: BlenderWriteAuthorization) -> BlenderLiveWriteOutcome:
        if not authorization.matches(action):
            raise ValueError("Blender write authorization does not match action")
        if self._authorization_ledger is not None and not self._authorization_ledger.consume(authorization):
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False, "authorization_consumed": True}, "Blender write authorization has already been consumed")
        if self._execution_journal is not None and not self._execution_journal.begin(action, authorization):
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False, "execution_journaled": True}, "Blender write authorization already has a journaled execution attempt")
        try:
            result, receipt = self._boundary.execute_authorized_write(action, authorization)
        except Exception as exc:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, None, "BLOCKED", type(exc).__name__)
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False, "execution_error": type(exc).__name__}, "Blender execution failed closed")
        if not result.ok:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False, "result": result}, "Blender executor did not establish a successful write")
        if result.mutation_performed is False:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": receipt.matches_authorization(authorization.authorization_id), "receipt_matches_execution": receipt.matches(action.tool, action.arguments, result), "result": result, "mutation_performed": False}, "Blender executor explicitly reported that no mutation was performed")
        if not receipt.matches_authorization(authorization.authorization_id):
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": False}, "Blender write receipt is not bound to authorization")
        if not receipt.matches(action.tool, action.arguments, result):
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": True, "receipt_matches_execution": False}, "Blender write receipt does not bind the requested action and execution result")
        if self._verifier is None:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": True, "receipt_matches_execution": True, "result": result}, "No authoritative Blender verifier is configured")
        try:
            verified, verification = self._verifier(action, receipt)
            if not isinstance(verified, bool):
                raise TypeError("authoritative verifier must return a bool verification result")
            if not isinstance(verification, Mapping):
                raise TypeError("authoritative verifier must return a mapping of verification details")
            verification = dict(verification)
        except Exception as exc:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED", type(exc).__name__)
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": True, "receipt_matches_execution": True, "result": result, "verification_error": type(exc).__name__}, "Authoritative Blender verification failed closed")
        if not verified:
            if self._execution_journal is not None:
                self._execution_journal.complete(authorization, receipt, "BLOCKED")
            return BlenderLiveWriteOutcome.blocked({"receipt_authorized": True, "receipt_matches_execution": True, "result": result, **verification}, "Authoritative Blender state did not verify the requested write")
        if self._execution_journal is not None:
            self._execution_journal.complete(authorization, receipt, "VERIFIED")
        return BlenderLiveWriteOutcome.verified(receipt, {"receipt_authorized": True, "receipt_matches_execution": True, "result": result, **verification})
