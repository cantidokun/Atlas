"""Scope enforcement for the Atlas Development Controller.

The scope guard validates that every file path is within the approved set
before any operation proceeds. It fails closed on any violation.
"""

import os
from typing import List


class ScopeViolationError(RuntimeError):
    """Raised when an operation references a file outside the approved scope."""


def normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison."""
    return os.path.normpath(path).replace("\\", "/").lower()


def validate_file_scope(files: List[str], allowed_files: List[str]) -> None:
    """Ensure every file is in the allowed set.

    Raises ``ScopeViolationError`` on the first violation.
    """
    allowed_normalized = {normalize_path(f) for f in allowed_files}
    for f in files:
        if normalize_path(f) not in allowed_normalized:
            raise ScopeViolationError(
                f"file is outside the approved scope: {f}"
            )


def validate_command_scope(command: str, allowed_commands: List[str]) -> None:
    """Ensure a command is in the approved set.

    Comparison is exact after stripping whitespace.
    Raises ``ScopeViolationError`` on any unapproved command.
    """
    stripped = command.strip()
    allowed_stripped = {cmd.strip() for cmd in allowed_commands}
    if stripped not in allowed_stripped:
        raise ScopeViolationError(
            f"command is not in the approved set: {command}"
        )
    # Double-check: never allow push or commit regardless of approved list
    lower = stripped.lower()
    if "git push" in lower or "git commit" in lower:
        raise ScopeViolationError(
            f"git push/commit commands are never allowed: {command}"
        )
