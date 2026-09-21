"""MF-1 — containment keeper authority isolation, and the composition root's shape.

Two structural claims, both testable without any engine:

1. The keeper's intrinsic authority is exactly {launch, Job Object management, assignment,
   handle retention, launch-identity recording, ActiveProcesses observation, drain-edge
   recovery trigger}. It does NOT import or invoke submission authority, receipt
   publication authority, historical execution authority, unrelated controller authority —
   nor the recovery coordinator's policy module (it calls the composition root instead).
2. ``scripts/run_unreal_recovery.py`` is a thin, assemblative composition root: no case
   decisions, no receipt publication, no submission, no invented identity, no operator
   supplied ``journal_root``, and no supervisor/Job Object of its own.

Modelled after the M12 authority-isolation pattern (``tests/m12/test_m12_authority_isolation.py``).
"""
from __future__ import annotations

import ast
import inspect

import pytest

import scripts.run_unreal_containment_keeper as keeper_module
import scripts.run_unreal_recovery as recovery_module

FORBIDDEN_MODULES = (
    "planning.unreal_render_submission",          # submission authority
    "planning.unreal_render_receipt",             # receipt minting
    "planning.unreal_render_receipt_store",       # receipt publication
    "planning.unreal_evidence_contract",          # evidence verification authority
    "planning.unreal_render_recovery_coordinator",  # recovery policy/decisions
    "planning.unreal_autonomous_execution_loop",  # historical execution authority
    "planning.unreal_authorized_execution_gate",  # historical execution authority
    "planning.unreal_production_autonomous_loop",
    "planning.unreal_production_controller_bridge",
    "atlas_dev_controller",
)

#: Tokens that imply authority the keeper must not hold (checked in CODE, not docstrings).
FORBIDDEN_CODE_TOKENS = (
    "publish_verified_receipt",
    "issue_receipt",
    "UnrealRenderReceipt",
    "submit_render",
    "reconcile_single_job",
    "reconcile_all_non_terminal_jobs",
    "verify_render_job_evidence",
    "case_classified",
    "receipt_reference",
    "authorization_id",
    "Case A",
    "Case B",
    "Case E",
    "Case F",
    "Case G",
    "Case H",
    "Case J",
    "Case K",
)

#: The keeper's declared intrinsic authority (Contract V1 §9; design §4.2 Option 4).
DECLARED_KEEPER_AUTHORITY = frozenset(
    {
        "launch",
        "job_record",
        "observe_active_processes",
        "wait_for_drain",
        "trigger_recovery",
        "release",
        "run",
    }
)


def _source_of(module) -> str:
    return inspect.getsource(module)


def _module_level_imports(source: str) -> set[str]:
    """Modules imported at module scope (not inside a function)."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _all_imports(source: str):
    """(module, is_module_level) for every import anywhere in the file."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, True))
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_level = node in tree.body
            found.append((node.module, module_level))
    return found


def _own_public_names(module) -> set[str]:
    """Names the module ITSELF defines (imports excluded)."""
    tree = ast.parse(_source_of(module))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return {name for name in names if not name.startswith("_")} - {"logger"}


def _functions_referencing(source: str, token: str) -> set[str]:
    """Names of functions that reference ``token`` as a name or attribute."""
    tree = ast.parse(source)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr == token:
                    out.add(node.name)
                elif isinstance(sub, ast.Name) and sub.id == token:
                    out.add(node.name)
    return out


def _code_tokens(source: str) -> set[str]:
    """Identifiers, attribute names and string literals used in CODE (docstrings excluded)."""
    tree = ast.parse(source)
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstring_nodes:
                found.add(node.value)
    return found


# ── keeper: no authority imports ─────────────────────────────────────────
def test_keeper_does_not_import_submission_receipt_or_execution_authority():
    imported = {name for name, _ in _all_imports(_source_of(keeper_module))}
    for forbidden in FORBIDDEN_MODULES:
        assert not any(
            name == forbidden or name.startswith(forbidden + ".")
            for name in imported
        ), f"containment keeper illegally imports authority module {forbidden}"


def test_keeper_imports_only_its_declared_dependencies():
    imported = {name for name, _ in _all_imports(_source_of(keeper_module))}
    allowed = {
        "__future__", "argparse", "logging", "pathlib", "time", "typing", "uuid",
        "planning.unreal_containment_launch_record",
        "planning.unreal_containment_project",
        "planning.unreal_render_job_store",
        "scripts.run_unreal_supervisor",
        "scripts.run_unreal_recovery",  # the composition root, invoked at the drain edge
    }
    assert imported <= allowed, f"unexpected keeper dependency: {sorted(imported - allowed)}"


