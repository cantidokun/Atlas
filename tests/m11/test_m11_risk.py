"""M11.1 deterministic tests: risk classification (design R1-R7)."""

import pytest

from planning.m11_router.risk import (
    RISK_DIMENSIONS,
    HARD_SELECTOR_DIMENSIONS,
    RiskAssessment,
    classify_task,
)
from planning.m11_router.model_profile import ModelTier


def _zero():
    return {d: 0 for d in RISK_DIMENSIONS}


# ---- each dimension 0/1/2/3 sets max_dim correctly ----

def test_all_zero_is_l0():
    r = classify_task("t", _zero(), task_classes=["docs"])
    assert r.max_dim == 0
    assert r.raw_tier == ModelTier.L0
    assert r.final_tier == ModelTier.L0


@pytest.mark.parametrize("dim", RISK_DIMENSIONS)
def test_dimension_1_gives_l1(dim):
    scores = _zero(); scores[dim] = 1
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.max_dim == 1
    assert r.raw_tier == ModelTier.L1
    assert r.final_tier == ModelTier.L1


@pytest.mark.parametrize("dim", RISK_DIMENSIONS)
def test_dimension_2_gives_l2(dim):
    scores = _zero(); scores[dim] = 2
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.raw_tier == ModelTier.L2


@pytest.mark.parametrize("dim", RISK_DIMENSIONS)
def test_dimension_3_gives_l3(dim):
    scores = _zero(); scores[dim] = 3
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.raw_tier == ModelTier.L3


def test_max_dimension_wins():
    scores = _zero(); scores["code_complexity"] = 1; scores["concurrency"] = 3
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.max_dim == 3
    assert r.raw_tier == ModelTier.L3


# ---- unknown/missing signal -> L3 / data_unknown ----

@pytest.mark.parametrize("missing_dim", RISK_DIMENSIONS)
def test_missing_dimension_fails_closed_l3(missing_dim):
    scores = _zero(); del scores[missing_dim]
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.data_complete is False
    assert r.data_unknown is True
    assert missing_dim in r.unknown_signals
    assert r.final_tier == ModelTier.L3  # R6


def test_unknown_not_inflated_when_all_present():
    r = classify_task("t", _zero(), task_classes=["docs"])
    assert r.data_complete is True
    assert r.unknown_signals == frozenset()


# ---- hard selectors force floors (R4) ----

@pytest.mark.parametrize("dim", HARD_SELECTOR_DIMENSIONS)
def test_hard_selector_2_forces_l2(dim):
    scores = _zero(); scores[dim] = 2
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.hard_tier == ModelTier.L2
    assert r.final_tier == ModelTier.L2


@pytest.mark.parametrize("dim", HARD_SELECTOR_DIMENSIONS)
def test_hard_selector_3_forces_l3(dim):
    scores = _zero(); scores[dim] = 3
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.hard_tier == ModelTier.L3
    assert r.final_tier == ModelTier.L3


def test_hard_selector_dim_overrides_low_raw():
    # raw worst dim = 1 (L1) but a hard selector dimension at 2 forces L2.
    scores = _zero()
    scores["code_complexity"] = 1       # non-hard dim
    scores["cryptography"] = 2          # hard selector >= 2 -> L2 floor
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.max_dim == 2
    assert r.raw_tier == ModelTier.L2
    assert r.hard_tier == ModelTier.L2
    assert r.final_tier == ModelTier.L2


def test_hard_file_token_forces_floor_when_raw_low():
    # Low raw score (max_dim=1, raw L1) but a touched hard file marker forces L2.
    scores = _zero()
    scores["code_complexity"] = 1
    r = classify_task("t", scores, task_classes=["docs"],
                      hard_file_tokens=["planning/unreal_render_recovery_coordinator.py"])
    assert r.max_dim == 1
    assert r.raw_tier == ModelTier.L1
    assert r.hard_tier == ModelTier.L2   # R4 hard-file floor
    assert r.final_tier == ModelTier.L2


def test_critical_hard_file_token_forces_l3():
    scores = _zero()
    r = classify_task("t", scores, task_classes=["docs"],
                      hard_file_tokens=["transport_attestation_hmac.cpp"])
    assert r.hard_tier == ModelTier.L3
    assert r.final_tier == ModelTier.L3


# ---- multiple hard selectors -> max (R5) ----

def test_multiple_hard_selectors_take_max():
    scores = _zero()
    scores["cryptography"] = 3    # -> L3
    scores["concurrency"] = 2     # -> L2
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.hard_tier == ModelTier.L3
    assert r.final_tier == ModelTier.L3


def test_two_l2_hard_selectors_stay_l2():
    scores = _zero()
    scores["concurrency"] = 2
    scores["cross_process"] = 2
    r = classify_task("t", scores, task_classes=["docs"])
    assert r.hard_tier == ModelTier.L2
    assert r.final_tier == ModelTier.L2


# ---- task-class hard floors ----

@pytest.mark.parametrize("cls,expect", [
    ("security-crypto", ModelTier.L3),
    ("recovery", ModelTier.L2),
    ("contract", ModelTier.L2),
    ("concurrency", ModelTier.L2),
    ("api-boundary", ModelTier.L1),
    ("adapter", ModelTier.L1),
    ("docs", ModelTier.L0),
])
def test_task_class_floor(cls, expect):
    r = classify_task("t", _zero(), task_classes=[cls])
    # docs alone has no hard floor; for floor classes the class floor wins.
    assert r.final_tier == ModelTier.L0 or r.final_tier == expect
    assert r.final_tier >= expect  # class floor is a minimum


# ---- confidence never influences ----

def test_confidence_ignored():
    scores = _zero(); scores["code_complexity"] = 2
    r_no_confidence = classify_task("t", scores, task_classes=["refactor"], confidence=None)
    r_high_confidence = classify_task("t", scores, task_classes=["refactor"], confidence=0.99)
    r_low_confidence = classify_task("t", scores, task_classes=["refactor"], confidence=0.01)
    assert r_no_confidence.final_tier == r_high_confidence.final_tier == r_low_confidence.final_tier
    assert r_no_confidence == r_high_confidence


def test_classify_is_pure_deterministic():
    scores = _zero(); scores["recovery_statefulness"] = 3; scores["cryptography"] = 2
    a = classify_task("job-x", dict(scores), task_classes=["recovery"])
    b = classify_task("job-x", dict(scores), task_classes=["recovery"])
    assert a == b
    # same scores, different task_id still same tier
    c = classify_task("job-y", dict(scores), task_classes=["recovery"])
    assert a.final_tier == c.final_tier


# ---- result shape ----

def test_risk_assessment_shape():
    scores = _zero(); scores["cryptography"] = 3
    r = classify_task("t", scores, task_classes=["security-crypto"])
    assert isinstance(r, RiskAssessment)
    assert r.final_tier == ModelTier.L3
    assert isinstance(r.reasons, tuple) and r.reasons
    assert set(r.dimension_scores.keys()) == set(RISK_DIMENSIONS)