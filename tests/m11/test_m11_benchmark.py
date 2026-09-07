"""M11.1 deterministic tests: benchmark harness skeleton (design §12)."""

from planning.m11_router.benchmark import (
    SAMPLE_BENCHMARKS,
    SAMPLE_BENCHMARK_TASKS,
    run_benchmark_task,
)
from planning.m11_router.model_profile import ModelTier, load_profiles
from planning.m11_router.router import ModelRouter
from planning.m11_router.risk import RISK_DIMENSIONS


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


def _profiles():
    return load_profiles([
        {"tier": "L0", "provider": "p0", "model": "m0", "capability_floor": "L0",
         "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
        {"tier": "L1", "provider": "p1", "model": "m1", "capability_floor": "L1",
         "supported_task_classes": ["docs", "test", "refactor", "adapter", "api-boundary"],
         "token_budget": 8000, "timeout_s": 60},
        {"tier": "L2", "provider": "p2", "model": "m2", "capability_floor": "L2",
         "supported_task_classes": ["docs", "test", "refactor", "api-boundary", "recovery", "concurrency", "contract"],
         "token_budget": 20000, "timeout_s": 180},
        {"tier": "L3", "provider": "p3", "model": "m3", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600},
    ])


def test_sample_benchmark_fixtures_present():
    ids = sorted(SAMPLE_BENCHMARKS.keys())
    assert ids == ["b-api-001", "b-crypto-001", "b-docs-001",
                   "b-recovery-001", "b-refactor-001", "b-test-001"]
    # expected tiers cover the full range
    assert {(t.task_id): t.expected_risk_tier for t in SAMPLE_BENCHMARK_TASKS} == {
        "b-docs-001": ModelTier.L0,
        "b-test-001": ModelTier.L1,
        "b-refactor-001": ModelTier.L1,
        "b-api-001": ModelTier.L2,
        "b-recovery-001": ModelTier.L2,
        "b-crypto-001": ModelTier.L3,
    }


def test_full_dimension_scores_are_complete():
    for task in SAMPLE_BENCHMARK_TASKS:
        full = task.full_dimension_scores
        assert set(full.keys()) == set(RISK_DIMENSIONS)
        assert all(isinstance(v, int) and 0 <= v <= 3 for v in full.values())


def test_run_benchmark_fixture_docs_l0():
    router = ModelRouter(_profiles())
    res = run_benchmark_task(SAMPLE_BENCHMARKS["b-docs-001"], router)
    assert res.outcome == "ROUTED"
    assert res.measured_metrics["selected_tier"] == "L0"
    assert res.measured_metrics["model"] == "m0"


def test_run_benchmark_fixture_crypto_l3():
    router = ModelRouter(_profiles())
    res = run_benchmark_task(SAMPLE_BENCHMARKS["b-crypto-001"], router)
    assert res.outcome == "ROUTED"
    assert res.measured_metrics["selected_tier"] == "L3"
    assert res.measured_metrics["model"] == "m3"


def test_token_cost_hooks_exist():
    # Fixtures carry a token/cost hook field (may be None).
    assert all(hasattr(t, "token_cost_hint") for t in SAMPLE_BENCHMARK_TASKS)