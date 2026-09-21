"""MF-2 — derived journal root, canonical validation, and the project association chain.

Production must derive the Contract V1 §10 journal root from the configured ``.uproject``
(``<ProjectDir>/AtlasWitnessJournal``) instead of accepting an operator-supplied
``journal_root``, must canonicalise it (no symlink/junction escape, no ``Saved/`` placement),
and must be able to prove ``project <-> journal root <-> render record`` for the invocation.

These tests also cover the composition root's assembly behaviour: what it refuses, what it
assembles, and what its invocation evidence records.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

import tests.m6.fault_fixtures as ff
from planning.unreal_containment_project import (
    ProjectBindingError,
    resolve_project_containment_context,
    verify_record_project_association,
)
from scripts.run_unreal_recovery import (
    RECOVERY_RECEIPT_PROBE_FILENAME,
    CompositionRefusedError,
    build_recovery_runtime,
    run_recovery_pass,
    write_invocation_evidence,
)
from tests.m7.containment_harness import ContainmentProject, ExplodingAdapter


def _project(tmp_path, **kwargs) -> ContainmentProject:
    return ContainmentProject(tmp_path, **kwargs)


# ── derivation & canonical validation ────────────────────────────────────
def test_journal_root_is_derived_from_the_configured_uproject(tmp_path):
    p = _project(tmp_path)
    context = resolve_project_containment_context(p.uproject, p.store_root)

    assert context.journal_root == str(pathlib.Path(p.journal_root).resolve())
    assert context.project_dir == str(p.project_dir.resolve())
    assert context.containment_dir == str(p.containment_dir.resolve())
    assert context.uproject_digest == _sha256(p.uproject.read_bytes())
    snapshot = context.snapshot()
    assert snapshot["journal_root_canonical"] == context.journal_root
    assert snapshot["uproject_digest"] == context.uproject_digest
    assert "derived from the configured .uproject" in snapshot["journal_root_derivation"]


def test_non_uproject_and_missing_project_are_refused(tmp_path):
    p = _project(tmp_path)
    other = p.project_dir / "NotAProject.txt"
    other.write_text("nope", encoding="utf-8")
    with pytest.raises(ProjectBindingError):
        resolve_project_containment_context(other, p.store_root)
    with pytest.raises(ProjectBindingError):
        resolve_project_containment_context(p.project_dir / "absent.uproject", p.store_root)
    with pytest.raises(ProjectBindingError):
        resolve_project_containment_context("", p.store_root)


@pytest.mark.parametrize("component", ["Saved", "saved", "SAVED", "SaVeD"])
def test_project_or_journal_root_under_saved_is_refused(tmp_path, component):
    """Regression (CI 2026-09-21, POSIX legs): the refusal must not depend on
    ``os.path.normcase``, which is a no-op off Windows and would silently stop refusing a
    ``Saved/`` placement there. All case variants must be refused on every platform."""
    saved_project = tmp_path / component / "proj"
    saved_project.mkdir(parents=True)
    uproject = saved_project / "Atlas.uproject"
    uproject.write_text("{}", encoding="utf-8")
    with pytest.raises(ProjectBindingError) as excinfo:
        resolve_project_containment_context(uproject, tmp_path / "store")
    assert "Saved/" in str(excinfo.value)


def test_symlink_or_junction_escape_is_refused(tmp_path):
    real = _project(tmp_path / "real")
    link = tmp_path / "linked_project"
    if not _make_directory_link(real.project_dir, link):
        pytest.skip("directory links are not creatable in this environment")
    escaped = link / real.uproject.name
    assert escaped.is_file()  # it resolves through the link
    with pytest.raises(ProjectBindingError) as excinfo:
        resolve_project_containment_context(escaped, tmp_path / "store2")
    assert "symlink/junction" in str(excinfo.value)


def test_containment_evidence_may_not_live_inside_the_journal_root(tmp_path):
    p = _project(tmp_path)
    with pytest.raises(ProjectBindingError) as excinfo:
        resolve_project_containment_context(p.uproject, p.journal_root)
    assert "witness journal root" in str(excinfo.value)


# ── project <-> journal root <-> render record ───────────────────────────
def test_project_association_binds_through_the_authenticated_launch_record(tmp_path):
    p = _project(tmp_path)
    context = resolve_project_containment_context(p.uproject, p.store_root)
    launch = ff.make_launch_record(
        p.record,
        project_identity=context.project_dir,
        uproject_digest=context.uproject_digest,
    )
    ok, reason, corroboration = verify_record_project_association(p.record, context, launch_record=launch)
    assert (ok, reason) == (True, "")
    assert corroboration == "WITHIN_PROJECT_DIR"


def test_project_association_refuses_a_launch_record_from_another_project(tmp_path):
    p = _project(tmp_path)
    context = resolve_project_containment_context(p.uproject, p.store_root)
    foreign = ff.make_launch_record(p.record)  # declares ff.TEST_PROJECT_IDENTITY
    ok, reason, corroboration = verify_record_project_association(p.record, context, launch_record=foreign)
    assert ok is False
    assert "does not match the configured project directory" in reason
    assert corroboration == "NONE"


def test_project_association_refuses_a_swapped_uproject_digest(tmp_path):
    p = _project(tmp_path)
    context = resolve_project_containment_context(p.uproject, p.store_root)
    swapped = ff.make_launch_record(
        p.record, project_identity=context.project_dir, uproject_digest="0" * 64
    )
    ok, reason, _ = verify_record_project_association(p.record, context, launch_record=swapped)
    assert ok is False
    assert "uproject_digest" in reason


# ── composition root: assembly behaviour ─────────────────────────────────
def _runtime(p, **overrides):
    launch = overrides.pop(
        "launch_record",
        ff.make_launch_record(
            p.record,
            project_identity=str(p.project_dir.resolve()),
            uproject_digest=resolve_project_containment_context(p.uproject, p.store_root).uproject_digest,
        ),
    )
    adapter = overrides.pop("adapter", ExplodingAdapter())
    return build_recovery_runtime(
        store_root=str(p.store_root),
        uproject=str(p.uproject),
        supervisor=p.contained_supervisor(),
        launch_record=launch,
        adapter=adapter,
        **overrides,
    )


def test_composition_root_assembles_the_reviewed_graph(tmp_path):
    p = _project(tmp_path)
    runtime = _runtime(p)

    assert runtime.store.root == p.store_root.resolve()
    assert runtime.coordinator.journal_root == str(p.journal_root.resolve())
    assert str(runtime.coordinator.containment_dir) == str(p.containment_dir.resolve())
    assert runtime.coordinator.containment_launch_record is runtime.launch_record
    assert runtime.coordinator.supervisor is runtime.supervisor
    assert runtime.coordinator.deployment_mode == "CONTAINED_JOB_OBJECT"
    assert runtime.receipt_store.path == p.store.receipts_dir / RECOVERY_RECEIPT_PROBE_FILENAME
    assert runtime.adapter_source_tag == "ExplodingAdapter"


def test_composition_root_refuses_without_a_retained_handle_or_launch_record(tmp_path):
    p = _project(tmp_path)
    launch = ff.make_launch_record(p.record)
    handleless = p.contained_supervisor(job_handle=None)

    with pytest.raises(CompositionRefusedError) as excinfo:
        build_recovery_runtime(store_root=str(p.store_root), uproject=str(p.uproject),
                               supervisor=handleless, launch_record=launch, adapter=ExplodingAdapter())
    assert "retained Job Object handle" in str(excinfo.value)

    with pytest.raises(CompositionRefusedError):
        build_recovery_runtime(store_root=str(p.store_root), uproject=str(p.uproject),
                               supervisor=p.contained_supervisor(), launch_record=None,
                               adapter=ExplodingAdapter())

    with pytest.raises(CompositionRefusedError):
        build_recovery_runtime(store_root=str(p.store_root), uproject=str(p.uproject),
                               supervisor=p.contained_supervisor(), launch_record={"not": "a record"},
                               adapter=ExplodingAdapter())


def test_composition_root_refuses_when_bindings_cannot_be_proven(tmp_path):
    """A launch record from another project may not drive this invocation."""
    p = _project(tmp_path)
    runtime = _runtime(p, launch_record=ff.make_launch_record(p.record))  # foreign project identity
    frame = p.write_frame()
    p.write_terminal_witness(frame)
    p.persist_launch_record()

    with pytest.raises(CompositionRefusedError) as excinfo:
        run_recovery_pass(runtime, atlas_job_id=p.record.atlas_job_id, job_records=[p.record])
    assert "project association=" in str(excinfo.value)
    assert list(p.store.receipts_dir.glob("*.json")) == []


def test_recovery_pass_adopts_case_b_and_records_invocation_evidence(tmp_path):
    p = _project(tmp_path)
    frame = p.write_frame()
    p.write_terminal_witness(frame)
    p.persist_launch_record()
    runtime = _runtime(p)

    evidence = run_recovery_pass(runtime, atlas_job_id=p.record.atlas_job_id,
                                 job_records=[p.record], lease_token=3)

    decisions = evidence["decisions"]
    assert decisions[0]["case_classified"] == "Case B"
    assert decisions[0]["lifecycle_state_after"] == "FINALIZED"
    assert len(list(p.store.receipts_dir.glob("*.json"))) == 1

    assert evidence["journal_root_canonical"] == runtime.context.journal_root
    assert evidence["uproject_digest"] == runtime.context.uproject_digest
    assert evidence["store_root_canonical"] == runtime.context.store_root
    assert evidence["launch_record_digest"] == runtime.launch_record.launch_record_digest
    assert evidence["lease_token"] == 3
    bindings = evidence["job_bindings"][0]
    assert bindings["launch_record_binding"] == "BOUND"
    assert bindings["project_association"] == "BOUND"
    assert bindings["project_association_corroboration"] == "WITHIN_PROJECT_DIR"


def test_invocation_evidence_is_written_beside_the_containment_provenance(tmp_path):
    p = _project(tmp_path)
    frame = p.write_frame()
    p.write_terminal_witness(frame)
    p.persist_launch_record()
    runtime = _runtime(p)
    evidence = run_recovery_pass(runtime, atlas_job_id=p.record.atlas_job_id, job_records=[p.record])

    path = write_invocation_evidence(runtime, evidence)

    assert path.parent == pathlib.Path(runtime.context.containment_dir)
    assert p.journal_root not in path.parents
    text = path.read_text(encoding="utf-8")
    assert p.record.attempt_nonce not in text  # never persisted, not even in evidence
    written = json.loads(text)
    assert written["journal_root_canonical"] == runtime.context.journal_root
    assert written["uproject_digest"] == runtime.context.uproject_digest
    assert written["launch_record_digest"] == runtime.launch_record.launch_record_digest


# ── helpers ──────────────────────────────────────────────────────────────
def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _make_directory_link(target: pathlib.Path, link: pathlib.Path) -> bool:
    """Create a junction (Windows, no admin needed) or symlink (POSIX)."""
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        return False
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False
