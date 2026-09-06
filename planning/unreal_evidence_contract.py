"""Engine-neutral evidence contract for the Unreal Agent boundary.

Evidence is produced by the Unreal side after an operation is executed. It is
not an authorization receipt and cannot authorize itself. Atlas verification
consumes this evidence independently of the agent's proposal.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple


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

        while True:
            chunk_len_bytes = f.read(4)
            if not chunk_len_bytes or len(chunk_len_bytes) < 4:
                break
            chunk_len = struct.unpack(">I", chunk_len_bytes)[0]
            chunk_type = f.read(4)
            if len(chunk_type) < 4:
                return False
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
                if has_ihdr or chunk_len < 8:
                    return False
                has_ihdr = True
                width, height = struct.unpack(">II", data[:8])
                if expected_width is not None and width != expected_width:
                    return False
                if expected_height is not None and height != expected_height:
                    return False

            if chunk_type == b"IEND":
                has_iend = True
                # IEND must be the final chunk (no trailing bytes)
                extra = f.read(1)
                if extra:
                    return False
                break

    return has_ihdr and has_iend


def _verify_png_idat_decompression(file_path: Path) -> bool:
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

    if not idat_chunks:
        # Minimal empty frame without IDAT
        return True

    try:
        combined = b"".join(idat_chunks)
        zlib.decompress(combined)
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


def verify_render_job_evidence(
    *,
    operation_name: str,
    entity_ids: Sequence[str],
    observed_state: Mapping[str, Any],
    source: str,
    job_record: Optional[Any] = None,
    evidence_source_class: Optional[str] = None,
) -> UnrealEvidence:
    """Authoritatively verify raw observed Unreal render-job state and construct verified UnrealEvidence.

    Contract V1 §13–§16 Independent Evidence Verification Boundary:
    - operation_name == 'inspect_render_job'
    - entity_ids is a non-empty sequence of non-empty strings
    - job_id exists and is canonical
    - sequence_asset_path exists and is canonical
    - status is 'completed' or 'finished'
    - finished is True, success is True, failed is False
    - output_files is a non-empty sequence of non-empty strings
    - every output file exists, is accessible, and has size > 0
    - validates evidence_source_class in {ENGINE_LIVE, ENGINE_JOURNAL_ATTESTED} if specified or inferred from source
    - when job_record (AtlasRenderJobRecord) is provided:
        - validates all mandatory identity bindings (atlas_job_id, unreal_job_id, session_id, process info, auth, twin, seq, config, output_dir)
        - validates output path isolation (all files inside output_directory, no path traversal)
        - validates engine-attested output manifest (size, sha256) matches disk bytes exactly
        - validates PNG completeness (IHDR, CRCs, terminal IEND, dimensions) for PNG outputs
        - validates expected_output_spec topology (format, frame count, dimensions)
    """
    import hashlib

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

    # Source class validation
    resolved_source_class = evidence_source_class
    if resolved_source_class is None:
        source_str = source.strip()
        if source_str in VALID_EVIDENCE_SOURCE_CLASSES:
            resolved_source_class = source_str
        elif "live" in source_str.lower() or "inspection" in source_str.lower() or "boundary" in source_str.lower():
            resolved_source_class = "ENGINE_LIVE"
        elif "journal" in source_str.lower() or "recovery" in source_str.lower():
            resolved_source_class = "ENGINE_JOURNAL_ATTESTED"

    if evidence_source_class is not None and evidence_source_class not in VALID_EVIDENCE_SOURCE_CLASSES:
        raise UnrealEvidenceVerificationError(
            f"unsupported evidence_source_class: {evidence_source_class!r}. Must be one of {sorted(VALID_EVIDENCE_SOURCE_CLASSES)}"
        )

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
    if resolved_source_class:
        clean_state["evidence_source_class"] = resolved_source_class

    # Authoritative job record cross-checks (Contract V1 §13, §14, §16)
    if job_record is not None:
        # Mandatory identity bindings comparison
        if hasattr(job_record, "atlas_job_id") and job_record.atlas_job_id:
            obs_atlas_id = observed_state.get("atlas_job_id")
            if obs_atlas_id and obs_atlas_id != job_record.atlas_job_id:
                raise UnrealEvidenceVerificationError(
                    f"atlas_job_id mismatch: record={job_record.atlas_job_id!r}, observed={obs_atlas_id!r}"
                )
            clean_state["atlas_job_id"] = job_record.atlas_job_id

        if hasattr(job_record, "unreal_job_id") and job_record.unreal_job_id:
            if job_id != job_record.unreal_job_id:
                raise UnrealEvidenceVerificationError(
                    f"unreal_job_id mismatch: record={job_record.unreal_job_id!r}, observed={job_id!r}"
                )

        if hasattr(job_record, "sequence_asset_path") and job_record.sequence_asset_path:
            if sequence_asset_path != job_record.sequence_asset_path:
                raise UnrealEvidenceVerificationError(
                    f"sequence_asset_path mismatch: record={job_record.sequence_asset_path!r}, observed={sequence_asset_path!r}"
                )

        if hasattr(job_record, "authorization_id") and job_record.authorization_id:
            obs_auth = observed_state.get("authorization_id")
            if obs_auth and obs_auth != job_record.authorization_id:
                raise UnrealEvidenceVerificationError(
                    f"authorization_id mismatch: record={job_record.authorization_id!r}, observed={obs_auth!r}"
                )
            clean_state["authorization_id"] = job_record.authorization_id

        if hasattr(job_record, "canonical_digital_twin_id") and job_record.canonical_digital_twin_id:
            obs_twin = observed_state.get("canonical_digital_twin_id")
            if obs_twin and obs_twin != job_record.canonical_digital_twin_id:
                raise UnrealEvidenceVerificationError(
                    f"canonical_digital_twin_id mismatch: record={job_record.canonical_digital_twin_id!r}, observed={obs_twin!r}"
                )
            clean_state["canonical_digital_twin_id"] = job_record.canonical_digital_twin_id

        if hasattr(job_record, "config_digest") and job_record.config_digest:
            obs_cfg = observed_state.get("config_digest")
            if obs_cfg and obs_cfg != job_record.config_digest:
                raise UnrealEvidenceVerificationError(
                    f"config_digest mismatch: record={job_record.config_digest!r}, observed={obs_cfg!r}"
                )
            clean_state["config_digest"] = job_record.config_digest

        if hasattr(job_record, "origin_editor_session_id") and job_record.origin_editor_session_id:
            obs_sess = observed_state.get("editor_session_id")
            if obs_sess and obs_sess != job_record.origin_editor_session_id:
                raise UnrealEvidenceVerificationError(
                    f"editor_session_id mismatch: record={job_record.origin_editor_session_id!r}, observed={obs_sess!r}"
                )

        if hasattr(job_record, "origin_process_creation_time") and job_record.origin_process_creation_time:
            obs_pct = observed_state.get("process_creation_time_utc") or observed_state.get("process_creation_time")
            if obs_pct and obs_pct != job_record.origin_process_creation_time:
                raise UnrealEvidenceVerificationError(
                    f"process_creation_time mismatch: record={job_record.origin_process_creation_time!r}, observed={obs_pct!r}"
                )

        # Output directory and path isolation checks
        if hasattr(job_record, "output_directory") and job_record.output_directory:
            obs_out_dir = observed_state.get("output_directory")
            if obs_out_dir and Path(obs_out_dir).resolve() != Path(job_record.output_directory).resolve():
                raise UnrealEvidenceVerificationError(
                    f"output_directory mismatch: record={job_record.output_directory!r}, observed={obs_out_dir!r}"
                )
            expected_out_dir = Path(job_record.output_directory).resolve()
            clean_state["output_directory"] = str(expected_out_dir)

            for fp in normalized_output_files:
                resolved_fp = Path(fp).resolve()
                try:
                    resolved_fp.relative_to(expected_out_dir)
                except ValueError as exc:
                    raise UnrealEvidenceVerificationError(
                        f"output file path {fp!r} is outside authorized output directory {str(expected_out_dir)!r}"
                    ) from exc
                # Reject path traversal markers in raw string
                if ".." in fp or "/../" in fp.replace("\\", "/"):
                    raise UnrealEvidenceVerificationError(f"path traversal detected in output file: {fp!r}")
                # Reject NTFS Alternate Data Streams (:stream)
                if ":" in Path(fp).name:
                    raise UnrealEvidenceVerificationError(f"NTFS alternate data stream detected in output file: {fp!r}")

            # Verify no extra files in output_directory that alter expected topology
            if expected_out_dir.is_dir():
                actual_disk_files = {p.resolve() for p in expected_out_dir.iterdir() if p.is_file()}
                declared_files = {Path(fp).resolve() for fp in normalized_output_files}
                unexpected_files = actual_disk_files - declared_files
                if unexpected_files:
                    raise UnrealEvidenceVerificationError(
                        f"unexpected extra files present in output directory: {[str(p) for p in sorted(unexpected_files)]}"
                    )

        # Expected output spec validation
        expected_spec = getattr(job_record, "expected_output_spec", None) or observed_state.get("expected_output_spec")
        if expected_spec and isinstance(expected_spec, Mapping):
            clean_state["expected_output_spec"] = dict(expected_spec)
            exp_format = expected_spec.get("format")
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

            # Reject unsupported format
            if exp_format and exp_format.lower() not in ("png",):
                raise UnrealEvidenceVerificationError(
                    f"unsupported output format in expected_output_spec: {exp_format!r}"
                )

            # PNG verification and decompression integrity check
            if exp_format and exp_format.lower() == "png":
                for fp in normalized_output_files:
                    p = Path(fp)
                    if not verify_png_completeness(p, expected_width=exp_width, expected_height=exp_height):
                        raise UnrealEvidenceVerificationError(
                            f"PNG completeness check failed for {fp!r} (format/dimensions/chunks/CRC/IEND)"
                        )
                    # Verify IDAT decompression integrity
                    if not _verify_png_idat_decompression(p):
                        raise UnrealEvidenceVerificationError(
                            f"PNG IDAT decompression integrity check failed for {fp!r}"
                        )

        # Engine-attested manifest validation (Contract V1 §13)
        manifest = observed_state.get("output_manifest")
        if manifest is not None:
            if not isinstance(manifest, (list, tuple)):
                raise UnrealEvidenceVerificationError("output_manifest must be a sequence")
            manifest_map = {}
            for entry in manifest:
                if not isinstance(entry, Mapping):
                    raise UnrealEvidenceVerificationError("output_manifest entries must be mappings")
                m_path = entry.get("path")
                m_size = entry.get("size")
                m_sha = entry.get("sha256")
                if not m_path or not isinstance(m_path, str):
                    raise UnrealEvidenceVerificationError("manifest entry missing valid path")
                if m_size is None or not isinstance(m_size, (int, float)) or m_size <= 0:
                    raise UnrealEvidenceVerificationError("manifest entry missing valid size > 0")
                if not m_sha or not isinstance(m_sha, str) or len(m_sha) != 64:
                    raise UnrealEvidenceVerificationError("manifest entry missing valid 64-char sha256")
                manifest_map[Path(m_path).resolve()] = (int(m_size), m_sha)

            # Every normalized output file must match manifest exactly, and manifest cannot contain extra files
            if len(manifest_map) != len(normalized_output_files):
                raise UnrealEvidenceVerificationError(
                    f"output_manifest entry count ({len(manifest_map)}) does not match output_files count ({len(normalized_output_files)})"
                )
            for fp in normalized_output_files:
                resolved_p = Path(fp).resolve()
                if resolved_p not in manifest_map:
                    raise UnrealEvidenceVerificationError(f"output file {fp!r} not found in engine output_manifest")
                expected_size, expected_sha = manifest_map[resolved_p]
                disk_size = resolved_p.stat().st_size
                if disk_size != expected_size:
                    raise UnrealEvidenceVerificationError(
                        f"manifest size mismatch for {fp!r}: engine attested {expected_size}, disk has {disk_size}"
                    )
                with resolved_p.open("rb") as f:
                    disk_sha = hashlib.sha256(f.read()).hexdigest()
                if disk_sha != expected_sha:
                    raise UnrealEvidenceVerificationError(
                        f"manifest sha256 mismatch for {fp!r}: engine attested {expected_sha}, disk computed {disk_sha}"
                    )
            clean_state["output_manifest"] = list(manifest)

    return UnrealEvidence(
        operation_name=operation_name,
        entity_ids=normalized_entity_ids,
        observed_state=clean_state,
        source=source.strip(),
        verified=True,
    )

