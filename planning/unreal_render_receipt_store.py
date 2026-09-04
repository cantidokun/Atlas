"""Atomic persistence for immutable Unreal render receipts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Union

from planning.unreal_render_receipt import UnrealRenderReceipt


class UnrealRenderReceiptStore:
    """Persist and restore render receipts with fail-closed validation."""

    VERSION = 1

    def __init__(self, path: Union[str, os.PathLike]):
        self.path = Path(path)

    def save(self, receipt: UnrealRenderReceipt) -> Dict[str, str]:
        if not isinstance(receipt, UnrealRenderReceipt):
            raise TypeError("receipt must be a UnrealRenderReceipt instance")
        envelope = {
            "version": self.VERSION,
            "job_id": receipt.job_id,
            "sequence_asset_path": receipt.sequence_asset_path,
            "evidence_digest": receipt.evidence_digest,
            "receipt_digest": receipt.receipt_digest,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(envelope, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return envelope

    def load(self) -> UnrealRenderReceipt:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                envelope = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Unreal render receipt is unreadable") from exc
        if not isinstance(envelope, dict):
            raise RuntimeError("Unreal render receipt is not an object")
        if envelope.get("version") != self.VERSION:
            raise RuntimeError("Unsupported or invalid Unreal render receipt version")
        required = {"job_id", "sequence_asset_path", "evidence_digest", "receipt_digest"}
        if set(envelope) != {"version", *required}:
            raise RuntimeError("Unreal render receipt has invalid fields")
        try:
            receipt = UnrealRenderReceipt(
                job_id=envelope["job_id"],
                sequence_asset_path=envelope["sequence_asset_path"],
                evidence_digest=envelope["evidence_digest"],
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Unreal render receipt contains invalid identity data") from exc
        if receipt.receipt_digest != envelope["receipt_digest"]:
            raise RuntimeError("Unreal render receipt digest is inconsistent")
        return receipt

    def exists(self) -> bool:
        return self.path.is_file()

    def delete(self) -> None:
        if self.path.exists():
            self.path.unlink()
