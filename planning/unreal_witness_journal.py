"""M7 Case B — Durable Witness Journal Reader (Contract V1 §10 / §21 Case B).

Read-only reader for the Atlas-designated durable engine witness journal located at

    <ProjectDir>/AtlasWitnessJournal/<atlas_job_id>__<unreal_job_id>.json

Contract basis
--------------
* §9 (`docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md:266-284`): Unreal is
  launched inside the Atlas Job Object, and quiescence requires
  ``JobObjectHandleValid AND ActiveProcesses == 0``; *"Only when ActiveProcesses == 0
  is confirmed may recovery inspect or adopt terminal disk artifacts."*
* §21 Case B (`:716-718`): *"**Prior session** journal contains an exact terminal
  FINISHED record for a bound ``unreal_job_id``"* -> *"Use ``ENGINE_JOURNAL_ATTESTED``
  evidence, verify hashes against the recorded output manifest, then continue normal
  receipt/provenance verification."*
* §10 (`:288-313`): the journal is a durable **witness** (not an authority system); its
  path and logical key ``(atlas_job_id, unreal_job_id)`` are Atlas-designated; it MUST
  retain execution history and MUST NOT overwrite a previous execution identity; the
  ``attempt_nonce`` is Atlas-generated and used by the engine only as the HMAC key.
* §20 Step 6 (`:669-686`): match candidates by exact bound identity and **"Ambiguous
  matches MUST fail closed."**
* §20 Step 8 (`:700-702`): engine-journal-attested observations may enter the
  authoritative evidence verifier.

Attribution rules (why "some JSON exists" is NOT evidence for a job)
-------------------------------------------------------------------
The §10 directory retains history and is shared by every Atlas job, so a healthy job must
never be reclassified because of *unrelated* material in that directory.  A file is
attributed to the requested job as follows:

1. filename matches the §10 logical key and its ``atlas_job_id`` component equals the
   requested job -> **relevant** (validated by content);
2. otherwise the file is read defensively and attributed by **content** only when it
   parses and its ``atlas_job_id`` equals the requested job -> **relevant but
   mislabeled** (fail closed as PARTIAL: a §10 witness for this job that ignores the
   mandated filename layout);
3. everything else - another job's retained history, unrelated or badly named JSON, and
   unreadable files that cannot be attributed - is **ignored**.  It is never evidence for
   this job, and it must not turn a journal-less job into Case J.

Status semantics
----------------
* ``ABSENT``   - no relevant witness for this job (unrelated material ignored).
* ``COMPLETE`` - exactly one relevant, parseable, schema-valid journal with one
  consistent engine identity and a terminal entry.  ``is_terminal`` is False when the
  only relevant witness is still in flight: an unfinished witness is neither adoptable
  nor allowed to preempt a healthy live engine session, so the coordinator falls through
  to the live path.
* ``PARTIAL``  - relevant material exists but is unusable (unreadable bytes,
  malformed/truncated JSON, unsupported schema, mislabeled content, or an absent /
  contradictory engine identity) -> the coordinator classifies Case J.  No such file can
  abort the recovery pass (B1).
* ``CONFLICT`` - more than one materially different execution claims this job
  (Contract V1 §21 Case H).

Safety properties (enforced by construction):
* it never performs an engine RPC (no transport/adapter is referenced);
* it never writes, renames, deletes or mutates a journal, artifact or record;
* it never issues a receipt (receipt publication remains the coordinator's store-gated
  path);
* it never invents engine-witnessed fields, and a contradictory engine identity is never
  resolved "toward adoption".
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

#: Journal-set status vocabulary (mirrors the engine's `journal_status`).
JOURNAL_STATUS_ABSENT = "ABSENT"
JOURNAL_STATUS_COMPLETE = "COMPLETE"
JOURNAL_STATUS_PARTIAL = "PARTIAL"
JOURNAL_STATUS_CONFLICT = "CONFLICT"

#: Directory name mandated by Contract V1 §10 (relative to <ProjectDir>).
JOURNAL_DIRECTORY_NAME = "AtlasWitnessJournal"

#: Current journal schema version (Contract V1 §10 / M7 hardening).
JOURNAL_SCHEMA_VERSION = 2

#: Terminal witness phases.
TERMINAL_PHASES: Tuple[str, ...] = ("FINISHED", "FAILED")

#: `<atlas_job_id>__<unreal_job_id>.json` (Contract V1 §10 logical key).
_JOURNAL_FILENAME_RE = re.compile(
    r"^(?P<atlas_job_id>[A-Za-z0-9._-]+)__(?P<unreal_job_id>[A-Za-z0-9._-]+)\.json$"
)


class DurableWitnessJournalError(RuntimeError):
    """Base error for durable witness journal reading."""


@dataclass(frozen=True)
class WitnessJournalSnapshot:
    """A stable fingerprint of one journal file, used for the A/B stability check."""

    path: str
    size: int
    mtime_ns: int
    content_sha256: str
    entry_digest: Optional[str]
    phase: Optional[str]
    phase_sequence: Optional[int]

    def identity(self) -> tuple:
        """Comparable identity; any material change between snapshots alters it."""
        return (
            self.path,
            self.size,
            self.mtime_ns,
            self.content_sha256,
            self.entry_digest,
            self.phase,
            self.phase_sequence,
        )


@dataclass(frozen=True)
class DurableWitness:
    """Result of reading the durable journal set for one bound Atlas job."""

    status: str
    journal_path: Optional[str] = None
    candidate: Optional[Mapping[str, Any]] = None
    snapshot: Optional[WitnessJournalSnapshot] = None
    is_terminal: bool = False
    is_terminal_finished: bool = False
    reason: str = ""
    scanned_files: Tuple[str, ...] = ()
    ignored_files: Tuple[str, ...] = ()

    @property
    def is_adoptable(self) -> bool:
        """True only for a bound terminal FINISHED witness with Case B evidence.

        A terminal FAILED witness is *adjudicated* by the coordinator's terminal path but
        is never adoptable: only a terminal FINISHED claim with successful,
        independently verified evidence may produce a receipt (Contract V1 §21 B/G).
        """
        return (
            self.status == JOURNAL_STATUS_COMPLETE
            and self.is_terminal_finished
            and self.candidate is not None
        )


def engine_identity_conflict(candidate: Mapping[str, Any]) -> bool:
    """True when a candidate carries two *disagreeing* engine execution identities.

    Contract V1 §20 Step 6 requires ambiguous matches to fail closed, so a witness naming
    two different engine executions is neither adoptable nor binding evidence.
    """
    if candidate is None:
        return False
    job_id = candidate.get("job_id")
    unreal_job_id = candidate.get("unreal_job_id")
    job_ok = isinstance(job_id, str) and bool(job_id)
    unreal_ok = isinstance(unreal_job_id, str) and bool(unreal_job_id)
    return job_ok and unreal_ok and job_id != unreal_job_id


def canonical_engine_job_id(candidate: Mapping[str, Any]) -> Optional[str]:
    """Return the single canonical engine job identity for a candidate.

    The live engine catalog names the field ``job_id``; the §10 durable witness journal
    names it ``unreal_job_id`` (Unreal does not create a ``job_id`` alias inside a
    journal).  Resolution rules:

    * the name that is present is authoritative;
    * both present and equal -> that value;
    * **both present and different -> ``None``** (a contradiction is never resolved
      toward adoption; callers must fail closed);
    * neither present -> ``None`` (an unbound witness).

    Normalizing the NAME never relaxes the binding requirement: callers must still prove
    equality with the durable record's bound ``unreal_job_id``.
    """
    if candidate is None:
        return None
    job_id = candidate.get("job_id")
    unreal_job_id = candidate.get("unreal_job_id")
    job_ok = isinstance(job_id, str) and bool(job_id)
    unreal_ok = isinstance(unreal_job_id, str) and bool(unreal_job_id)
    if job_ok and unreal_ok:
        return job_id if job_id == unreal_job_id else None
    if unreal_ok:
        return unreal_job_id
    if job_ok:
        return job_id
    return None


def normalize_witness_candidate(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a journal entry into the coordinator's candidate shape.

    The entry's own identity fields are preserved; a single resolved engine identity is
    carried under both names so downstream consumers see one identity.  A contradiction
    has no canonical identity and is rejected by the reader before reaching here, so this
    function can never pick a winner between disagreeing names.  No engine-witnessed
    field is created, altered or defaulted.
    """
    bound = {k: v for k, v in entry.items()}
    engine_job = canonical_engine_job_id(entry)
    if engine_job is not None:
        bound.setdefault("job_id", engine_job)
        bound.setdefault("unreal_job_id", engine_job)
    return bound


