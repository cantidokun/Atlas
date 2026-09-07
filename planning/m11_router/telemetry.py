"""Append-only, privacy-safe telemetry for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §11.

Telemetry is a durable append-only ledger (JSONL). Records are never mutated or
overwritten after creation; corrections/escalations write NEW records under the
same task_id with a fresh attempt_id.

Security (strict allow-list): a record that contains any protected token
(secret, API key, credential, ``attempt_nonce``, HMAC key, key material,
credential-bearing prompt) is REJECTED and DROPPED fail-closed — it is never
persisted.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from planning.m11_router.model_profile import ModelTier


# Substrings that, if present in any string value or key, cause fail-closed rejection.
SENSITIVE_SUBSTRINGS: tuple = (
    "attempt_nonce",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "hmac",
    "private_key",
    "token=",
    "password",
    "bearer ",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
)


class TelemetryValidationError(ValueError):
    """Raised when a telemetry record is invalid or contains a disallowed field."""


@dataclass(frozen=True)
class RouterTelemetryRecord:
    """Immutable, privacy-validated telemetry record (design §11)."""

    task_id: str
    attempt_id: str
    record_type: str = "attempt"  # "attempt" | "escalation" | "correction"
    escalation_id: Optional[str] = None
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    task_classes: frozenset = field(default_factory=frozenset)
    risk_dimension_scores: Mapping[str, int] = field(default_factory=dict)
    risk_tier: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_model: Optional[str] = None
    requested_token_budget: Optional[int] = None
    actual_token_usage: Optional[int] = None
    latency_ms: Optional[int] = None
    tool_call_count: Optional[int] = None
    correction_count: int = 0
    escalation_count: int = 0
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    build_result: Optional[str] = None
    static_result: Optional[str] = None
    contract_result: Optional[str] = None
    final_outcome: Optional[str] = None  # PASS/ESCALATED/BLOCKED/NEEDS_HUMAN_REVIEW/FAILED
    estimated_cost_usd: Optional[float] = None
    selection_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.task_id or not isinstance(self.task_id, str) or not self.task_id.strip():
            raise TelemetryValidationError("task_id must be a non-empty string")
        if not self.attempt_id or not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
            raise TelemetryValidationError("attempt_id must be a non-empty string")
        if self.escalation_id is not None and (
            not isinstance(self.escalation_id, str) or not self.escalation_id.strip()
        ):
            raise TelemetryValidationError("escalation_id must be a non-empty string")
        if self.record_type not in ("attempt", "escalation", "correction"):
            raise TelemetryValidationError(f"invalid record_type: {self.record_type}")
        # Strict allow-list: reject any protected token anywhere in the payload.
        if _contains_sensitive(asdict(self)):
            raise TelemetryValidationError(
                "record contains a disallowed sensitive field; dropped fail-closed"
            )


def _contains_sensitive(payload: Any) -> bool:
    def walk(value: Any) -> bool:
        if isinstance(value, str):
            low = value.lower()
            return any(s.lower() in low for s in SENSITIVE_SUBSTRINGS)
        if isinstance(value, Mapping):
            if any(
                any(s.lower() in str(k).lower() for s in SENSITIVE_SUBSTRINGS) for k in value
            ):
                return True
            return any(walk(v) for v in value.values())
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(walk(v) for v in value)
        return False

    return walk(payload)


def _record_from_dict(raw: Mapping[str, Any]) -> RouterTelemetryRecord:
    """Rebuild an immutable record from a decoded JSON dict (for read-back)."""
    try:
        return RouterTelemetryRecord(
            task_id=str(raw["task_id"]),
            attempt_id=str(raw["attempt_id"]),
            record_type=str(raw.get("record_type", "attempt")),
            escalation_id=raw.get("escalation_id"),
            task_classes=frozenset(raw.get("task_classes") or ()),
            risk_dimension_scores=dict(raw.get("risk_dimension_scores") or {}),
            risk_tier=raw.get("risk_tier"),
            selected_provider=raw.get("selected_provider"),
            selected_model=raw.get("selected_model"),
            requested_token_budget=raw.get("requested_token_budget"),
            actual_token_usage=raw.get("actual_token_usage"),
            latency_ms=raw.get("latency_ms"),
            tool_call_count=raw.get("tool_call_count"),
            correction_count=int(raw.get("correction_count", 0)),
            escalation_count=int(raw.get("escalation_count", 0)),
            tests_passed=raw.get("tests_passed"),
            tests_failed=raw.get("tests_failed"),
            build_result=raw.get("build_result"),
            static_result=raw.get("static_result"),
            contract_result=raw.get("contract_result"),
            final_outcome=raw.get("final_outcome"),
            estimated_cost_usd=raw.get("estimated_cost_usd"),
            selection_reason=raw.get("selection_reason"),
        )
    except (KeyError, TypeError, ValueError):
        raise TelemetryValidationError("malformed telemetry record") from None


class AppendOnlyTelemetry:
    """A durable, append-only, thread-safe telemetry ledger (JSONL file)."""

    def __init__(self, path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: RouterTelemetryRecord) -> None:
        if not isinstance(record, RouterTelemetryRecord):
            raise TelemetryValidationError("only RouterTelemetryRecord may be appended")
        line = json.dumps(asdict(record), sort_keys=True, default=str) + "\n"
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line)
                    fh.flush()
            except OSError as exc:
                raise TelemetryValidationError(
                    f"telemetry write failed (state is UNKNOWN; fail closed): {exc}"
                ) from exc

    def read_all(self) -> List[RouterTelemetryRecord]:
        with self._lock:
            return self._read_lines()

    def read_task(self, task_id: str) -> List[RouterTelemetryRecord]:
        with self._lock:
            return [r for r in self._read_lines() if r.task_id == task_id]

    def _read_lines(self) -> List[RouterTelemetryRecord]:
        if not self._path.is_file():
            return []
        records: List[RouterTelemetryRecord] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    records.append(_record_from_dict(raw))
                except (TelemetryValidationError, KeyError):
                    continue
        return records

    def count(self) -> int:
        return len(self.read_all())