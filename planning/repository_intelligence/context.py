"""Minimum-sufficient repository context compilation for Atlas development models."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights, RelevanceExplanation, rank_repository_files

DEFAULT_MAX_CONTEXT_CHARS = 32_000
DEFAULT_MAX_FILE_CHARS = 12_000
DEFAULT_MIN_SCORE = 1
SECONDARY_MIN_SCORE = 35
STRUCTURAL_MAX_FILES = 6
SECONDARY_MAX_FILES = 8
SENSITIVE_PATH_MARKERS = frozenset({".env", ".pem", ".key", ".p12", ".pfx", "credentials", "secrets", "secret"})
SECONDARY_CONTEXT_RESERVE_RATIO = 0.25
SECONDARY_COVERAGE_PER_SIGNAL = 1
SECONDARY_COVERAGE_FILE_RATIO = 0.5
SECONDARY_COVERAGE_SIGNAL_SLOTS = 6
SECONDARY_SNIPPET_CONTEXT_LINES = 1
SECONDARY_SNIPPET_HEADER_LINES = 3
_CONTENT_TERM_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")

@dataclass(frozen=True)
class ContextFile:
    path: str
    score: int
    reasons: tuple[str, ...]
    content: str
    truncated: bool = False

@dataclass(frozen=True)
class ContextPackage:
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
        return {"query": {"text": self.query.text, "paths": list(self.query.paths), "symbols": list(self.query.symbols), "task_classes": list(self.query.task_classes), "contract_paths": list(self.query.contract_paths), "test_paths": list(self.query.test_paths), "recent_paths": list(self.query.recent_paths)}, "repository_fingerprint": self.repository_fingerprint, "included": [{"path": item.path, "score": item.score, "reasons": list(item.reasons), "content": item.content, "truncated": item.truncated} for item in self.included], "excluded_paths": list(self.excluded_paths), "stable_instructions": self.stable_instructions, "dynamic_state": dict(self.dynamic_state), "fingerprint": self.fingerprint, "selection_fingerprint": self.selection_fingerprint, "max_context_chars": self.max_context_chars, "max_file_chars": self.max_file_chars}
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
    @property
    def context_chars(self) -> int:
        return sum(len(item.content) for item in self.included)
    @property
    def selection_fingerprint(self) -> str:
        selection = {"repository_fingerprint": self.repository_fingerprint, "query": {"text": self.query.text, "paths": list(self.query.paths), "symbols": list(self.query.symbols), "task_classes": list(self.query.task_classes), "contract_paths": list(self.query.contract_paths), "test_paths": list(self.query.test_paths), "recent_paths": list(self.query.recent_paths)}, "included": [(item.path, item.score, item.reasons, item.truncated) for item in self.included], "excluded_paths": list(self.excluded_paths), "max_context_chars": max_context_chars, "max_file_chars": max_file_chars}
        return hashlib.sha256(json.dumps(selection, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def compile_context(index: RepositoryIndex, query: RelevanceQuery, source_by_path: Mapping[str, str], *, stable_instructions: str = "", dynamic_state: Mapping[str, object] | None = None, max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS, max_file_chars: int = DEFAULT_MAX_FILE_CHARS, minimum_score: int = DEFAULT_MIN_SCORE, weights: RelevanceWeights = RelevanceWeights()) -> ContextPackage:
    if not isinstance(stable_instructions, str): raise TypeError("stable_instructions must be a string")
    if max_context_chars <= 0 or max_file_chars <= 0: raise ValueError("context limits must be positive")
    if minimum_score < 0: raise ValueError("minimum_score must be non-negative")
    ranking = rank_repository_files(index, query, weights=weights)
    records = {item["path"]: item for item in index.files}
    included: list[ContextFile] = []
    excluded: set[str] = set()
    remaining = max_context_chars
    anchor_paths = _explicit_anchor_paths(ranking.explanations, query)
    anchors = _explicit_anchor_explanations(anchor_paths, query, ranking.explanations, records)
    structural = _structural_candidates(ranking.explanations, anchor_paths)
    secondary_minimum_score = max(minimum_score, SECONDARY_MIN_SCORE)
    secondary = [item for item in ranking.explanations if item.path not in anchor_paths and item not in structural and item.score >= secondary_minimum_score]
    coverage = _coverage_candidates(secondary)[:SECONDARY_MAX_FILES]
    anchor_count = len(anchors)
    anchor_budget = remaining
    anchor_file_budget = max(1, anchor_budget // anchor_count) if anchor_count else 0
    anchor_used = _append_context_files(anchors, anchor_budget, max_file_chars, 0, source_by_path, included, excluded, per_file_budget=anchor_file_budget)
    remaining -= anchor_used
    reserve = min(max(0, remaining - 1), int(remaining * SECONDARY_CONTEXT_RESERVE_RATIO)) if coverage else 0
    priority_budget = remaining - reserve
    structural_used = _append_context_files(structural, priority_budget, max_file_chars, minimum_score, source_by_path, included, excluded)
    remaining -= structural_used
    secondary_budget = min(remaining, reserve + max(0, priority_budget - structural_used))
    coverage_slots = min(len(coverage), SECONDARY_COVERAGE_SIGNAL_SLOTS)
    coverage_budget = min(secondary_budget, max(1, int(secondary_budget * SECONDARY_COVERAGE_FILE_RATIO))) if coverage else 0
    coverage_file_budget = max(1, coverage_budget // coverage_slots) if coverage_slots else 0
    coverage_used = _append_context_files(coverage, coverage_budget, max_file_chars, secondary_minimum_score, source_by_path, included, excluded, per_file_budget=coverage_file_budget)
    remaining -= coverage_used
    if remaining > 0:
        coverage_paths = {candidate.path for candidate in coverage}
        remainder = [item for item in secondary if item.path not in coverage_paths]
        remaining_slots = max(0, SECONDARY_MAX_FILES - len(coverage))
        if remaining_slots:
            optimized_sources = {
                item.path: _secondary_context_source(item, query, source_by_path[item.path], min(max_file_chars, remaining))
                for item in remainder
                if item.path in source_by_path and isinstance(source_by_path[item.path], str)
            }
            ordered = _token_aware_secondary_order(remainder, optimized_sources, max_file_chars, budget=remaining)
            _append_context_files(ordered[:remaining_slots], remaining, max_file_chars, secondary_minimum_score, optimized_sources, included, excluded)
    selected = {item.path for item in included}
    excluded.update(path for path in records if path not in selected)
    excluded.update(path for path in source_by_path if path not in records)
    stable = stable_instructions
    dynamic = dict(dynamic_state or {})
    manifest = {"repository_fingerprint": index.fingerprint, "included": [item.path for item in included], "excluded": sorted(excluded), "max_context_chars": max_context_chars, "max_file_chars": max_file_chars, "minimum_score": minimum_score, "weights": weights.__dict__, "secondary_min_score": SECONDARY_MIN_SCORE, "structural_max_files": STRUCTURAL_MAX_FILES, "secondary_max_files": SECONDARY_MAX_FILES}
    fingerprint = hashlib.sha256(json.dumps({"manifest": manifest, "stable_instructions": stable, "dynamic_state": dynamic, "content": [(item.path, item.content) for item in included]}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return ContextPackage(query, index.fingerprint, tuple(included), tuple(sorted(excluded)), stable, dynamic, fingerprint, max_context_chars, max_file_chars)

def _append_context_files(explanations: list, budget: int, max_file_chars: int, minimum_score: int, source_by_path: Mapping[str, str], included: list[ContextFile], excluded: set[str], *, per_file_budget: int | None = None) -> int:
    used = 0
    for explanation in explanations:
        path = explanation.path
        if explanation.score < minimum_score or _sensitive_path(path) or path not in source_by_path:
            excluded.add(path); continue
        source = source_by_path[path]
        if not isinstance(source, str) or not source:
            excluded.add(path); continue
        limit = min(max_file_chars, budget - used)
        if per_file_budget is not None: limit = min(limit, per_file_budget)
        content, truncated = _bounded_source(source, limit)
        if not content:
            excluded.add(path); continue
        included.append(ContextFile(path, explanation.score, explanation.reasons, content, truncated))
        used += len(content)
        if used >= budget: break
    return used

def _explicit_anchor_paths(explanations: tuple, query: RelevanceQuery) -> set[str]:
    anchors = set(query.paths) | set(query.contract_paths) | set(query.test_paths) | set(query.recent_paths)
    for explanation in explanations:
        if "exact_symbol" in explanation.reasons: anchors.add(explanation.path)
    return anchors

def _explicit_anchor_explanations(anchor_paths: set[str], query: RelevanceQuery, explanations: tuple, records: Mapping[str, dict]) -> list[RelevanceExplanation]:
    by_path = {item.path: item for item in explanations}
    ordered_paths: list[str] = []
    for path in (*query.paths, *query.contract_paths, *query.test_paths, *query.recent_paths):
        if path not in ordered_paths: ordered_paths.append(path)
    for explanation in explanations:
        if "exact_symbol" in explanation.reasons and explanation.path not in ordered_paths: ordered_paths.append(explanation.path)
    materialized: list[RelevanceExplanation] = []
    for path in ordered_paths:
        if path not in anchor_paths or path not in records: continue
        materialized.append(by_path.get(path, RelevanceExplanation(path, 0, ("explicit_anchor",))))
    return materialized

def _structural_candidates(explanations: tuple, anchor_paths: set[str]) -> list[RelevanceExplanation]:
    architectural = [item for item in explanations if item.path not in anchor_paths and any(reason.startswith("architectural_role:") for reason in item.reasons)]
    dependencies = [item for item in explanations if item.path not in anchor_paths and "direct_dependency" in item.reasons and item not in architectural]
    candidates = architectural + dependencies
    candidates.sort(key=lambda item: (-item.score, 0 if any(reason.startswith("architectural_role:") for reason in item.reasons) else 1, item.path, item.reasons))
    return candidates[:STRUCTURAL_MAX_FILES]

def _coverage_candidates(explanations: list) -> list:
    signal_order = ("reverse_dependency", "test_association", "contract_association", "architectural_role", "documentation_role", "recent_change")
    selected: list = []
    selected_paths: set[str] = set()
    for signal in signal_order:
        candidates = [item for item in explanations if any(reason == signal or reason.startswith(signal + ":") for reason in item.reasons) and item.path not in selected_paths]
        for candidate in candidates[:SECONDARY_COVERAGE_PER_SIGNAL]:
            selected.append(candidate); selected_paths.add(candidate.path)
    return selected

def _token_aware_secondary_order(explanations: list, source_by_path: Mapping[str, str], max_file_chars: int, *, budget: int | None = None) -> list:
    """Rank secondary files by deterministic relevance per bounded context character.

    When a budget is supplied, prefer candidates that fit completely in the remaining
    budget before considering candidates that would have to be truncated. This keeps
    the token-aware stage from spending the tail of the budget on a partial file when
    a complete, useful file would fit.
    """
    candidates = []
    for item in explanations:
        source = source_by_path.get(item.path, "")
        cost = min(max_file_chars, len(source)) if isinstance(source, str) else 0
        if cost <= 0: continue
        utility = item.score + sum(1 for reason in item.reasons if reason.startswith(("architectural_role:", "documentation_role:")))
        candidates.append((utility, cost, item.path, item))
    if budget is None:
        candidates.sort(key=lambda value: (-value[0] / value[1], -value[0], value[1], value[2]))
        return [value[3] for value in candidates]
    remaining = budget
    ordered = []
    pending = list(candidates)
    while pending:
        fitting = [value for value in pending if value[1] <= remaining]
        pool = fitting if fitting else pending
        pool.sort(key=lambda value: (-value[0] / value[1], -value[0], value[1], value[2]))
        chosen = pool[0]
        ordered.append(chosen[3])
        pending.remove(chosen)
        if chosen[1] <= remaining:
            remaining -= chosen[1]
        else:
            remaining = 0
            break
    return ordered

def _secondary_context_source(explanation: RelevanceExplanation, query: RelevanceQuery, source: str, limit: int) -> str:
    """Extract high-information lines for a secondary file under a tight budget.

    This is deliberately deterministic and conservative: matching lines are retained
    with one line of local context, plus a short file header. Explicit anchors and
    structural candidates never pass through this optimizer.
    """
    if not source or limit <= 0 or len(source) <= limit:
        return source
    lines = source.splitlines(keepends=True)
    if len(lines) <= SECONDARY_SNIPPET_HEADER_LINES:
        return _bounded_source(source, limit)[0]
    terms = set(_CONTENT_TERM_RE.findall(query.text.lower()))
    for value in query.symbols:
        terms.update(_CONTENT_TERM_RE.findall(value.lower()))
    if not terms:
        return _bounded_source(source, limit)[0]
    matched: set[int] = set()
    for index, line in enumerate(lines):
        line_terms = set(_CONTENT_TERM_RE.findall(line.lower()))
        if terms & line_terms:
            matched.update(range(max(0, index - SECONDARY_SNIPPET_CONTEXT_LINES), min(len(lines), index + SECONDARY_SNIPPET_CONTEXT_LINES + 1)))
    if not matched:
        return _bounded_source(source, limit)[0]
    selected = set(range(min(SECONDARY_SNIPPET_HEADER_LINES, len(lines)))) | matched
    candidate = "".join(lines[index] for index in sorted(selected))
    if len(candidate) <= limit:
        return candidate
    matched_only = "".join(lines[index] for index in sorted(matched))
    if len(matched_only) <= limit:
        return matched_only
    return _bounded_source(matched_only, limit)[0]

def _bounded_source(source: str, limit: int) -> tuple[str, bool]:
    if limit <= 0: return "", bool(source)
    if len(source) <= limit: return source, False
    boundary = source.rfind("\n", 0, limit + 1)
    if boundary > 0: return source[:boundary], True
    return source[:limit], True

def _sensitive_path(path: str) -> bool:
    lowered = path.lower(); parts = lowered.split("/"); name = parts[-1]
    if name == ".env" or name.startswith(".env."): return True
    if name.endswith((".pem", ".key", ".p12", ".pfx")): return True
    return any(part in SENSITIVE_PATH_MARKERS for part in parts) or name.startswith(("secret", "credential"))

def is_sensitive_context_path(path: str) -> bool:
    return _sensitive_path(path)
