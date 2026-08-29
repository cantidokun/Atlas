"""Tests for immutable heterogeneous Unreal production transaction bookkeeping."""

import pytest

from planning.unreal_production_transaction_ledger import UnrealProductionTransactionLedger


def test_ledger_records_contiguous_success_and_preserves_arguments():
    ledger = UnrealProductionTransactionLedger("shot-001")
    next_ledger = ledger.record_success(
        0,
        "inspect_blueprint_state",
        ("FIELD_SURFACE",),
        {"entity_ids": ("FIELD_SURFACE",), "asset_path": "/Game/Atlas/BP_Field"},
        0,
    )

    assert ledger.entries == ()
    assert next_ledger.next_operation_index == 1
    assert next_ledger.completed_operation_indices == (0,)
    assert next_ledger.entries[0].operation_name == "inspect_blueprint_state"
    assert next_ledger.entries[0].arguments["asset_path"] == "/Game/Atlas/BP_Field"


def test_ledger_rejects_non_contiguous_success():
    ledger = UnrealProductionTransactionLedger("shot-001")

    with pytest.raises(ValueError, match="not the next transaction index"):
        ledger.record_success(1, "set_actor_location", ("FIELD_SURFACE",), {}, 0)


def test_ledger_failure_freezes_completed_boundary():
    ledger = UnrealProductionTransactionLedger("shot-001").record_success(
        0,
        "inspect_blueprint_state",
        ("FIELD_SURFACE",),
        {"entity_ids": ("FIELD_SURFACE",)},
        0,
    )
    failed = ledger.record_failure(1)

    assert failed.terminal is True
    assert failed.failed_operation_index == 1
    assert failed.completed_operation_indices == (0,)

    with pytest.raises(ValueError, match="terminal production transaction"):
        failed.record_success(1, "compile_blueprint", ("FIELD_SURFACE",), {}, 1)


def test_ledger_rejects_failure_before_next_operation():
    ledger = UnrealProductionTransactionLedger("shot-001").record_success(
        0,
        "inspect_blueprint_state",
        ("FIELD_SURFACE",),
        {"entity_ids": ("FIELD_SURFACE",)},
        0,
    )

    with pytest.raises(ValueError, match="not the next transaction index"):
        ledger.record_failure(0)


def test_ledger_rejects_second_terminal_failure():
    failed = UnrealProductionTransactionLedger("shot-001").record_failure(0)

    with pytest.raises(ValueError, match="already terminal"):
        failed.record_failure(0)
