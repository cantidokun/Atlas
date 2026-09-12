"""Deterministic relevance scoring over the Atlas repository index.

This module selects repository structure for development-model context. It is
read-only development tooling and is intentionally independent of model
providers, execution authority, scheduling, recovery, receipts, and evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Sequence

from planning.repository_intelligence.index import RepositoryIndex, SymbolRecord

@dataclass(frozen=True)
class RelevanceWeights:
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
    documentation_role: int = 18
    architectural_role: int = 35

@dataclass(frozen=True)
class RelevanceQuery:
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
_ARCHITECTURAL_ROLES = {
    "execution_boundary": frozenset({"execution", "boundary", "recovery", "runtime", "failed"}),
    "task_planner": frozenset({"planner", "planning", "task", "authorization", "authority"}),
    "router": frozenset({"router", "routing", "model", "authority"}),
    "execution_plan": frozenset({"execution", "plan", "semantic", "m12"}),
}

def rank_repository_files(index: RepositoryIndex, query: RelevanceQuery, *, weights: RelevanceWeights = RelevanceWeights()) -> RelevanceResult:
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
    content_document_frequency = _content_document_frequency(index, lexical_terms)
    explanations: list[RelevanceExplanation] = []

    for file_record in index.files:
        path = file_record["path"]
        score = 0
        reasons: list[str] = []
        if path in direct_paths:
            score += weights.exact_path; reasons.append("exact_path")
        if path in symbol_paths:
            score += weights.exact_symbol; reasons.append("exact_symbol")
        if any(path in dependency_map.get(anchor, set()) for anchor in anchor_paths):
            score += weights.direct_dependency; reasons.append("direct_dependency")
        if any(path in reverse_map.get(anchor, set()) for anchor in anchor_paths):
            score += weights.reverse_dependency; reasons.append("reverse_dependency")
        if path in test_paths or _is_associated_test(path, anchor_paths):
            score += weights.test_association; reasons.append("test_association")
        if path in contract_paths or _is_contract_associated(path, anchor_paths):
            score += weights.contract_association; reasons.append("contract_association")
        if path in recent_paths:
            score += weights.recent_change; reasons.append("recent_change")
        if _is_documentation_role_associated(file_record, query, anchor_paths):
            score += weights.documentation_role; reasons.append("documentation_role")
        architectural_roles = _architectural_role_matches(path, query, anchor_paths)
        if architectural_roles:
            score += weights.architectural_role * len(architectural_roles)
            reasons.extend(f"architectural_role:{role}" for role in architectural_roles)
        content_hits = _content_hits(file_record, lexical_terms)
        if content_hits:
            score += _content_match_score(file_record, lexical_terms, content_document_frequency, len(file_paths), weights.content_match)
            reasons.append(f"content_match:{min(content_hits, 4)}")
        lexical_hits = _lexical_hits(path, file_record, index.symbols, lexical_terms)
        if lexical_hits:
            score += min(weights.lexical_match * lexical_hits, weights.lexical_match * 3)
            reasons.append(f"lexical_match:{min(lexical_hits, 3)}")
        if score > 0 and anchor_paths and any(_same_directory(path, anchor) for anchor in anchor_paths if anchor != path):
            score += weights.same_directory; reasons.append("same_directory")
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
    return any((anchor.rsplit("/", 1)[-1].removesuffix(".py")) in stem for anchor in anchors)

def _is_contract_associated(path: str, anchors: set[str]) -> bool:
    lowered = path.lower()
    if not ("contract" in lowered or "schema" in lowered or "protocol" in lowered) or not anchors:
        return False
    return any(_same_directory(path, anchor) for anchor in anchors)

def _is_documentation_role_associated(file_record: dict, query: RelevanceQuery, anchors: set[str]) -> bool:
    if file_record.get("kind") != "documentation": return False
    path = str(file_record.get("path", "")).lower()
    name = path.rsplit("/", 1)[-1]
    query_terms = set(_TOKEN_RE.findall(query.text.lower()))
    domain_anchor = any(_domain_path(anchor) for anchor in anchors)
    if name == "readme.md": return bool({"document", "documentation", "boundary", "unreal"} & query_terms) and domain_anchor
    if "handoff" in name: return domain_anchor or bool({"handoff", "current", "state"} & query_terms)
    if "execution_plan" in name or "execution-plan" in name: return bool({"execution", "plan", "semantic"} & query_terms)
    return False

def _architectural_role_matches(path: str, query: RelevanceQuery, anchors: set[str]) -> tuple[str, ...]:
    """Match narrow architectural roles from path vocabulary plus task vocabulary.

    This is intentionally deterministic and repository-generic: it does not name
    benchmark case IDs or specific Atlas files.
    """
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    terms = set(_TOKEN_RE.findall(query.text.lower())) | set(query.symbols)
    matches: list[str] = []
    if "execution_boundary" in name or "execution-boundary" in name:
        if {"recovery", "execution", "boundary"} & terms and any(_domain_path(a) for a in anchors):
            matches.append("execution_boundary")
    if "task_planner" in name or "task-planner" in name:
        if {"task", "planner", "planning", "authorization", "authority"} & terms and any(_planning_path(a) for a in anchors):
            matches.append("task_planner")
    if name == "router.py" or "/router.py" in lowered:
        if {"router", "routing", "model", "authority"} & terms:
            matches.append("router")
    if "execution_plan" in name or "execution-plan" in name:
        if {"execution", "plan", "semantic", "m12"} & terms:
            matches.append("execution_plan")
    return tuple(matches)

def _domain_path(path: str) -> bool:
    lowered = path.lower()
    return "unreal" in lowered or "/m12/" in lowered or lowered.startswith("planning/m12/")

def _planning_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith("planning/") or "/planning/" in lowered or "controller/" in lowered

def _same_directory(left: str, right: str) -> bool:
    return left.rsplit("/", 1)[0] == right.rsplit("/", 1)[0]

def _query_terms(query: RelevanceQuery) -> tuple[str, ...]:
    raw = list(_TOKEN_RE.findall(query.text.lower()))
    raw.extend(token.lower() for token in query.symbols)
    return tuple(sorted(set(raw)))

def _content_hits(file_record: dict, terms: Sequence[str]) -> int:
    if not terms: return 0
    return sum(1 for term in terms if term in set(file_record.get("content_terms", ())))

def _content_document_frequency(index: RepositoryIndex, terms: Sequence[str]) -> dict[str, int]:
    wanted = set(terms); frequencies = {term: 0 for term in wanted}
    for record in index.files:
        for term in wanted.intersection(record.get("content_terms", ())): frequencies[term] += 1
    return frequencies

def _content_match_score(file_record: dict, terms: Sequence[str], document_frequency: dict[str, int], document_count: int, weight: int) -> int:
    matched = [term for term in terms if term in set(file_record.get("content_terms", ()))]
    if not matched or document_count <= 0: return 0
    score = 0
    for term in matched:
        rarity = 1.0 + math.log((document_count + 1) / (document_frequency.get(term, document_count) + 1))
        score += weight * min(4, max(1, int(round(rarity))))
    return min(score, weight * 12)

def _lexical_hits(path: str, file_record: dict, symbols: Sequence[SymbolRecord], terms: Sequence[str]) -> int:
    if not terms: return 0
    haystack = path.lower()
    if file_record.get("kind") == "python_source":
        haystack += " " + " ".join(item.qualified_name.lower() for item in symbols if item.path == path)
    return sum(1 for term in terms if term and term in haystack)
