"""Shared fixtures for M11.1 router tests."""

import pytest


@pytest.fixture
def profiles_raw():
    return [
        {
            "tier": "L0", "provider": "p0", "model": "m0",
            "capability_floor": "L0",
            "supported_task_classes": ["docs", "doc", "test"],
            "token_budget": 2000, "timeout_s": 30,
        },
        {
            "tier": "L1", "provider": "p1", "model": "m1",
            "capability_floor": "L1",
            "supported_task_classes": ["docs", "test", "refactor", "adapter", "api-boundary"],
            "token_budget": 8000, "timeout_s": 60,
        },
        {
            "tier": "L2", "provider": "p2", "model": "m2",
            "capability_floor": "L2",
            "supported_task_classes": ["docs", "test", "refactor", "api-boundary",
                                       "recovery", "concurrency", "contract"],
            "token_budget": 20000, "timeout_s": 180,
        },
        {
            "tier": "L3", "provider": "p3", "model": "m3",
            "capability_floor": "L3",
            "supported_task_classes": ["docs", "test", "security-crypto", "recovery", "contract"],
            "token_budget": 60000, "timeout_s": 600,
        },
    ]


@pytest.fixture
def profiles(profiles_raw):
    from planning.m11_router.model_profile import load_profiles
    return load_profiles(profiles_raw)


@pytest.fixture
def zero_dims():
    from planning.m11_router.risk import RISK_DIMENSIONS
    return {d: 0 for d in RISK_DIMENSIONS}