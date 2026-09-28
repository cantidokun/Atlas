"""Live gate for the portable read-only extraction plugin.

This gate runs the plugin inside a REAL Unreal Editor process, through a bare host project
that contains no Atlas content, no ``atlas_entity`` tag, no fixture asset and no harness
module. It proves, against the engine rather than against the sources:

* loading the plugin does NOT start the transport (explicit opt-in only);
* with ``-AtlasReadOnlyTransport`` the transport comes up and answers exactly the two
  extraction operations, with the existing Atlas transport envelope and the six session
  identity fields;
* every write/render operation of the full Atlas transport is refused, and a write-shaped
  kind is refused even for an exposed operation;
* the extraction refusal path returns a closed ``ERR_EXTRACTION_*`` code and no payload;
* the plugin's own automation tests pass in a project that has no fixture content.

The gate is honest about its environment: when no Unreal Engine installation or no built
plugin is available it reports that state and skips, rather than passing vacuously. Every
assertion is taken from a real process, a real named pipe and the real engine log.

Run:
    python -m pytest tests/test_unreal_read_only_extraction_live_gate.py -v -s
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from planning import unreal_read_only_extraction as contract
from planning.unreal_transport_contract import UnrealTransportResponse

#: This gate drives the plugin's transport through kernel32, and the transport is a Windows
#: named pipe. The module must nevertheless import everywhere — CI collects the whole suite
#: on Linux — so the Windows binding is created only on Windows and only the tests that need
#: it are gated. The Windows run is unchanged: on Windows every test below still executes.
IS_WINDOWS = sys.platform == "win32"

pytestmark = pytest.mark.skipif(
    not IS_WINDOWS,
    reason=(
        "the Atlas read-only extraction transport is a Windows named pipe: the live gate "
        "executes on Windows and is skipped where kernel32 does not exist"
    ),
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
HOST_PROJECT_DIR = LOCALAPPDATA / "Temp" / "atlas_u1_ro_plugin_host"
HOST_PROJECT_NAME = "AtlasReadOnlyHost"

#: Where the host project's build puts the plugin binary. A project-hosted plugin in a
#: junctioned folder is linked in place, so this path resolves through the junction to the
#: repository's plugin directory — the same file in both views.
BUILT_PLUGIN_DLL = (
    HOST_PROJECT_DIR
    / "Plugins"
    / "AtlasReadOnlyExtraction"
    / "Binaries"
    / "Win64"
    / "UnrealEditor-AtlasReadOnlyExtraction.dll"
)
HOST_PLUGIN_DLL = HOST_PROJECT_DIR / "Binaries" / "Win64" / "UnrealEditor-AtlasReadOnlyExtraction.dll"

ENGINE_CANDIDATES = (
    Path("C:/Program Files/Epic Games/UE_5.6"),
    Path("C:/Program Files/Epic Games/UE_5.8"),
)

#: Refused operations used as live probes, one write and one render surface.
WRITE_PROBE_OPERATION = "set_actor_location"
RENDER_PROBE_OPERATION = "submit_render"
ABSENT_ENTITY_ID = "ATLAS_U1_PROBE_ENTITY_ABSENT"

PIPE_TIMEOUT_MILLISECONDS = 20_000
EDITOR_STARTUP_TIMEOUT_SECONDS = 240
AUTOMATION_TIMEOUT_SECONDS = 600

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
PIPE_READMODE_MESSAGE = 0x2
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_PIPE_BUSY = 231
ERROR_FILE_NOT_FOUND = 2

if IS_WINDOWS:  # pragma: no cover - the Windows run exercises this branch
    import ctypes.wintypes as wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.SetNamedPipeHandleState.restype = wintypes.BOOL
    kernel32.SetNamedPipeHandleState.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
else:  # pragma: no cover - the Linux CI collection exercises this branch
    # A platform without kernel32: no binding is created, the module still imports, and the
    # pipe helpers below refuse to run rather than failing obscurely.
    wintypes = None
    kernel32 = None


# ---------------------------------------------------------------------------
# Host project
# ---------------------------------------------------------------------------

def _selected_engine() -> Path:
    for candidate in ENGINE_CANDIDATES:
        if (candidate / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe").is_file():
            return candidate
    pytest.skip(
        "no Unreal Engine installation found in "
        + ", ".join(str(candidate) for candidate in ENGINE_CANDIDATES)
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def ensure_host_project() -> Path:
    """Create the bare host project and junction the repository plugin into it."""
    engine = _selected_engine()
    association = engine.name.split("_", 1)[1] if "_" in engine.name else "5.6"

    _write(
        HOST_PROJECT_DIR / f"{HOST_PROJECT_NAME}.uproject",
        json.dumps(
            {
                "FileVersion": 3,
                "EngineAssociation": association,
                "Category": "Atlas",
                "Description": (
                    "Bare host project for the Atlas read-only extraction plugin. No Atlas "
                    "content, no atlas_entity tag, no fixture asset, no harness module."
                ),
                "Plugins": [{"Name": "AtlasReadOnlyExtraction", "Enabled": True}],
            },
            indent="\t",
        )
        + "\n",
    )
    _write(
        HOST_PROJECT_DIR / "Source" / f"{HOST_PROJECT_NAME}.Target.cs",
        "using UnrealBuildTool;\n"
        "using System.Collections.Generic;\n\n"
        f"public class {HOST_PROJECT_NAME}Target : TargetRules\n"
        "{\n"
        f"\tpublic {HOST_PROJECT_NAME}Target(TargetInfo Target) : base(Target)\n"
        "\t{\n"
        "\t\tType = TargetType.Game;\n"
        "\t\tDefaultBuildSettings = BuildSettingsVersion.Latest;\n"
        "\t\tIncludeOrderVersion = EngineIncludeOrderVersion.Latest;\n"
        "\t\tExtraModuleNames.AddRange(new string[] { });\n"
        "\t}\n"
        "}\n",
    )
    _write(
        HOST_PROJECT_DIR / "Source" / f"{HOST_PROJECT_NAME}Editor.Target.cs",
        "using UnrealBuildTool;\n"
        "using System.Collections.Generic;\n\n"
        f"public class {HOST_PROJECT_NAME}EditorTarget : TargetRules\n"
        "{\n"
        f"\tpublic {HOST_PROJECT_NAME}EditorTarget(TargetInfo Target) : base(Target)\n"
        "\t{\n"
        "\t\tType = TargetType.Editor;\n"
        "\t\tDefaultBuildSettings = BuildSettingsVersion.Latest;\n"
        "\t\tIncludeOrderVersion = EngineIncludeOrderVersion.Latest;\n"
        "\t\tExtraModuleNames.AddRange(new string[] { });\n"
        "\t}\n"
        "}\n",
    )
    _write(
        HOST_PROJECT_DIR / "Config" / "DefaultEngine.ini",
        "; Bare host project for the Atlas read-only extraction plugin.\n"
        "; The transport starts only under explicit opt-in: -AtlasReadOnlyTransport on the\n"
        "; command line, or the settings below (uncommented). Loading the plugin alone never\n"
        "; opens a pipe.\n"
        ";\n"
        "; [AtlasReadOnlyExtraction]\n"
        "; bReadOnlyTransportEnabled=True\n"
        f"; ReadOnlyTransportPipeName={contract.PIPE_NAME}\n",
    )
    (HOST_PROJECT_DIR / "Content").mkdir(parents=True, exist_ok=True)

    plugin_link = HOST_PROJECT_DIR / "Plugins" / "AtlasReadOnlyExtraction"
    if not plugin_link.exists():
        plugin_link.parent.mkdir(parents=True, exist_ok=True)
        created = subprocess.run(
            [
                "cmd",
                "/c",
                "mklink",
                "/J",
                str(plugin_link),
                str(contract.PLUGIN_DIR),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert created.returncode == 0, f"could not junction the plugin: {created.stdout} {created.stderr}"

    build_script = HOST_PROJECT_DIR / "build_plugin.bat"
    uproject_path = HOST_PROJECT_DIR / f"{HOST_PROJECT_NAME}.uproject"
    _write(
        build_script,
        "@echo off\n"
        "rem Atlas U1 — build the read-only extraction plugin through the bare host project.\n"
        "rem The project path is absolute because Build.bat changes directory to the engine\n"
        "rem batch-files folder.\n"
        f'call "{engine}\\Engine\\Build\\BatchFiles\\Build.bat" '
        f'{HOST_PROJECT_NAME}Editor Win64 Development -project="{uproject_path}" -waitmutex\n'
        "echo BUILD_EXIT=%ERRORLEVEL%\n",
    )

    return HOST_PROJECT_DIR


def build_plugin(force: bool = False) -> Tuple[int, str]:
    """Build (or reuse) the plugin for the host project; return the exit code and log tail."""
    ensure_host_project()
    log_path = HOST_PROJECT_DIR / "build.log"
    if not force and BUILT_PLUGIN_DLL.is_file():
        _deploy_plugin_binary()
        return 0, f"reused existing build: {BUILT_PLUGIN_DLL}"

    completed = subprocess.run(
        ["cmd", "/c", "build_plugin.bat"],
        cwd=str(HOST_PROJECT_DIR),
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8", errors="replace")
    tail = "\n".join((completed.stdout + completed.stderr).splitlines()[-25:])
    if BUILT_PLUGIN_DLL.is_file():
        _deploy_plugin_binary()
    return completed.returncode, tail


def _deploy_plugin_binary() -> None:
    """Make the built plugin module visible to the editor from the host project.

    The module is linked in place (through the junction), which the editor also searches;
    copying it into the host project's own ``Binaries/Win64`` makes the load independent of
    that search order. The copy is byte-identical by construction and is not a second build.
    """
    if not BUILT_PLUGIN_DLL.is_file():
        return
    if HOST_PLUGIN_DLL.is_file() and HOST_PLUGIN_DLL.read_bytes() == BUILT_PLUGIN_DLL.read_bytes():
        return
    HOST_PLUGIN_DLL.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILT_PLUGIN_DLL, HOST_PLUGIN_DLL)
    for suffix in (".pdb",):
        source = BUILT_PLUGIN_DLL.with_suffix(suffix)
        if source.is_file():
            shutil.copy2(source, HOST_PLUGIN_DLL.with_suffix(suffix))


def _editor_command(extra: Sequence[str], log_path: Path) -> List[str]:
    engine = _selected_engine()
    editor = engine / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    return [
        str(editor),
        str(HOST_PROJECT_DIR / f"{HOST_PROJECT_NAME}.uproject"),
        "-unattended",
        "-nosplash",
        "-nop4",
        "-nullrhi",
        "-stdout",
        "-nopause",
        f"-abslog={log_path}",
        *extra,
    ]


def _launch_editor(extra: Sequence[str], log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    return subprocess.Popen(
        _editor_command(extra, log_path),
        cwd=str(HOST_PROJECT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_log(log_path: Path, pattern: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    expression = re.compile(pattern)
    while time.monotonic() < deadline:
        if log_path.is_file():
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if expression.search(text):
                return True
        time.sleep(1.0)
    return False


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)


# ---------------------------------------------------------------------------
# Named pipe client (ctypes; no pywin32 dependency)
# ---------------------------------------------------------------------------

def _require_windows_kernel32() -> None:
    """Refuse to reach the kernel32 binding on a platform that has none.

    The module-level gate already keeps the live tests off non-Windows platforms; this is the
    second line of defence, so no future caller can reach the binding by accident.
    """
    if not IS_WINDOWS or kernel32 is None:
        raise AssertionError(
            "the Atlas read-only extraction transport is a Windows named pipe: the pipe "
            f"helpers are unavailable on sys.platform={sys.platform!r}"
        )


def pipe_connect(pipe_name: str, timeout_ms: int = PIPE_TIMEOUT_MILLISECONDS) -> Optional[int]:
    """Return a connected message-mode handle, or None when the pipe is not there."""
    _require_windows_kernel32()
    kernel32.WaitNamedPipeW(pipe_name, timeout_ms)
    handle = kernel32.CreateFileW(
        pipe_name,
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if not handle or handle == INVALID_HANDLE_VALUE:
        return None
    mode = wintypes.DWORD(PIPE_READMODE_MESSAGE)
    kernel32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None)
    return handle


def pipe_exchange(pipe_name: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One request per connection: the server closes the pipe after every response."""
    handle = pipe_connect(pipe_name)
    if handle is None:
        return None

    try:
        payload = json.dumps(request).encode("utf-8")
        written = wintypes.DWORD(0)
        buffer = ctypes.create_string_buffer(payload, len(payload))
        if not kernel32.WriteFile(handle, buffer, len(payload), ctypes.byref(written), None):
            raise AssertionError(f"WriteFile failed: {ctypes.get_last_error()}")
        assert written.value == len(payload)

        limit = contract.WIRE_MESSAGE_LIMIT
        read_buffer = ctypes.create_string_buffer(limit)
        read = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, read_buffer, limit, ctypes.byref(read), None):
            raise AssertionError(f"ReadFile failed: {ctypes.get_last_error()}")
        if read.value == 0:
            return None
        return json.loads(read_buffer.raw[: read.value].decode("utf-8"))
    finally:
        kernel32.CloseHandle(handle)


