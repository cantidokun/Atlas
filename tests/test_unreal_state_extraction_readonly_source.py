"""Read-only and separation gates asserted against the extraction sources.

Contract obligations exercised here: Revision 3.1 §10.2 (own translation unit, one-way
dispatch seam, forbidden-token set, accessor allowlist, const-ness discipline), §3.1.1
(no order-dependent world selection), §3.1.2 (no engine-version branching), §12 (scope
prohibitions: no render/recovery coupling) and §6.4 (no reuse of the existing digest
path).

These are *static* gates. The dynamic gate — package dirty state across the extraction
call — belongs to the live gate (§11.3) and cannot be asserted here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_DIR = (
    REPO_ROOT
    / "unreal"
    / "AtlasUnrealHarness"
    / "Source"
    / "AtlasUnrealTransport"
    / "Private"
)
EXTRACTOR_CPP = EXTRACTOR_DIR / "AtlasStateExtraction.cpp"
EXTRACTOR_H = EXTRACTOR_DIR / "AtlasStateExtraction.h"
SERVER_CPP = EXTRACTOR_DIR / "AtlasTransportServer.cpp"
PYTHON_PACKAGE = REPO_ROOT / "planning" / "unreal_state_extraction"

#: The forbidden-token set of §10.2 item 3.
FORBIDDEN_TOKENS = (
    "MarkPackageDirty",
    "Modify(",
    "SavePackage",
    "CreatePackage",
    "NewObject<",
    "SpawnActor",
    "Destroy(",
    "Rename(",
    "SetActor",
    "SetIsTemporarilyHiddenInEditor",
    "SetStaticMesh",
    "SetMaterial",
    "CreateDynamicMaterialInstance",
    "SetSequence",
    "SetPlaybackRange",
    "InitializePlayer",
    "GetSequencePlayer",
    "LoadObject",
    "StaticLoadObject",
    "TryLoad",
    "FSoftObjectPath",
    "Tags.Add",
    "Tags.Remove",
)

#: Engine paths the contract explicitly replaces or forbids (§3.2.1.4, §3.1.1, §7.2).
FORBIDDEN_ENGINE_PATHS = (
    "TActorIterator",
    "GetActiveEditorWorld",
    "GetWorldContexts",
    "StreamingLevelsToConsider",
    "FLevelCollection",
    "UActorContainer",
)

#: Accessors the extractor is permitted to call (§10.2 item 4) and is expected to use.
ALLOWLISTED_ACCESSORS = (
    "GetEditorWorldContext",
    "WorldType",
    "IsPartitionedWorld",
    "GetStreamingLevels",
    "IsLevelLoaded",
    "IsLevelVisible",
    "GetWorldAssetPackageFName",
    "GetLoadedLevel",
    "GetLevels",
    "IsValid",
    "IsRegistered",
    "GetAttachParentActor",
    "GetActorLocation",
    "GetActorQuat",
    "GetActorScale3D",
    "IsHiddenEdAtStartup",
    "IsTemporarilyHiddenInEditor",
    "bHiddenEdLayer",
    "bHiddenEdLevel",
    "GetStaticMesh",
    "GetSkinnedAsset",
    "GetNumMaterials",
    "GetMaterial",
    "OverrideMaterials",
    "IsCompiling",
    "GetSequence",
    "GetMovieScene",
    "GetPlaybackRange",
    "GetTickResolution",
    "GetDisplayRate",
    "FEngineVersion::Current",
    "FApp::GetBuildVersion",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing source file: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_comments(text: str) -> str:
    """Remove /* */ blocks and // line comments (the design's rule excludes comments)."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line.split("//", 1)[0] for line in without_blocks.splitlines())


@pytest.fixture(scope="module")
def extractor_source() -> str:
    return _read(EXTRACTOR_CPP)


@pytest.fixture(scope="module")
def extractor_code(extractor_source: str) -> str:
    return _strip_comments(extractor_source)


