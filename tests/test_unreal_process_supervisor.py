"""Deterministic unit tests for AtlasProcessSupervisor and process quiescence evaluation."""

from unittest.mock import MagicMock
import pytest

from scripts.run_unreal_supervisor import (
    AtlasProcessSupervisor,
    evaluate_process_quiescence,
)


def test_evaluate_process_quiescence_uncontained():
    res = evaluate_process_quiescence(None, "UNCONTAINED_ATTACHED")
    assert not res.is_quiescent
    assert res.deployment_mode == "UNCONTAINED_ATTACHED"
    assert "fails closed" in res.reason


def test_evaluate_process_quiescence_contained_active_zero():
    mock_sup = MagicMock(spec=AtlasProcessSupervisor)
    mock_sup.job_handle = 9999
    mock_sup.query_active_processes.return_value = 0

    res = evaluate_process_quiescence(mock_sup, "CONTAINED_JOB_OBJECT")
    assert res.is_quiescent
    assert res.active_process_count == 0
    assert "exactly 0 active processes" in res.reason


def test_evaluate_process_quiescence_contained_active_nonzero():
    mock_sup = MagicMock(spec=AtlasProcessSupervisor)
    mock_sup.job_handle = 9999
    mock_sup.query_active_processes.return_value = 2

    res = evaluate_process_quiescence(mock_sup, "CONTAINED_JOB_OBJECT")
    assert not res.is_quiescent
    assert res.active_process_count == 2
    assert "still has 2 active processes" in res.reason


def test_evaluate_process_quiescence_missing_supervisor():
    res = evaluate_process_quiescence(None, "CONTAINED_JOB_OBJECT")
    assert not res.is_quiescent
    assert "missing/invalid" in res.reason
