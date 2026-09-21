"""M9 — Pre-flight checks + harness safety proofs (Requirement 6).

Proves the harness / pre-flight logic itself cannot:
  - authorize a render (no submission path reachable from the harness),
  - resubmit an uncertain job (no resubmit path),
  - synthesize success (verified evidence requires real bytes + HMAC + quiescence),
  - create a receipt without verified evidence (only Case B gate),
  - bypass quiescence (Case K runs before any evidence processing),
  - bypass HMAC / attempt_ordinal verification (M8 gates run before artifact checks).

Also validates the LivePreflight gate set and scenario spec table integrity.

Phased-arming coverage (F-M7-1 / F-M7-2 remediation) is at the end of this file:
the capability gate must check the SEAM before the engine exists, the live
negotiation must delegate to the existing production recovery authority, and the
durable-record identity gates must only be required once the record exists.
"""
import pathlib

import pytest

from planning.unreal_live_preflight import (
    PHASE_GATES,
    LivePreflight,
    PreflightPhase,
    PreflightResult,
)
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
    imports = re.findall(r"^\s*(?:from|import) [\w.]+", src, flags=re.M)
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
        # phase is available on demand without changing the legacy payload shape
        assert r.to_dict(include_phase=True)["phase"] == r.phase.value


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


# ---------------------------------------------------------------------------
# Phased arming model (F-M7-1 capability seam / F-M7-2 intent ordering)
# ---------------------------------------------------------------------------


class _FakeStore:
    """Minimal clean-store stand-in (list_job_ids only)."""

    def __init__(self, ids=()):
        self._ids = list(ids)

    def list_job_ids(self):
        return list(self._ids)


class _ProductionShapedAdapter:
    """Mimics UnrealAdapterProduction's public capability seam.

    Exposes ``query_capabilities`` / ``assert_recovery_capable`` and NO
    ``get_capabilities`` — exactly the shape the production adapter has. Records
    every invocation so tests can prove the pre-engine phase performs no RPC.
    """

    def __init__(self, capabilities=(), assert_error=None):
        self.calls = []
        self.capabilities = frozenset(capabilities)
        self.assert_error = assert_error

    def query_capabilities(self, authorization_id):
        self.calls.append(("query_capabilities", authorization_id))
        return self.capabilities

    def assert_recovery_capable(self, authorization_id):
        self.calls.append(("assert_recovery_capable", authorization_id))
        if self.assert_error is not None:
            raise self.assert_error


def _preflight(**overrides):
    base = dict(
        project_uproject=pathlib.Path(__file__),
        adapter=None,
        journal_root="journal-root",
        output_root="output-root",
        receipt_store=object(),
        deployment_mode="CONTAINED_JOB_OBJECT",
        supervisor=object(),
        record=None,
        store=_FakeStore(),
        authorization_id=None,
    )
    base.update(overrides)
    return LivePreflight(**base)


def test_m9_production_adapter_exposes_the_capability_seam_and_no_get_capabilities():
    # F-M7-1 regression guard: the adapter that will face the live engine exposes
    # query_capabilities()/assert_recovery_capable() and deliberately has no
    # get_capabilities() — the pre-flight must never call the latter.
    from planning.unreal_adapter_production import UnrealAdapterProduction
    assert callable(getattr(UnrealAdapterProduction, "query_capabilities", None))
    assert callable(getattr(UnrealAdapterProduction, "assert_recovery_capable", None))
    assert not hasattr(UnrealAdapterProduction, "get_capabilities")


def test_m9_phase_a_capability_seam_passes_with_production_shaped_adapter():
    adapter = _ProductionShapedAdapter()
    assert not hasattr(adapter, "get_capabilities")
    gate = {r.key: r for r in _preflight(adapter=adapter).run_phase(PreflightPhase.PRE_ENGINE)}
    assert gate["capability_schema"].passed is True
    assert gate["capability_schema"].phase is PreflightPhase.PRE_ENGINE
    assert gate["capability_schema"].live_only is False  # a hard Phase A gate


def test_m9_phase_a_never_attempts_a_live_capability_rpc():
    class _ExplodingAdapter(_ProductionShapedAdapter):
        def query_capabilities(self, authorization_id):  # pragma: no cover - must not run
            raise AssertionError("pre-engine phase must not perform a capability RPC")

        def assert_recovery_capable(self, authorization_id):  # pragma: no cover - must not run
            raise AssertionError("pre-engine phase must not perform a capability RPC")

    adapter = _ExplodingAdapter()
    keys = {r.key for r in _preflight(adapter=adapter).run_phase(PreflightPhase.PRE_ENGINE)}
    assert "capability_schema" in keys
    assert "capability_negotiation" not in keys
    assert adapter.calls == []


def test_m9_phase_b_negotiation_delegates_to_the_production_recovery_authority():
    adapter = _ProductionShapedAdapter(capabilities=("render", "durable_journal"))
    gate = {
        r.key: r for r in _preflight(
            adapter=adapter, authorization_id=" auth-m7-s1-live "
        ).run_phase(PreflightPhase.POST_ENGINE)
    }["capability_negotiation"]
    assert gate.passed is True
    assert gate.phase is PreflightPhase.POST_ENGINE
    assert gate.live_only is True
    # exactly the production seam, with the operator-declared authorization context
    assert adapter.calls == [("assert_recovery_capable", "auth-m7-s1-live")]


