"""Static gates for the portable read-only extraction plugin (U1 evidence mechanism).

These gates are pure file analysis: no engine, no editor, no network. They assert the
properties the plugin promises about itself, and each "absence" gate is paired with a
control that proves the scan can actually detect presence (the same pattern taken against
the Atlas validation harness, which does contain write operations, fixture provisioning and
the full transport surface).

What is asserted here:

* the read-only forbidden-token/engine-path gate of
  ``tests/test_unreal_state_extraction_readonly_source.py`` holds for the whole plugin, not
  only for the carried-forward extractor — the token tuple is imported from that module, so
  the plugin cannot weaken the harness's list;
* the carried-forward extraction core is byte-identical to the harness version (so
  "carried forward without semantic alteration" is a hash equality, not a claim);
* no write/render/fixture operation is named anywhere in the shipping sources;
* no AtlasUnrealHarness / fixture / ``/Game/`` coupling exists in any plugin source;
* the build rules omit the harness's UI, Kismet, render-pipeline and asset-registry
  dependencies while keeping the extraction dependencies;
* the C++ constants and the Python contract in :mod:`planning.unreal_read_only_extraction`
  agree, so the declaration cannot drift;
* the response envelope and the six session identity fields are the existing Atlas
  transport ones (parsed out of both implementations and compared);
* the extraction payload bound is preserved;
* module startup is gated by the declared opt-in policy and provisions nothing;
* the plugin holds no verification authority and does not reach the U1 registry;
* the change stays inside the plugin, its tests and its contract.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, Optional, Sequence, Set, Tuple

import pytest

from planning import unreal_read_only_extraction as contract
# The harness's own read-only gate defines the token set. Importing it (rather than
# restating it) is what makes "the plugin does not weaken the gate" checkable.
from tests.test_unreal_state_extraction_readonly_source import (
    FORBIDDEN_ENGINE_PATHS,
    FORBIDDEN_TOKENS,
)
# The build-provenance helpers live with the live gate that performs the build; importing them
# keeps these checks tied to the real decision logic instead of restating it.
from tests.test_unreal_read_only_extraction_live_gate import (
    BUILD_EXIT_MARKER,
    MODULE_PROVENANCE_SCHEMA,
    _build_failure_reason,
    _build_result_ok,
    _build_wrapper_text,
    _ensure_plugin_junction,
    _module_provenance_path,
    _plugin_source_fingerprint,
    _reuse_decision,
    _write_module_provenance,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_TRANSPORT_DIR = REPO_ROOT / "unreal" / "AtlasUnrealHarness" / "Source" / "AtlasUnrealTransport"
HARNESS_SERVER_CPP = HARNESS_TRANSPORT_DIR / "Private" / "AtlasTransportServer.cpp"
HARNESS_MODULE_CPP = HARNESS_TRANSPORT_DIR / "Private" / "AtlasUnrealTransport.cpp"
HARNESS_BUILD_RULES = HARNESS_TRANSPORT_DIR / "AtlasUnrealTransport.Build.cs"
HARNESS_CORE_CPP = HARNESS_TRANSPORT_DIR / "Private" / "AtlasStateExtraction.cpp"
HARNESS_CORE_H = HARNESS_TRANSPORT_DIR / "Private" / "AtlasStateExtraction.h"

PLUGIN_CORE_CPP = contract.PRIVATE_DIR / "AtlasStateExtraction.cpp"
PLUGIN_CORE_H = contract.PRIVATE_DIR / "AtlasStateExtraction.h"
PLUGIN_MODULE_CPP = contract.PRIVATE_DIR / "AtlasReadOnlyExtraction.cpp"
PLUGIN_CONTRACT_CPP = contract.PRIVATE_DIR / "AtlasReadOnlyExtractionContract.cpp"
PLUGIN_SERVER_CPP = contract.PRIVATE_DIR / "AtlasReadOnlyExtractionServer.cpp"
PLUGIN_SERVER_H = contract.PUBLIC_DIR / "AtlasReadOnlyExtractionServer.h"
PLUGIN_TESTS_CPP = contract.PRIVATE_DIR / contract.AUTOMATION_TEST_SOURCE_NAME
LIVE_GATE_PATH = REPO_ROOT / "tests" / "test_unreal_read_only_extraction_live_gate.py"

HARNESS_SERIALIZE_SIGNATURE = "FString FAtlasTransportServer::SerializeResponse(const FTransportResponse& Response)"
PLUGIN_SERIALIZE_SIGNATURE = "FString FAtlasReadOnlyExtractionServer::SerializeResponse(const FResponse& Response) const"
HARNESS_IDENTITY_SIGNATURE = "void FAtlasTransportServer::CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject)"
PLUGIN_IDENTITY_SIGNATURE = "void FAtlasReadOnlyExtractionServer::CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject) const"

FIELD_KEY_PATTERN = re.compile(r'Set(?:String|Number|Bool|Object|Array)Field\(TEXT\("([A-Za-z_]+)"\)')

FIXTURE_AND_HARNESS_IDENTIFIERS = (
    "AtlasUnrealHarness",
    "AtlasExtractionFixture",
    "AtlasSequencerFixtureSequence",
    "AtlasRenderFixture",
    "AtlasSequencerFixture",
    "AtlasFieldSurfaceFixture",
    "atlas_sequencer_fixture",
    # The fixture tag value, not the `atlas_entity:` tag convention: production actors
    # carry `atlas_entity:<id>` tags too, and reading them is the extractor's whole job.
    "atlas_entity:FIELD_SURFACE",
    "FIELD_SURFACE",
    "IMPL_PERM_A",
    "IMPL_MATERIAL_OVERRIDE_A",
    "/Game/",
    "AtlasTest",
)

FORBIDDEN_DEPENDENCIES = (
    "EditorStyle",
    "EditorWidgets",
    "ToolMenus",
    "KismetCompiler",
    "MovieRenderPipeline",
    "AssetRegistry",
    "FileHelpers",
    "Niagara",
    "Slate",
    "SlateCore",
)

REQUIRED_DEPENDENCIES = (
    "Core",
    "CoreUObject",
    "Engine",
    "UnrealEd",
    "LevelSequence",
    "MovieScene",
    "Json",
)

WRITE_CAPABLE_AUTOMATION_TOKENS = (
    "SpawnActor",
    "CreatePackage",
    "SavePackage",
    "MarkPackageDirty",
    "NewObject<",
    "LoadObject",
)

CHANGE_ALLOWED_PREFIXES = (
    "unreal/plugins/AtlasReadOnlyExtraction/",
    "planning/unreal_read_only_extraction.py",
    "tests/test_unreal_read_only_extraction_plugin.py",
    "tests/test_unreal_read_only_extraction_live_gate.py",
    "docs/UNREAL_READ_ONLY_EXTRACTION_PLUGIN.md",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing source file: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_comments(text: str) -> str:
    """Remove /* */ blocks and // line comments (the same rule the harness gate applies)."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line.split("//", 1)[0] for line in without_blocks.splitlines())