# ---------------------------------------------------------------------------
# Forbidden tokens
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
def test_no_forbidden_token_outside_comments(extractor_code: str, token: str) -> None:
    assert token not in extractor_code, f"forbidden token {token!r} present in the extractor"


@pytest.mark.parametrize("path", FORBIDDEN_ENGINE_PATHS)
def test_no_forbidden_engine_path(extractor_code: str, path: str) -> None:
    assert path not in extractor_code, f"forbidden engine path {path!r} present in the extractor"


# ---------------------------------------------------------------------------
# Translation unit and one-way seam
# ---------------------------------------------------------------------------

def test_the_extractor_is_its_own_translation_unit(extractor_source: str) -> None:
    assert EXTRACTOR_CPP.is_file() and EXTRACTOR_H.is_file()
    assert '#include "AtlasStateExtraction.h"' in extractor_source
    assert "AtlasTransportServer.h" not in extractor_source


def test_the_extractor_is_not_a_member_of_the_server(extractor_source: str) -> None:
    assert "FAtlasTransportServer" not in extractor_source
    assert "class FAtlasTransportServer" not in _read(EXTRACTOR_H)


def test_the_server_seam_is_one_way_and_wraps_the_value_tree() -> None:
    server = _read(SERVER_CPP)
    assert server.count("AtlasStateExtraction::ExtractActorState(") == 1
    assert server.count("AtlasStateExtraction::ExtractSequencerState(") == 1
    # The envelope wrapping the contract requires stays in the server, not the extractor.
    assert 'SetObjectField(TEXT("unreal_state_extraction"),ValueTree)' in server
    extractor_code = _strip_comments(_read(EXTRACTOR_CPP))
    assert 'TEXT("unreal_state_extraction")' not in extractor_code
    # The extractor is never handed the server, and the server never inspects the tree.
    assert "FAtlasTransportServer" not in _read(EXTRACTOR_CPP)


def test_the_seam_adds_no_other_behaviour_to_the_dispatcher() -> None:
    """The seam is additive: existing operations and their handlers are untouched."""
    server = _read(SERVER_CPP)
    for operation in (
        "inspect_world",
        "inspect_target_actors",
        "inspect_material_state",
        "inspect_sequencer_state",
        "submit_render",
        "inspect_render_state",
        "verify_render_state",
        "get_capabilities",
        "reconcile_render_jobs",
    ):
        assert f'TEXT("{operation}")' in server, operation


# ---------------------------------------------------------------------------
# World selection and version discipline
# ---------------------------------------------------------------------------

def test_world_selection_is_the_authoritative_site(extractor_code: str) -> None:
    assert "GEditor->GetEditorWorldContext().World()" in extractor_code
    assert "EWorldType::Editor" in extractor_code
    assert "IsPartitionedWorld()" in extractor_code


def test_no_engine_version_branching_or_compatibility_shim(extractor_code: str) -> None:
    assert "5.6" not in extractor_code.replace("5.6.1", "")
    for banned in ("Compatibility", "Downgrade", "EngineVersion >", "EngineVersion <", "bIsUE5"):
        assert banned not in extractor_code, banned


def test_engine_identity_is_sourced_not_literal(extractor_code: str) -> None:
    assert "FEngineVersion::Current()" in extractor_code
    assert "FApp::GetBuildVersion()" in extractor_code


# ---------------------------------------------------------------------------
# Accessor allowlist and const-ness discipline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("accessor", ALLOWLISTED_ACCESSORS)
def test_allowlisted_accessor_is_used(extractor_code: str, accessor: str) -> None:
    assert accessor in extractor_code, f"expected allowlisted accessor {accessor!r}"


def test_no_mutation_of_allowlisted_mutable_containers(extractor_code: str) -> None:
    for banned in (
        ".Actors.Add",
        ".Actors.Remove",
        ".Actors.Empty",
        ".Actors.Sort",
        "Tags.Add",
        "Tags.Remove",
        "OverrideMaterials.Add",
        "OverrideMaterials.Remove",
        "OverrideMaterials[SlotIndex] =",
        "StreamingLevels.Add",
        "SetShouldBeLoaded",
        "SetShouldBeVisible",
    ):
        assert banned not in extractor_code, banned


