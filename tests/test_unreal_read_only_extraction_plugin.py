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
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Dict, Sequence, Set, Tuple

import pytest

from planning import unreal_read_only_extraction as contract
# The harness's own read-only gate defines the token set. Importing it (rather than
# restating it) is what makes "the plugin does not weaken the gate" checkable.
from tests.test_unreal_state_extraction_readonly_source import (
    FORBIDDEN_ENGINE_PATHS,
    FORBIDDEN_TOKENS,
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


def _worktree_changed_files() -> Sequence[str]:
    """Uncommitted and untracked paths in this worktree."""
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
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


def _plugin_change_commits() -> Sequence[str]:
    """The commits that carry this change: every commit that touched an allowlisted path."""
    log = subprocess.run(
        ["git", "log", "--format=%H", "--", *CHANGE_ALLOWED_PREFIXES],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in log.stdout.splitlines() if line.strip()]


def _changed_files() -> Sequence[str]:
    """Every path this change touches: the files of this change's own commits, plus the worktree.

    "This change" is the plugin work, identified by the commits that touch an allowlisted path
    (the plugin, its tests or its contract): every file those commits touch must itself be
    inside the allowlist. The reference used to be merge-base(origin/main, HEAD)..HEAD, which
    stopped isolating this change once unrelated work (documentation, later milestones) landed
    on the same branch — it then flagged paths that are not part of this change at all.
    """
    touched: List[str] = []

    for sha in _plugin_change_commits():
        show = subprocess.run(
            # --no-renames: a rename must show BOTH sides, or a protected file renamed into the
            # plugin directory would hide its source path. -m --first-parent: a merge shows its
            # first-parent diff instead of printing nothing.
            ["git", "show", "--name-only", "--format=", "--no-renames", "-m", "--first-parent", sha],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        touched.extend(line.strip() for line in show.stdout.splitlines() if line.strip())

    touched.extend(_worktree_changed_files())
    return sorted(set(touched))


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
