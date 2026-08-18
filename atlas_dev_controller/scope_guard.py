"""Scope enforcement for the Atlas Development Controller.

The scope guard validates that every file path is within the approved set
before any operation proceeds. It fails closed on any violation.

Post-Aider enforcement detects actual Git working-tree changes (modified,
added, deleted, renamed) and rejects any path outside the approved scope.

Aider's own runtime artifacts (``.aider.chat.history.md``,
``.aider.input.history``, ``.aider.tags.cache.v4/``) are excluded from
scope-violation checks so they never cause false-positive failures during
autonomous runs.  Arbitrary other files still fail closed.
"""

import os
import subprocess
from typing import FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Aider runtime artifact patterns (fail-open only for these exact names)
# ---------------------------------------------------------------------------

AIDER_RUNTIME_ARTIFACTS: FrozenSet[str] = frozenset(
    {
        ".aider.chat.history.md",
        ".aider.input.history",
    }
)

AIDER_RUNTIME_DIRECTORY_PREFIXES: FrozenSet[str] = frozenset(
    {
        ".aider.tags.cache.v4/",
        ".aider.tags.cache.v4\\",
    }
)


def is_aider_runtime_artifact(path: str) -> bool:
    """Return True when *path* is a known Aider runtime artifact.

    Only the exact file names and the ``.aider.tags.cache.v4/`` directory
    tree are recognised.  Everything else is treated as production content
    and must pass normal scope validation.
    """
    norm = path.replace("\\", "/").strip("/")
    basename = norm.rsplit("/", 1)[-1] if "/" in norm else norm

    # Exact file-name match (may appear at repo root or nested)
    if basename in AIDER_RUNTIME_ARTIFACTS:
        return True

    # Directory prefix match for the tags-cache tree
    for prefix in (".aider.tags.cache.v4/",):
        if norm == prefix.rstrip("/") or norm.startswith(prefix) or ("/" + prefix) in ("/" + norm):
            # Check if any path component matches
            parts = norm.split("/")
            for i, part in enumerate(parts):
                if part == ".aider.tags.cache.v4":
                    return True

    return False


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

def capture_baseline_changes(repo_dir: Optional[str] = None) -> FrozenSet[str]:
    """Capture the current set of changed files as a baseline.
    
    Returns a frozen set of normalized file paths that are already changed
    before Aider runs. This baseline is used to distinguish pre-existing
    changes from new changes introduced by Aider.
    
    Raises ``ScopeViolationError`` if git commands fail (fail-closed).
    """
    changed_files = detect_changed_files(repo_dir)
    return frozenset(normalize_path(f) for f in changed_files)


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
    baseline_changes: Optional[FrozenSet[str]] = None,
    repo_dir: Optional[str] = None,
) -> List[str]:
    """Detect working-tree changes and fail closed if any NEW changes are outside scope.

    Only changes introduced since the baseline are validated against allowed_files.
    Pre-existing changes (in baseline_changes) are ignored to avoid false positives
    for files that were already modified before Aider ran.

    Aider runtime artifacts are silently excluded — they are expected side
    effects of every Aider invocation and must never trigger a scope
    violation.

    Parameters
    ----------
    allowed_files : List[str]
        Files that Aider is authorized to modify
    baseline_changes : Optional[FrozenSet[str]]
        Normalized paths of files that were already changed before Aider ran.
        If None, defaults to empty set (all changes are considered new).
    repo_dir : Optional[str]
        Repository directory for git commands

    Returns
    -------
    List[str]
        The list of *production* changed files (artifacts excluded) for logging.
        
    Raises
    ------
    ScopeViolationError
        On the first out-of-scope production path that is NEW (not in baseline).
    """
    raw_changed = detect_changed_files(repo_dir)
    if not raw_changed:
        return raw_changed

    # Partition into artifacts vs. production changes
    production_changed: List[str] = []
    for f in raw_changed:
        if not is_aider_runtime_artifact(f):
            production_changed.append(f)

    if not production_changed:
        return production_changed

    # Use empty baseline if none provided (backward compatibility)
    if baseline_changes is None:
        baseline_changes = frozenset()

    # Only validate NEW changes (not in baseline) against allowed_files
    allowed_normalized = {normalize_path(f) for f in allowed_files}
    new_changes: List[str] = []
    
    for f in production_changed:
        f_normalized = normalize_path(f)
        if f_normalized not in baseline_changes:
            # This is a NEW change introduced by Aider
            new_changes.append(f)
            if f_normalized not in allowed_normalized:
                raise ScopeViolationError(
                    f"Aider modified a file outside the approved scope: {f}"
                )
    
    return production_changed


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
