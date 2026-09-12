"""Minimum-sufficient repository context compilation for Atlas development models."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights, rank_repository_files


DEFAULT_MAX_CONTEXT_CHARS = 48_000
DEFAULT_MAX_FILE_CHARS = 16_000
DEFAULT_MIN_SCORE = 1
SENSITIVE_PATH_MARKERS = frozenset({".env", ".pem", ".key", ".p12", ".pfx", "credentials", "secrets", "secret"})


@dataclass(frozen=True)
class ContextFile:
    path: str
    score: int
    reasons: tuple[str, ...]
    content: str
    truncated: bool = False


@dataclass(frozen=True)
class ContextPackage:
    """Deterministic model context plus its selection manifest."""
    query: RelevanceQuery
    repository_fingerprint: str
    included: tuple[ContextFile, ...]
    excluded_paths: tuple[str, ...]
    stable_instructions: str
    dynamic_state: dict
    fingerprint: str
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS
    max_file_chars: int = DEFAULT_MAX_FILE_CHARS

    def to_dict(self) -> dict:
        return {
            "query": {"text": self.query.text, "paths": list(self.query.paths), "symbols": list(self.query.symbols), "task_classes": list(self.query.task_classes), "contract_paths": list(self.query.contract_paths), "test_paths": list(self.query.test_paths), "recent_paths": list(self.query.recent_paths)},
            "repository_fingerprint": self.repository_fingerprint,
            "included": [{"path": item.path, "score": item.score, "reasons": list(item.reasons), "content": item.content, "truncated": item.truncated} for item in self.included],
            "excluded_paths": list(self.excluded_paths), "stable_instructions": self.stable_instructions, "dynamic_state": dict(self.dynamic_state), "fingerprint": self.fingerprint, "selection_fingerprint": self.selection_fingerprint, "max_context_chars": self.max_context_chars, "max_file_chars": self.max_file_chars,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @property
    def context_chars(self) -> int:
        return sum(len(item.content) for item in self.included)

    @property
    def selection_fingerprint(self) -> str:
        selection = {"repository_fingerprint": self.repository_fingerprint, "query": {"text": self.query.text, "paths": list(self.query.paths), "symbols": list(self.query.symbols), "task_classes": list(self.query.task_classes), "contract_paths": list(self.query.contract_paths), "test_paths": list(self.query.test_paths), "recent_paths": list(self.query.recent_paths)}, "included": [(item.path, item.score, item.reasons, item.truncated) for item in self.included], "excluded_paths": list(self.excluded_paths), "max_context_chars": self.max_context_chars, "max_file_chars": self.max_file_chars}
        return hashlib.sha256(json.dumps(selection, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def compile_context(index: RepositoryIndex, query: RelevanceQuery, source_by_path: Mapping[str, str], *, stable_instructions: str = "", dynamic_state: Mapping[str, object] | None = None, max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS, max_file_chars: int = DEFAULT_MAX_FILE_CHARS, minimum_score: int = DEFAULT_MIN_SCORE, weights: RelevanceWeights = RelevanceWeights()) -> ContextPackage:
    if not isinstance(stable_instructions, str):
        raise TypeError("stable_instructions must be a string")
    if max_context_chars <= 0 or max_file_chars <= 0:
        raise ValueError("context limits must be positive")
    if minimum_score < 0:
        raise ValueError("minimum_score must be non-negative")

    ranking = rank_repository_files(index, query, weights=weights)
    records = {item["path"]: item for item in index.files}
    included: list[ContextFile] = []
    excluded: set[str] = set()
    remaining = max_context_chars

    # Selection is staged so explicit intent is protected, structural context
    # is expanded next, and secondary signals get a bounded coverage pass before
    # ordinary score ordering fills the remaining budget.
    anchor_paths = _explicit_anchor_paths(ranking.explanations, query)
    anchors = [item for item in ranking.explanations if item.path in anchor_paths]
    structural = [item for item in ranking.explanations if item.path not in anchor_paths and "direct_dependency" in item.reasons]
    secondary = [item for item in ranking.explanations if item.path not in anchor_paths and item not in structural]
    coverage = _coverage_candidates(secondary)
    coverage_paths = {item.path for item in coverage}
    secondary_remainder = [item for item in secondary if item.path not in coverage_paths]
    ordered = anchors + structural + coverage + secondary_remainder

    for explanation in ordered:
        path = explanation.path
        if explanation.score < minimum_score or _sensitive_path(path) or path not in source_by_path:
            excluded.add(path)
            continue
        source = source_by_path[path]
        if not isinstance(source, str) or not source:
            excluded.add(path)
            continue
        content, truncated = _bounded_source(source, min(max_file_chars, remaining))
        if not content:
            excluded.add(path)
            continue
        included.append(ContextFile(path, explanation.score, explanation.reasons, content, truncated))
        remaining -= len(content)
        if remaining <= 0:
            break

    selected = {item.path for item in included}
    excluded.update(path for path in records if path not in selected)
    excluded.update(path for path in source_by_path if path not in records)
    stable = stable_instructions
    dynamic = dict(dynamic_state or {})
    manifest = {"repository_fingerprint": index.fingerprint, "included": [item.path for item in included], "excluded": sorted(excluded), "max_context_chars": max_context_chars, "max_file_chars": max_file_chars, "minimum_score": minimum_score, "weights": weights.__dict__}
    fingerprint = hashlib.sha256(json.dumps({"manifest": manifest, "stable_instructions": stable, "dynamic_state": dynamic, "content": [(item.path, item.content) for item in included]}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return ContextPackage(query, index.fingerprint, tuple(included), tuple(sorted(excluded)), stable, dynamic, fingerprint, max_context_chars, max_file_chars)


def _explicit_anchor_paths(explanations: tuple, query: RelevanceQuery) -> set[str]:
    """Resolve the query's explicit context associations to indexed paths."""
    anchors = set(query.paths) | set(query.contract_paths) | set(query.test_paths) | set(query.recent_paths)
    for explanation in explanations:
        if "exact_symbol" in explanation.reasons:
            anchors.add(explanation.path)
    return anchors


def _coverage_candidates(explanations: list) -> list:
    """Select one deterministic representative for each available secondary signal."""
    signal_order = (
        "reverse_dependency",
        "test_association",
        "contract_association",
        "recent_change",
        "lexical_match",
        "same_directory",
    )
    selected: list = []
    selected_paths: set[str] = set()
    for signal in signal_order:
        candidates = [item for item in explanations if signal in item.reasons and item.path not in selected_paths]
        if not candidates:
            continue
        candidate = candidates[0]
        selected.append(candidate)
        selected_paths.add(candidate.path)
    return selected


def _bounded_source(source: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(source)
    if len(source) <= limit:
        return source, False
    boundary = source.rfind("\n", 0, limit + 1)
    if boundary > 0:
        return source[:boundary], True
    return source[:limit], True


def _sensitive_path(path: str) -> bool:
    lowered = path.lower()
    parts = lowered.split("/")
    name = parts[-1]
    if name == ".env" or name.startswith(".env."):
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx")):
        return True
    return any(part in SENSITIVE_PATH_MARKERS for part in parts) or name.startswith(("secret", "credential"))


def is_sensitive_context_path(path: str) -> bool:
    return _sensitive_path(path)
