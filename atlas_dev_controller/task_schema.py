"""Task file schema and validation for the Atlas Development Controller.

A task file is a JSON document that declares exactly:
- which files Aider is allowed to edit
- which test commands are approved to run
- the Aider prompt message

The controller refuses to operate without a valid task file.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class TaskValidationError(ValueError):
    """Raised when a task file is invalid or violates scope constraints."""


@dataclass(frozen=True)
class AtlasTask:
    """One validated, immutable development task."""

    task_id: str
    message: str
    allowed_files: List[str]
    allowed_test_commands: List[str]
    read_only_files: List[str] = field(default_factory=list)
    model: str = "gpt-4o"

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise TaskValidationError("task_id must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise TaskValidationError("message must be a non-empty string")
        if not isinstance(self.allowed_files, list) or not self.allowed_files:
            raise TaskValidationError("allowed_files must be a non-empty list")
        for f in self.allowed_files:
            if not isinstance(f, str) or not f.strip():
                raise TaskValidationError("allowed_files must contain only non-empty strings")
        if not isinstance(self.allowed_test_commands, list) or not self.allowed_test_commands:
            raise TaskValidationError("allowed_test_commands must be a non-empty list")
        for cmd in self.allowed_test_commands:
            if not isinstance(cmd, str) or not cmd.strip():
                raise TaskValidationError("allowed_test_commands must contain only non-empty strings")
        # Validate read_only_files
        if not isinstance(self.read_only_files, list):
            raise TaskValidationError("read_only_files must be a list")
        for f in self.read_only_files:
            if not isinstance(f, str) or not f.strip():
                raise TaskValidationError("read_only_files must contain only non-empty strings")
        # Fail closed: no overlap between editable and read-only files
        overlap = set(self.allowed_files) & set(self.read_only_files)
        if overlap:
            raise TaskValidationError(
                f"read_only_files must not overlap with allowed_files: {sorted(overlap)}"
            )
        # Fail closed: no push/commit commands allowed
        for cmd in self.allowed_test_commands:
            lower = cmd.lower()
            if "git push" in lower or "git commit" in lower:
                raise TaskValidationError(
                    f"test commands must not contain git push or commit: {cmd}"
                )


def load_task(path: str) -> AtlasTask:
    """Load and validate a task file from disk.

    Fails closed on missing file, invalid JSON, or schema violations.
    """
    task_path = Path(path)
    if not task_path.is_file():
        raise TaskValidationError(f"task file does not exist: {path}")

    try:
        raw = task_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TaskValidationError(f"cannot read task file: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TaskValidationError(f"task file is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise TaskValidationError("task file must be a JSON object")

    required_keys = {"task_id", "message", "allowed_files", "allowed_test_commands"}
    missing = required_keys - set(data.keys())
    if missing:
        raise TaskValidationError(f"task file missing required keys: {sorted(missing)}")

    return AtlasTask(
        task_id=data["task_id"],
        message=data["message"],
        allowed_files=data["allowed_files"],
        allowed_test_commands=data["allowed_test_commands"],
        read_only_files=data.get("read_only_files", []),
        model=data.get("model", "gpt-4o"),
    )
