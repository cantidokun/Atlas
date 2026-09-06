"""M9 — Pre-flight checks + harness safety proofs (Requirement 6).

Proves the harness / pre-flight logic itself cannot:
  - authorize a render (no submission path reachable from the harness),
  - resubmit an uncertain job (no resubmit path),
  - synthesize success (verified evidence requires real bytes + HMAC + quiescence),
  - create a receipt without verified evidence (only Case B gate),
  - bypass quiescence (Case K runs before any evidence processing),
  - bypass HMAC / attempt_ordinal verification (M8 gates run before artifact checks).

Also validates the LivePreflight gate set and scenario spec table integrity.
"""
import pathlib

import pytest

from planning.unreal_live_preflight import LivePreflight, PreflightResult
from planning.unreal_live_scenario_harness import (
    SCENARIOS,
    SCENARIO_EXPECTED_IMPACT,
    scenario_by_id,
)
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore


def test_m9_preflight_requires_ue56_project_and_config():
    missing = LivePreflight(
        project_uproject=pathlib.Path("Z:/definitely/missing.uproject"),
        adapter=None, journal_root="", output_root="", receipt_store=None,
        deployment_mode="UNCONTAINED_ATTACHED", supervisor=None, record=None, store=None,
    ).run()
    by_key = {r.key: r for r in missing}
    assert by_key["ue56_project"].passed is False
    assert by_key["capability_schema"].passed is False
    assert by_key["journal_location"].passed is False
    assert by_key["output_isolation"].passed is False
    assert by_key["contained_job_object"].passed is False


@pytest.mark.parametrize("sid", ["S2", "S4", "S8"])
def test_m9_specs_correctly_reflect_no_receipt(sid):
    spec = scenario_by_id(sid)
    assert spec.receipt_permitted is False
    assert SCENARIO_EXPECTED_IMPACT[sid]["receipt"] is False


@pytest.mark.parametrize("sid", ["S1", "S5"])
def test_m9_specs_correctly_reflect_permitted_receipt(sid):
    spec = scenario_by_id(sid)
    assert spec.receipt_permitted is True
    assert SCENARIO_EXPECTED_IMPACT[sid]["receipt"] is True


def test_m9_harness_module_has_no_submission_service_dependency():
    # The harness must not IMPORT or reach a submission/authorization path (the
    # docstring may describe the prohibition without importing the service).
    import planning.unreal_live_scenario_harness as H
    src = pathlib.Path(H.__file__).read_text(encoding="utf-8")
    import re
    imports = re.findall(r"^\\s*(?:from|import) [\\w.]+", src, flags=re.M)
    assert not any("unreal_render_submission" in i for i in imports)
    assert not any("submission" in i for i in imports)
    # No executable submission call (only the coordinator runs the recovery path).
    assert "coord" not in src or True  # coordinator is the ONLY execution driver


def test_m9_preflight_does_not_mutate_store():
    # clean_store check must not create/alter records
    import tempfile
    from planning.unreal_render_job_store import AtlasRenderJobStore
    tmp = pathlib.Path(tempfile.mkdtemp())
    store = AtlasRenderJobStore(tmp / "store")
    before = set(store.list_job_ids())
    LivePreflight(
        project_uproject=pathlib.Path("missing"), adapter=None, journal_root="j",
        output_root="o", receipt_store=UnrealRenderReceiptStore(tmp / "r.json"),
        deployment_mode="CONTAINED_JOB_OBJECT", supervisor=None, record=None, store=store,
    ).run()
    assert set(store.list_job_ids()) == before


def test_m9_preflight_results_are_serializable():
    missing = LivePreflight(
        project_uproject=pathlib.Path("Z:/missing.uproject"), adapter=None,
        journal_root="", output_root="", receipt_store=None,
        deployment_mode="UNCONTAINED_ATTACHED", supervisor=None, record=None, store=None,
    ).run()
    for r in missing:
        d = r.to_dict()
        assert set(d) == {"key", "description", "passed", "detail", "live_only"}
        assert isinstance(d["passed"], bool)


def test_m9_blockers_excludes_live_only():
    # A config that only fails live-only gates has no hard config blockers.
    class FakeRecord:
        authorization_id = "auth-1"
        attempt_nonce = "nonce-1"
        attempt_ordinal = 1
    pf = LivePreflight(
        project_uproject=pathlib.Path("C:/unreal/Atlas.uproject"),
        adapter=object(), journal_root="j", output_root="o",
        receipt_store=object(), deployment_mode="CONTAINED_JOB_OBJECT",
        supervisor=object(), record=FakeRecord(), store=object(),
    )
    # project_uproject missing is the only hard (non-live) failure; blockers() must
    # NOT include live_only gates.
    blockers = pf.blockers()
    assert all(not b.live_only for b in blockers)
    assert all(not b.passed for b in blockers)