def _function_body(text: str, signature: str) -> str:
    """The body of one function, from its signature to its matching closing brace."""
    start = text.index(signature)
    brace_start = text.index("{", start)
    depth = 0
    for index in range(brace_start, len(text)):
        character = text[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated function body for {signature!r}")


def _keys_in(text: str, signature: str) -> Set[str]:
    return set(FIELD_KEY_PATTERN.findall(_function_body(text, signature)))


def _each_production_source() -> Sequence[Tuple[Path, str]]:
    return [(path, _strip_comments(_read(path))) for path in contract.production_sources()]


def _each_source() -> Sequence[Tuple[Path, str]]:
    return [(path, _strip_comments(_read(path))) for path in contract.all_sources()]


# ---------------------------------------------------------------------------
# Descriptor
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def descriptor() -> Dict[str, object]:
    return json.loads(_read(contract.DESCRIPTOR_PATH))


def test_descriptor_declares_exactly_one_module(descriptor: Dict[str, object]) -> None:
    modules = descriptor["Modules"]
    assert isinstance(modules, list) and len(modules) == 1
    assert modules[0]["Name"] == "AtlasReadOnlyExtraction"


def test_descriptor_declares_an_editor_module(descriptor: Dict[str, object]) -> None:
    module = descriptor["Modules"][0]
    assert module["Type"] == "Editor"
    assert module["LoadingPhase"] == "Default"


def test_descriptor_is_not_enabled_by_default(descriptor: Dict[str, object]) -> None:
    """Loading the plugin in a host project is itself an explicit act."""
    assert descriptor["EnabledByDefault"] is False


def test_descriptor_declares_no_plugin_dependency(descriptor: Dict[str, object]) -> None:
    """The plugin must not drag the harness, the render pipeline or any other plugin in."""
    assert descriptor["Plugins"] == []


def test_descriptor_contains_no_content(descriptor: Dict[str, object]) -> None:
    assert descriptor.get("CanContainContent", False) is False


def test_plugin_ignores_its_own_build_outputs() -> None:
    """A host project links the plugin in place; its binaries must never be committed."""
    ignore = _read(contract.PLUGIN_DIR / ".gitignore")
    for entry in ("Binaries/", "Intermediate/", "Saved/", "DerivedDataCache/"):
        assert entry in ignore, f"the plugin does not ignore {entry}"


# ---------------------------------------------------------------------------
# The extraction core is carried forward, byte for byte
# ---------------------------------------------------------------------------

def test_extraction_core_cpp_is_byte_identical_to_the_harness_core() -> None:
    assert PLUGIN_CORE_CPP.read_bytes() == HARNESS_CORE_CPP.read_bytes()


def test_extraction_core_header_is_byte_identical_to_the_harness_core() -> None:
    assert PLUGIN_CORE_H.read_bytes() == HARNESS_CORE_H.read_bytes()


def test_extraction_core_keeps_the_one_way_seam_and_the_closed_vocabulary() -> None:
    core_code = _strip_comments(_read(PLUGIN_CORE_CPP))
    assert "FAtlasTransportServer" not in core_code, "the extractor must not reference the server"
    assert "AtlasReadOnlyExtractionServer" not in core_code, "the extractor must not reference the server"
    assert "ERR_EXTRACTION_" in core_code


# ---------------------------------------------------------------------------
# Read-only token gate (the harness's own set, applied to the whole plugin)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
def test_no_forbidden_token_in_the_plugin_production_sources(token: str) -> None:
    for path, code in _each_production_source():
        assert token not in code, f"forbidden token {token!r} present in {path.name}"


@pytest.mark.parametrize("engine_path", FORBIDDEN_ENGINE_PATHS)
def test_no_forbidden_engine_path_in_the_plugin_production_sources(engine_path: str) -> None:
    for path, code in _each_production_source():
        assert engine_path not in code, f"forbidden engine path {engine_path!r} present in {path.name}"


def test_the_token_and_path_scans_can_detect_presence() -> None:
    """Control: the same scan finds write tokens in the harness, so absence here is real."""
    harness_code = _strip_comments(_read(HARNESS_SERVER_CPP)) + _strip_comments(_read(HARNESS_MODULE_CPP))
    found = [token for token in FORBIDDEN_TOKENS if token in harness_code]
    assert found, "the forbidden-token scan detects nothing in the harness: the scan is broken"
    for token in found:
        for path, code in _each_production_source():
            assert token not in code, f"the harness write token {token!r} leaked into {path.name}"


def test_the_harness_still_carries_the_write_surface_this_plugin_omits() -> None:
    """Control for the operation-surface gates: the source they came from is write-capable."""
    harness_code = _strip_comments(_read(HARNESS_SERVER_CPP))
    assert "SavePackage" in harness_code or "MarkPackageDirty" in harness_code
    assert "MoviePipeline" in _read(HARNESS_SERVER_CPP) or "MovieRenderPipeline" in _read(HARNESS_BUILD_RULES)


# ---------------------------------------------------------------------------
# The write/render/fixture operation surface is absent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("operation", contract.FORBIDDEN_OPERATIONS)
def test_production_sources_never_name_a_refused_operation(operation: str) -> None:
    for path, code in _each_production_source():
        assert operation not in code, f"refused operation {operation!r} is named in {path.name}"


@pytest.mark.parametrize("operation", contract.FORBIDDEN_OPERATIONS)
def test_the_operation_scan_can_detect_presence(operation: str) -> None:
    """Control: every refused operation IS named by the harness server it came from."""
    harness_code = _strip_comments(_read(HARNESS_SERVER_CPP))
    assert operation in harness_code, f"{operation!r} is not in the harness server: stale control"


def test_only_the_guarded_automation_test_file_names_refused_operations() -> None:
    """The refused names appear only as test data inside a development-only guard."""
    test_source = _read(PLUGIN_TESTS_CPP)
    assert "#if WITH_DEV_AUTOMATION_TESTS" in test_source
    assert "#endif // WITH_DEV_AUTOMATION_TESTS" in test_source
    for operation in contract.FORBIDDEN_OPERATIONS:
        assert operation in test_source, f"{operation!r} is not asserted as refused"


@pytest.mark.parametrize("token", WRITE_CAPABLE_AUTOMATION_TOKENS)
def test_the_automation_tests_are_not_write_capable(token: str) -> None:
    """The plugin's own tests provision nothing: no spawn, no package, no save, no load."""
    assert token not in _strip_comments(_read(PLUGIN_TESTS_CPP))


def test_the_advertised_operations_are_the_two_extraction_operations() -> None:
    contract_code = _strip_comments(_read(PLUGIN_CONTRACT_CPP))
    declared = set(
        re.findall(
            r'const TCHAR\* const (?:ExtractActorState|ExtractSequencerState) = TEXT\("([a-z_]+)"\)',
            contract_code,
        )
    )
    assert declared == set(contract.OPERATIONS)
    assert len(declared) == 2


def test_the_dispatch_table_is_closed_on_the_two_operations() -> None:
    server_code = _strip_comments(_read(PLUGIN_SERVER_CPP))
    dispatched = set(re.findall(r"Operations::(ExtractActorState|ExtractSequencerState)\b", server_code))
    assert dispatched == {"ExtractActorState", "ExtractSequencerState"}
    # No other extraction entry point is reachable from this file.
    assert "AtlasStateExtraction::" in server_code
    other_calls = set(re.findall(r"AtlasStateExtraction::(\w+)", server_code))
    assert other_calls <= {"ExtractActorState", "ExtractSequencerState"}


# ---------------------------------------------------------------------------
# Fixture isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("identifier", FIXTURE_AND_HARNESS_IDENTIFIERS)
def test_no_plugin_source_references_fixture_or_harness_content(identifier: str) -> None:
    for path, code in _each_source():
        assert identifier not in code, f"fixture/harness identifier {identifier!r} present in {path.name}"


def test_the_fixture_scan_can_detect_presence() -> None:
    """Control: those identifiers do exist where they belong, in the harness."""
    harness_code = _read(HARNESS_MODULE_CPP)
    present = [identifier for identifier in FIXTURE_AND_HARNESS_IDENTIFIERS if identifier in harness_code]
    assert "/Game/" in present
    assert "AtlasTest" in present


def test_the_plugin_declares_no_game_content_path() -> None:
    """No content package, no map, no asset: the plugin reads the loaded world only."""
    for path, code in _each_source():
        assert not re.search(r'"/Game', code), f"{path.name} names a content package"


# ---------------------------------------------------------------------------
# Dependency minimality
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dependency", FORBIDDEN_DEPENDENCIES)
def test_build_rules_omit_write_render_and_ui_dependencies(dependency: str) -> None:
    build_rules = _read(contract.BUILD_RULES_PATH)
    # Comment lines name the omitted dependencies on purpose (as documentation of why);
    # what must not appear is a dependency declaration.
    declared = "\n".join(
        line for line in build_rules.splitlines() if not line.strip().startswith("//")
    )
    declared_dependencies = set(re.findall(r'"([A-Za-z0-9_]+)"', declared))
    offending = sorted(name for name in declared_dependencies if name.startswith(dependency))
    assert not offending, f"the plugin's build rules declare {offending}"


@pytest.mark.parametrize("dependency", REQUIRED_DEPENDENCIES)
def test_build_rules_keep_the_extraction_dependencies(dependency: str) -> None:
    build_rules = _read(contract.BUILD_RULES_PATH)
    assert f'"{dependency}"' in build_rules, f"{dependency} is missing from the plugin's build rules"


def test_the_dependency_gate_can_detect_presence() -> None:
    """Control: the harness build rules do declare the dependencies the plugin omits."""
    harness_rules = _read(HARNESS_BUILD_RULES)
    harness_dependencies = set(re.findall(r'"([A-Za-z0-9_]+)"', harness_rules))
    present = [
        dependency
        for dependency in FORBIDDEN_DEPENDENCIES
        if any(name.startswith(dependency) for name in harness_dependencies)
    ]
    assert "KismetCompiler" in present
    assert "MovieRenderPipeline" in present
    assert "AssetRegistry" in present


# ---------------------------------------------------------------------------
# Cross-language contract agreement
# ---------------------------------------------------------------------------

def _cpp_string_constant(name: str) -> str:
    contract_code = _read(PLUGIN_CONTRACT_CPP)
    match = re.search(rf'const TCHAR\* const {name} = TEXT\("([^"]*)"\)', contract_code)
    assert match, f"the plugin contract does not declare {name}"
    return match.group(1)


def test_cpp_pipe_name_matches_the_python_contract() -> None:
    # The C++ literal is escaped for the C preprocessor: \\\\.\\pipe\\X in source text.
    assert _cpp_string_constant("DefaultPipeName") == contract.PIPE_NAME.replace("\\", "\\\\")


def test_cpp_source_string_matches_the_python_contract() -> None:
    assert _cpp_string_constant("SourceString") == contract.SOURCE


def test_cpp_opt_in_switch_matches_the_python_contract() -> None:
    assert _cpp_string_constant("OptInSwitch") == contract.OPT_IN_SWITCH.lstrip("-")
    assert _cpp_string_constant("PipeNameSwitch") == contract.PIPE_SWITCH_PREFIX.lstrip("-").rstrip("=")


def test_cpp_config_keys_match_the_python_contract() -> None:
    assert _cpp_string_constant("ConfigSection") == contract.CONFIG_SECTION
    assert _cpp_string_constant("ConfigEnableKey") == contract.CONFIG_ENABLE_KEY
    assert _cpp_string_constant("ConfigPipeNameKey") == contract.CONFIG_PIPE_KEY


def test_cpp_wire_bound_matches_the_python_contract() -> None:
    contract_code = _strip_comments(_read(PLUGIN_CONTRACT_CPP))
    match = re.search(r"return (\d+) \* (\d+);", contract_code)
    assert match, "the wire bound is not declared as a product of two literals"
    assert int(match.group(1)) * int(match.group(2)) == contract.WIRE_MESSAGE_LIMIT


def test_cpp_capabilities_match_the_python_contract() -> None:
    contract_code = _strip_comments(_read(PLUGIN_CONTRACT_CPP))
    pairs = dict(
        re.findall(
            r'if \(OperationName == Extract(\w+)State\)\s*\{\s*return TEXT\("([a-z_]+)"\);',
            contract_code,
        )
    )
    assert pairs == {"Actor": "inspect_actor", "Sequencer": "sequencer"}


def test_the_plugin_pipe_is_not_the_harness_pipe() -> None:
    assert contract.PIPE_NAME != contract.HARNESS_PIPE_NAME
    assert _cpp_string_constant("DefaultPipeName") != contract.HARNESS_PIPE_NAME.replace("\\", "\\\\")


# ---------------------------------------------------------------------------
# Envelope and session identity parity with the existing transport
# ---------------------------------------------------------------------------

def test_response_envelope_keys_match_the_harness_envelope() -> None:
    harness_keys = _keys_in(_read(HARNESS_SERVER_CPP), HARNESS_SERIALIZE_SIGNATURE)
    plugin_keys = _keys_in(_read(PLUGIN_SERVER_CPP), PLUGIN_SERIALIZE_SIGNATURE)
    assert harness_keys, "the harness envelope was not parsed"
    assert plugin_keys == harness_keys
    assert plugin_keys == set(contract.RESPONSE_FIELDS)


def test_session_identity_fields_match_the_harness() -> None:
    harness_fields = _keys_in(_read(HARNESS_SERVER_CPP), HARNESS_IDENTITY_SIGNATURE)
    plugin_fields = _keys_in(_read(PLUGIN_SERVER_CPP), PLUGIN_IDENTITY_SIGNATURE)
    assert harness_fields, "the harness session identity was not parsed"
    assert plugin_fields == harness_fields
    assert plugin_fields == set(contract.SESSION_IDENTITY_FIELDS)


def test_error_code_vocabulary_is_the_existing_one() -> None:
    server_code = _read(PLUGIN_SERVER_CPP)
    codes = set(re.findall(r'"(ERR_[A-Z_]+)"', server_code))
    assert codes <= {
        "ERR_UNSUPPORTED_SCHEMA_VERSION",
        "ERR_UNKNOWN_OPERATION",
        "ERR_MISSING_ARGUMENT",
        "ERR_OPERATION_FAILED",
        "ERR_OPERATION_TIMED_OUT",
        "ERR_OPERATION_CANCELLED",
        "ERR_EXTRACTION_PAYLOAD_TOO_LARGE",
    }
    # No new error vocabulary is invented by the plugin.
    assert not any(code.startswith("ERR_READ_ONLY") for code in codes)


def test_the_extraction_payload_bound_is_preserved() -> None:
    server_code = _strip_comments(_read(PLUGIN_SERVER_CPP))
    assert "ERR_EXTRACTION_PAYLOAD_TOO_LARGE" in server_code
    assert "ExceedsTransportBound" in server_code


def test_the_response_is_wrapped_the_way_the_extraction_schema_expects() -> None:
    server_code = _strip_comments(_read(PLUGIN_SERVER_CPP))
    assert 'SetObjectField(TEXT("unreal_state_extraction"), ValueTree)' in server_code


# ---------------------------------------------------------------------------
# Startup gating
# ---------------------------------------------------------------------------

def test_module_startup_is_gated_by_the_declared_policy() -> None:
    module_code = _strip_comments(_read(PLUGIN_MODULE_CPP))
    decision_index = module_code.index("Startup::Evaluate(")
    server_index = module_code.index("new FAtlasReadOnlyExtractionServer(")
    assert decision_index < server_index, "the server is constructed before the opt-in decision"
    assert "if (!Decision.bStartTransport)" in module_code
    # The early return must sit between the decision and the construction.
    assert decision_index < module_code.index("if (!Decision.bStartTransport)") < server_index


def test_module_startup_provisions_nothing() -> None:
    module_code = _strip_comments(_read(PLUGIN_MODULE_CPP))
    for provisioning in ("AddTicker", "SpawnActor", "CreatePackage", "SavePackage", "LoadObject", "MarkPackageDirty"):
        assert provisioning not in module_code, f"module startup provisions content via {provisioning}"


def test_no_plugin_source_starts_the_transport_outside_the_gate() -> None:
    """Exactly one construction site exists, and it is the gated one."""
    construction_sites = 0
    for path, code in _each_source():
        construction_sites += code.count("new FAtlasReadOnlyExtractionServer(")
    assert construction_sites == 1


def test_the_startup_policy_is_a_pure_function_of_the_command_line_and_config() -> None:
    contract_code = _strip_comments(_read(PLUGIN_CONTRACT_CPP))
    body = _function_body(contract_code, "FDecision Evaluate(")
    assert "IsOptInSwitchPresent" in body
    assert "bConfigEnabled" in body
    # No engine state, no file system, no pipe creation in the policy.
    for forbidden in ("GEditor", "GEngine", "CreateNamedPipe", "IFileManager", "FPlatformFileManager"):
        assert forbidden not in body


# ---------------------------------------------------------------------------
# Authority model
# ---------------------------------------------------------------------------

def test_the_plugin_declares_no_verification_authority() -> None:
    for path, code in _each_production_source():
        lowered = code.lower()
        for term in ("satisfied", "not_satisfied", "expectation", "authoritative", "registry"):
            assert term not in lowered, f"{path.name} refers to {term!r}: the plugin decides nothing"


def test_the_plugin_does_not_reach_the_u1_registry() -> None:
    for path in contract.all_sources():
        code = _read(path).lower()
        assert "m12" not in code, f"{path.name} reaches the M12 registry"
        assert "planning" not in code, f"{path.name} refers to Atlas planning code"


def test_the_python_contract_imports_only_the_transport_contract() -> None:
    """The Python half of the contract may not import the registry or its authority."""
    module_source = _read(contract.REPO_ROOT / "planning" / "unreal_read_only_extraction.py")
    tree = ast.parse(module_source)
    imported: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert sorted(set(imported)) == [
        "__future__",
        "pathlib",
        "planning.unreal_transport_contract",
        "planning.unreal_transport_named_pipe",
        "typing",
    ]


def test_the_plugin_never_emits_a_decision_word_in_its_response_path() -> None:
    server_code = _strip_comments(_read(PLUGIN_SERVER_CPP)).lower()
    for term in ("satisfied", "expectation", "authoritative"):
        assert term not in server_code


# ---------------------------------------------------------------------------
# CI collection safety: the live gate must import on a platform without kernel32
# ---------------------------------------------------------------------------

def test_live_gate_binds_kernel32_only_under_the_platform_guard() -> None:
    """The module-level Windows binding lives inside the IS_WINDOWS branch, nowhere else."""
    tree = ast.parse(_read(LIVE_GATE_PATH))

    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If) and "IS_WINDOWS" in ast.dump(node.test)
    ]
    assert len(guards) == 1, "the live gate must carry exactly one module-level IS_WINDOWS guard"
    guard = guards[0]

    windows_branch = ast.unparse(guard.body)
    other_branch = ast.unparse(guard.orelse)
    assert "ctypes.WinDLL" in windows_branch
    assert "import ctypes.wintypes" in windows_branch
    assert "kernel32 = None" in other_branch
    assert "wintypes = None" in other_branch

    for node in tree.body:
        if node is guard or isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom),
        ):
            continue
        dumped = ast.dump(node)
        assert "WinDLL" not in dumped and "wintypes" not in dumped, (
            "module-level code outside the platform guard touches the Windows binding"
        )


