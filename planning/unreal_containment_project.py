"""Atlas containment project binding (MF-2) — derived journal root + canonical validation.

Contract V1 §10 mandates the engine witness journal at

    <ProjectDir>/AtlasWitnessJournal/<atlas_job_id>__<unreal_job_id>.json

so the *production* recovery path MUST derive that root from the configured
``.uproject`` instead of accepting an arbitrary operator-supplied
``journal_root``. An arbitrary root is a trust-relevant directory (it decides which
bytes may become adoption evidence), so this module is the single, canonical resolver:

* derive ``ProjectDir`` from the configured ``.uproject`` (its parent directory);
* derive the journal root as ``<ProjectDir>/AtlasWitnessJournal`` (no operator input);
* canonicalise the resolved paths and refuse symlink/junction traversal;
* refuse a project/journal root placed under a disposable ``Saved/`` tree;
* hash the ``.uproject`` bytes as the project identity digest that the containment
  launch record and the recovery invocation evidence carry, so recovery can prove

      project <-> journal root <-> render record

Every refusal raises :class:`ProjectBindingError` — nothing is "repaired" silently.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from planning.unreal_containment_launch_record import containment_dir_for_store
from planning.unreal_witness_journal import JOURNAL_DIRECTORY_NAME

#: Component names that MUST NOT appear as the project/journal root location.
#: Compared case-insensitively on EVERY platform (``str.casefold``), not via
#: ``os.path.normcase``: that helper is a no-op on POSIX, so a normcase-based check silently
#: stops refusing a ``Saved/`` placement there (caught by CI on the Linux legs).
_DISPOSABLE_COMPONENT_NAMES = frozenset({"saved"})


class ProjectBindingError(RuntimeError):
    """Raised when the configured project cannot be canonically bound to a journal root."""


#: Windows FILE_ATTRIBUTE_REPARSE_POINT — set for junctions and symlinks.
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_link_or_reparse_point(path: Path) -> bool:
    """True when ``path`` itself is a symlink or a directory junction.

    Detected from the filesystem attributes rather than by comparing ``realpath`` with
    ``abspath``: the latter also differs for harmless reasons (e.g. Windows 8.3 short-name
    expansion of ``%TEMP%``), which would turn a canonicalisation check into a false
    refusal. A reparse point, by contrast, is exactly the redirection that must be refused.
    """
    try:
        if os.path.islink(path):
            return True
        stat_result = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _canonicalise(path: Path, label: str) -> Path:
    """Return the canonical path, refusing symlink/junction traversal.

    Every component is inspected: a project reached through a symlinked or junctioned
    directory (including one pointing outside the configured project) is refused, so the
    derived journal root cannot be redirected to an attacker-chosen witness directory.
    """
    absolute = Path(os.path.abspath(str(path)))
    current = Path(absolute.anchor) if absolute.anchor else Path()
    for part in absolute.parts[1:] if absolute.anchor else absolute.parts:
        current = current / part
        if _is_link_or_reparse_point(current):
            raise ProjectBindingError(
                f"{label} traverses a symlink/junction: {current}"
            )
    try:
        real = Path(os.path.realpath(str(absolute)))
    except OSError as exc:  # pragma: no cover - defensive
        raise ProjectBindingError(f"{label} could not be canonicalised: {path} ({exc})") from exc
    return real


def _reject_disposable_placement(path: Path, label: str) -> None:
    """Refuse a location under a disposable ``Saved/`` component.

    ``Saved/`` is the engine's disposable tree: evidence placed there is not durable, so
    neither the project binding nor the journal root may live inside it. The check is
    case-insensitive on every platform and does not depend on ``os.path.normcase``.
    """
    for component in path.parts:
        if component.casefold() in _DISPOSABLE_COMPONENT_NAMES:
            raise ProjectBindingError(
                f"{label} is placed under a disposable Saved/ tree: {path}"
            )


@dataclass(frozen=True)
class ProjectContainmentContext:
    """Canonically resolved project binding used by the recovery composition root."""

    uproject_path: str
    project_dir: str
    uproject_digest: str
    journal_root: str
    containment_dir: str
    store_root: str

    def snapshot(self) -> dict:
        """Invocation-evidence material (path/identity facts, no secrets)."""
        return {
            "uproject_path": self.uproject_path,
            "project_dir": self.project_dir,
            "uproject_digest": self.uproject_digest,
            "journal_root_canonical": self.journal_root,
            "containment_dir_canonical": self.containment_dir,
            "store_root_canonical": self.store_root,
            "journal_root_derivation": (
                f"<ProjectDir>/{JOURNAL_DIRECTORY_NAME} derived from the configured .uproject"
            ),
        }


def resolve_project_containment_context(
    uproject_path: os.PathLike | str,
    store_root: os.PathLike | str,
) -> ProjectContainmentContext:
    """Resolve + validate the project binding for a production recovery invocation."""
    if uproject_path is None or str(uproject_path).strip() == "":
        raise ProjectBindingError("a configured .uproject path is required to derive the journal root")
    if store_root is None or str(store_root).strip() == "":
        raise ProjectBindingError("a durable store root is required")

    configured = Path(uproject_path)
    if configured.suffix.lower() != ".uproject":
        raise ProjectBindingError(f"configured project is not a .uproject file: {configured}")
    if not configured.is_file():
        raise ProjectBindingError(f"configured .uproject does not exist: {configured}")

    canonical_uproject = _canonicalise(configured, "configured .uproject")
    project_dir = canonical_uproject.parent
    _reject_disposable_placement(project_dir, "project directory")

    try:
        uproject_digest = hashlib.sha256(canonical_uproject.read_bytes()).hexdigest()
    except OSError as exc:
        raise ProjectBindingError(f"configured .uproject could not be read: {canonical_uproject} ({exc})") from exc

    journal_root = _canonicalise(
        project_dir / JOURNAL_DIRECTORY_NAME, "derived journal root"
    )
    if os.path.normcase(journal_root.parent.as_posix()) != os.path.normcase(project_dir.as_posix()):
        raise ProjectBindingError(
            f"derived journal root {journal_root} is not directly inside the project directory"
        )
    _reject_disposable_placement(journal_root, "derived journal root")
    if journal_root.is_symlink():
        raise ProjectBindingError(f"derived journal root is a symlink: {journal_root}")

    canonical_store_root = _canonicalise(Path(store_root), "durable store root")
    containment_dir = _canonicalise(
        containment_dir_for_store(canonical_store_root), "containment directory"
    )
    # The containment evidence must never be written into the witness journal tree.
    if os.path.normcase(str(containment_dir)).startswith(
        os.path.normcase(str(journal_root)) + os.sep
    ) or os.path.normcase(str(containment_dir)) == os.path.normcase(str(journal_root)):
        raise ProjectBindingError(
            "the containment directory would live inside the witness journal root; the launch "
            "record is Atlas-side identity evidence and must stay outside the journal directory"
        )

    return ProjectContainmentContext(
        uproject_path=str(canonical_uproject),
        project_dir=str(project_dir),
        uproject_digest=uproject_digest,
        journal_root=str(journal_root),
        containment_dir=str(containment_dir),
        store_root=str(canonical_store_root),
    )


def project_identity_of(job_record: Any) -> Optional[str]:
    """Best-effort project association carried by a durable render record.

    The durable record does not carry a project field, so this returns the canonical
    output directory (which the submission creates inside the project) when present.
    It is corroboration only: the authoritative project binding is the authenticated
    containment launch record (Contract V1 §9 conjunct 1).
    """
    output_directory = getattr(job_record, "output_directory", None)
    if not isinstance(output_directory, str) or not output_directory.strip():
        return None
    try:
        return os.path.normcase(os.path.realpath(output_directory))
    except OSError:  # pragma: no cover - defensive
        return None


def verify_record_project_association(
    job_record: Any,
    context: ProjectContainmentContext,
    launch_record: Any = None,
) -> Tuple[bool, str, str]:
    """Prove ``project <-> journal root <-> render record`` for this invocation.

    Returns ``(ok, reason, corroboration)``.

    * The **gate** is the authenticated launch record: it must declare this
      invocation's canonical project directory and ``.uproject`` digest, which ties the
      attempt (and therefore the render record, via the attempt binding) to this
      project and to the journal root derived from it.
    * The record's output directory, when it lies inside the project directory, is
      reported as ``WITHIN_PROJECT_DIR`` corroboration; when it does not, that is
      reported (``NOT_WITHIN_PROJECT_DIR``) without being turned into a gate, because
      output isolation is a separate contract surface (§12) and refusing here would
      invent a rule the contract does not state.
    """
    if launch_record is None:
        return False, "no containment launch record supplied: project association is unprovable", "NONE"
    launch_project = getattr(launch_record, "project_identity", None)
    launch_digest = getattr(launch_record, "uproject_digest", None)
    if not isinstance(launch_project, str) or os.path.normcase(launch_project) != os.path.normcase(
        context.project_dir
    ):
        return (
            False,
            f"launch record project_identity {launch_project!r} does not match the configured "
            f"project directory {context.project_dir!r}",
            "NONE",
        )
    if launch_digest != context.uproject_digest:
        return (
            False,
            "launch record uproject_digest does not match the configured .uproject digest",
            "NONE",
        )
    record_output = project_identity_of(job_record)
    if record_output is None:
        return True, "", "UNKNOWN_OUTPUT_DIRECTORY"
    project_dir_norm = os.path.normcase(context.project_dir)
    if record_output == project_dir_norm or record_output.startswith(project_dir_norm + os.sep):
        return True, "", "WITHIN_PROJECT_DIR"
    return True, "", "NOT_WITHIN_PROJECT_DIR"
