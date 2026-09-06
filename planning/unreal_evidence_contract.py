"""Engine-neutral evidence contract for the Unreal Agent boundary.

Evidence is produced by the Unreal side after an operation is executed. It is
not an authorization receipt and cannot authorize itself. Atlas verification
consumes this evidence independently of the agent's proposal.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple
from planning.unreal_render_job_record import AtlasRenderJobRecord


def _validate_canonical_identity(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a non-empty canonical string")
    return value


VALID_EVIDENCE_SOURCE_CLASSES = frozenset({"ENGINE_LIVE", "ENGINE_JOURNAL_ATTESTED"})


class UnrealEvidenceVerificationError(ValueError):
    """Raised when raw Unreal render-job evidence fails verification checks."""


def verify_png_completeness(
    file_path: Path,
    expected_size: Optional[int] = None,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> bool:
    """Validate PNG container completeness: signature, IHDR dimensions, chunk structure, chunk CRCs, and IEND."""
    import struct
    import zlib

    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    if not file_path.is_file():
        return False

    file_size = file_path.stat().st_size
    if file_size < 8 + 12 + 12:  # Signature + minimal IHDR + minimal IEND
        return False
    if expected_size is not None and file_size != expected_size:
        return False

    with file_path.open("rb") as f:
        sig = f.read(8)
        if sig != bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
            return False

        has_ihdr = False
        has_iend = False
        chunk_index = 0

        while True:
            chunk_len_bytes = f.read(4)
            if not chunk_len_bytes or len(chunk_len_bytes) < 4:
                break
            chunk_len = struct.unpack(">I", chunk_len_bytes)[0]
            chunk_type = f.read(4)
            if len(chunk_type) < 4:
                return False
            # Chunk type must be 4 legal PNG ASCII letters (65-90, 97-122)
            if not all((65 <= b <= 90) or (97 <= b <= 122) for b in chunk_type):
                return False

            chunk_index += 1

            if chunk_type == b"IHDR":
                if has_ihdr or chunk_index != 1:
                    return False
                if chunk_len != 13:
                    return False
                has_ihdr = True

            data = f.read(chunk_len)
            if len(data) < chunk_len:
                return False
            crc_bytes = f.read(4)
            if len(crc_bytes) < 4:
                return False
            expected_crc = struct.unpack(">I", crc_bytes)[0]
            actual_crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                return False

            if chunk_type == b"IHDR":
                width, height = struct.unpack(">II", data[:8])
                if width <= 0 or height <= 0:
                    return False
                if expected_width is not None and width != expected_width:
                    return False
                if expected_height is not None and height != expected_height:
                    return False

            if chunk_type == b"IEND":
                if has_iend or not has_ihdr:
                    return False
                if chunk_len != 0:
                    return False
                has_iend = True
                # IEND must be the final chunk (no trailing bytes)
                extra = f.read(1)
                if extra:
                    return False
                break

    return has_ihdr and has_iend


def _verify_png_idat_decompression(file_path: Path, min_decompressed_bytes: Optional[int] = None) -> bool:
    """Verify that IDAT compressed data can be successfully decompressed via zlib without truncation."""
    import struct
    import zlib

    if not file_path.is_file():
        return False

    idat_chunks = []
    with file_path.open("rb") as f:
        sig = f.read(8)
        if sig != bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
            return False

        while True:
            chunk_len_bytes = f.read(4)
            if not chunk_len_bytes or len(chunk_len_bytes) < 4:
                break
            chunk_len = struct.unpack(">I", chunk_len_bytes)[0]
            chunk_type = f.read(4)
            if len(chunk_type) < 4:
                return False
            data = f.read(chunk_len)
            f.read(4)  # skip CRC
            if chunk_type == b"IDAT":
                idat_chunks.append(data)
            elif chunk_type == b"IEND":
                break

    # Block 6: A PNG intended as an image output MUST contain non-empty IDAT chunk(s)
    if not idat_chunks:
        raise UnrealEvidenceVerificationError(f"PNG contains zero IDAT data chunks: {file_path}")

    try:
        combined = b"".join(idat_chunks)
        decompressor = zlib.decompressobj()
        decompressed = decompressor.decompress(combined)
        # Flush any remaining uncompressed data
        decompressed += decompressor.flush()

        if not decompressor.eof:
            return False
        if decompressor.unused_data:
            return False
        if decompressor.unconsumed_tail:
            return False
        if len(decompressed) == 0:
            raise UnrealEvidenceVerificationError(f"PNG IDAT decompressed to zero bytes: {file_path}")
        if min_decompressed_bytes is not None and len(decompressed) < min_decompressed_bytes:
            raise UnrealEvidenceVerificationError(
                f"PNG IDAT decompressed bytes {len(decompressed)} less than expected raster minimum {min_decompressed_bytes}: {file_path}"
            )
        return True
    except zlib.error:
        return False


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


def validate_raw_render_observation(
    *,
    operation_name: str,
    entity_ids: Sequence[str],
    observed_state: Mapping[str, Any],
    source: str,
) -> dict:
    """Non-authoritative validation for preliminary raw Unreal render observation data.

    This helper verifies basic shape and terminal flags for debugging and status polling.
    CRITICAL INVARIANT: This helper MUST NOT construct or return UnrealEvidence(verified=True).
    Only verify_render_job_evidence() with an authoritative AtlasRenderJobRecord can construct verified evidence.
    """
    if operation_name != "inspect_render_job":
        raise ValueError("render job validation requires operation_name == 'inspect_render_job'")
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

    for file_path in output_files:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("output file path must be a non-empty string")
        path_obj = Path(file_path.strip())
        if not path_obj.exists():
            raise FileNotFoundError(f"render output file does not exist on disk: {file_path}")
        if not path_obj.is_file():
            raise ValueError(f"render output path is not a file: {file_path}")
        if path_obj.stat().st_size <= 0:
            raise ValueError(f"render output file has zero or negative size: {file_path}")

    return dict(observed_state)


def verify_render_job_evidence(
    *,
    operation_name: str,
    entity_ids: Sequence[str],
    observed_state: Mapping[str, Any],
    source: str,
    job_record: Any,
    evidence_source_class: Optional[str] = None,
) -> UnrealEvidence:
    """Authoritatively verify raw observed Unreal render-job state and construct verified UnrealEvidence.

    Contract V1 §13–§16 Independent Evidence Verification Boundary:
    - job_record: AtlasRenderJobRecord is STRICTLY MANDATORY. Authoritative verification cannot occur without durable intent.
    - operation_name == 'inspect_render_job'
    - entity_ids is a non-empty sequence of non-empty strings
    - job_id exists and is canonical
    - sequence_asset_path exists and is canonical
    - status is 'completed' or 'finished'
    - finished is True, success is True, failed is False
    - output_files is a non-empty sequence of non-empty strings
    - every output file exists, is accessible, and has size > 0
    - validates evidence_source_class in {ENGINE_LIVE, ENGINE_JOURNAL_ATTESTED} (strictly enforced; unknown fails closed)
    - validates all mandatory identity bindings (atlas_job_id, unreal_job_id, session_id, process info, auth, twin, seq, config, output_dir)
    - validates output path isolation (all files inside output_directory, no path traversal, no ADS, no 8.3/device namespaces)
    - validates engine-attested output manifest (size, sha256) matches disk bytes exactly
    - validates PNG completeness (IHDR, CRCs, terminal IEND, dimensions, IDAT decompression) for PNG outputs
    - validates expected_output_spec topology (format, frame count, dimensions)
    """
    import hashlib

    if job_record is None:
        raise UnrealEvidenceVerificationError("job_record is strictly mandatory for authoritative evidence verification")

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

    # Source class validation (Block 1: mandatory & strict)
    if not isinstance(source, str) or not source.strip() or "\x00" in source:
        raise UnrealEvidenceVerificationError("source must be a non-empty string without null bytes")
    source_clean = source.strip()

    if evidence_source_class is None:
        if source_clean in VALID_EVIDENCE_SOURCE_CLASSES:
            resolved_source_class = source_clean
        else:
            raise UnrealEvidenceVerificationError(
                f"missing or invalid evidence_source_class: source {source_clean!r} is not an allowed source class {sorted(VALID_EVIDENCE_SOURCE_CLASSES)}"
            )
    else:
        if not isinstance(evidence_source_class, str) or evidence_source_class not in VALID_EVIDENCE_SOURCE_CLASSES:
            raise UnrealEvidenceVerificationError(
                f"unsupported evidence_source_class: {evidence_source_class!r}. Must be one of {sorted(VALID_EVIDENCE_SOURCE_CLASSES)}"
            )
        resolved_source_class = evidence_source_class

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
        # Reject path traversal markers in raw string
        raw_fp = file_path.strip()
        if ".." in raw_fp or "/../" in raw_fp.replace("\\", "/"):
            raise UnrealEvidenceVerificationError(f"path traversal detected in output file: {file_path!r}")
        # Reject NTFS Alternate Data Streams (:stream)
        if ":" in Path(raw_fp).name:
            raise UnrealEvidenceVerificationError(f"NTFS alternate data stream detected in output file: {file_path!r}")
        # Reject Windows device namespace and 8.3 short name patterns
        if raw_fp.startswith("\\\\.\\") or raw_fp.startswith("\\\\?\\"):
            raise UnrealEvidenceVerificationError(f"Windows device namespace path rejected: {file_path!r}")
        if "~" in Path(raw_fp).name:
            raise UnrealEvidenceVerificationError(f"Windows 8.3 short name path rejected: {file_path!r}")
        path_obj = Path(raw_fp)
        try:
            if not path_obj.exists():
                raise FileNotFoundError(f"render output file does not exist on disk: {file_path}")
            if not path_obj.is_file():
                raise ValueError(f"render output path is not a file: {file_path}")
            file_stat = path_obj.stat()
            if file_stat.st_size <= 0:
                raise ValueError(f"render output file has zero or negative size: {file_path} ({file_stat.st_size} bytes)")
        except (OSError, PermissionError) as exc:
            if isinstance(exc, (FileNotFoundError, ValueError, UnrealEvidenceVerificationError)):
                raise
            raise PermissionError(f"render output file is not accessible: {file_path}") from exc
        normalized_output_files.append(raw_fp)

    # Build clean state mapping with verified values
    clean_state = dict(observed_state)
    clean_state["output_files"] = normalized_output_files
    clean_state["evidence_source_class"] = resolved_source_class

    # Duplicate checks on output files
    if len(normalized_output_files) != len(set(normalized_output_files)):
        raise UnrealEvidenceVerificationError("duplicate output file path in declared output_files")
    declared_canon = {Path(fp).resolve() for fp in normalized_output_files}
    if len(declared_canon) != len(normalized_output_files):
        raise UnrealEvidenceVerificationError("duplicate canonical path in declared output_files")

    # Authoritative job record cross-checks (Contract V1 §13, §14, §16)
    # Validate that job_record is strictly an instance of AtlasRenderJobRecord
    if type(job_record) is not AtlasRenderJobRecord:
        raise UnrealEvidenceVerificationError(
            f"job_record must be an instance of AtlasRenderJobRecord, got {type(job_record)!r}"
        )
    if hasattr(job_record, "authoritative_digest") and not job_record.authoritative_digest:
        raise UnrealEvidenceVerificationError("job_record authoritative_digest must not be empty")
    # Attempt ordinal comparison
    obs_attempt = observed_state.get("attempt_ordinal")
    if obs_attempt is not None:
        if isinstance(obs_attempt, bool) or not isinstance(obs_attempt, int) or obs_attempt != getattr(job_record, "attempt_ordinal", None):
            raise UnrealEvidenceVerificationError(
                f"attempt_ordinal mismatch: record={getattr(job_record, 'attempt_ordinal', None)!r}, observed={obs_attempt!r}"
            )
        clean_state["attempt_ordinal"] = obs_attempt

    # 1. atlas_job_id
    obs_atlas_id = observed_state.get("atlas_job_id")
    if not obs_atlas_id or not isinstance(obs_atlas_id, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'atlas_job_id' in observed state")
    if obs_atlas_id != getattr(job_record, "atlas_job_id", None):
        raise UnrealEvidenceVerificationError(
            f"atlas_job_id mismatch: record={getattr(job_record, 'atlas_job_id', None)!r}, observed={obs_atlas_id!r}"
        )
    clean_state["atlas_job_id"] = obs_atlas_id

    # 2. unreal_job_id
    if not job_id:
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'unreal_job_id' (job_id) in observed state")
    rec_unreal_id = getattr(job_record, "unreal_job_id", None)
    if rec_unreal_id is not None and job_id != rec_unreal_id:
        raise UnrealEvidenceVerificationError(
            f"unreal_job_id mismatch: record={rec_unreal_id!r}, observed={job_id!r}"
        )
    clean_state["unreal_job_id"] = job_id

    # 3. sequence_asset_path
    if not sequence_asset_path:
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'sequence_asset_path' in observed state")
    if sequence_asset_path != getattr(job_record, "sequence_asset_path", None):
        raise UnrealEvidenceVerificationError(
            f"sequence_asset_path mismatch: record={getattr(job_record, 'sequence_asset_path', None)!r}, observed={sequence_asset_path!r}"
        )

    # 4. authorization_id
    obs_auth = observed_state.get("authorization_id")
    if not obs_auth or not isinstance(obs_auth, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'authorization_id' in observed state")
    if obs_auth != getattr(job_record, "authorization_id", None):
        raise UnrealEvidenceVerificationError(
            f"authorization_id mismatch: record={getattr(job_record, 'authorization_id', None)!r}, observed={obs_auth!r}"
        )
    clean_state["authorization_id"] = obs_auth

    # 5. canonical_digital_twin_id
    obs_twin = observed_state.get("canonical_digital_twin_id")
    if not obs_twin or not isinstance(obs_twin, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'canonical_digital_twin_id' in observed state")
    if obs_twin != getattr(job_record, "canonical_digital_twin_id", None):
        raise UnrealEvidenceVerificationError(
            f"canonical_digital_twin_id mismatch: record={getattr(job_record, 'canonical_digital_twin_id', None)!r}, observed={obs_twin!r}"
        )
    clean_state["canonical_digital_twin_id"] = obs_twin

    # 6. config_digest
    obs_cfg = observed_state.get("config_digest")
    if not obs_cfg or not isinstance(obs_cfg, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'config_digest' in observed state")
    if obs_cfg != getattr(job_record, "config_digest", None):
        raise UnrealEvidenceVerificationError(
            f"config_digest mismatch: record={getattr(job_record, 'config_digest', None)!r}, observed={obs_cfg!r}"
        )
    clean_state["config_digest"] = obs_cfg

    # 7. editor_session_id
    obs_sess = observed_state.get("editor_session_id")
    if not obs_sess or not isinstance(obs_sess, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'editor_session_id' in observed state")
    rec_sess = getattr(job_record, "origin_editor_session_id", None)
    if not rec_sess or not isinstance(rec_sess, str):
        raise UnrealEvidenceVerificationError("record missing mandatory origin_editor_session_id")
    if obs_sess != rec_sess:
        raise UnrealEvidenceVerificationError(
            f"editor_session_id mismatch: record={rec_sess!r}, observed={obs_sess!r}"
        )
    clean_state["editor_session_id"] = obs_sess

    # 8. process_id
    obs_pid = observed_state.get("process_id")
    if obs_pid is None or isinstance(obs_pid, bool) or not isinstance(obs_pid, int):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'process_id' (must be an integer) in observed state")
    rec_pid = getattr(job_record, "origin_process_id", None)
    if rec_pid is None or isinstance(rec_pid, bool) or not isinstance(rec_pid, int):
        raise UnrealEvidenceVerificationError("record missing mandatory origin_process_id")
    if int(obs_pid) != rec_pid:
        raise UnrealEvidenceVerificationError(
            f"process_id mismatch: record={rec_pid!r}, observed={int(obs_pid)!r}"
        )
    clean_state["process_id"] = int(obs_pid)

    # 9. process_creation_time
    obs_pct = observed_state.get("process_creation_time_utc") or observed_state.get("process_creation_time")
    if not obs_pct or not isinstance(obs_pct, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'process_creation_time' in observed state")
    rec_pct = getattr(job_record, "origin_process_creation_time", None)
    if not rec_pct or not isinstance(rec_pct, str):
        raise UnrealEvidenceVerificationError("record missing mandatory origin_process_creation_time")
    if obs_pct != rec_pct:
        raise UnrealEvidenceVerificationError(
            f"process_creation_time mismatch: record={rec_pct!r}, observed={obs_pct!r}"
        )
    clean_state["process_creation_time"] = obs_pct

    # 10. output_directory
    obs_out_dir = observed_state.get("output_directory")
    if not obs_out_dir or not isinstance(obs_out_dir, str):
        raise UnrealEvidenceVerificationError("missing mandatory identity field 'output_directory' in observed state")
    rec_out_dir = getattr(job_record, "output_directory", None)
    if not rec_out_dir:
        raise UnrealEvidenceVerificationError("record missing output_directory")
    if Path(obs_out_dir).resolve() != Path(rec_out_dir).resolve():
        raise UnrealEvidenceVerificationError(
            f"output_directory mismatch: record={rec_out_dir!r}, observed={obs_out_dir!r}"
        )
    expected_out_dir = Path(rec_out_dir).resolve()
    clean_state["output_directory"] = str(expected_out_dir)

    # Output directory confinement and traversal checks
    if not expected_out_dir.is_dir():
        raise UnrealEvidenceVerificationError(f"authorized output_directory is not an existing directory: {str(expected_out_dir)!r}")

    for fp in normalized_output_files:
        resolved_fp = Path(fp).resolve()
        try:
            resolved_fp.relative_to(expected_out_dir)
        except ValueError as exc:
            raise UnrealEvidenceVerificationError(
                f"output file path {fp!r} is outside authorized output directory {str(expected_out_dir)!r}"
            ) from exc
        if ".." in fp or "/../" in fp.replace("\\", "/"):
            raise UnrealEvidenceVerificationError(f"path traversal detected in output file: {fp!r}")
        if ":" in Path(fp).name:
            raise UnrealEvidenceVerificationError(f"NTFS alternate data stream detected in output file: {fp!r}")
        if fp.startswith("\\\\.\\") or fp.startswith("\\\\?\\"):
            raise UnrealEvidenceVerificationError(f"Windows device namespace path rejected: {fp!r}")
        if "~" in Path(fp).name:
            raise UnrealEvidenceVerificationError(f"Windows 8.3 short name path rejected: {fp!r}")

    if expected_out_dir.is_dir():
        # Scans for unexpected extra files in output_directory that alter expected topology
        actual_disk_files = {p.resolve() for p in expected_out_dir.iterdir() if p.is_file()}
        declared_files = {Path(fp).resolve() for fp in normalized_output_files}
        unexpected_files = actual_disk_files - declared_files
        if unexpected_files:
            raise UnrealEvidenceVerificationError(
                f"unexpected extra files present in output directory: {[str(p) for p in sorted(unexpected_files)]}"
            )

    # 11. expected_output_spec topology validation (mandatory from AtlasRenderJobRecord)
    rec_expected_spec = getattr(job_record, "expected_output_spec", None)
    if not rec_expected_spec or not isinstance(rec_expected_spec, Mapping):
        raise UnrealEvidenceVerificationError("record missing mandatory expected_output_spec")

    if "expected_output_spec" not in observed_state:
        raise UnrealEvidenceVerificationError("observed_state missing mandatory 'expected_output_spec'")
    obs_expected_spec = observed_state["expected_output_spec"]
    if not isinstance(obs_expected_spec, Mapping):
        raise UnrealEvidenceVerificationError("observed_state 'expected_output_spec' must be a mapping")
    if dict(obs_expected_spec) != dict(rec_expected_spec):
        raise UnrealEvidenceVerificationError(
            f"expected_output_spec mismatch: record={dict(rec_expected_spec)!r}, observed={dict(obs_expected_spec)!r}"
        )

    clean_state["expected_output_spec"] = dict(rec_expected_spec)
    expected_spec = rec_expected_spec
    exp_format = expected_spec.get("format")
    if not exp_format or not isinstance(exp_format, str):
        raise UnrealEvidenceVerificationError("expected_output_spec missing valid format")
    if exp_format.lower() not in ("png",):
        raise UnrealEvidenceVerificationError(
            f"unsupported output format in expected_output_spec: {exp_format!r}"
        )

    exp_width = expected_spec.get("width")
    exp_height = expected_spec.get("height")
    exp_start = expected_spec.get("start_frame")
    exp_end = expected_spec.get("end_frame")

    if exp_start is not None and exp_end is not None and exp_end >= exp_start:
        expected_count = exp_end - exp_start + 1
        if len(normalized_output_files) != expected_count:
            raise UnrealEvidenceVerificationError(
                f"output file count mismatch: expected {expected_count} frames, got {len(normalized_output_files)}"
            )

    # Reconcile disk files against engine manifest
    # Compute expected byte size from IHDR: height * (1 + width * bpp)
    expected_raw_min_size = None
    if exp_width and exp_height:
        expected_raw_min_size = exp_height * (1 + exp_width * 3)

    for fp in normalized_output_files:
        p = Path(fp)
        if not verify_png_completeness(p, expected_width=exp_width, expected_height=exp_height):
            raise UnrealEvidenceVerificationError(
                f"PNG completeness check failed for {fp!r} (format/dimensions/chunks/CRC/IEND)"
            )
        if not _verify_png_idat_decompression(p, min_decompressed_bytes=expected_raw_min_size):
            raise UnrealEvidenceVerificationError(
                f"PNG IDAT decompression integrity check failed for {fp!r}"
            )

    # 12. Engine-attested manifest validation (Block 3 & 4: mandatory when terminal outputs present)
    manifest = observed_state.get("output_manifest")
    if manifest is None:
        raise UnrealEvidenceVerificationError("missing required engine-attested 'output_manifest'")
    if not isinstance(manifest, (list, tuple)):
        raise UnrealEvidenceVerificationError("output_manifest must be a sequence")
    if len(manifest) == 0 and len(normalized_output_files) > 0:
        raise UnrealEvidenceVerificationError("output_manifest cannot be empty when outputs are required")

    manifest_map = {}
    for entry in manifest:
        if not isinstance(entry, Mapping):
            raise UnrealEvidenceVerificationError("output_manifest entries must be mappings")
        m_path = entry.get("path")
        m_size = entry.get("size")
        m_sha = entry.get("sha256")
        if not m_path or not isinstance(m_path, str):
            raise UnrealEvidenceVerificationError("manifest entry missing valid path string")
        if m_size is None or isinstance(m_size, bool) or not isinstance(m_size, int) or m_size <= 0:
            raise UnrealEvidenceVerificationError("manifest entry size must be an exact positive integer > 0")
        if not m_sha or not isinstance(m_sha, str) or len(m_sha) != 64:
            raise UnrealEvidenceVerificationError("manifest entry sha256 must be exactly 64 hexadecimal characters")
        if m_sha.lower() != m_sha:
            raise UnrealEvidenceVerificationError("manifest entry sha256 must be lowercase hexadecimal characters")
        try:
            int(m_sha, 16)
        except ValueError:
            raise UnrealEvidenceVerificationError("manifest entry sha256 contains non-hexadecimal characters")

        canonical_m_path = Path(m_path).resolve()
        if canonical_m_path in manifest_map:
            raise UnrealEvidenceVerificationError(f"duplicate manifest path detected: {m_path!r}")
        manifest_map[canonical_m_path] = (m_size, m_sha)

    # Exact set equality between declared output_files and manifest paths
    manifest_canon = set(manifest_map.keys())
    if declared_canon != manifest_canon:
        raise UnrealEvidenceVerificationError(
            f"manifest paths do not exactly match declared output_files: diff={declared_canon ^ manifest_canon}"
        )

    # Reconcile disk files against engine manifest
    for fp in normalized_output_files:
        p_canon = Path(fp).resolve()
        attested_size, attested_sha = manifest_map[p_canon]
        actual_bytes = p_canon.read_bytes()
        actual_size = len(actual_bytes)
        actual_sha = hashlib.sha256(actual_bytes).hexdigest()
        if actual_size != attested_size:
            raise UnrealEvidenceVerificationError(
                f"manifest size mismatch for {fp!r}: attested={attested_size}, actual={actual_size}"
            )
        if actual_sha != attested_sha:
            raise UnrealEvidenceVerificationError(
                f"manifest sha256 mismatch for {fp!r}: attested={attested_sha}, actual={actual_sha}"
            )
    clean_state["output_manifest"] = list(manifest)

    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=normalized_entity_ids,
        observed_state=clean_state,
        verified=True,
        source=source,
    )