def test_material_reads_are_index_guarded(extractor_code: str) -> None:
    assert "OverrideMaterials.IsValidIndex" in extractor_code
    assert "GetMaterials().IsValidIndex" in extractor_code


def test_scope_is_snapshotted_and_revalidated(extractor_code: str) -> None:
    assert "SnapshotScope" in extractor_code
    assert extractor_code.count("SnapshotScope(") >= 3  # definition + snapshot + re-query
    assert "ScopeChanged" in extractor_code


def test_level_list_is_used_for_identity_only_never_for_order(extractor_code: str) -> None:
    """The one documented use of a forbidden-by-default container, tightly constrained.

    UE 5.6 keeps ``UWorld::PersistentLevel`` private with no public getter, so the
    persistent level is identified by package identity — the equivalence §4.4 states —
    using the world's level list as a *candidate set*. §7.2 forbids that list as a scope
    *order*, so this test pins the use to exactly one site and requires the canonical
    ordering and the fail-closed arm to be present.
    """
    assert extractor_code.count("GetLevels()") == 1, "the level list must be touched once"
    assert "persistent levels (expected exactly 1)" in extractor_code, "fail-closed arm missing"
    assert "PackagePath.Compare" in extractor_code, "canonical scope ordering missing"
    assert ".Sort(" in extractor_code


# ---------------------------------------------------------------------------
# Scope prohibitions (§12) and digest-path separation (§6.4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "banned",
    [
        "TargetStateEvaluator",
        "MoviePipeline",
        "SubmitRender",
        "recovery",
        "Recovery",
        "receipt",
        "Receipt",
        "M12.5",
        "m12_5",
    ],
)
def test_no_render_recovery_or_target_state_coupling(extractor_code: str, banned: str) -> None:
    assert banned not in extractor_code, banned


def _python_code_surface(package_dir: Path) -> "tuple[set[str], set[str], set[str]]":
    """Return (imported modules, called dotted names, referenced identifiers).

    Prose is deliberately excluded: the contract forbids *using* the existing digest and
    verification paths, and this package names them in docstrings precisely in order to
    forbid them. The gate therefore analyses the AST, not the text.
    """
    import ast

    modules: set[str] = set()
    calls: set[str] = set()
    identifiers: set[str] = set()

    def dotted(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = dotted(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    for path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
                modules.update(f"{node.module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Call):
                name = dotted(node.func)
                if name:
                    calls.add(name)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
            elif isinstance(node, ast.Name):
                identifiers.add(node.id)
    return modules, calls, identifiers


def test_python_package_does_not_reuse_the_existing_digest_path() -> None:
    modules, calls, identifiers = _python_code_surface(PYTHON_PACKAGE)
    assert modules, "the extraction package must exist and import something"
    for banned_module in (
        "planning.unreal_evidence_digest",
        "planning.unreal_evidence_contract",
        "planning.target_state",
        "planning.unreal_render_contract",
        "planning.production_artifact",
        "planning.blender_execution_receipt",
    ):
        assert banned_module not in modules, banned_module
    for banned_call in ("json.dumps", "digest_evidence", "digest_evidence_ledger"):
        assert banned_call not in calls, banned_call
    # ``json`` itself is imported on purpose: the *parser* is the hardened loader required
    # by §6.4. What is forbidden is canonicalizing with it, which the call check above
    # covers explicitly (``json.dumps`` must never be a canonicalization oracle, §6.3).
    for banned_identifier in ("digest_evidence", "digest_evidence_ledger", "UnrealEvidence"):
        assert banned_identifier not in identifiers, banned_identifier


def test_python_package_declares_no_verification_authority() -> None:
    modules, calls, identifiers = _python_code_surface(PYTHON_PACKAGE)
    for banned in ("TargetStateEvaluator", "satisfied", "unsatisfied", "verdict", "invariant"):
        assert banned not in identifiers, banned
        assert banned not in calls, banned
        assert banned not in modules, banned
