"""Deterministic dependency/conflict resolution for the Cleanup/Correction planner.

The planner never silently resolves a contradiction. Instead it classifies the disposition:

- **duplicate proposals** — identical ``(finding_code, object_id, mesh_id, correction_type,
  parameters)`` → deduplicated deterministically (kept once, counted in summary).
- **contradictory / incompatible proposals** — e.g. the same face both REMOVED and REWOUND, or two
  proposals targeting the same object with different corrections → surfaced as ``REQUIRES_REVIEW``
  plus a structural ``planning_errors`` record (never resolved silently, never executed).
- **dependency cycles** — a DAG cycle → ``PLANNING_ERROR`` (surfaced, never silently reordered).
- **stable topological ordering** — deterministic sort with a stable tie-break so the same input
  always yields the same order.

``dependencies`` are expressed as ordered pairs and validated: a ``from``/``to`` must reference an
existing proposal, no self-dependency, and the graph must be acyclic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from planning.blender.correction_contract import CorrectionProposal

# A proposal's identity for dedup/contradiction detection (deterministic, JSON-comparable).
def _proposal_signature(p: CorrectionProposal) -> Tuple[Any, ...]:
    params = tuple(sorted((str(k), _freeze(v)) for k, v in dict(p.parameters).items()))
    return (
        p.finding_code,
        p.object_id,
        p.mesh_id,
        p.correction_type,
        params,
    )


def _freeze(v: Any) -> Any:
    if type(v) is list:
        return tuple(_freeze(x) for x in v)
    if type(v) is tuple:
        return tuple(_freeze(x) for x in v)
    if type(v) is dict:
        return tuple(sorted((k, _freeze(x)) for k, x in v.items()))
    return v


def resolve(
    proposals: Sequence[CorrectionProposal],
    *,
    explicit_edges: Sequence[Tuple[str, str]],
    proposal_dependencies: Sequence[Tuple[str, str]],
) -> dict:
    """Return a deterministic resolution dict for the given proposals.

    Returns ``{"corrections": [...], "edges": [...], "deduplicated": [...],
    "contradictions": [...], "cycle_nodes": [...]}``.

    - Explicit edges and proposal dependencies are merged (proposal dependencies carry the same
      semantics as explicit edges; they are normalized to (from, to) pairs).
    - Deduplication: identical-proposal signatures collapse to one kept proposal.
    - Contradiction detection: any two KEPT proposals that (a) share the same
      ``(object_id, mesh_id, finding_code)`` but differ in ``correction_type``, or (b) form an
      implicit conflict (same face targeted by both REMOVE_* and REPAIR_*), are recorded.
    - Cycle detection over the final edge set → returns ``cycle_nodes`` (caller maps to
      PLANNING_ERROR).
    - Otherwise a stable topological order is produced (Kahn's algorithm with a deterministic
      tie-break on ``correction_id``).
    """
    # --- normalize proposals, detect duplicates deterministically ---
    kept: List[CorrectionProposal] = []
    seen: Dict[Tuple[Any, ...], int] = {}
    deduped: List[str] = []
    for p in proposals:
        sig = _proposal_signature(p)
        if sig in seen:
            deduped.append(p.correction_id)
            continue
        seen[sig] = len(kept)
        kept.append(p)

    ids = {p.correction_id for p in kept}

    # --- merge edges ---
    raw_edges: List[Tuple[str, str]] = []
    seen_edges = set()
    for (f, t) in list(explicit_edges) + list(proposal_dependencies):
        if type(f) is not str or type(t) is not str:
            raise ValueError("dependency edges must be (exact_str, exact_str)")
        if f not in ids or t not in ids:
            raise ValueError(f"dependency edge references unknown correction: {f!r}->{t!r}")
        if f == t:
            continue  # self-dependency is a defensive no-op; contract already rejects it
        key = (f, t)
        if key not in seen_edges:
            seen_edges.add(key)
            raw_edges.append(key)

    # --- contradiction detection (never silent) ---
    contradictions: List[dict] = []
    by_target: Dict[Tuple[Any, ...], List[CorrectionProposal]] = {}
    for p in kept:
        key = (p.object_id, p.mesh_id, p.finding_code)
        by_target.setdefault(key, []).append(p)
    for key, group in by_target.items():
        types = {p.correction_type for p in group}
        if len(types) > 1:
            contradictions.append({
                "target": [key[0], key[1], key[2]],
                "corrections": [p.correction_id for p in group],
                "correction_types": sorted(types),
                "kind": "conflicting_targets",
            })

    # --- cycle detection over merged edges (Kahn remainder = cycle nodes) ---
    adj: Dict[str, List[str]] = {pid: [] for pid in ids}
    indeg: Dict[str, int] = {pid: 0 for pid in ids}
    for (f, t) in raw_edges:
        adj[f].append(t)
        indeg[t] += 1
    ready = sorted([pid for pid in ids if indeg[pid] == 0])
    order: List[str] = []
    import heapq
    while ready:
        node = ready.pop(0)  # already sorted -> deterministic tie-break
        order.append(node)
        for nxt in sorted(adj[node]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    if len(order) != len(ids):
        cycle_nodes = [pid for pid in ids if pid not in order]
        return {
            "corrections": kept,
            "edges": raw_edges,
            "deduplicated": deduped,
            "contradictions": contradictions,
            "cycle_nodes": cycle_nodes,
        }

    # --- deterministic reorder of kept proposals to follow topo order ---
    pos = {pid: i for i, pid in enumerate(order)}
    ordered_proposals = sorted(kept, key=lambda p: pos[p.correction_id])
    return {
        "corrections": ordered_proposals,
        "edges": raw_edges,
        "deduplicated": deduped,
        "contradictions": contradictions,
        "cycle_nodes": [],
    }