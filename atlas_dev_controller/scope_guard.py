"""Scope enforcement for the Atlas Development Controller.

The scope guard validates that every file path is within the approved set
before any operation proceeds. It fails closed on any violation.

Post-Aider enforcement detects actual Git working-tree changes (modified,
added, deleted, renamed) and rejects any path outside the approved scope.
"""

import os
import subprocess
from typing import List, Optional


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


# ---------------------------------------------------------------------------
# Post-Aider working-tree change detection
# ---------------------------------------------------------------------------

def detect_changed_files(repo_dir: Optional[str] = None) -> List[str]:
    """Return every file path changed in the Git working tree.

    Detects modified, added, deleted, and renamed files by combining:
    - ``git diff --name-only`` (tracked changes)
    - ``git ls-files --others --exclude-standard`` (untracked new files)

    Raises ``ScopeViolationError`` if git commands fail (fail-closed).
    """
    cwd = repo_dir or os.getcwd()
    changed: List[str] = []

    # Tracked changes: modified, deleted, renamed
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=30, cwd=cwd,
        )
        if result.returncode != 0:
            raise ScopeViolationError(
                f"git diff failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        for line in result.stdout.strip().splitlines():
            path = line.strip()
            if path:
                changed.append(path)
    except FileNotFoundError:
        raise ScopeViolationError("git is not available on PATH")
    except subprocess.TimeoutExpired:
        raise ScopeViolationError("git diff timed out")

    # Untracked new files
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=30, cwd=cwd,
        )
        if result.returncode != 0:
            raise ScopeViolationError(
                f"git ls-files failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        for line in result.stdout.strip().splitlines():
            path = line.strip()
            if path:
                changed.append(path)
    except FileNotFoundError:
        raise ScopeViolationError("git is not available on PATH")
    except subprocess.TimeoutExpired:
        raise ScopeViolationError("git ls-files timed out")

    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for p in changed:
        norm = normalize_path(p)
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def validate_post_aider_scope(
    allowed_files: List[str],
    repo_dir: Optional[str] = None,
) -> List[str]:
    """Detect working-tree changes and fail closed if any are outside scope.

    Returns the list of changed files for logging.
    Raises ``ScopeViolationError`` on the first out-of-scope path.
    """
    changed = detect_changed_files(repo_dir)
    if not changed:
        return changed

    allowed_normalized = {normalize_path(f) for f in allowed_files}
    for f in changed:
        if normalize_path(f) not in allowed_normalized:
            raise ScopeViolationError(
                f"Aider modified a file outside the approved scope: {f}"
            )
    return changed


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
