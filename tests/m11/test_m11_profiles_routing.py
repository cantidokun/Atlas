"""M11.1 deterministic tests: model profile + routing (design §5, §6)."""

import pytest

from planning.m11_router.model_profile import (
    ModelProfile,
    ModelTier,
    ProfileLoadError,
    load_profiles,
)
from planning.m11_router.risk import RISK_DIMENSIONS, classify_task
from planning.m11_router.routing import NoCapableProfileError, select_profile


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


# ---- malformed config rejected fail-closed ----

def test_profile_missing_tier_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs"], "token_budget": 1, "timeout_s": 1}])


def test_profile_missing_provider_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L0", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs"], "token_budget": 1, "timeout_s": 1}])


def test_profile_capability_floor_must_equal_tier():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L1", "provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs"], "token_budget": 1, "timeout_s": 1}])


def test_profile_empty_supported_classes_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L0", "provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": [], "token_budget": 1, "timeout_s": 1}])


def test_profile_unknown_task_class_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L0", "provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs", "made-up-class"], "token_budget": 1, "timeout_s": 1}])


def test_profile_nonpositive_budget_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L0", "provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs"], "token_budget": 0, "timeout_s": 1}])


def test_profile_nonpositive_timeout_rejected():
    with pytest.raises(ProfileLoadError):
        load_profiles([{"tier": "L0", "provider": "p", "model": "m", "capability_floor": "L0",
                        "supported_task_classes": ["docs"], "token_budget": 1, "timeout_s": 0}])


def test_profile_is_immutable():
    profiles = load_profiles([{"tier": "L0", "provider": "p", "model": "m", "capability_floor": "L0",
                               "supported_task_classes": ["docs"], "token_budget": 100, "timeout_s": 10}])
    p = profiles[0]
    with pytest.raises(AttributeError):
        p.token_budget = 999  # frozen dataclass


# ---- routing: lowest capable tier selected ----

def test_routing_picks_lowest_capable(profiles):
    risk = classify_task("t", _zero(), task_classes=["docs"])
    sel = select_profile("t", risk, profiles)
    assert sel.selected_tier == ModelTier.L0
    assert sel.selected_model_id == "m0"


def test_routing_escalates_class_to_proper_tier(profiles):
    scores = _zero(); scores["cryptography"] = 3
    risk = classify_task("t", scores, task_classes=["security-crypto"])
    sel = select_profile("t", risk, profiles)
    assert sel.selected_tier == ModelTier.L3
    assert sel.selected_model_id == "m3"


def test_routing_capability_mismatch_fails_safely(profiles_raw):
    # Only an L0 profile exists but the task needs L3 -> no capable profile.
    only_l0 = load_profiles([profiles_raw[0]])
    scores = _zero(); scores["cryptography"] = 3
    risk = classify_task("t", scores, task_classes=["security-crypto"])
    with pytest.raises(NoCapableProfileError):
        select_profile("t", risk, only_l0)


def test_routing_unsupported_task_class_rejected_safely(profiles_raw):
    # A profile set that does NOT list 'security-crypto' anywhere.
    profiles_without_crypto = load_profiles([
        {**profiles_raw[1]},
        {**profiles_raw[0]},
    ])
    scores = _zero(); scores["cryptography"] = 3
    risk = classify_task("t", scores, task_classes=["security-crypto"])
    # L2 profile (m2) covers... actually none support security-crypto -> raise.
    with pytest.raises(NoCapableProfileError):
        select_profile("t", risk, profiles_without_crypto, require_task_class_support=True)


def test_routing_self_report_cannot_lower_tier(profiles):
    # The same profile set must be selected regardless of any 'confidence'.
    risk_low = classify_task("t", _zero(), task_classes=["docs"], confidence=0.0)
    risk_high = classify_task("t", _zero(), task_classes=["docs"], confidence=0.99)
    assert select_profile("t", risk_low, profiles) == select_profile("t", risk_high, profiles)


# ---- provider/model names are config ----

def test_profiles_are_config_driven():
    # Same task classes, different provider/model names from config -> respected.
    profiles = load_profiles([
        {"tier": "L0", "provider": "acme", "model": "tiny-7b", "capability_floor": "L0",
         "supported_task_classes": ["docs"], "token_budget": 500, "timeout_s": 15},
        {"tier": "L3", "provider": "acme", "model": "huge-120b", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto"], "token_budget": 90000, "timeout_s": 900},
    ])
    assert profiles[0].provider == "acme"
    assert profiles[0].model_id == "tiny-7b"
    scores = _zero(); scores["cryptography"] = 3
    risk = classify_task("t", scores, task_classes=["security-crypto"])
    sel = select_profile("t", risk, profiles)
    assert sel.selected_model_id == "huge-120b"