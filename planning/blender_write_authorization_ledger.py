"""Single-use ledger for authorization-bound Blender writes."""
from threading import Lock
from typing import Set

from planning.blender_write_authorization import BlenderWriteAuthorization


class BlenderWriteAuthorizationLedger:
    """Track authorization IDs that have already been consumed.

    The ledger is deliberately separate from the immutable authorization object:
    authorization snapshots remain auditable while the ledger supplies runtime
    single-use semantics.
    """

    def __init__(self) -> None:
        self._consumed: Set[str] = set()
        self._lock = Lock()

    def consume(self, authorization: BlenderWriteAuthorization) -> bool:
        """Atomically consume an authorization; return False if already consumed."""
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        authorization_id = authorization.authorization_id
        with self._lock:
            if authorization_id in self._consumed:
                return False
            self._consumed.add(authorization_id)
            return True

    def is_consumed(self, authorization: BlenderWriteAuthorization) -> bool:
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        with self._lock:
            return authorization.authorization_id in self._consumed
