"""Deterministic structural repository index for Atlas development tooling.

This module is deliberately read-only and development-only. It discovers source
files, Python symbols, imports, test files, and optional Git revision/history
metadata. It has no imports from production execution or authorization paths.

The index is an information source for later context compilation; it is not an
execution, authorization, recovery, receipt, scheduler, or evidence authority.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_IGNORED_DIRS = frozenset({".git", ".hg", ".svn", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"})
PYTHON_SUFFIXES = frozenset({".py", ".pyi"})
CONTENT_TERM_LIMIT = 512
CONTENT_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
SENSITIVE_PATH_MARKERS = frozenset({".env", ".pem", ".key", ".p12", ".pfx", "credentials", "secrets", "secret"})
SENSITIVE_FILENAME_PREFIXES = ("secret", "credential")
CONTENT_STOP_WORDS = frozenset({"and", "are", "but", "for", "from", "has", "have", "into", "not", "only", "that", "the", "their", "then", "this", "these", "those", "with", "when", "where", "which", "while", "will", "would", "you"})

@dataclass(frozen=True)
class SymbolRecord:
    path: str
    qualified_name: str
    kind: str
    line: int
    end_line: int
    parent: Optional[str] = None

@dataclass(frozen=True)
class ImportRecord:
    path: str
    module: str
    imported_name: Optional[str]
    alias: Optional[str]
    level: int
    resolved_path: Optional[str] = None

@dataclass(frozen=True)
class GitHistory:
    revision: Optional[str]
    recent_commits: tuple[str, ...]

@dataclass(frozen=True)
class RepositoryIndex:
    root: str
    files: tuple[dict, ...]
    symbols: tuple[SymbolRecord, ...]
    imports: tuple[ImportRecord, ...]
    git: GitHistory
    fingerprint: str

    def to_dict(self) -> dict:
        return {"root": self.root, "files": list(self.files), "symbols": [asdict(item) for item in self.symbols], "imports": [asdict(item) for item in self.imports], "git": asdict(self.git), "fingerprint": self.fingerprint}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

def build_repository_index(root: str | Path, *, ignored_dirs: Iterable[str] = DEFAULT_IGNORED_DIRS, include_git_history: bool = True, history_limit: int = 20) -> RepositoryIndex:
    """Build a deterministic index of a repository tree."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    ignored = frozenset(ignored_dirs)
    files: list[dict] = []
    symbols: list[SymbolRecord] = []
    imports: list[ImportRecord] = []
    for path in _iter_files(root_path, ignored):
        rel = path.relative_to(root_path).as_posix()
        raw = path.read_bytes()
        text = _decode_text(raw)
        suffix = path.suffix.lower()
        is_python = suffix in PYTHON_SUFFIXES
        record = {"path": rel, "kind": _file_kind(path, is_python), "language": "python" if is_python else "text", "size_bytes": len(raw), "line_count": text.count("\n") + (1 if text else 0), "sha256": hashlib.sha256(raw).hexdigest(), "is_test": _is_test_path(rel), "parse_status": "not_applicable", "content_terms": _content_terms(rel, text)}
        if is_python:
            record["parse_status"] = "ok"
            try:
                tree = ast.parse(text, filename=rel)
            except (SyntaxError, ValueError, TypeError, UnicodeError):
                record["parse_status"] = "error"
            else:
                file_symbols, file_imports = _extract_python_structure(tree, rel, root_path)
                symbols.extend(file_symbols)
                imports.extend(file_imports)
        files.append(record)
    files.sort(key=lambda item: item["path"])
    symbols.sort(key=lambda item: (item.path, item.line, item.qualified_name, item.kind))
    imports.sort(key=lambda item: (item.path, item.level, item.module, item.imported_name or "", item.alias or "", item.resolved_path or ""))
    git = _git_history(root_path, history_limit) if include_git_history else GitHistory(None, ())
    payload = {"root": ".", "files": files, "symbols": [asdict(item) for item in symbols], "imports": [asdict(item) for item in imports], "git": asdict(git)}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RepositoryIndex(".", tuple(files), tuple(symbols), tuple(imports), git, fingerprint)

def _iter_files(root: Path, ignored: frozenset[str]) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in ignored for part in relative_parts):
            continue
        yield path

def _decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return ""

def _content_terms(rel: str, text: str) -> tuple[str, ...]:
    if not text or _is_sensitive_path(rel):
        return ()
    terms = {token.lower() for token in CONTENT_TOKEN_RE.findall(text) if len(token) >= 3 and token.lower() not in CONTENT_STOP_WORDS}
    return tuple(sorted(terms)[:CONTENT_TERM_LIMIT])

def _is_sensitive_path(rel: str) -> bool:
    path = Path(rel)
    if {part.lower() for part in path.parts} & SENSITIVE_PATH_MARKERS:
        return True
    return path.name.lower().startswith(SENSITIVE_FILENAME_PREFIXES)

def _file_kind(path: Path, is_python: bool) -> str:
    if is_python:
        return "python_source"
    if path.suffix.lower() in {".md", ".rst", ".txt"}:
        return "documentation"
    if path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini"}:
        return "configuration"
    return "file"

def _is_test_path(rel: str) -> bool:
    path = Path(rel)
    return path.name.startswith("test_") or path.name.endswith("_test.py") or "tests" in path.parts

def _extract_python_structure(tree: ast.AST, rel: str, root: Path) -> tuple[list[SymbolRecord], list[ImportRecord]]:
    symbols: list[SymbolRecord] = []
    imports: list[ImportRecord] = []
    def visit_body(body: list[ast.stmt], parent: Optional[str] = None) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                qualified = f"{parent}.{node.name}" if parent else node.name
                symbols.append(SymbolRecord(rel, qualified, kind, node.lineno, getattr(node, "end_lineno", node.lineno), parent))
                visit_body(node.body, qualified)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportRecord(rel, alias.name, None, alias.asname, 0, _resolve_import(root, alias.name, 0)))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(ImportRecord(rel, module, alias.name, alias.asname, node.level, _resolve_from_import(root, rel, module, node.level)))
    visit_body(tree.body)
    return symbols, imports

def _resolve_import(root: Path, module: str, level: int) -> Optional[str]:
    if level or not module:
        return None
    return _module_to_path(root, module.split("."))

def _resolve_from_import(root: Path, rel: str, module: str, level: int) -> Optional[str]:
    if level == 0:
        return _module_to_path(root, module.split(".")) if module else None
    base = Path(rel).parent
    for _ in range(max(level - 1, 0)):
        base = base.parent
    parts = [part for part in base.parts if part not in {".", ""}]
    if module:
        parts.extend(module.split("."))
    return _parts_to_repo_path(root, parts)

def _module_to_path(root: Path, parts: list[str]) -> Optional[str]:
    return _parts_to_repo_path(root, parts)

def _parts_to_repo_path(root: Path, parts: list[str]) -> Optional[str]:
    if not parts:
        return None
    candidate = root.joinpath(*parts)
    for path in (candidate.with_suffix(".py"), candidate / "__init__.py"):
        if path.is_file():
            return path.relative_to(root).as_posix()
    return None

def _git_history(root: Path, limit: int) -> GitHistory:
    if limit <= 0:
        return GitHistory(None, ())
    try:
        revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=5).stdout.strip()
        commits = subprocess.run(["git", "-C", str(root), "log", f"-{limit}", "--format=%H"], check=True, capture_output=True, text=True, timeout=5).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return GitHistory(None, ())
    return GitHistory(revision or None, tuple(item.strip() for item in commits if item.strip()))