def extraction_request(operation: str, entity_ids: Sequence[str], kind: str = "read") -> Dict[str, Any]:
    entity_list = list(entity_ids)
    return {
        "request_id": f"atlas-live-gate-{operation}",
        "operation_name": operation,
        "capability": contract.CAPABILITY_BY_OPERATION.get(operation, "read"),
        "kind": kind,
        "arguments": {"entity_ids": entity_list},
        "entity_ids": entity_list,
        "authorization_id": "atlas-live-gate",
        "schema_version": contract.SCHEMA_VERSION,
    }


def refused_operation_request(operation: str) -> Dict[str, Any]:
    entity_list = [ABSENT_ENTITY_ID]
    return {
        "request_id": f"atlas-live-gate-{operation}",
        "operation_name": operation,
        "capability": "modify_actor",
        "kind": "write",
        "arguments": {"entity_ids": entity_list},
        "entity_ids": entity_list,
        "authorization_id": "atlas-live-gate",
        "schema_version": contract.SCHEMA_VERSION,
    }


def _validate_envelope(response: Dict[str, Any]) -> UnrealTransportResponse:
    """The response must still satisfy the existing Atlas transport contract."""
    return UnrealTransportResponse(
        request_id=response["request_id"],
        operation_name=response["operation_name"],
        entity_ids=tuple(response["entity_ids"]),
        success=response["success"],
        observed_state=response["observed_state"],
        error=response["error"],
        source=response["source"],
        schema_version=response["schema_version"],
        error_code=response["error_code"],
        session_identity=response["session_identity"],
    )


