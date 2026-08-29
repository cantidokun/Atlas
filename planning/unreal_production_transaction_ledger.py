"""Immutable execution ledger for heterogeneous Unreal production transactions.

The executor remains responsible for performing Unreal operations. This module
owns only transaction bookkeeping: contiguous progress, terminal failure
boundaries, and immutable evidence/operation context needed for recovery.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Tuple


def _freeze(value: Any) -> Any:
    """Recursively snapshot operation context so nested values cannot mutate."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class UnrealProductionLedgerEntry:
    """One operation that reached a terminal execution result."""

    operation_index: int
    operation_name: str
    entity_ids: Tuple[str, ...]
    arguments: Mapping[str, Any]
    evidence_index: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "entity_ids", tuple(self.entity_ids))
        object.__setattr__(self, "arguments", _freeze(dict(self.arguments)))


@dataclass(frozen=True)
class UnrealProductionTransactionLedger:
    """Immutable cursor over a single production-plan execution."""

    intent_id: str
    entries: Tuple[UnrealProductionLedgerEntry, ...] = ()
    failed_operation_index: int | None = None
    failed_operation_name: str | None = None
    failed_entity_ids: Tuple[str, ...] = ()
    failed_arguments: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise ValueError("intent_id must be a non-empty string")
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "failed_entity_ids", tuple(self.failed_entity_ids))
        object.__setattr__(self, "failed_arguments", _freeze({} if self.failed_arguments is None else dict(self.failed_arguments)))
        if self.failed_operation_index is not None and self.failed_operation_index < 0:
            raise ValueError("failed_operation_index must be non-negative")
        if self.failed_operation_index is None:
            if self.failed_operation_name is not None or self.failed_entity_ids or self.failed_arguments:
                raise ValueError("failure context cannot exist without failed_operation_index")
        elif not isinstance(self.failed_operation_name, str) or not self.failed_operation_name.strip():
            raise ValueError("failed_operation_name must be provided for a terminal transaction")

    @property
    def next_operation_index(self) -> int:
        return len(self.entries)

    @property
    def terminal(self) -> bool:
        return self.failed_operation_index is not None

    @property
    def completed_operation_indices(self) -> Tuple[int, ...]:
        return tuple(entry.operation_index for entry in self.entries)

    def record_success(
        self,
        operation_index: int,
        operation_name: str,
        entity_ids: Tuple[str, ...],
        arguments: Mapping[str, Any],
        evidence_index: int,
    ) -> "UnrealProductionTransactionLedger":
        """Return a new ledger after one successful operation."""
        if self.terminal:
            raise ValueError("cannot append to a terminal production transaction")
        if operation_index != self.next_operation_index:
            raise ValueError(
                f"operation index {operation_index} is not the next transaction index {self.next_operation_index}"
            )
        if evidence_index < 0:
            raise ValueError("evidence_index must be non-negative")
        entry = UnrealProductionLedgerEntry(
            operation_index,
            operation_name,
            tuple(entity_ids),
            dict(arguments),
            evidence_index,
        )
        return UnrealProductionTransactionLedger(
            intent_id=self.intent_id,
            entries=self.entries + (entry,),
        )

    def record_failure(
        self,
        operation_index: int,
        operation_name: str,
        entity_ids: Tuple[str, ...],
        arguments: Mapping[str, Any],
    ) -> "UnrealProductionTransactionLedger":
        """Return a terminal ledger containing the exact failed operation context."""
        if self.terminal:
            raise ValueError("production transaction is already terminal")
        if operation_index != self.next_operation_index:
            raise ValueError(
                f"failure index {operation_index} is not the next transaction index {self.next_operation_index}"
            )
        return UnrealProductionTransactionLedger(
            intent_id=self.intent_id,
            entries=self.entries,
            failed_operation_index=operation_index,
            failed_operation_name=operation_name,
            failed_entity_ids=tuple(entity_ids),
            failed_arguments=dict(arguments),
        )
