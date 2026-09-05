"""Engine-neutral evidence contract for the Unreal Agent boundary.

Evidence is produced by the Unreal side after an operation is executed. It is
not an authorization receipt and cannot authorize itself. Atlas verification
consumes this evidence independently of the agent's proposal.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence, Tuple


def _validate_canonical_identity(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a non-empty canonical string")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(item) for item in value), key=repr)
    return value


@dataclass(frozen=True)
class UnrealEvidence:
    operation_name: str
    entity_ids: Tuple[str, ...]
    observed_state: Mapping[str, Any]
    source: str
    verified: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation_name, str) or not self.operation_name.strip():
            raise ValueError("operation_name must not be empty")
        if not isinstance(self.entity_ids, (list, tuple)):
            raise TypeError("evidence entity_ids must be a sequence")
        entity_ids = tuple(self.entity_ids)
        if not entity_ids:
            raise ValueError("evidence requires explicit entity IDs")
        if any(not isinstance(entity_id, str) or not entity_id.strip() for entity_id in entity_ids):
            raise ValueError("evidence entity_ids must not contain empty values")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("evidence source must not be empty")
        if not isinstance(self.observed_state, Mapping):
            raise TypeError("observed_state must be a mapping")
        if not isinstance(self.verified, bool):
            raise TypeError("verified must be a boolean")
        object.__setattr__(self, "entity_ids", entity_ids)
        object.__setattr__(self, "observed_state", _freeze(self.observed_state))

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible snapshot of the immutable evidence."""
        return {
            "operation_name": self.operation_name,
            "entity_ids": list(self.entity_ids),
            "observed_state": _thaw(self.observed_state),
            "source": self.source,
            "verified": self.verified,
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "UnrealEvidence":
        """Reconstruct evidence from an exact persisted snapshot, fail-closed."""
        if not isinstance(snapshot, Mapping):
            raise TypeError("Unreal evidence snapshot must be a mapping")
        required = {"operation_name", "entity_ids", "observed_state", "source", "verified"}
        if set(snapshot) != required:
            raise ValueError("Unreal evidence snapshot fields are invalid")
        return cls(
            operation_name=snapshot["operation_name"],
            entity_ids=snapshot["entity_ids"],
            observed_state=snapshot["observed_state"],
            source=snapshot["source"],
            verified=snapshot["verified"],
        )


def validate_evidence_for_operation(evidence: UnrealEvidence, operation_name: str, entity_ids: Tuple[str, ...]) -> UnrealEvidence:
    """Ensure evidence refers exactly to the operation and Atlas targets."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence instance")
    if evidence.operation_name != operation_name:
        raise ValueError("evidence operation_name does not match operation")
    if tuple(evidence.entity_ids) != tuple(entity_ids):
        raise ValueError("evidence entity_ids do not match operation targets")
    return evidence


def verify_render_job_evidence(
    *,
    operation_name: str,
    entity_ids: Sequence[str],
    observed_state: Mapping[str, Any],
    source: str,
) -> UnrealEvidence:
    """Authoritatively verify raw observed Unreal render-job state and construct verified UnrealEvidence.

    This is the independent verification boundary for Unreal render jobs.
    It verifies:
    - operation_name == 'inspect_render_job'
    - entity_ids is a non-empty sequence of non-empty strings
    - job_id exists and is canonical
    - sequence_asset_path exists and is canonical
    - status is 'completed' or 'finished'
    - finished is True
    - success is True
    - failed is False
    - output_files is a non-empty sequence of non-empty strings
    - every output file exists on the local filesystem, is accessible, and has size > 0

    Only after all checks succeed is UnrealEvidence instantiated with verified=True.
    """
    if operation_name != "inspect_render_job":
        raise ValueError("render job verification requires operation_name == 'inspect_render_job'")
    if not isinstance(entity_ids, (list, tuple)):
        raise TypeError("entity_ids must be a sequence")
    normalized_entity_ids = tuple(entity_ids)
    if not normalized_entity_ids:
        raise ValueError("entity_ids cannot be empty")
    for eid in normalized_entity_ids:
        _validate_canonical_identity("entity_id", eid)
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not isinstance(observed_state, Mapping):
        raise TypeError("observed_state must be a mapping")

    job_id = observed_state.get("job_id")
    sequence_asset_path = observed_state.get("sequence_asset_path")
    _validate_canonical_identity("job_id", job_id)
    _validate_canonical_identity("sequence_asset_path", sequence_asset_path)

    status = observed_state.get("status")
    if status not in ("completed", "finished"):
        raise ValueError(f"render job status must be 'completed' or 'finished', got: {status!r}")

    finished = observed_state.get("finished")
    if finished is not True:
        raise ValueError(f"render job finished flag must be True, got: {finished!r}")

    success = observed_state.get("success")
    if success is not True:
        raise ValueError(f"render job success flag must be True, got: {success!r}")

    failed = observed_state.get("failed")
    if failed is not False:
        raise ValueError(f"render job failed flag must be False, got: {failed!r}")

    output_files = observed_state.get("output_files")
    if not isinstance(output_files, (list, tuple)):
        raise TypeError("observed_state.output_files must be a sequence")
    if len(output_files) == 0:
        raise ValueError("observed_state.output_files must not be empty")

    normalized_output_files = []
    for file_path in output_files:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("output file path must be a non-empty string")
        path_obj = Path(file_path.strip())
        try:
            if not path_obj.exists():
                raise FileNotFoundError(f"render output file does not exist on disk: {file_path}")
            if not path_obj.is_file():
                raise ValueError(f"render output path is not a file: {file_path}")
            file_stat = path_obj.stat()
            if file_stat.st_size <= 0:
                raise ValueError(f"render output file has zero or negative size: {file_path} ({file_stat.st_size} bytes)")
        except (OSError, PermissionError) as exc:
            if isinstance(exc, (FileNotFoundError, ValueError)):
                raise
            raise PermissionError(f"render output file is not accessible: {file_path}") from exc
        normalized_output_files.append(file_path.strip())

    # Build clean state mapping with verified values
    clean_state = dict(observed_state)
    clean_state["output_files"] = normalized_output_files

    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=normalized_entity_ids,
        observed_state=clean_state,
        source=source.strip(),
        verified=True,
    )

