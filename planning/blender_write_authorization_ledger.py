"""Single-use ledgers for authorization-bound Blender writes."""
import sqlite3
from threading import Lock
from typing import Set

from planning.blender_write_authorization import BlenderWriteAuthorization


class BlenderWriteAuthorizationLedger:
    """Track consumed authorization IDs for one running Atlas process."""

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


class SQLiteBlenderWriteAuthorizationLedger:
    """Persist single-use authorization consumption across process restarts."""

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise ValueError("database_path must be a non-empty string")
        self._lock = Lock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS blender_write_authorizations ("
            "authorization_id TEXT PRIMARY KEY, consumed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.commit()

    def consume(self, authorization: BlenderWriteAuthorization) -> bool:
        """Atomically persist authorization consumption; return False on replay."""
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        with self._lock:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO blender_write_authorizations (authorization_id) VALUES (?)",
                (authorization.authorization_id,),
            )
            self._connection.commit()
            return cursor.rowcount == 1

    def is_consumed(self, authorization: BlenderWriteAuthorization) -> bool:
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM blender_write_authorizations WHERE authorization_id = ? LIMIT 1",
                (authorization.authorization_id,),
            ).fetchone()
            return row is not None

    def close(self) -> None:
        with self._lock:
            self._connection.close()