def test_live_gate_pipe_helpers_require_the_windows_binding() -> None:
    """The way into kernel32 is guarded twice: by the module gate and by the helpers."""
    tree = ast.parse(_read(LIVE_GATE_PATH))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "_require_windows_kernel32" in functions
    assert "IS_WINDOWS" in ast.dump(functions["_require_windows_kernel32"])
    assert "_require_windows_kernel32" in ast.dump(functions["pipe_connect"])


def test_live_gate_module_imports_without_kernel32() -> None:
    """Import the live gate the way CI collects it: where ``ctypes.WinDLL`` does not exist.

    The probe fakes ``sys.platform`` and replaces ``ctypes.WinDLL`` with a trap, so a module
    that still reached for the binding at import time fails here exactly as it fails on the
    Linux runner.
    """
    probe = textwrap.dedent(
        f"""
        import ctypes, importlib.util, sys

        sys.path.insert(0, {str(REPO_ROOT)!r})
        sys.platform = "linux"

        def _trap(*args, **kwargs):
            raise AssertionError("ctypes.WinDLL was reached at import time off Windows")

        ctypes.WinDLL = _trap

        spec = importlib.util.spec_from_file_location("live_gate_probe", {str(LIVE_GATE_PATH)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.IS_WINDOWS is False, "IS_WINDOWS must follow sys.platform"
        assert module.kernel32 is None, "kernel32 must not be bound off Windows"
        assert module.wintypes is None, "ctypes.wintypes must not be imported off Windows"

        marks = module.pytestmark
        marks = list(marks) if isinstance(marks, (list, tuple)) else [marks]
        skip_marks = [mark for mark in marks if getattr(mark, "name", None) == "skipif"]
        assert skip_marks, "the live gate must be gated by a skipif mark"
        assert skip_marks[0].args[0] is True, "the skipif condition must hold off Windows"

        try:
            module._require_windows_kernel32()
        except AssertionError as exc:
            assert "Windows named pipe" in str(exc), str(exc)
        else:
            raise AssertionError("the pipe helpers must refuse to run off Windows")

        print("PROBE_OK")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0 and "PROBE_OK" in completed.stdout, (
        "the live gate does not import on a platform without kernel32:\n"
        + completed.stdout
        + completed.stderr
    )


# ---------------------------------------------------------------------------
# The change stays where it belongs
# ---------------------------------------------------------------------------

def _branch_changed_files() -> Sequence[str]:
    """Every path the branch touches: committed against the merge base, plus the worktree.

    The branch-wide reference, used by the protected-artifact check: it is deliberately wider
    than ``_changed_files`` so that a commit anywhere on this branch that edits a protected
    artifact is caught, whether or not it belongs to the plugin change.
    """
    touched: List[str] = []

    merge_base = subprocess.run(
        ["git", "merge-base", "origin/main", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if merge_base.returncode == 0:
        diff = subprocess.run(
            ["git", "diff", "--name-only", merge_base.stdout.strip(), "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        touched.extend(line.strip() for line in diff.stdout.splitlines() if line.strip())

    touched.extend(_worktree_changed_files())
    return sorted(set(touched))


def _worktree_changed_files(repo: Path = REPO_ROOT) -> Sequence[str]:
    """Uncommitted and untracked paths in this worktree (staged, unstaged and untracked)."""
    status = _git_in(repo, "status", "--porcelain", "--untracked-files=all")
    touched: List[str] = []
    for line in status.stdout.splitlines():
        entry = line[3:].strip()
        if not entry:
            continue
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1].strip()
        if entry.startswith('"') and entry.endswith('"'):
            entry = entry[1:-1]
        touched.append(entry)
    return touched


#: The base and head of the current change may be supplied explicitly; a local run, or a test of
#: this machinery, can then name the change it means instead of relying on inference.
CHANGE_BASE_ENV = "ATLAS_CHANGE_BASE"
CHANGE_HEAD_ENV = "ATLAS_CHANGE_HEAD"

#: The all-zero object name Git uses for "no such object" (a push event's `before` on a new branch).
ZERO_OBJECT_NAME = "0" * 40


def _git_in(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=check,
    )


def _revision_resolves(repo: Path, revision: str) -> bool:
    return _git_in(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}", check=False).returncode == 0


def _github_event_change_range() -> Optional[Tuple[str, str]]:
    """The (base, head) identities GitHub Actions reports for this run, when it reports them.

    For a pull request the payload carries the real base and head commits, so the synthetic
    merge commit GitHub checks out is never used as a change boundary. For a push it carries
    ``before`` and ``after``: the pushed commits themselves, which is what the repository's
    landing strategy (individual commits preserved) leaves on the branch.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not Path(event_path).is_file():
        return None
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    pull_request = payload.get("pull_request")
    if isinstance(pull_request, dict):
        base = str((pull_request.get("base") or {}).get("sha") or "").strip()
        head = str((pull_request.get("head") or {}).get("sha") or "").strip()
        if base and head:
            return base, head
    before = str(payload.get("before") or "").strip()
    after = str(payload.get("after") or "").strip()
    if after and before and before != ZERO_OBJECT_NAME:
        return before, after
    return None


def _change_identities(repo: Path = REPO_ROOT) -> Tuple[Optional[str], Optional[str]]:
    """The base and head of the current change, from the most authoritative source available.

    Order: explicit ``ATLAS_CHANGE_BASE``/``ATLAS_CHANGE_HEAD``; the GitHub Actions event payload;
    then, locally, the merge base with the default branch. ``None`` for the base means no base
    could be established and the caller must fail closed rather than treat the whole history or a
    bare tree listing as "this change".
    """
    base = os.environ.get(CHANGE_BASE_ENV, "").strip()
    head = os.environ.get(CHANGE_HEAD_ENV, "").strip()
    if base or head:
        if not (base and head):
            raise AssertionError(
                "ATLAS_CHANGE_BASE and ATLAS_CHANGE_HEAD must be set together: a half-set "
                "override would silently fall back to inference, so it is refused"
            )
        return base, head
    from_event = _github_event_change_range()
    if from_event is not None:
        return from_event
    for default_branch in ("origin/main", "main"):
        if not _revision_resolves(repo, default_branch):
            continue
        # A locally checked-out synthetic merge (GitHub's `refs/pull/N/merge` shape) is not the
        # change's head: its second parent is. Recognise that shape structurally — a merge whose
        # first parent is the default branch — instead of guessing parent order blindly.
        head = "HEAD"
        if _parent_count(repo, "HEAD") >= 2:
            first_parent = _git_in(repo, "rev-parse", "HEAD^1", check=False).stdout.strip()
            ancestor = _git_in(repo, "merge-base", "--is-ancestor", first_parent, default_branch, check=False)
            if first_parent and ancestor.returncode == 0:
                head = "HEAD^2"
        merge_base = _git_in(repo, "merge-base", default_branch, head, check=False)
        if merge_base.returncode == 0 and merge_base.stdout.strip():
            return merge_base.stdout.strip(), head
    return None, "HEAD"


def _parent_count(repo: Path, revision: str) -> int:
    """How many parent records this clone holds for a commit (0 for a root or a shallow graft)."""
    listed = _git_in(repo, "rev-list", "--parents", "-n", "1", revision, check=False)
    if listed.returncode != 0:
        return 0
    return max(len(listed.stdout.split()) - 1, 0)


def _is_shallow(repo: Path) -> bool:
    """Whether this clone has history boundaries (a shallow checkout) that break range walks."""
    completed = _git_in(repo, "rev-parse", "--is-shallow-repository", check=False)
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip() == "true"
    return (repo / ".git" / "shallow").is_file()


def _plugin_change_commits(repo: Path = REPO_ROOT) -> Sequence[str]:
    """The commits of THIS change that touch an allowlisted path.

    The walk is bounded by the change's own base..head identities, so history outside the change
    cannot contribute paths — including history on the target branch that once touched the same
    plugin paths. A base that cannot be established, or a shallow checkout whose boundaries make
    the walk incomplete (which is how a grafted merge commit once got listed as an entire tree),
    is a hard failure, never a vacuous pass.

    Selection is by design "commits that touch the allowlist": a change with no plugin work at all
    (for example a merge that only adds an unrelated file) is not this test's subject and yields
    an empty selection — only changes that include plugin work are policed here.
    """
    base, head = _change_identities(repo)
    if head is None or not _revision_resolves(repo, head):
        raise AssertionError(
            f"cannot identify this change's head commit ({head!r}) in this checkout: "
            "fetch enough history for the change range before checking its scope"
        )
    if base is None:
        raise AssertionError(
            "cannot establish the base of this change: no ATLAS_CHANGE_BASE/ATLAS_CHANGE_HEAD, "
            "no GitHub Actions event payload, and no default branch to compare against"
        )
    if not _revision_resolves(repo, base):
        raise AssertionError(
            f"this change's base commit ({base}) is not available in this checkout: "
            "the checkout does not carry the change range (shallow clone?); fetch full history"
        )
    if _is_shallow(repo):
        raise AssertionError(
            f"this checkout is shallow, so the change range {base}..{head} cannot be walked "
            "completely (a grafted commit would be listed as an entire tree): fetch full history "
            "before checking scope (actions/checkout with fetch-depth: 0)"
        )
    # --full-history: default history simplification can hide a merge-brought commit whose
    # allowlisted edit was resolved away in the merge result, which would hide its other paths.
    listed = _git_in(
        repo, "log", "--full-history", "--format=%H", f"{base}..{head}", "--", *CHANGE_ALLOWED_PREFIXES
    )
    return [line.strip() for line in listed.stdout.splitlines() if line.strip()]


def _changed_files(repo: Path = REPO_ROOT) -> Sequence[str]:
    """Every path this change touches: its range-bounded commits' files, plus the worktree.

    "This change" is the plugin work, identified by the commits inside the change range that
    touch an allowlisted path (the plugin, its tests or its contract): every file those commits
    touch must itself be inside the allowlist. Two earlier references were wrong: the merge base
    against the target branch stopped isolating this change once unrelated work landed beside it
    on the same branch, and an unbounded `git log -- <paths>` reached back through the whole of
    history and, in a shallow checkout, selected a grafted merge commit whose listing is an
    entire tree.
    """
    touched: List[str] = []

    for sha in _plugin_change_commits(repo):
        touched.extend(_commit_own_files(repo, sha))

    touched.extend(_worktree_changed_files(repo))
    return sorted(set(touched))


def _commit_own_files(repo: Path, sha: str) -> Sequence[str]:
    """The files a commit itself contributes, not what it brings from elsewhere.

    A merge's first-parent diff is everything it brings from the other side: on a landing merge
    that is the whole pull request, and on an "update branch" merge it is the target branch's own
    work. Those paths belong to the commits that made them — they are already examined there, and
    they may legitimately include files outside the allowlist — so they are left to those commits.
    What remains is the merge's own contribution: the paths whose content differs from EVERY
    parent (the combined-diff notion) — an "evil merge" that writes a file no side commit wrote,
    or a conflict resolution whose result comes from no single parent — which must still satisfy
    the scope.

    ``--no-renames``: a rename must show BOTH sides, or a protected file renamed into the plugin
    directory would hide its source path. ``-m --first-parent``: a merge shows its first-parent
    diff instead of printing nothing.
    """
    show = _git_in(
        repo, "show", "--name-only", "--format=", "--no-renames", "-m", "--first-parent", sha,
    )
    files = {line.strip() for line in show.stdout.splitlines() if line.strip()}
    parents = _parent_count(repo, sha)
    if parents >= 2:
        # A merge's own paths are the ones whose content differs from EVERY parent — the
        # combined-diff notion. What a clean landing merge or an "update branch" merge brings
        # equals one parent, so it is excluded and stays attributed to the commits that made it;
        # a conflict resolution (or an "evil merge" edit) is content from no single parent, so it
        # is kept and must satisfy the scope. A name-only subtraction would erase the resolution.
        own: Optional[Set[str]] = None
        for ordinal in range(1, parents + 1):
            versus_parent = _git_in(
                repo, "diff", "--name-only", "--no-renames", sha, f"{sha}^{ordinal}", check=False,
            )
            names = {line.strip() for line in versus_parent.stdout.splitlines() if line.strip()}
            own = names if own is None else (own & names)
        files = files & (own or set())
    return sorted(files)


def test_the_change_is_limited_to_the_plugin_its_tests_and_its_contract() -> None:
    for path in _changed_files():
        assert path.startswith(CHANGE_ALLOWED_PREFIXES), f"unexpected file in this change: {path}"


def test_the_change_touches_no_normative_or_existing_artifact() -> None:
    protected = (
        "ATLAS_M12_6_R2B_NORMATIVE_DESIGN_REV10.md",
        "ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV25.md",
        "planning/m12/expectation.py",
        "unreal/AtlasUnrealHarness/",
        "tests/test_unreal_state_extraction_readonly_source.py",
        "planning/unreal_state_extraction/",
    )
    for path in _branch_changed_files():
        assert not path.startswith(protected), f"protected artifact modified: {path}"


# ---------------------------------------------------------------------------
# Module provenance: current source -> recorded build -> artifact the gate inspects
# ---------------------------------------------------------------------------

MODULE_NAME = "UnrealEditor-AtlasReadOnlyExtraction.dll"


def _fake_build(
    directory: Path,
    source_fingerprint: str = "a" * 64,
    exit_code: int = 0,
    module_bytes: bytes = b"built module",
) -> Tuple[Path, Path]:
    """A disposable module and its provenance record; no toolchain involved."""
    module = directory / "Binaries" / "Win64" / MODULE_NAME
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_bytes(module_bytes)
    record = _write_module_provenance(module, source_fingerprint, exit_code)
    return module, record


def test_the_provenance_record_binds_the_artifact_the_build_produced(tmp_path: Path) -> None:
    module, record = _fake_build(tmp_path, "b" * 64)
    assert record == _module_provenance_path(module)
    payload = json.loads(record.read_text(encoding="utf-8"))
    assert payload["schema"] == MODULE_PROVENANCE_SCHEMA
    assert payload["source_fingerprint"] == "b" * 64
    assert payload["module_sha256"] == hashlib.sha256(b"built module").hexdigest()
    assert payload["module_bytes"] == len(b"built module")
    assert payload["build_exit_code"] == 0


def test_reuse_is_refused_unless_the_record_matches_the_current_source(tmp_path: Path) -> None:
    fingerprint = "c" * 64

    assert _reuse_decision(tmp_path / "absent" / MODULE_NAME, fingerprint) == (
        False,
        "no existing module",
    )

    module, record = _fake_build(tmp_path / "no-record", fingerprint)
    record.unlink()
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "record" in reason, reason

    module, record = _fake_build(tmp_path / "unreadable", fingerprint)
    record.write_text("{ not json", encoding="utf-8")
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "record" in reason, reason

    module, record = _fake_build(tmp_path / "schema", fingerprint)
    record.write_text(json.dumps({"schema": 99, "build_exit_code": 0, "source_fingerprint": fingerprint}), encoding="utf-8")
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "schema" in reason, reason

    module, record = _fake_build(tmp_path / "failed", fingerprint, exit_code=6)
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "succeed" in reason, reason

    module, record = _fake_build(tmp_path / "drifted", "d" * 64)
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "fingerprint" in reason, reason

    module, record = _fake_build(tmp_path / "replaced", fingerprint)
    module.write_bytes(b"a different artifact")
    reusable, reason = _reuse_decision(module, fingerprint)
    assert not reusable and "artifact" in reason, reason

    module, record = _fake_build(tmp_path / "valid", fingerprint)
    reusable, reason = _reuse_decision(module, fingerprint)
    assert reusable, reason


def test_the_source_fingerprint_tracks_source_and_ignores_build_outputs(tmp_path: Path) -> None:
    plugin = tmp_path / "AtlasReadOnlyExtraction"
    (plugin / "Source").mkdir(parents=True)
    (plugin / "Source" / "module.cpp").write_text("// one\n", encoding="utf-8")
    (plugin / "AtlasReadOnlyExtraction.uplugin").write_text("{}\n", encoding="utf-8")
    first = _plugin_source_fingerprint(plugin)
    assert _plugin_source_fingerprint(plugin) == first, "the fingerprint must be deterministic"

    (plugin / "Source" / "module.cpp").write_text("// two\n", encoding="utf-8")
    changed = _plugin_source_fingerprint(plugin)
    assert changed != first, "a source edit must change the fingerprint"

    (plugin / "Binaries" / "Win64").mkdir(parents=True)
    (plugin / "Binaries" / "Win64" / MODULE_NAME).write_bytes(b"build output")
    (plugin / "Intermediate").mkdir()
    (plugin / "Intermediate" / "module.obj").write_bytes(b"build output")
    assert _plugin_source_fingerprint(plugin) == changed, "build outputs are not source"


def test_a_build_is_judged_by_its_process_result_not_by_console_text(tmp_path: Path) -> None:
    module = tmp_path / MODULE_NAME
    assert not _build_result_ok(0, module), "a missing module is not a successful build"
    module.write_bytes(b"module")
    assert not _build_result_ok(6, module), "a failed process is not a successful build"
    assert _build_result_ok(0, module)

    # A wrapper can mask its own exit code (a batch file returns the exit code of its last
    # command); the BUILD_EXIT marker it prints is the second, independent failure signal.
    masked = "text before\nBUILD_EXIT=6\ntext after\n"
    assert not _build_result_ok(0, module, masked), (
        "a wrapper that reports a failed build must not be certified by its masked exit code"
    )
    assert _build_result_ok(0, module, "BUILD_EXIT=0\n"), "a clean build stays certified"
    assert _build_failure_reason(0, module, "BUILD_EXIT=6\n") is not None
    assert _build_failure_reason(6, module, "BUILD_EXIT=6\n") is not None
    assert _build_failure_reason(0, module, "no marker at all\n") is None
    assert BUILD_EXIT_MARKER.findall("BUILD_EXIT=13 then BUILD_EXIT=0") == ["13", "0"]


@pytest.mark.skipif(sys.platform != "win32", reason="the build wrapper is a batch file")
def test_the_generated_build_wrapper_propagates_the_real_exit_code(tmp_path: Path) -> None:
    """The wrapper must report the toolchain's exit code, not the exit code of its own echo."""
    engine = tmp_path / "fake-engine"
    batch_files = engine / "Engine" / "Build" / "BatchFiles"
    batch_files.mkdir(parents=True)
    (batch_files / "Build.bat").write_text(
        "@echo off\necho the toolchain ran\nexit /b 6\n", encoding="utf-8"
    )
    wrapper = tmp_path / "build_plugin.bat"
    wrapper.write_text(_build_wrapper_text(engine, tmp_path / "AtlasReadOnlyHost.uproject"), encoding="utf-8")

    completed = subprocess.run(
        ["cmd", "/c", str(wrapper)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    assert "BUILD_EXIT=6" in output, output
    assert completed.returncode == 6, (
        f"the wrapper masked the failed build: rc={completed.returncode}, output={output!r}"
    )
    assert _build_failure_reason(completed.returncode, tmp_path / "absent.dll", output) is not None

    # the stub succeeds -> the wrapper reports success
    (batch_files / "Build.bat").write_text("@echo off\nrem ok\nexit /b 0\n", encoding="utf-8")
    completed = subprocess.run(
        ["cmd", "/c", str(wrapper)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    assert "BUILD_EXIT=0" in output, output
    assert completed.returncode == 0, f"rc={completed.returncode}, output={output!r}"


def test_the_success_path_records_provenance_only_after_a_successful_build() -> None:
    source = LIVE_GATE_PATH.read_text(encoding="utf-8", errors="replace")
    body = source[source.index("def build_plugin(") : source.index("def _deploy_plugin_binary(")]
    removed = body.index("for stale in (BUILT_PLUGIN_DLL,")
    launched = body.index('["cmd", "/c", "build_plugin.bat"]')
    judged = body.index("_build_failure_reason(completed.returncode, BUILT_PLUGIN_DLL, build_output)")
    recorded = body.index("_write_module_provenance(BUILT_PLUGIN_DLL")
    assert removed < launched < judged < recorded, (
        "a stale module must be removed before the build, the build judged before anything is "
        "written back, and the provenance record written only for a successful build"
    )
    assert "return completed.returncode, tail" in body[judged:recorded], (
        "a build that fails the judgment must return before any provenance record is written"
    )
    assert "reused existing build" in body, "the reuse path must stay distinguishable"


@pytest.mark.skipif(sys.platform != "win32", reason="a junction is a Windows reparse point")
def test_a_stale_plugin_link_is_repointed_and_its_previous_target_is_left_alone(tmp_path: Path) -> None:
    repository_plugin = tmp_path / "repository" / "AtlasReadOnlyExtraction"
    repository_plugin.mkdir(parents=True)
    (repository_plugin / "AtlasReadOnlyExtraction.uplugin").write_text("{}\n", encoding="utf-8")

    decoy = tmp_path / "decoy"
    decoy.mkdir()
    sentinel = decoy / "SENTINEL.txt"
    sentinel.write_text("the previous target must not be touched\n", encoding="utf-8")

    link = tmp_path / "host" / "Plugins" / "AtlasReadOnlyExtraction"
    link.parent.mkdir(parents=True)
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(decoy)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    assert Path(os.path.realpath(link)) == Path(os.path.realpath(decoy))

    _ensure_plugin_junction(link, repository_plugin)
    assert Path(os.path.realpath(link)) == Path(os.path.realpath(repository_plugin))
    assert sentinel.read_text(encoding="utf-8") == "the previous target must not be touched\n", (
        "re-pointing the link must never modify the previous target"
    )

    _ensure_plugin_junction(link, repository_plugin)
    assert Path(os.path.realpath(link)) == Path(os.path.realpath(repository_plugin)), (
        "re-pointing an already correct link must be a no-op"
    )

    os.rmdir(str(link))
    link.mkdir(parents=True)
    (link / "stale-copy.txt").write_text("a stale plain copy\n", encoding="utf-8")
    _ensure_plugin_junction(link, repository_plugin)
    assert Path(os.path.realpath(link)) == Path(os.path.realpath(repository_plugin))
    assert not (link / "stale-copy.txt").exists()


# ---------------------------------------------------------------------------
# The change-scope detector: range-bounded, fail-closed, deterministic
# ---------------------------------------------------------------------------

ALLOWED_SAMPLE = "unreal/plugins/AtlasReadOnlyExtraction/Source/probe.cpp"
UNRELATED_SAMPLE = "docs/UNRELATED_SCOPE_SAMPLE.md"
WORKFLOW_SAMPLE = ".github/workflows/blender-correction-bridge-live.yml"


def _git_cli(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=str(repo), capture_output=True, text=True, check=True)
    return completed.stdout


def _scope_repo(tmp_path: Path, name: str = "scope-repo") -> Path:
    """A disposable repository with a stable identity, so scope behaviour is deterministic."""
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    # git 2.24 (this workstation) predates `git init -b`, so select the branch explicitly.
    _git_cli(repo, "init", "-q", ".")
    _git_cli(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git_cli(repo, "config", "user.email", "scope@example.invalid")
    _git_cli(repo, "config", "user.name", "Scope Probe")
    return repo


def _scope_commit(repo: Path, message: str, files: Dict[str, str]) -> str:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git_cli(repo, "add", "-A")
    _git_cli(repo, "commit", "-q", "-m", message)
    return _git_cli(repo, "rev-parse", "HEAD").strip()


def _pin_change(monkeypatch, base: str, head: str = "HEAD") -> None:
    monkeypatch.setenv(CHANGE_BASE_ENV, base)
    monkeypatch.setenv(CHANGE_HEAD_ENV, head)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)


def _event_payload(monkeypatch, tmp_path: Path, payload: Dict[str, object]) -> Path:
    path = tmp_path / "event.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    monkeypatch.delenv(CHANGE_BASE_ENV, raising=False)
    monkeypatch.delenv(CHANGE_HEAD_ENV, raising=False)
    return path


def test_a_historical_commit_outside_the_change_range_cannot_contaminate_it(tmp_path, monkeypatch):
    """The CI failure this check exists for: history before the change must never leak in."""
    repo = _scope_repo(tmp_path)
    historical = _scope_commit(
        repo,
        "historical: plugin path and a workflow file in one commit",
        {ALLOWED_SAMPLE: "historical\n", WORKFLOW_SAMPLE: "name: historical\n"},
    )
    _scope_commit(repo, "later target work", {"docs/other.md": "unrelated\n"})
    _scope_commit(repo, "the change", {ALLOWED_SAMPLE: "change\n"})
    _pin_change(monkeypatch, historical)

    touched = _changed_files(repo)
    assert WORKFLOW_SAMPLE not in touched, (
        "a commit that predates this change's base contributed a path: " + repr(touched)
    )
    assert set(touched) == {ALLOWED_SAMPLE}


def test_a_commit_inside_the_change_range_touching_outside_files_is_flagged(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    base = _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n"})
    _scope_commit(repo, "the change mixes scopes", {ALLOWED_SAMPLE: "change\n", UNRELATED_SAMPLE: "out\n"})
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert UNRELATED_SAMPLE in touched, "a mixed commit inside the range must be visible"
    assert not all(path.startswith(CHANGE_ALLOWED_PREFIXES) for path in touched), (
        "the scope assertion must fail for a commit inside the range that touches unrelated files"
    )


def test_a_change_confined_to_the_allowlist_passes(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    base = _scope_commit(repo, "base", {UNRELATED_SAMPLE: "base\n"})
    _scope_commit(repo, "the change", {ALLOWED_SAMPLE: "change\n"})
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert touched and all(path.startswith(CHANGE_ALLOWED_PREFIXES) for path in touched), touched


def test_a_rename_inside_the_range_reports_both_paths(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    old = "unreal/plugins/AtlasReadOnlyExtraction/Source/old_name.cpp"
    new = "unreal/plugins/AtlasReadOnlyExtraction/Source/new_name.cpp"
    base = _scope_commit(repo, "base", {old: "content\n"})
    _git_cli(repo, "mv", old, new)
    _git_cli(repo, "commit", "-q", "-m", "rename a plugin file")
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert old in touched and new in touched, touched


def test_a_merge_inside_the_range_is_read_as_its_first_parent_diff(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    second_allowed = "unreal/plugins/AtlasReadOnlyExtraction/Source/probe_two.cpp"
    third_allowed = "unreal/plugins/AtlasReadOnlyExtraction/Source/probe_three.cpp"
    base = _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n"})
    _scope_commit(repo, "the change", {second_allowed: "change\n"})
    _git_cli(repo, "checkout", "-q", "-b", "side", base)
    _scope_commit(repo, "side work", {third_allowed: "side\n", UNRELATED_SAMPLE: "side\n"})
    _git_cli(repo, "checkout", "-q", "main")
    _git_cli(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert second_allowed in touched and third_allowed in touched, touched
    assert UNRELATED_SAMPLE in touched, (
        "a merge that brings an unrelated file onto the branch must be visible: " + repr(touched)
    )


def test_worktree_changes_are_part_of_the_change(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n", UNRELATED_SAMPLE: "base\n"})
    (repo / ALLOWED_SAMPLE).write_text("unstaged\n", encoding="utf-8")
    (repo / UNRELATED_SAMPLE).write_text("staged\n", encoding="utf-8")
    _git_cli(repo, "add", UNRELATED_SAMPLE)
    (repo / "docs" / "untracked.md").write_text("untracked\n", encoding="utf-8")
    _pin_change(monkeypatch, "HEAD", "HEAD")

    touched = _changed_files(repo)
    assert set(touched) >= {ALLOWED_SAMPLE, UNRELATED_SAMPLE, "docs/untracked.md"}, touched


def test_a_push_event_payload_defines_a_working_range(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    historical = _scope_commit(
        repo, "historical", {ALLOWED_SAMPLE: "historical\n", WORKFLOW_SAMPLE: "name: historical\n"}
    )
    after = _scope_commit(repo, "pushed plugin-only work", {ALLOWED_SAMPLE: "pushed\n"})
    _event_payload(monkeypatch, tmp_path, {"before": historical, "after": after})

    assert _change_identities(repo) == (historical, after)
    touched = _changed_files(repo)
    assert WORKFLOW_SAMPLE not in touched, touched
    assert set(touched) == {ALLOWED_SAMPLE}


def test_a_new_branch_push_without_a_usable_before_fails_closed(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    _scope_commit(repo, "first", {ALLOWED_SAMPLE: "first\n"})
    _git_cli(repo, "branch", "-m", "feature-without-a-default-branch")
    _event_payload(monkeypatch, tmp_path, {"before": ZERO_OBJECT_NAME, "after": "f" * 40})

    base, head = _change_identities(repo)
    assert base is None and head == "HEAD"
    with pytest.raises(AssertionError, match="cannot establish the base"):
        _plugin_change_commits(repo)


def test_a_pull_request_payload_prefers_the_real_base_and_head(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    base = _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n"})
    head = _scope_commit(repo, "the change", {ALLOWED_SAMPLE: "change\n"})
    _event_payload(
        monkeypatch,
        tmp_path,
        {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}},
    )
    assert _change_identities(repo) == (base, head)


def test_a_shallow_checkout_fails_closed_instead_of_listing_a_tree(tmp_path, monkeypatch):
    """The CI signature: a grafted commit must be refused, never listed as an entire tree."""
    repo = _scope_repo(tmp_path)
    head = _scope_commit(repo, "only commit", {ALLOWED_SAMPLE: "content\n", WORKFLOW_SAMPLE: "name: x\n"})
    shallow = tmp_path / "shallow-clone"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo.as_posix()}", str(shallow)],
        capture_output=True, text=True, check=True,
    )
    assert _is_shallow(shallow), "the clone must be shallow for this check"

    # a base the clone does not hold is refused first ...
    _pin_change(monkeypatch, "0123456789abcdef0123456789abcdef01234567", "HEAD")
    with pytest.raises(AssertionError, match="not available in this checkout"):
        _plugin_change_commits(shallow)

    # ... and a walk that a shallow checkout cannot complete is refused as well
    _pin_change(monkeypatch, head, "HEAD")
    with pytest.raises(AssertionError, match="shallow"):
        _plugin_change_commits(shallow)


def test_a_locally_checked_out_synthetic_merge_uses_its_second_parent(tmp_path, monkeypatch):
    """GitHub's `refs/pull/N/merge` shape: the merge is not the change's head, its second parent is."""
    repo = _scope_repo(tmp_path)
    base = _scope_commit(repo, "base", {UNRELATED_SAMPLE: "base\n"})
    _git_cli(repo, "checkout", "-q", "-b", "feature", base)
    head = _scope_commit(repo, "the change", {ALLOWED_SAMPLE: "change\n"})
    # the synthetic merge GitHub builds: first parent = the target tip, second parent = the head,
    # created on its own ref so `main` itself does not move
    _git_cli(repo, "checkout", "-q", "-b", "synthetic-merge", base)
    _git_cli(repo, "merge", "-q", "--no-ff", "-m", "synthetic merge", "feature")
    monkeypatch.delenv(CHANGE_BASE_ENV, raising=False)
    monkeypatch.delenv(CHANGE_HEAD_ENV, raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    _git_cli(repo, "remote", "add", "origin", f"file://{repo.as_posix()}")
    _git_cli(repo, "fetch", "-q", "origin", "main:refs/remotes/origin/main")

    inferred_base, inferred_head = _change_identities(repo)
    assert inferred_base == base, (inferred_base, base)
    assert inferred_head == "HEAD^2", inferred_head
    touched = _changed_files(repo)
    assert set(touched) == {ALLOWED_SAMPLE}, touched


def test_a_merge_resolved_away_plugin_edit_still_shows_its_other_paths(tmp_path, monkeypatch):
    """History simplification must not hide a commit inside the range (M2 in review round 1)."""
    repo = _scope_repo(tmp_path)
    base = _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n", "docs/far_away.md": "base\n"})
    _scope_commit(repo, "the change", {ALLOWED_SAMPLE: "change\n"})
    _git_cli(repo, "checkout", "-q", "-b", "side", base)
    _scope_commit(repo, "side work", {ALLOWED_SAMPLE: "side\n", UNRELATED_SAMPLE: "side\n"})
    _git_cli(repo, "checkout", "-q", "main")
    # -X ours: the plugin file is resolved to this side of the merge, so the side commit's
    # plugin edit is not in the merge result — default simplification would drop it entirely
    _git_cli(repo, "merge", "-q", "--no-ff", "-X", "ours", "-m", "merge side", "side")
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert UNRELATED_SAMPLE in touched, (
        "a commit inside the range was hidden by history simplification; its other paths are "
        "still part of this change: " + repr(touched)
    )
    assert not all(path.startswith(CHANGE_ALLOWED_PREFIXES) for path in touched)


def test_a_half_set_override_is_refused(tmp_path, monkeypatch):
    repo = _scope_repo(tmp_path)
    _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n"})
    monkeypatch.setenv(CHANGE_BASE_ENV, "HEAD")
    monkeypatch.delenv(CHANGE_HEAD_ENV, raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    with pytest.raises(AssertionError, match="must be set together"):
        _change_identities(repo)
    monkeypatch.delenv(CHANGE_BASE_ENV, raising=False)
    monkeypatch.setenv(CHANGE_HEAD_ENV, "HEAD")
    with pytest.raises(AssertionError, match="must be set together"):
        _change_identities(repo)


def test_a_landing_merge_commit_does_not_re_flag_what_it_brings(tmp_path, monkeypatch):
    """F1: a merge-commit landing must not go red for files that have their own commits."""
    repo = _scope_repo(tmp_path)
    tip = _scope_commit(repo, "target work", {"docs/other.md": "before\n"})
    _git_cli(repo, "checkout", "-q", "-b", "feature", tip)
    _scope_commit(repo, "the plugin change", {ALLOWED_SAMPLE: "change\n"})
    _scope_commit(repo, "a separate, legitimate commit", {WORKFLOW_SAMPLE: "name: ci\n"})
    _git_cli(repo, "checkout", "-q", "main")
    _git_cli(repo, "merge", "-q", "--no-ff", "-m", "Merge pull request", "feature")
    _pin_change(monkeypatch, tip)

    touched = _changed_files(repo)
    assert ALLOWED_SAMPLE in touched, touched
    assert WORKFLOW_SAMPLE not in touched, (
        "the landing merge re-flagged a file that its own commit made: " + repr(touched)
    )
    assert all(path.startswith(CHANGE_ALLOWED_PREFIXES) for path in touched), touched


def test_an_evil_merge_that_writes_its_own_file_is_still_flagged(tmp_path, monkeypatch):
    """The merge-ownership rule must not become a hole: a merge's own edits still count."""
    repo = _scope_repo(tmp_path)
    tip = _scope_commit(repo, "target work", {"docs/other.md": "before\n"})
    _git_cli(repo, "checkout", "-q", "-b", "feature", tip)
    _scope_commit(repo, "the plugin change", {ALLOWED_SAMPLE: "change\n"})
    _git_cli(repo, "checkout", "-q", "main")
    _git_cli(repo, "merge", "-q", "--no-commit", "--no-ff", "feature")
    (repo / UNRELATED_SAMPLE).parent.mkdir(parents=True, exist_ok=True)
    (repo / UNRELATED_SAMPLE).write_text("written by the merge itself\n", encoding="utf-8")
    _git_cli(repo, "add", UNRELATED_SAMPLE)
    _git_cli(repo, "commit", "-q", "-m", "Merge pull request (with an extra edit)")
    _pin_change(monkeypatch, tip)

    touched = _changed_files(repo)
    assert UNRELATED_SAMPLE in touched, (
        "a file written by the merge itself is part of this change: " + repr(touched)
    )


def test_an_update_branch_merge_does_not_import_the_targets_files(tmp_path, monkeypatch):
    """F2: merging the target into the branch brings the target's work, which is not this change."""
    repo = _scope_repo(tmp_path)
    fork_point = _scope_commit(repo, "shared base", {ALLOWED_SAMPLE: "base\n"})
    _git_cli(repo, "checkout", "-q", "-b", "feature", fork_point)
    _scope_commit(repo, "the plugin change", {ALLOWED_SAMPLE: "change\n"})
    _git_cli(repo, "checkout", "-q", "main")
    target_tip = _scope_commit(
        repo, "target work", {ALLOWED_SAMPLE: "base\n", WORKFLOW_SAMPLE: "name: ci\n"}
    )
    _git_cli(repo, "checkout", "-q", "feature")
    _git_cli(repo, "merge", "-q", "--no-ff", "-X", "ours", "-m", "Merge main into feature", "main")
    # a pull_request event: base = the target tip at event time, head = the branch tip
    monkeypatch.setenv(CHANGE_BASE_ENV, target_tip)
    monkeypatch.setenv(CHANGE_HEAD_ENV, "HEAD")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    touched = _changed_files(repo)
    assert WORKFLOW_SAMPLE not in touched, (
        "the target's own file was imported as if this change had touched it: " + repr(touched)
    )
    assert all(path.startswith(CHANGE_ALLOWED_PREFIXES) for path in touched), touched


def test_a_merge_resolution_is_kept_even_when_the_side_touched_that_path(tmp_path, monkeypatch):
    """Round-3 M1: a merge's own rewrite must survive even if a side commit touched the path."""
    repo = _scope_repo(tmp_path)
    side_path = "docs/p.md"
    base = _scope_commit(repo, "base", {ALLOWED_SAMPLE: "base\n"})
    _git_cli(repo, "checkout", "-q", "-b", "feature", base)
    _scope_commit(repo, "the plugin change", {ALLOWED_SAMPLE: "side\n"})
    _scope_commit(repo, "a docs commit", {side_path: "side\n"})
    _git_cli(repo, "checkout", "-q", "main")
    _git_cli(repo, "merge", "-q", "--no-commit", "--no-ff", "feature")
    # the merge keeps the plugin from the side but rewrites the docs path to content from
    # NEITHER parent — a real merge-time edit, not something a side commit made
    (repo / side_path).write_text("written by the merge itself\n", encoding="utf-8")
    _git_cli(repo, "add", side_path)
    _git_cli(repo, "commit", "-q", "-m", "Merge pull request (resolving docs)")
    _pin_change(monkeypatch, base)

    touched = _changed_files(repo)
    assert side_path in touched, (
        "the merge's own rewrite of a path the side also touched was hidden: " + repr(touched)
    )
