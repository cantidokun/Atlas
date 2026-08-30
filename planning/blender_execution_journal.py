"""Durable execution journal for authorization-bound Blender writes."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Mapping, Optional

from planning.action_plan import ActionSpec
from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_write_authorization import BlenderWriteAuthorization


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SQLiteBlenderExecutionJournal:
    """Persist write attempts so interrupted execution can be reconciled safely."""

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise ValueError("database_path must be a non-empty string")
        self._lock = Lock()
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS blender_execution_journal ("
            "authorization_id TEXT PRIMARY KEY, tool TEXT NOT NULL, "
            "arguments_digest TEXT NOT NULL, arguments_json TEXT, authorization_json TEXT, "
            "status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, "
            "receipt_digest TEXT, outcome_status TEXT, error_type TEXT)"
        )
        self._ensure_column("arguments_json", "TEXT")
        self._ensure_column("authorization_json", "TEXT")
        self._connection.commit()

    def _ensure_column(self, name: str, column_type: str) -> None:
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(blender_execution_journal)")}
        if name not in columns:
            self._connection.execute(f"ALTER TABLE blender_execution_journal ADD COLUMN {name} {column_type}")

    def begin(self, action: ActionSpec, authorization: BlenderWriteAuthorization) -> bool:
        """Record an execution attempt; return False when authorization is already journaled."""
        if not isinstance(action, ActionSpec):
            raise TypeError("action must be an ActionSpec")
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        if not authorization.matches(action):
            raise ValueError("authorization does not match action")
        with self._lock:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO blender_execution_journal "
                "(authorization_id, tool, arguments_digest, arguments_json, authorization_json, status, started_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    authorization.authorization_id,
                    action.tool,
                    _digest(action.arguments),
                    json.dumps(action.arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                    json.dumps(authorization.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                    "STARTED",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._connection.commit()
            return cursor.rowcount == 1

    def complete(self, authorization: BlenderWriteAuthorization, receipt: Optional[BlenderExecutionReceipt], outcome_status: str, error_type: Optional[str] = None) -> None:
        """Finalize an execution attempt without changing its authorization identity."""
        if not isinstance(authorization, BlenderWriteAuthorization):
            raise TypeError("authorization must be BlenderWriteAuthorization")
        if not isinstance(outcome_status, str) or not outcome_status.strip():
            raise ValueError("outcome_status must be a non-empty string")
        if receipt is not None and not isinstance(receipt, BlenderExecutionReceipt):
            raise TypeError("receipt must be a BlenderExecutionReceipt or None")
        with self._lock:
            self._connection.execute(
                "UPDATE blender_execution_journal SET status = ?, completed_at = ?, receipt_digest = ?, outcome_status = ?, error_type = ? WHERE authorization_id = ?",
                ("COMPLETED", datetime.now(timezone.utc).isoformat(), None if receipt is None else receipt.result_digest, outcome_status, error_type, authorization.authorization_id),
            )
            self._connection.commit()

    def get(self, authorization_id: str) -> Optional[Mapping[str, Any]]:
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise ValueError("authorization_id must be a non-empty string")
        with self._lock:
            row = self._connection.execute(
                "SELECT authorization_id, tool, arguments_digest, arguments_json, authorization_json, status, started_at, completed_at, receipt_digest, outcome_status, error_type FROM blender_execution_journal WHERE authorization_id = ?",
                (authorization_id.strip(),),
            ).fetchone()
        if row is None:
            return None
        keys = ("authorization_id", "tool", "arguments_digest", "arguments_json", "authorization_json", "status", "started_at", "completed_at", "receipt_digest", "outcome_status", "error_type")
        record = dict(zip(keys, row))
        if record["arguments_json"] is not None:
            record["arguments"] = json.loads(record["arguments_json"])
        if record["authorization_json"] is not None:
            record["authorization"] = json.loads(record["authorization_json"])
        return record

    def close(self) -> None:
        with self._lock:
            self._connection.close()
