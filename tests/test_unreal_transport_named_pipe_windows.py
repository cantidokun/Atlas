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


def _response_payload(request):
    import json

    return json.dumps(
        {
            "request_id": request.request_id,
            "operation_name": request.operation_name,
            "entity_ids": list(request.entity_ids),
            "success": True,
            "observed_state": {"FIELD_SURFACE": {"actor_name": "TestActor"}},
            "error": "",
            "source": "unreal-editor-atlas-transport",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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
            request = __import__("json").loads(bytes(request_data).decode("utf-8"))

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
            }
            response_data = __import__("json").dumps(
                response, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            win32file.WriteFile(handle, response_data)
            win32file.FlushFileBuffers(handle)
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

    started = time.monotonic()
    with pytest.raises(Exception, match="Read operation timed out"):
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
