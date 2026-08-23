"""Integrity guard for receipts produced by autonomous corrective execution."""
from __future__ import annotations

from typing import Any


def require_bound_receipt(executor: Any, tool: str, arguments: dict[str, Any]) -> Any:
    """Return the executor's retained receipt only when it binds this request."""
    if not executor.receipt_matches_last_execution(tool, arguments):
        raise RuntimeError("corrective execution receipt does not bind the requested action")
    receipt = executor.last_receipt
    if receipt is None:
        raise RuntimeError("corrective execution completed without a receipt")
    return receipt
