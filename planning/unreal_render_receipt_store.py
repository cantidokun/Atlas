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

    def _flush_parent_directory(self) -> None:
        """Persist the directory entry where the receipt replacement occurred.

        POSIX filesystems expose directory fsync for the rename durability
        boundary. Windows does not provide a portable directory-fsync API, so
        the flushed replacement file is the durability boundary there.
        """
        if os.name == "nt":
            return
        try:
            fd = os.open(str(self.path.parent), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def save(self, receipt: UnrealRenderReceipt) -> Dict[str, str]:
        if not isinstance(receipt, UnrealRenderReceipt):
            raise TypeError("receipt must be a UnrealRenderReceipt instance")
        envelope = {
            "version": self.VERSION,
            **receipt.snapshot(),
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
            self._flush_parent_directory()
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
        receipt_fields = {"job_id", "sequence_asset_path", "evidence_digest", "receipt_digest"}
        if set(envelope) != {"version", *receipt_fields}:
            raise RuntimeError("Unreal render receipt has invalid fields")
        try:
            snapshot = {field: envelope[field] for field in receipt_fields if field != "receipt_digest"}
            receipt = UnrealRenderReceipt.from_snapshot(snapshot)
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
            self._flush_parent_directory()