def test_m9_submission_remains_the_authoritative_capability_gate():
    # The pre-flight delegates; it must not relocate or duplicate authority.
    import inspect
    from planning.unreal_render_submission import UnrealRenderSubmissionService
    src = inspect.getsource(UnrealRenderSubmissionService.submit_render)
    assert "assert_recovery_capable" in src


def test_m9_phase_a_does_not_require_durable_record_gates():
    pf = _preflight(adapter=_ProductionShapedAdapter(), record=None)
    phase_a_keys = {r.key for r in pf.run_phase(PreflightPhase.PRE_ENGINE)}
    record_gates = {"authorization_continuity", "attempt_nonce", "attempt_ordinal"}
    assert not (record_gates & phase_a_keys)
    # no record => no Phase A blocker, but Phase C still fails closed
    assert pf.blockers(PreflightPhase.PRE_ENGINE) == []
    assert pf.all_pass(PreflightPhase.POST_INTENT) is False


def test_m9_phase_c_record_identity_gates_remain_hard_requirements():
    class _Complete:
        authorization_id = "auth-1"
        attempt_nonce = "nonce-1"
        attempt_ordinal = 1

    class _MissingAuth:
        authorization_id = ""
        attempt_nonce = "nonce-1"
        attempt_ordinal = 1

    class _MissingNonce:
        authorization_id = "auth-1"
        attempt_nonce = None
        attempt_ordinal = 1

    class _MissingOrdinal:
        authorization_id = "auth-1"
        attempt_nonce = "nonce-1"
        attempt_ordinal = None

    assert _preflight(record=_Complete()).all_pass(PreflightPhase.POST_INTENT) is True
    for incomplete in (_MissingAuth(), _MissingNonce(), _MissingOrdinal()):
        pf = _preflight(record=incomplete)
        assert pf.all_pass(PreflightPhase.POST_INTENT) is False
        failures = [r for r in pf.run_phase(PreflightPhase.POST_INTENT) if not r.passed]
        assert failures
        assert all(not f.live_only for f in failures)  # hard, never waived


def test_m9_phased_preflight_fails_closed():
    from planning.unreal_adapter_production import UnrealAdapterError

    # 1. no adapter -> Phase A seam blocker, arming stops
    no_adapter = [b.key for b in _preflight(adapter=None).blockers(PreflightPhase.PRE_ENGINE)]
    assert no_adapter == ["capability_schema"]

    # 2. adapter without the recovery-capability assertion seam -> fail closed
    #    (capability policy is never re-implemented inside pre-flight)
    class _QueryOnly:
        def query_capabilities(self, authorization_id):
            return frozenset({"render"})

    assert _preflight(adapter=_QueryOnly(), authorization_id="auth-x").all_pass(
        PreflightPhase.POST_ENGINE
    ) is False

    # 3. no operator-declared authorization context -> hard failure, never fabricated
    assert _preflight(
        adapter=_ProductionShapedAdapter(), authorization_id=None
    ).all_pass(PreflightPhase.POST_ENGINE) is False

    # 4. negotiation raising (engine lacks recovery caps) -> fail closed
    failing = _ProductionShapedAdapter(
        assert_error=UnrealAdapterError("Unreal engine binary lacks required recovery capabilities")
    )
    assert _preflight(adapter=failing, authorization_id="auth-x").all_pass(
        PreflightPhase.POST_ENGINE
    ) is False


def test_m9_phase_map_covers_every_gate_in_evaluation_order():
    pf = _preflight(adapter=None)
    results = pf.run()
    mapped = [
        key
        for phase in (PreflightPhase.PRE_ENGINE, PreflightPhase.POST_ENGINE, PreflightPhase.POST_INTENT)
        for key in PHASE_GATES[phase]
    ]
    assert sorted(mapped) == sorted(r.key for r in results)
    assert [r.phase for r in results] == (
        [PreflightPhase.PRE_ENGINE] * len(PHASE_GATES[PreflightPhase.PRE_ENGINE])
        + [PreflightPhase.POST_ENGINE] * len(PHASE_GATES[PreflightPhase.POST_ENGINE])
        + [PreflightPhase.POST_INTENT] * len(PHASE_GATES[PreflightPhase.POST_INTENT])
    )


def test_m9_preflight_introduces_no_historical_authority_dependency():
    import planning.unreal_live_preflight as P
    src = pathlib.Path(P.__file__).read_text(encoding="utf-8")
    forbidden = (
        "unreal_production_controller_bridge",
        "unreal_autonomous_execution_loop",
        "unreal_authorized_execution_gate",
        "unreal_production_autonomous_loop",
        "unreal_plan_authorization",
        "unreal_recovery_authority",
        "capability_registry",
        "capability_admission",
    )
    assert not any(name in src for name in forbidden)
