"""Tests for the production-ledger-backed Unreal executor."""

import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_plan_executor import UnrealPlanExecutionError
from planning.unreal_production_transaction_ledger import UnrealProductionTransactionLedger
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transactional_executor import UnrealTransactionalPlanExecutor


class _Harness(UnrealTransactionalPlanExecutor):
    def __init__(self, failures=None):
        self._failures = dict(failures or {})
        self.calls = []

    def _validate_execution_shape(self, plan):
        return None

    def _preflight_plan(self, plan):
        return None

    def _execute_one(self, operation, authorization_id, **kwargs):
        self.calls.append(operation.name)
        if operation.name in self._failures:
            raise ValueError(self._failures[operation.name])
        return object()


def _plan(*names):
    operations = tuple(
        UnrealOperation(
            UnrealCapability.INSPECT_ACTOR,
            UnrealOperationKind.READ,
            name,
            {"entity_ids": ("FIELD_SURFACE",)},
            ("FIELD_SURFACE",),
        )
        for name in names
    )
    return UnrealTaskPlan("shot-transaction", operations)


def test_successful_execution_returns_complete_transaction_ledger():
    executor = _Harness()
    result = executor.execute(_plan("inspect_a", "inspect_b"), "auth-001")

    assert isinstance(result.transaction_ledger, UnrealProductionTransactionLedger)
    assert result.transaction_ledger.completed_operation_indices == (0, 1)
    assert result.transaction_ledger.failed_operation_index is None
    assert [entry.operation_name for entry in result.transaction_ledger.entries] == ["inspect_a", "inspect_b"]
    assert executor.calls == ["inspect_a", "inspect_b"]


def test_failure_freezes_ledger_at_exact_operation_and_does_not_continue():
    executor = _Harness({"inspect_b": "injected failure"})

    with pytest.raises(UnrealPlanExecutionError) as raised:
        executor.execute(_plan("inspect_a", "inspect_b", "inspect_c"), "auth-001")

    failure = raised.value.failure
    ledger = raised.value.transaction_ledger
    assert failure is not None
    assert failure.operation_index == 1
    assert failure.completed_operation_arguments == ({"entity_ids": ("FIELD_SURFACE",)},)
    assert executor.calls == ["inspect_a", "inspect_b"]
    assert ledger.failed_operation_index == 1
    assert ledger.failed_operation_name == "inspect_b"
    assert ledger.failed_entity_ids == ("FIELD_SURFACE",)
    assert ledger.failed_arguments == {"entity_ids": ("FIELD_SURFACE",)}
    assert ledger.completed_operation_indices == (0,)
    assert ledger.terminal is True


def test_transactional_ledger_deeply_freezes_nested_arguments():
    arguments = {
        "entity_ids": ("FIELD_SURFACE",),
        "render": {"resolution": {"width": 1280, "height": 720}, "passes": ["beauty", "depth"]},
    }
    ledger = UnrealProductionTransactionLedger("shot-transaction").record_success(
        0, "configure_render", arguments["entity_ids"], arguments, 0
    )

    arguments["render"]["resolution"]["width"] = 9999
    arguments["render"]["passes"].append("motion_vectors")

    stored = ledger.entries[0].arguments
    assert stored["render"]["resolution"]["width"] == 1280
    assert stored["render"]["passes"] == ("beauty", "depth")
    with pytest.raises(TypeError):
        stored["render"]["resolution"]["width"] = 1


def test_terminal_ledger_rejects_any_further_progress():
    ledger = UnrealProductionTransactionLedger("shot-transaction").record_failure(
        0, "inspect_a", ("FIELD_SURFACE",), {"entity_ids": ("FIELD_SURFACE",)}
    )
    with pytest.raises(ValueError, match="cannot append"):
        ledger.record_success(1, "inspect_b", ("FIELD_SURFACE",), {}, 1)
    with pytest.raises(ValueError, match="already terminal"):
        ledger.record_failure(0, "inspect_a", ("FIELD_SURFACE",), {})


def test_transactional_executor_rejects_empty_authorization_id():
    executor = _Harness()

    with pytest.raises(UnrealPlanExecutionError, match="authorization_id must be a non-empty string"):
        executor.execute(_plan("inspect_a"), "")
