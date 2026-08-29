"""Static contract coverage for the native Unreal MRQ transport boundary."""

from pathlib import Path


CPP = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")
HEADER = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h")


def test_native_render_transport_declares_mrq_operations():
    header = HEADER.read_text(encoding="utf-8")
    assert "static bool SubmitRender(" in header
    assert "static bool InspectRenderJob(" in header


def test_native_render_transport_routes_mrq_operations():
    source = CPP.read_text(encoding="utf-8")
    assert '#include "MoviePipelineQueueEngineSubsystem.h"' in source
    assert '#include "MoviePipelineExecutor.h"' in source
    assert 'TEXT("submit_render")' in source
    assert 'TEXT("inspect_render_job")' in source
    assert "FAtlasTransportServer::SubmitRender(" in source
    assert "FAtlasTransportServer::InspectRenderJob(" in source
    assert "OnExecutorFinished()" in source
