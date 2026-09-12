"""Deterministic relevance scoring over the Atlas repository index.

This module selects repository structure for development-model context. It is
read-only development tooling and is intentionally independent of model
providers, execution authority, scheduling, recovery, receipts, and evidence.

The scorer is deliberately explainable: every score is the sum of named,
bounded signals. Ties are resolved deterministically by repository path and
symbol name rather than insertion order.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from planning.repository_intelligence.index import RepositoryIndex, SymbolRecord


@dataclass(frozen=True)
class RelevanceWeights:
    """Frozen scoring weights for M13.2."""
    exact_path: int = 100
    exact_symbol: int = 90
    direct_dependency: int = 70
    reverse_dependency: int = 60
    test_association: int = 50
    contract_association: int = 45
    recent_change: int = 20
    content_match: int = 8
    lexical_match: int = 10
    same_directory: int = 5


@dataclass(frozen=True)
class RelevanceQuery:
    """Structured development-task signals used by the scorer."""
    text: str = ""
    paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    task_classes: tuple[str, ...] = ()
    contract_paths: tuple[str, ...] = ()
    test_paths: tuple[str, ...] = ()
    recent_paths: tuple[str, ...] = ()

    @classmethod
    def from_values(cls, *, text: str = "", paths: Iterable[str] = (), symbols: Iterable[str] = (), task_classes: Iterable[str] = (), contract_paths: Iterable[str] = (), test_paths: Iterable[str] = (), recent_paths: Iterable[str] = ()) -> "RelevanceQuery":
        return cls(text=text.strip() if isinstance(text, str) else "", paths=_normalized_tuple(paths), symbols=_normalized_tuple(symbols), task_classes=_normalized_tuple(task_classes), contract_paths=_normalized_tuple(contract_paths), test_paths=_normalized_tuple(test_paths), recent_paths=_normalized_tuple(recent_paths))


@dataclass(frozen=True)
class RelevanceExplanation:
    path: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RelevanceResult:
    query: RelevanceQuery
    explanations: tuple[RelevanceExplanation, ...]

    def ranked_paths(self, *, minimum_score: int = 1, limit: int | None = None) -> tuple[str, ...]:
        selected = [item.path for item in self.explanations if item.score >= minimum_score]
        if limit is not None:
            selected = selected[: max(0, limit)]
        return tuple(selected)


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")


def rank_repository_files(index: RepositoryIndex, query: RelevanceQuery, *, weights: RelevanceWeights = RelevanceWeights()) -> RelevanceResult:
    """Rank every indexed file against a structured development query."""
    file_paths = {item["path"] for item in index.files}
    direct_paths = set(query.paths) & file_paths
    contract_paths = set(query.contract_paths) & file_paths
    test_paths = set(query.test_paths) & file_paths
    recent_paths = set(query.recent_paths) & file_paths
    symbol_paths = _symbol_paths(index.symbols, query.symbols)
    dependency_map = _dependency_map(index)
    reverse_map = _reverse_dependency_map(dependency_map)
    anchor_paths = direct_paths | symbol_paths
    lexical_terms = _query_terms(query)
    explanations: list[RelevanceExplanation] = []

    for file_record in index.files:
        path = file_record["path"]
        score = 0
        reasons: list[str] = []
        if path in direct_paths:
            score += weights.exact_path
            reasons.append("exact_path")
        if path in symbol_paths:
            score += weights.exact_symbol
            reasons.append("exact_symbol")
        if any(path in dependency_map.get(anchor, set()) for anchor in anchor_paths):
            score += weights.direct_dependency
            reasons.append("direct_dependency")
        if any(path in reverse_map.get(anchor, set()) for anchor in anchor_paths):
            score += weights.reverse_dependency
            reasons.append("reverse_dependency")
        if path in test_paths or _is_associated_test(path, anchor_paths):
            score += weights.test_association
            reasons.append("test_association")
        if path in contract_paths or _is_contract_associated(path, anchor_paths):
            score += weights.contract_association
            reasons.append("contract_association")
        if path in recent_paths:
            score += weights.recent_change
            reasons.append("recent_change")

        content_hits = _content_hits(file_record, lexical_terms)
        if content_hits:
            score += min(weights.content_match * content_hits, weights.content_match * 4)
            reasons.append(f"content_match:{min(content_hits, 4)}")

        lexical_hits = _lexical_hits(path, file_record, index.symbols, lexical_terms)
        if lexical_hits:
            score += min(weights.lexical_match * lexical_hits, weights.lexical_match * 3)
            reasons.append(f"lexical_match:{min(lexical_hits, 3)}")
        if score > 0 and anchor_paths and any(_same_directory(path, anchor) for anchor in anchor_paths if anchor != path):
            score += weights.same_directory
            reasons.append("same_directory")
        if score > 0:
            explanations.append(RelevanceExplanation(path, score, tuple(reasons)))

    explicit_paths = direct_paths | symbol_paths | contract_paths | test_paths | recent_paths
    explanations.sort(key=lambda item: (0 if item.path in explicit_paths else 1, 0 if item.path in direct_paths or item.path in symbol_paths else 1, 0 if "direct_dependency" in item.reasons else 1, -item.score, item.path, item.reasons))
    return RelevanceResult(query=query, explanations=tuple(explanations))


def _normalized_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().replace("\\", "/") for value in values if isinstance(value, str) and value.strip()}))


def _symbol_paths(symbols: Sequence[SymbolRecord], requested: Sequence[str]) -> set[str]:
    wanted = set(requested)
    return {item.path for item in symbols if item.qualified_name in wanted or f"{item.path}:{item.qualified_name}" in wanted}


def _dependency_map(index: RepositoryIndex) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for item in index.imports:
        if item.resolved_path:
            result.setdefault(item.path, set()).add(item.resolved_path)
    return result


def _reverse_dependency_map(dependencies: dict[str, set[str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for source, targets in dependencies.items():
        for target in targets:
            result.setdefault(target, set()).add(source)
    return result


def _is_associated_test(path: str, anchors: set[str]) -> bool:
    if not anchors or not path.lower().endswith(".py"):
        return False
    if not any(part == "tests" for part in path.split("/")) and not path.split("/")[-1].startswith("test_"):
        return False
    stem = path.rsplit("/", 1)[-1]
    for anchor in anchors:
        anchor_stem = anchor.rsplit("/", 1)[-1].removesuffix(".py")
        if anchor_stem and anchor_stem in stem:
            return True
    return False


def _is_contract_associated(path: str, anchors: set[str]) -> bool:
    lowered = path.lower()
    contract_named = "contract" in lowered or "schema" in lowered or "protocol" in lowered
    if not contract_named or not anchors:
        return False
    return any(_same_directory(path, anchor) for anchor in anchors)


def _same_directory(left: str, right: str) -> bool:
    return left.rsplit("/", 1)[0] == right.rsplit("/", 1)[0]


def _query_terms(query: RelevanceQuery) -> tuple[str, ...]:
    raw = list(_TOKEN_RE.findall(query.text.lower()))
    raw.extend(token.lower() for token in query.symbols)
    raw.extend(token.lower() for token in query.task_classes)
    return tuple(sorted(set(raw)))


def _content_hits(file_record: dict, terms: Sequence[str]) -> int:
    if not terms:
        return 0
    content_terms = set(file_record.get("content_terms", ()))
    return sum(1 for term in terms if term in content_terms)


def _lexical_hits(path: str, file_record: dict, symbols: Sequence[SymbolRecord], terms: Sequence[str]) -> int:
    if not terms:
        return 0
    haystack = path.lower()
    if file_record.get("kind") == "python_source":
        haystack += " " + " ".join(item.qualified_name.lower() for item in symbols if item.path == path)
    return sum(1 for term in terms if term and term in haystack)
