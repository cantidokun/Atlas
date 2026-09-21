"""Shared deterministic harness for the M7 containment-rung tests.

Builds a real project binding (a ``.uproject`` on disk), a real durable store/record, the
attempt's real authenticated launch record, a terminal HMAC-attested witness journal and
valid PNG bytes — everything the production containment path requires, with only the engine
transport faked. No Unreal, no render, no Blender.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import zlib

import tests.m6.fault_fixtures as ff
from planning.unreal_containment_launch_record import (
    containment_dir_for_store,
    write_launch_record,
)
from scripts.run_unreal_supervisor import JobObjectContainmentState

JOURNAL_DIR_NAME = "AtlasWitnessJournal"
DEFAULT_NONCE = "m7-rung-nonce-0123456789abcdef0123456789abcdef"


class RecordingExplodingAdapter:
    """Adapter double: records calls; raises if anything ever touches the engine."""

    def __init__(self, *, capable: bool = False):
        self.calls = []
        self.capable = capable

    def assert_recovery_capable(self, authorization_id):
        self.calls.append(("assert_recovery_capable", authorization_id))
        if not self.capable:
            from planning.unreal_adapter_production import UnrealAdapterError

            raise UnrealAdapterError("engine down")


class ExplodingAdapter:
    """Every attribute access raises: proves a path never touched the engine."""

    def __getattr__(self, item):
        raise AssertionError(f"engine transport was touched (attribute {item!r})")


def make_valid_png(path: pathlib.Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr = b"\x00\x00\x00\x0dIHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    idat_data = zlib.compress(b"\x00\x00\x00\x00")
    idat = b"\x00\x00\x00" + bytes([len(idat_data)]) + b"IDAT" + idat_data + struct.pack(
        ">I", zlib.crc32(b"IDAT" + idat_data)
    )
    iend = b"\x00\x00\x00\x00IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    path.write_bytes(sig + ihdr + idat + iend)
    return path.read_bytes()


def manifest_for(frame: pathlib.Path) -> list:
    data = frame.read_bytes()
    return [{"path": str(frame), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}]


class ContainmentProject:
    """A project + store + record + launch record triple, with witness helpers."""

    def __init__(self, tmp_path, *, atlas_job_id=None, attempt_ordinal=1, nonce=DEFAULT_NONCE):
        self.tmp_path = pathlib.Path(tmp_path)
        self.project_dir = self.tmp_path / "proj"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.uproject = self.project_dir / "Atlas.uproject"
        self.uproject.write_text('{"FileVersion": 3}', encoding="utf-8")
        self.store_root = self.tmp_path / "store"
        self.journal_root = self.project_dir / JOURNAL_DIR_NAME

        self.job_id = atlas_job_id or ff.canonical_intent_kwargs(self.tmp_path)["atlas_job_id"]
        renders_parent = self.project_dir / "Saved" / "MovieRenders"
        self.store = ff.make_store(self.tmp_path)
        self.record = ff.make_submitted_record(
            self.tmp_path,
            attempt_ordinal=attempt_ordinal,
            attempt_nonce=nonce,
            atlas_job_id=self.job_id,
            output_parent_directory=str(renders_parent),
            output_directory=str(renders_parent / self.job_id),
        )
        self.store.create(self.record)
        pathlib.Path(self.record.output_directory).mkdir(parents=True, exist_ok=True)
        self.containment_dir = containment_dir_for_store(self.store_root)
        self.launch_record = ff.make_launch_record(self.record)

    # -- durable launch record ------------------------------------------------
    def persist_launch_record(self):
        return write_launch_record(
            self.containment_dir, self.launch_record, attempt_nonce=self.record.attempt_nonce
        )

    # -- witness + artifacts --------------------------------------------------
    def write_terminal_witness(self, frame: pathlib.Path):
        entry = self._entry(self.record, manifest_for(frame))
        self.journal_root.mkdir(parents=True, exist_ok=True)
        path = self.journal_root / f"{self.record.atlas_job_id}__{self.record.unreal_job_id}.json"
        journal = {
            "journal_schema_version": 2,
            "atlas_job_id": self.record.atlas_job_id,
            "unreal_job_id": self.record.unreal_job_id,
            "phase": entry["phase"],
            "phase_sequence": entry["phase_sequence"],
            "status": entry["status"],
            "progress": 1,
            "success": entry["success"],
            "finished": entry["finished"],
            "failed": False,
            "phase_history": [
                {"phase": "ACCEPTED", "phase_sequence": 1},
                {"phase": "STARTED", "phase_sequence": 2},
                entry,
            ],
        }
        path.write_text(json.dumps(journal), encoding="utf-8")
        return path

    def _entry(self, record, manifest):
        from planning.unreal_journal_attestation import compute_journal_attestation_digest

        payload = {
            "schema_version": 1,
            "atlas_job_id": record.atlas_job_id,
            "unreal_job_id": record.unreal_job_id,
            "attempt_ordinal": record.attempt_ordinal,
            "phase": "FINISHED",
            "phase_sequence": 3,
            "editor_session_id": record.origin_editor_session_id,
            "process_creation_time_utc": record.origin_process_creation_time,
            "output_directory": record.output_directory,
            "output_manifest": manifest,
        }
        entry = {
            "journal_schema_version": 2,
            "atlas_job_id": record.atlas_job_id,
            "unreal_job_id": record.unreal_job_id,
            "phase": "FINISHED",
            "phase_sequence": 3,
            "attempt_ordinal": record.attempt_ordinal,
            "authorization_id": record.authorization_id,
            "sequence_asset_path": record.sequence_asset_path,
            "config_digest": record.config_digest,
            "output_directory": record.output_directory,
            "editor_session_id": record.origin_editor_session_id,
            "process_id": record.origin_process_id,
            "process_creation_time_utc": record.origin_process_creation_time,
            "expected_output_spec": dict(record.expected_output_spec),
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "output_manifest": manifest,
            "output_files": [m["path"] for m in manifest],
            "entry_digest": compute_journal_attestation_digest(record.attempt_nonce, payload),
            "state_source": "unreal-editor-atlas-transport",
            "written_at": "2026-09-21T22:05:00+00:00",
        }
        return entry

    def write_frame(self):
        frame = pathlib.Path(self.record.output_directory) / "AtlasRender_0001.png"
        make_valid_png(frame)
        return frame

    # -- quiescence sources ---------------------------------------------------
    def contained_supervisor(self, *, active=0, total=1, job_handle=0x4242):
        return ff.contained_supervisor(active=active, total_processes=total, job_handle=job_handle)


def containment_state(active=0, total=1, *, kill_on_job_close=True, breakaway_disabled=True):
    """A raw kernel-state value (for direct predicate calls)."""
    return JobObjectContainmentState(
        active_processes=active,
        total_processes=total,
        total_terminated_processes=0,
        limit_flags=(0x00002000 if kill_on_job_close else 0)
        | (0 if breakaway_disabled else 0x00001000),
        kill_on_job_close=kill_on_job_close,
        silent_breakaway_ok=not breakaway_disabled,
        breakaway_ok=False,
    )