def _exchange_when_engine_ready(
    pipe_name: str,
    request: Dict[str, Any],
    attempts: int = 20,
    delay_seconds: float = 2.0,
) -> Dict[str, Any]:
    """Exchange one request, retrying while the engine is still initialising.

    A plugin module loads (and its transport starts) before ``FEngineLoop::Init()`` returns,
    so a request that arrives during editor startup can elapse the engine's own five-second
    operation timeout on a game thread that is not ticking yet. That is a startup ordering
    fact, not a refusal: the gate waits for the engine and retries, and it fails if the
    operation never completes.
    """
    response: Optional[Dict[str, Any]] = None
    for attempt in range(1, attempts + 1):
        response = pipe_exchange(pipe_name, request)
        assert response is not None, "no response on the read-only extraction pipe"
        if response.get("error_code") != "ERR_OPERATION_TIMED_OUT":
            if attempt > 1:
                print(f"[evidence] operation answered on attempt {attempt} after engine startup")
            return response
        time.sleep(delay_seconds)

    raise AssertionError(
        "the engine never completed the operation (last response: "
        f"{response}) — the transport answered but the game thread did not run it"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built_plugin() -> Path:
    exit_code, tail = build_plugin()
    if exit_code != 0 or not BUILT_PLUGIN_DLL.is_file():
        pytest.skip(f"the plugin did not build in this environment:\n{tail}")
    return BUILT_PLUGIN_DLL


@pytest.fixture(scope="module")
def engine_version() -> str:
    engine = _selected_engine()
    return engine.name


# ---------------------------------------------------------------------------
# 1. The transport is down unless the operator opted in
# ---------------------------------------------------------------------------

def test_transport_stays_down_when_the_plugin_is_loaded_without_opt_in(built_plugin: Path) -> None:
    log_path = HOST_PROJECT_DIR / "editor_no_optin.log"
    process = _launch_editor([], log_path)
    try:
        loaded = _wait_for_log(
            log_path,
            r"Atlas read-only extraction plugin starting up",
            EDITOR_STARTUP_TIMEOUT_SECONDS,
        )
        assert loaded, (
            "the plugin module did not report loading in the host project; log tail:\n"
            + ("\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
               if log_path.is_file() else "(no log)")
        )

        decided = _wait_for_log(
            log_path,
            r"Read-only transport NOT started",
            EDITOR_STARTUP_TIMEOUT_SECONDS,
        )
        assert decided, "the plugin did not report the opt-in decision"

        # No pipe: a client cannot reach any operation.
        assert pipe_connect(contract.PIPE_NAME, timeout_ms=2000) is None, (
            "the read-only extraction pipe is reachable although nothing opted in"
        )

        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        assert "no explicit opt-in" in log_text or "no explicit opt-in" in log_text.replace("\u2019", "'"), (
            "the opt-in decision was not reported with its reason"
        )
        print(
            "\n[evidence] plugin loaded, transport down without opt-in; pipe "
            f"{contract.PIPE_NAME} not reachable"
        )
    finally:
        _stop(process)


# ---------------------------------------------------------------------------
# 2. With opt-in: the closed read-only surface, live
# ---------------------------------------------------------------------------

def test_transport_with_opt_in_serves_only_the_two_extractions(built_plugin: Path) -> None:
    log_path = HOST_PROJECT_DIR / "editor_optin.log"
    process = _launch_editor(["-AtlasReadOnlyTransport"], log_path)
    try:
        started = _wait_for_log(log_path, r"Read-only transport started on", EDITOR_STARTUP_TIMEOUT_SECONDS)
        assert started, (
            "the transport did not start under -AtlasReadOnlyTransport; log tail:\n"
            + ("\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:])
               if log_path.is_file() else "(no log)")
        )

        # The pipe is up before the engine finishes initialising; wait for the engine so the
        # operations are executed on a ticking game thread (see _exchange_when_engine_ready).
        engine_ready = _wait_for_log(log_path, r"Engine is initialized", EDITOR_STARTUP_TIMEOUT_SECONDS)
        print(f"[evidence] engine initialisation observed: {engine_ready}")

        # (a) extract_actor_state against an entity no project content can carry.
        actor_response = _exchange_when_engine_ready(
            contract.PIPE_NAME,
            extraction_request(contract.OPERATIONS[0], [ABSENT_ENTITY_ID]),
        )
        assert actor_response is not None, "no response on the read-only extraction pipe"
        validated = _validate_envelope(actor_response)
        assert validated.source == contract.SOURCE
        assert validated.session_identity, "the response carries no session identity"
        for field in contract.SESSION_IDENTITY_FIELDS:
            assert field in validated.session_identity, f"session identity lacks {field}"
            assert validated.session_identity[field] not in (None, ""), f"session identity {field} is empty"
        assert validated.success is False, "an absent entity must not extract successfully"
        assert validated.error_code.startswith("ERR_EXTRACTION_"), (
            f"the refusal is not a closed extraction code: {validated.error_code!r}"
        )
        assert validated.error_code != "ERR_EXTRACTION_ERROR_CODE_UNKNOWN"
        assert validated.observed_state == {}, "a refusal must carry no partial payload"
        print(
            f"\n[evidence] extract_actor_state refusal: {validated.error_code} "
            f"(source={validated.source}, engine={validated.session_identity['engine_version']})"
        )

        # (b) extract_sequencer_state, same closed behaviour.
        sequencer_response = _exchange_when_engine_ready(
            contract.PIPE_NAME,
            extraction_request(contract.OPERATIONS[1], [ABSENT_ENTITY_ID]),
        )
        assert sequencer_response is not None
        sequencer = _validate_envelope(sequencer_response)
        assert sequencer.success is False
        assert sequencer.error_code.startswith("ERR_EXTRACTION_")
        assert sequencer.observed_state == {}

        # (c) A write kind for an exposed operation is refused.
        write_kind_response = _exchange_when_engine_ready(
            contract.PIPE_NAME,
            extraction_request(contract.OPERATIONS[0], [ABSENT_ENTITY_ID], kind="write"),
        )
        assert write_kind_response is not None
        assert write_kind_response["success"] is False
        assert write_kind_response["error_code"] == "ERR_MISSING_ARGUMENT", write_kind_response
        assert write_kind_response["observed_state"] == {}

        # (d) Every refused operation is unknown to this transport.
        for operation in (WRITE_PROBE_OPERATION, RENDER_PROBE_OPERATION):
            response = _exchange_when_engine_ready(contract.PIPE_NAME, refused_operation_request(operation))
            assert response is not None, f"no response for {operation}"
            assert response["success"] is False, response
            assert response["error_code"] == "ERR_UNKNOWN_OPERATION", (operation, response)
            print(f"[evidence] {operation} refused with {response['error_code']}")
    finally:
        _stop(process)


# ---------------------------------------------------------------------------
# 3. The plugin's own automation tests pass in a fixture-free project
# ---------------------------------------------------------------------------

AUTOMATION_RESULT_PATTERN = re.compile(
    r"Test Completed\. Result=\{(\w+)\}\.?\s+Name=\{([^}]+)\}(?:\s+Path=\{([^}]+)\})?"
)

EXPECTED_AUTOMATION_TESTS = {
    "Atlas.ReadOnlyExtraction.OperationSurfaceIsClosed",
    "Atlas.ReadOnlyExtraction.NonExtractionOperationsAreRefused",
    "Atlas.ReadOnlyExtraction.CapabilityAndKindMustBeRead",
    "Atlas.ReadOnlyExtraction.EnvelopeIsPreserved",
    "Atlas.ReadOnlyExtraction.SessionIdentityIsPreserved",
    "Atlas.ReadOnlyExtraction.RefusalCarriesNoPartialPayload",
    "Atlas.ReadOnlyExtraction.PackageDirtyInvarianceAcrossExtractionCall",
    "Atlas.ReadOnlyExtraction.TransportStartupIsExplicitOptIn",
}


def test_automation_tests_pass_in_the_bare_host_project(built_plugin: Path) -> None:
    log_path = HOST_PROJECT_DIR / "editor_automation.log"
    report_dir = HOST_PROJECT_DIR / "automation_report"
    if report_dir.exists():
        shutil.rmtree(report_dir)

    process = _launch_editor(
        [
            "-ExecCmds=Automation RunTests Atlas.ReadOnlyExtraction",
            "-testexit=Automation Test Queue Empty",
            f"-ReportExportPath={report_dir}",
        ],
        log_path,
    )
    try:
        process.wait(timeout=AUTOMATION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _stop(process)
        raise AssertionError(
            "the automation run did not finish; log tail:\n"
            + "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:])
        )

    log_text = log_path.read_text(encoding="utf-8", errors="replace")

    # Primary evidence: the engine's own structured report of the run.
    report_path = report_dir / "index.json"
    assert report_path.is_file(), (
        "the engine wrote no automation report (the plugin's tests did not run); log tail:\n"
        + "\n".join(log_text.splitlines()[-25:])
    )
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    reported = {
        entry["fullTestPath"]: entry["state"]
        for entry in report.get("tests", [])
        if "fullTestPath" in entry
    }

    print(
        f"\n[evidence] engine automation report: succeeded={report['succeeded']}, "
        f"failed={report['failed']}, notRun={report['notRun']}"
    )
    for path, state in sorted(reported.items()):
        print(f"[evidence]   {state.upper():8s} {path}")

    assert report["failed"] == 0, f"automation failures reported: {report}"
    assert report["notRun"] == 0, f"automation tests did not run: {report}"
    assert set(reported) == EXPECTED_AUTOMATION_TESTS, (
        f"the plugin's own test set did not run: {sorted(set(reported) ^ EXPECTED_AUTOMATION_TESTS)}"
    )
    assert all(state == "Success" for state in reported.values()), reported

    # Secondary evidence: the same run, as the engine logged it per test.
    logged_by_path = {}
    for result, name, path in AUTOMATION_RESULT_PATTERN.findall(log_text):
        identifier = path or name
        if identifier.startswith("Atlas.ReadOnlyExtraction."):
            logged_by_path[identifier] = result
    assert len(logged_by_path) == len(EXPECTED_AUTOMATION_TESTS), (
        f"the log reports {len(logged_by_path)} of {len(EXPECTED_AUTOMATION_TESTS)} plugin tests: "
        f"{sorted(logged_by_path)}"
    )
    assert all(result == "Success" for result in logged_by_path.values()), logged_by_path


# ---------------------------------------------------------------------------
# 4. The plugin is built from the repository source, not a copy
# ---------------------------------------------------------------------------

def test_the_built_plugin_comes_from_the_repository_source(built_plugin: Path) -> None:
    assert built_plugin.is_file(), f"the plugin binary is missing: {built_plugin}"
    link = HOST_PROJECT_DIR / "Plugins" / "AtlasReadOnlyExtraction"
    assert link.exists(), "the host project has no plugin link"
    descriptor = link / "AtlasReadOnlyExtraction.uplugin"
    assert descriptor.read_bytes() == contract.DESCRIPTOR_PATH.read_bytes(), (
        "the host project's plugin source is not the repository's plugin source"
    )
    assert built_plugin.resolve() == (contract.PLUGIN_DIR / "Binaries" / "Win64" / built_plugin.name).resolve(), (
        "the plugin binary was not produced from the repository's plugin directory"
    )


def test_engine_version_is_reported(engine_version: str) -> None:
    print(f"\n[evidence] engine used for the live gate: {engine_version}")
    assert engine_version.startswith("UE_")
