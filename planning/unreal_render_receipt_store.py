"""Atomic persistence for immutable Unreal render receipts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict

from planning.unreal_render_receipt import UnrealRenderReceipt


class UnrealRenderReceiptStore:
    """Persist and restore render receipts with fail-closed validation."""

    VERSION = 1

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def save(self, receipt: UnrealRenderReceipt) -> Dict[str, object]:
        if not isinstance(receipt, UnrealRenderReceipt):
            raise TypeError("receipt must be a UnrealRenderReceipt instance")

        envelope = {
            "version": self.VERSION,
            **receipt.snapshot(),
            "receipt_digest": receipt.receipt_digest,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    envelope,
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                )
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
            raise RuntimeError(
                "Unreal render receipt is unreadable"
            ) from exc

        if not isinstance(envelope, dict):
            raise RuntimeError("Unreal render receipt is not an object")

        if envelope.get("version") != self.VERSION:
            raise RuntimeError(
                "Unsupported or invalid Unreal render receipt version"
            )

        receipt_fields = set(envelope) - {"version", "receipt_digest"}
        if receipt_fields not in (
            {"job_id", "sequence_asset_path", "evidence_digest"},
            {
                "job_id",
                "sequence_asset_path",
                "evidence_digest",
                "start_frame",
                "end_frame",
                "output_directory",
                "output_format",
            },
        ):
            raise RuntimeError(
                "Unreal render receipt has invalid fields"
            )

        try:
            receipt = UnrealRenderReceipt.from_snapshot(
                {key: envelope[key] for key in receipt_fields}
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Unreal render receipt contains invalid identity data"
            ) from exc

        if receipt.receipt_digest != envelope["receipt_digest"]:
            raise RuntimeError(
                "Unreal render receipt digest is inconsistent"
            )

        return receipt

    def exists(self) -> bool:
        return self.path.is_file()

    def delete(self) -> None:
        if self.path.exists():
            self.path.unlink()
