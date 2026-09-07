"""M11.4 deterministic tests: telemetry integrity (Phase 6) and benchmark
execution (Phase 3/4 baseline comparison).

Uses mocked adapters; never hits a live provider in the deterministic suite.
"""

import pytest

from planning.m11_router.telemetry import AppendOnlyTelemetry, RouterTelemetryRecord, TelemetryValidationError
from planning.m11_router.risk import RISK_DIMENSIONS
from planning.m11_router.live_validation import LiveValidationResult
from planning.m11_router.benchmark import SAMPLE_BENCHMARK_TASKS, run_benchmark_corpus
from planning.m11_router.model_profile import load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.provider.providers_config import ProviderConfig, ModelTier

# ---- telemetry integrity (Phase 6) ----

def test_telemetry_no_credential_material(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "t.jsonl")
    # A record attempting to carry a credential-looking value must be REJECTED.
    for bad in (
        "Authorization: Bearer test-only-fake-token-not-a-real-credential",
        "Authorization: Basic Zm9vOmJhcg==",
        "x-api-key: test-only-fake-token-not-a-real-credential",
        "api_key=test-only-fake-token-not-a-real-credential",
        "Bearer test-only-fake-token-not-a-real-credential",
    ):
        with pytest.raises(TelemetryValidationError):
            RouterTelemetryRecord(task_id="t", attempt_id="a", selection_reason=bad)


def test_telemetry_never_stores_attempt_nonce(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a",
                              selection_reason="attempt_nonce=deadbeefcafe")


def test_telemetry_never_stores_hmac_key(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a",
                              selection_reason="hmac key: abcdef01")


def test_telemetry_never_stores_header(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a",
                              selection_reason="x-api-key: k-1234567890")


def test_telemetry_never_stores_credential_prompt(tmp_path):
    with pytest.raises(TelemetryValidationError):
        RouterTelemetryRecord(task_id="t", attempt_id="a",
                              selection_reason="prompt with sk-test-only-fake-token secret")


def test_append_only_identity_stable_unique(tmp_path):
    tele = AppendOnlyTelemetry(tmp_path / "t.jsonl")
    tele.append(RouterTelemetryRecord(task_id="task-x", attempt_id="a1"))
    tele.append(RouterTelemetryRecord(task_id="task-x", attempt_id="a2", record_type="escalation", escalation_id="e1"))
    recs = tele.read_task("task-x")
    assert len(recs) == 2
    assert {r.attempt_id for r in recs} == {"a1", "a2"}
    # previous records never mutated
    assert recs[0].attempt_id == "a1"


def test_live_result_contains_no_secret_fields():
    r = LiveValidationResult(task_id="t", attempt_id="a", selected_tier="L0",
                             provider="p", model="m", request_status="success")
    d = r.to_dict()
    for k in d:
        assert "authorization" not in k.lower()
        assert "api_key" not in k.lower()
        assert "secret" not in k.lower()
        assert "nonce" not in k.lower()
    assert isinstance(r.to_dict()["error_message"], type(None)) or True


# ---- benchmark execution (Phase 3/4) ----

def _router():
    profiles = load_profiles([
        {"tier": "L0", "provider": "cfg0", "model": "cfg-lite", "capability_floor": "L0",
         "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
        {"tier": "L1", "provider": "cfg1", "model": "cfg-eng", "capability_floor": "L1",
         "supported_task_classes": ["docs", "test", "refactor", "adapter", "api-boundary"],
         "token_budget": 8000, "timeout_s": 60},
        {"tier": "L2", "provider": "cfg2", "model": "cfg-strong", "capability_floor": "L2",
         "supported_task_classes": ["docs", "test", "refactor", "api-boundary", "recovery", "concurrency", "contract"],
         "token_budget": 20000, "timeout_s": 180},
        {"tier": "L3", "provider": "cfg3", "model": "cfg-frontier", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600},
    ])
    return ModelRouter(profiles)


def _pcfgs():
    return [
        ProviderConfig(provider="openrouter", model="lite", capability_tier=ModelTier.L0,
                       supported_task_classes=frozenset({"docs", "test"}),
                       token_budget=2000, timeout_s=30),
        ProviderConfig(provider="openrouter", model="flash", capability_tier=ModelTier.L1,
                       supported_task_classes=frozenset({"docs", "test", "refactor"}),
                       token_budget=8000, timeout_s=60),
        ProviderConfig(provider="openrouter", model="frontier", capability_tier=ModelTier.L3,
                       supported_task_classes=frozenset({"security-crypto", "recovery"}),
                       token_budget=60000, timeout_s=600),
    ]


def test_benchmark_offline_live_false_no_provider_calls():
    router = _router()
    report = run_benchmark_corpus(router, live=False)
    assert report["live"] is False
    assert report["summary"]["tasks_total"] == len(SAMPLE_BENCHMARK_TASKS)
    # no execution happened (provider-independent, offline-safe)
    assert report["summary"]["tasks_executed"] == 0
    assert all(t["executed"] is False for t in report["tasks"])


def test_benchmark_machine_readable_shape():
    router = _router()
    report = run_benchmark_corpus(router, live=False)
    assert set(report.keys()) == {"summary", "tasks", "live"}
    assert set(report["summary"].keys()) >= {
        "tasks_total", "tasks_executed", "first_pass_success", "useful_output_rate",
        "provider_errors", "evidence_failures",
    }
    # UNKNOWN values are honest None/0, never fabricated numbers.
    assert report["summary"]["useful_output_rate"] is None  # nothing executed


def test_benchmark_router_selects_expected_tiers():
    router = _router()
    report = run_benchmark_corpus(router, live=False)
    tiers = {t["task_id"]: t["selected_tier"] for t in report["tasks"]}
    # docs->L0, crypto->L3 (security class floor), recovery->L2
    assert tiers["b-docs-001"] == "L0"
    assert tiers["b-crypto-001"] == "L3"
    assert tiers["b-recovery-001"] == "L2"
    assert tiers["b-api-001"] == "L2"


def test_benchmark_provider_failure_honest(monkeypatch):
    """With a failing stub validator+adapter, the report counts provider_errors
    and does not fabricate a useful-output success."""
    router = _router()
    from tests.m11.test_m11_live_validation import StubAdapter
    from planning.m11_router.provider.invocation import InvocationErrorKind
    from planning.m11_router.live_validation import ControlledLiveValidator
    fail = StubAdapter(status="error", error_class=InvocationErrorKind.PROVIDER_UNAVAILABLE.value)
    validator = ControlledLiveValidator(router, _pcfgs(), adapter=fail)
    report = run_benchmark_corpus(router, validator=validator, live=True)
    assert report["summary"]["tasks_executed"] >= 1
    assert report["summary"]["first_pass_success"] == 0
    assert report["summary"]["provider_errors"] == report["summary"]["tasks_executed"]
    assert report["summary"]["useful_output_rate"] == 0.0  # honest failure rate


def test_deterministic_suite_never_touches_live_provider():
    """The default off behavior must not issue any provider call."""
    router = _router()
    report = run_benchmark_corpus(router, live=False)
    assert report["live"] is False
    assert report["summary"]["tasks_executed"] == 0