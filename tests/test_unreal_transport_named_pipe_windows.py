import os
import threading
import time
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Windows named pipe transport requires Windows",
)


@pytest.fixture
def win32_modules():
    win32file = pytest.importorskip("win32file")
    win32pipe = pytest.importorskip("win32pipe")
    pywintypes = pytest.importorskip("pywintypes")
    return win32file, win32pipe, pywintypes


def _make_request():
    from planning.unreal_transport_contract import UnrealTransportRequest

    return UnrealTransportRequest(
        request_id=f"test-{uuid.uuid4().hex[:12]}",
        operation_name="inspect_target_actors",
        capability="inspect_actor",
        kind="read",
        arguments={"entity_ids": ("FIELD_SURFACE",)},
        entity_ids=("FIELD_SURFACE",),
        authorization_id="test-authorization",
    )


def _start_server(pipe_name, win32_modules, behavior):
    win32file, win32pipe, pywintypes = win32_modules
    ready = threading.Event()
    finished = threading.Event()
    errors = []

    def server():
        handle = None
        try:
            handle = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE
                | win32pipe.PIPE_READMODE_MESSAGE
                | win32pipe.PIPE_WAIT,
                1,
                1024 * 1024,
                1024 * 1024,
                1000,
                None,
            )
            ready.set()

            try:
                hr = win32pipe.ConnectNamedPipe(handle)
                if hr not in (0, 535):  # ERROR_PIPE_CONNECTED
                    raise RuntimeError(f"ConnectNamedPipe returned {hr}")
            except pywintypes.error as exc:
                if exc.winerror != 535:  # ERROR_PIPE_CONNECTED
                    raise

            _, request_data = win32file.ReadFile(handle, 1024 * 1024)
            import json

            request = json.loads(bytes(request_data).decode("utf-8"))

            if behavior == "delay":
                time.sleep(0.5)

            if behavior == "disconnect":
                return

            response = {
                "request_id": request["request_id"],
                "operation_name": request["operation_name"],
                "entity_ids": request["entity_ids"],
                "success": True,
                "observed_state": {"FIELD_SURFACE": {"actor_name": "TestActor"}},
                "error": "",
                "source": "unreal-editor-atlas-transport",
                "schema_version": 1,
                "error_code": "",
                "session_identity": {
                    "editor_session_id": "test-session-001",
                    "process_id": 12345,
                    "process_creation_time_utc": "2026-09-06T00:00:00Z",
                    "server_start_time_utc": "2026-09-06T00:00:01Z",
                    "engine_version": "5.6",
                    "project_identity": "AtlasUnrealHarness",
                },
            }
            response_data = json.dumps(
                response, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            try:
                win32file.WriteFile(handle, response_data)
                win32file.FlushFileBuffers(handle)
            except pywintypes.error:
                if behavior != "delay":
                    raise
                # The client is expected to close the pipe after the timeout.
        except Exception as exc:  # pragma: no cover - surfaced to test thread
            errors.append(exc)
        finally:
            if handle is not None:
                try:
                    win32file.CloseHandle(handle)
                except Exception:
                    pass
            finished.set()

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(2), "named pipe test server did not start"
    return thread, finished, errors


def _transport(pipe_name):
    from planning.unreal_transport_named_pipe import WindowsNamedPipeTransport

    return WindowsNamedPipeTransport(pipe_name)


def test_named_pipe_normal_response(win32_modules):
    pipe_name = rf"\\.\pipe\AtlasTransportTest_{uuid.uuid4().hex}"
    thread, finished, errors = _start_server(pipe_name, win32_modules, "normal")

    response = _transport(pipe_name).send(_make_request())

    assert response.success is True
    assert response.entity_ids == ("FIELD_SURFACE",)
    assert response.observed_state["FIELD_SURFACE"]["actor_name"] == "TestActor"
    assert finished.wait(2)
    assert not errors
    thread.join(1)


def test_named_pipe_pending_read_timeout_cancels_and_closes(win32_modules):
    pipe_name = rf"\\.\pipe\AtlasTransportTest_{uuid.uuid4().hex}"
    thread, finished, errors = _start_server(pipe_name, win32_modules, "delay")
    transport = _transport(pipe_name)
    transport.READ_TIMEOUT_MS = 100

    from planning.unreal_transport_named_pipe import NamedPipeTransportError

    started = time.monotonic()
    with pytest.raises(NamedPipeTransportError, match="Read operation timed out"):
        transport.send(_make_request())
    elapsed = time.monotonic() - started

    assert elapsed < 1.5
    assert finished.wait(2)
    assert not errors
    thread.join(1)


def test_named_pipe_server_disconnect_is_transport_error(win32_modules):
    pipe_name = rf"\\.\pipe\AtlasTransportTest_{uuid.uuid4().hex}"
    thread, finished, errors = _start_server(pipe_name, win32_modules, "disconnect")

    from planning.unreal_transport_named_pipe import NamedPipeTransportError

    with pytest.raises(NamedPipeTransportError):
        _transport(pipe_name).send(_make_request())

    assert finished.wait(2)
    assert not errors
    thread.join(1)


def test_named_pipe_framing_verification_success_and_failure(win32_modules):
    win32file, win32pipe, pywintypes = win32_modules
    import hashlib
    import json
    from planning.unreal_transport_named_pipe import NamedPipeTransportFramingError

    # 1. Test valid framed response
    pipe_name = rf"\\.\pipe\AtlasTransportTest_{uuid.uuid4().hex}"
    ready = threading.Event()

    def server_framed():
        h = win32pipe.CreateNamedPipe(
            pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 1024*1024, 1024*1024, 1000, None,
        )
        ready.set()
        win32pipe.ConnectNamedPipe(h)
        win32file.ReadFile(h, 1024*1024)
        resp_obj = {
            "request_id": "req-1",
            "operation_name": "inspect_target_actors",
            "entity_ids": ["FIELD_SURFACE"],
            "success": True,
            "observed_state": {"status": "ok"},
            "error": "",
            "source": "test",
            "schema_version": 1,
            "error_code": "",
            "session_identity": {},
        }
        payload = json.dumps(resp_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sha = hashlib.sha256(payload).hexdigest()
        frame_header = f"ATLAS_FRAME:{len(payload)}:{sha}:\n".encode("ascii")
        win32file.WriteFile(h, frame_header + payload)
        win32file.FlushFileBuffers(h)
        win32file.CloseHandle(h)

    t = threading.Thread(target=server_framed, daemon=True)
    t.start()
    assert ready.wait(2)
    resp = _transport(pipe_name).send(_make_request())
    assert resp.success is True
    t.join(1)

    # 2. Test truncated/tampered framed response fails closed
    pipe_name_bad = rf"\\.\pipe\AtlasTransportTest_{uuid.uuid4().hex}"
    ready_bad = threading.Event()

    def server_framed_bad():
        h = win32pipe.CreateNamedPipe(
            pipe_name_bad,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 1024*1024, 1024*1024, 1000, None,
        )
        ready_bad.set()
        win32pipe.ConnectNamedPipe(h)
        win32file.ReadFile(h, 1024*1024)
        payload = b'{"truncated": true'
        # Provide declared length 100 which mismatches actual length
        frame_header = f"ATLAS_FRAME:100:badsha:\n".encode("ascii")
        win32file.WriteFile(h, frame_header + payload)
        win32file.FlushFileBuffers(h)
        win32file.CloseHandle(h)

    t2 = threading.Thread(target=server_framed_bad, daemon=True)
    t2.start()
    assert ready_bad.wait(2)
    with pytest.raises(NamedPipeTransportFramingError, match="Framing length mismatch"):
        _transport(pipe_name_bad).send(_make_request())
    t2.join(1)