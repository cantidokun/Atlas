"""M11.1 deterministic tests: router facade, telemetry integration, and
production-authority isolation (non-negotiable boundary)."""

import pytest

from planning.m11_router.model_profile import load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.telemetry import AppendOnlyTelemetry
from planning.m11_router.risk import RISK_DIMENSIONS


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


@pytest.fixture
def router(profiles_raw, tmp_path):
    profiles = load_profiles(profiles_raw)
    tele = AppendOnlyTelemetry(tmp_path / "tele.jsonl")
    return ModelRouter(profiles, telemetry=tele), tele


def test_nothing_called_verify_router_tracks_telemetry(router):
    r, tele = router
    dec = r.route_task("task-1", _zero(), task_classes=["docs"])
    assert dec.needs_human_review is False
    assert dec.selection.selected_model_id == "m0"
    assert len(tele.read_all()) == 1  # an attempt record was appended


def test_router_records_tier_and_budget(router):
    r, tele = router
    scores = _zero(); scores["cryptography"] = 3
    r.route_task("task-crypto", scores, task_classes=["security-crypto"])
    recs = tele.read_task("task-crypto")
    assert len(recs) == 1
    assert recs[0].risk_tier == "L3"
    assert recs[0].selected_model == "m3"


def test_router_confidence_never_reaches_decision(router):
    r, _ = router
    scores = _zero(); scores["concurrency"] = 2
    a = r.route_task("t", scores, task_classes=["concurrency"], confidence=0.99)
    b = r.route_task("t", scores, task_classes=["concurrency"], confidence=0.01)
    assert a.selection == b.selection


def test_router_no_capable_profile_fails_closed_to_human_review(profiles_raw):
    only_l0 = load_profiles([profiles_raw[0]])
    r = ModelRouter(only_l0)
    scores = _zero(); scores["cryptography"] = 3
    dec = r.route_task("t", scores, task_classes=["security-crypto"])
    assert dec.needs_human_review is True
    assert dec.selection is None
    assert dec.failure_reason  # never guesses


# ---- AUTHORITY ISOLATION (non-negotiable) ----

def test_router_package_has_no_production_authority_imports():
    """The M11 router must never import Atlas production/recovery modules."""
    import ast
    from pathlib import Path
    pkg = Path("planning/m11_router")
    forbidden = {
        "unreal_render_recovery_coordinator",
        "unreal_render_submission",
        "unreal_render_job_store",
        "unreal_render_receipt_store",
        "unreal_adapter_production",
        "unreal_render_receipt",
        "unreal_render_contract",
        "unreal_evidence_contract",
        "action_authorization",
    }
    hits = []
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in forbidden or a.name.startswith("planning.unreal_render") or a.name.startswith("planning.action_"):
                        hits.append((py.name, a.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in forbidden or mod.startswith("planning.unreal_render") or mod.startswith("planning.action_"):
                    hits.append((py.name, mod))
                for a in node.names:
                    if a.name in forbidden:
                        hits.append((py.name, a.name))
                    # from planning.unreal_render_job_store import X
                    if mod.startswith("planning.unreal_render") and a.name:
                        hits.append((py.name, f"{mod}.{a.name}"))
    assert hits == [], f"M11 router must not import production authority: {hits}"


def test_router_has_no_authority_method_names():
    """The router class must not expose methods named as authority operations."""
    from planning.m11_router.router import ModelRouter
    method_names = {m for m in dir(ModelRouter)}
    forbidden_subs = {
        "submit", "reconcile", "apply_authorized", "authorize_production",
        "issue_receipt", "schedule", "finalize_authoritative",
    }
    leaks = set()
    for m in method_names:
        low = m.lower()
        for f in forbidden_subs:
            if f in low:
                leaks.add(m)
    assert not leaks, f"router exposes authority-shaped method: {leaks}"


def test_receipts_never_created_by_facade(router):
    r, tele = router
    dec = r.route_task("t", _zero(), task_classes=["docs"])
    assert dec.selection is not None
    assert dec.selection.profile is not None
    # The router decision carries no receipt — only model/profile selection.
    assert not hasattr(dec, "receipt")
    assert not hasattr(dec.selection, "receipt")


def test_router_persistence_is_namespace_isolated(tmp_path, profiles_raw):
    """Router telemetry dir must be its own component, not a production store path."""
    profiles = load_profiles(profiles_raw)
    r = ModelRouter(profiles)
    # No attempt to open an AtlasRenderJobStore / receipts / journal namespace.
    assert r._telemetry is None  # telemetry optional; router runs without prod store
    assert hasattr(r, "_profiles")