class DurableWitnessJournalReader:
    """Read-only accessor for the Atlas-designated durable witness journal set."""

    def __init__(self, root: os.PathLike | str):
        self.root = Path(root)

    # -- root resolution ---------------------------------------------------
    @staticmethod
    def resolve_root(project_dir: os.PathLike | str) -> Path:
        """Return the Contract V1 §10 journal root for a project directory."""
        return Path(project_dir) / JOURNAL_DIRECTORY_NAME

    # -- low-level, never-raising primitives (B1) -------------------------
    def _resolve_under_root(self, path: Path) -> Optional[Path]:
        """Return the canonical path when it stays inside the journal root.

        A journal outside the Atlas-designated root (symlink/junction escape, or a
        hand-placed file elsewhere) is not a witness for this root: canonicalization is
        validated before any content is trusted.
        """
        try:
            root_real = self.root.resolve(strict=False)
            real = path.resolve(strict=False)
            if real.parent != root_real:
                return None
            if path.is_symlink():
                return None
        except OSError:
            return None
        return real

    def _scan_root(self) -> Tuple[list, Optional[str]]:
        """List `*.json` files in the root; never raises.

        Returns ``(files, scan_error)``.  An unreadable *existing* root reports a scan
        error (classified PARTIAL upstream) instead of propagating an exception or being
        silently treated as "no witness".
        """
        try:
            if not self.root.is_dir():
                return [], None
        except OSError as exc:
            return [], f"journal root is not readable: {self.root} ({exc.__class__.__name__})"
        try:
            files = sorted(p for p in self.root.glob("*.json") if p.is_file())
        except OSError as exc:
            return [], f"journal root could not be listed: {self.root} ({exc.__class__.__name__})"
        return files, None

    @staticmethod
    def _read_bytes(path: Path) -> Tuple[Optional[bytes], Optional[str]]:
        try:
            return path.read_bytes(), None
        except OSError as exc:
            return None, f"journal could not be read: {path.name} ({exc.__class__.__name__})"

    # -- snapshots ---------------------------------------------------------
    def snapshot(self, journal_path: os.PathLike | str) -> Optional[WitnessJournalSnapshot]:
        """Fingerprint one journal file (size, mtime, content digest, signed entry)."""
        path = Path(journal_path)
        real = self._resolve_under_root(path)
        if real is None:
            return None
        data, _err = self._read_bytes(real)
        if data is None:
            return None
        try:
            mtime_ns = real.stat().st_mtime_ns
        except OSError:
            return None
        entry = self._terminal_entry(self._parse(data))
        return WitnessJournalSnapshot(
            path=str(real),
            size=len(data),
            mtime_ns=mtime_ns,
            content_sha256=hashlib.sha256(data).hexdigest(),
            entry_digest=(entry or {}).get("entry_digest"),
            phase=(entry or {}).get("phase"),
            phase_sequence=(entry or {}).get("phase_sequence"),
        )

    # -- parsing -----------------------------------------------------------
    @staticmethod
    def _parse(data: bytes) -> Optional[Mapping[str, Any]]:
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return parsed if isinstance(parsed, Mapping) else None

    @staticmethod
    def _phase_history(journal: Mapping[str, Any]) -> list:
        history = journal.get("phase_history")
        if isinstance(history, list):
            return [e for e in history if isinstance(e, Mapping)]
        return []

    @classmethod
    def _terminal_entry(cls, journal: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
        """Return the terminal phase entry of a journal (highest phase_sequence)."""
        if not isinstance(journal, Mapping):
            return None
        entries = [
            e for e in cls._phase_history(journal)
            if isinstance(e.get("phase"), str) and e.get("phase") in TERMINAL_PHASES
        ]
        if entries:
            return max(entries, key=lambda e: e.get("phase_sequence") or 0)
        phase = journal.get("phase")
        if isinstance(phase, str) and phase in TERMINAL_PHASES:
            return journal
        return None

    # -- main read ---------------------------------------------------------
    def read(
        self,
        atlas_job_id: str,
        unreal_job_id: Optional[str] = None,
    ) -> DurableWitness:
        """Classify the durable journal set for one bound Atlas job (see module docstring).

        ``unreal_job_id`` is accepted for callers asserting the bound pair; identity is
        NOT filtered here so a mismatched engine job id still reaches the coordinator's
        binding check (Case E/F) instead of silently becoming "no witness".
        """
        files, scan_error = self._scan_root()
        scanned: list[str] = []
        ignored: list[str] = []

        def _partial(reason: str) -> DurableWitness:
            return DurableWitness(
                status=JOURNAL_STATUS_PARTIAL,
                reason=reason,
                scanned_files=tuple(scanned),
                ignored_files=tuple(ignored),
            )

        if scan_error is not None:
            return _partial(scan_error)

        matching: list[tuple[Path, Mapping[str, Any], Mapping[str, Any]]] = []
        in_flight: Optional[str] = None

        for path in files:
            name_match = _JOURNAL_FILENAME_RE.match(path.name)
            relevant_by_name = (
                name_match is not None
                and name_match.group("atlas_job_id") == atlas_job_id
            )
            if name_match is not None and not relevant_by_name:
                # Retained history for ANOTHER Atlas job: never evidence for this job.
                ignored.append(path.name)
                continue

            real = self._resolve_under_root(path)
            if real is None:
                if relevant_by_name:
                    return _partial(f"journal path outside the designated root: {path.name}")
                ignored.append(path.name)
                continue

            data, read_error = self._read_bytes(real)
            if data is None:
                if relevant_by_name:
                    return _partial(read_error or f"journal could not be read: {real.name}")
                ignored.append(path.name)
                continue

            journal = self._parse(data)
            if journal is None:
                if relevant_by_name:
                    return _partial(f"journal is unparseable/truncated: {real.name}")
                ignored.append(path.name)
                continue

            if journal.get("atlas_job_id") != atlas_job_id:
                if relevant_by_name:
                    return _partial(
                        "journal content is bound to a different atlas_job_id than its §10 "
                        f"filename: {real.name}"
                    )
                ignored.append(path.name)
                continue

            if not relevant_by_name:
                # A witness for THIS job that ignores the mandated §10 filename layout.
                return _partial(
                    f"journal filename does not follow the §10 logical key: {real.name}"
                )

            scanned.append(str(real))
            schema = journal.get("journal_schema_version")
            if schema != JOURNAL_SCHEMA_VERSION:
                return _partial(
                    f"unsupported journal_schema_version {schema!r} in {real.name}"
                )

            entry = self._terminal_entry(journal)
            if entry is None:
                # Relevant but not terminal yet: an in-flight execution. Neither
                # adoptable nor a rejection - the live path decides Case A / Case J.
                in_flight = str(real)
                continue

            if engine_identity_conflict(entry):
                return _partial(
                    "terminal entry carries contradictory engine identities "
                    f"(job_id={entry.get('job_id')!r}, "
                    f"unreal_job_id={entry.get('unreal_job_id')!r}) in {real.name}"
                )
            if canonical_engine_job_id(entry) is None:
                return _partial(f"terminal entry carries no engine identity: {real.name}")
            matching.append((real, journal, entry))

        if not matching:
            if in_flight is not None:
                return DurableWitness(
                    status=JOURNAL_STATUS_COMPLETE,
                    journal_path=in_flight,
                    snapshot=self.snapshot(in_flight),
                    is_terminal=False,
                    is_terminal_finished=False,
                    reason="relevant witness present but not terminal (execution in flight)",
                    scanned_files=tuple(scanned),
                    ignored_files=tuple(ignored),
                )
            return DurableWitness(
                status=JOURNAL_STATUS_ABSENT,
                reason=f"no journal bound to atlas_job_id {atlas_job_id}",
                scanned_files=tuple(scanned),
                ignored_files=tuple(ignored),
            )

        # CONFLICT: more than one materially different execution claims this job
        # (Contract V1 §21 Case H). Retention never makes a duplicate benign, and a
        # contradictory identity was already rejected as PARTIAL above.
        engine_ids = {canonical_engine_job_id(entry) for _, _, entry in matching}
        if len(engine_ids) > 1:
            return DurableWitness(
                status=JOURNAL_STATUS_CONFLICT,
                reason=(
                    "multiple distinct engine execution identities claim atlas_job_id "
                    f"{atlas_job_id}: {sorted(i for i in engine_ids if i)}"
                ),
                scanned_files=tuple(scanned),
                ignored_files=tuple(ignored),
            )
        finished_digests = {
            entry.get("entry_digest")
            for _, _, entry in matching
            if entry.get("phase") == "FINISHED"
        }
        if len(finished_digests) > 1:
            return DurableWitness(
                status=JOURNAL_STATUS_CONFLICT,
                reason=(
                    "multiple materially different terminal FINISHED witnesses claim "
                    f"atlas_job_id {atlas_job_id}"
                ),
                scanned_files=tuple(scanned),
                ignored_files=tuple(ignored),
            )

        path, _journal, entry = max(matching, key=lambda t: t[2].get("phase_sequence") or 0)
        candidate = normalize_witness_candidate(entry)
        candidate.setdefault("state_source", "witness_journal")
        return DurableWitness(
            status=JOURNAL_STATUS_COMPLETE,
            journal_path=str(path),
            candidate=candidate,
            snapshot=self.snapshot(path),
            is_terminal=True,
            is_terminal_finished=(
                entry.get("phase") == "FINISHED" and bool(entry.get("finished", True))
            ),
            reason="bound terminal witness present",
            scanned_files=tuple(scanned),
            ignored_files=tuple(ignored),
        )