def test_keeper_invokes_the_composition_root_only_from_inside_the_drain_edge():
    for module_name, module_level in _all_imports(_source_of(keeper_module)):
        if module_name == "scripts.run_unreal_recovery":
            assert module_level is False, (
                "the recovery composition root must be imported lazily inside the drain-edge "
                "trigger, not at keeper import time"
            )


def test_keeper_code_contains_no_recovery_or_receipt_authority_tokens():
    tokens = _code_tokens(_source_of(keeper_module))
    for token in FORBIDDEN_CODE_TOKENS:
        assert token not in tokens, f"keeper code references forbidden authority token {token!r}"


def test_keeper_public_authority_surface_is_exactly_the_declared_one():
    public_methods = {
        name
        for name, value in inspect.getmembers(keeper_module.ContainmentKeeper, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods == DECLARED_KEEPER_AUTHORITY

    for name in public_methods:
        for forbidden in ("submit", "publish", "authorize", "decide", "classify", "verify_evidence"):
            assert forbidden not in name, f"keeper exposes authority-shaped method {name!r}"


def test_keeper_api_is_frozen_to_the_reviewed_set():
    exported = _own_public_names(keeper_module)
    assert exported == {
        "KEEPER_SOURCE_IDENTITY",
        "DEFAULT_DRAIN_POLL_SECONDS",
        "DEFAULT_DRAIN_TIMEOUT_SECONDS",
        "ContainmentKeeperRefusedError",
        "ContainmentKeeper",
        "default_recovery_trigger",
        "build_arg_parser",
        "main",
    }, f"keeper public surface changed: {sorted(exported)}"


# ── composition root: assemblative only ──────────────────────────────────
def test_composition_root_has_no_operator_supplied_journal_root():
    for func in (recovery_module.build_recovery_runtime, recovery_module.run_recovery_pass):
        assert "journal_root" not in inspect.signature(func).parameters
    source = _source_of(recovery_module)
    assert source.count("journal_root=") == 1, (
        "the composition root may only bind journal_root from the derived project context"
    )
    assert "journal_root=context.journal_root" in source
    assert "ATLAS_JOURNAL_ROOT" not in source and "JOURNAL_ROOT" not in _code_tokens(source)


def test_composition_root_never_decides_or_publishes():
    source = _source_of(recovery_module)
    tokens = _code_tokens(source)
    for token in ("publish_verified_receipt", "UnrealRenderReceipt", "submit_render",
                  "authorization_id", "issue", "Receipt"):
        assert token not in tokens, f"composition root references {token!r}"
    # No case-name literal may appear anywhere in the module's code: the root reports the
    # coordinator's decision, it never produces or special-cases one.
    assert not any(tok.startswith("Case ") for tok in tokens)
    # Reading the decision for the invocation record is allowed, but only in the evidence
    # packaging function - never in an assembly or branch of its own.
    assert _functions_referencing(source, "case_classified") <= {"_decision_evidence"}


def test_composition_root_assembles_the_reviewed_components():
    source = _source_of(recovery_module)
    for required in (
        "AtlasRenderJobStore",
        "UnrealRenderReceiptStore",
        "UnrealRenderRecoveryCoordinator",
        "create_production_adapter",
        "resolve_project_containment_context",
    ):
        assert required in source, f"composition root does not assemble {required}"


def test_composition_root_never_creates_a_supervisor_or_job_object():
    source = _source_of(recovery_module)
    assert "AtlasProcessSupervisor" not in source
    assert "CreateJobObject" not in source
    assert "create_contained_job" not in source


def test_composition_root_api_is_frozen_to_the_reviewed_set():
    exported = _own_public_names(recovery_module)
    assert exported == {
        "RECOVERY_RECEIPT_PROBE_FILENAME",
        "DEFAULT_COORDINATOR_ID",
        "CompositionRefusedError",
        "RecoveryRuntime",
        "build_recovery_runtime",
        "run_recovery_pass",
        "write_invocation_evidence",
        "main",
    }, f"composition root public surface changed: {sorted(exported)}"


def test_composition_root_is_not_a_standalone_recovery_authority():
    with pytest.raises(recovery_module.CompositionRefusedError):
        recovery_module.main([])
