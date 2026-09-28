// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (module implementation).
//
// Startup is explicitly opt-in and provisions nothing. Loading this module — which happens
// whenever a host project loads the plugin — never opens a pipe, never creates, loads or
// saves an asset, and never touches the level. The transport comes up only when the
// operator opted in with -AtlasReadOnlyTransport or with the Engine.ini setting.

#include "AtlasReadOnlyExtraction.h"

#include "AtlasReadOnlyExtractionContract.h"
#include "AtlasReadOnlyExtractionServer.h"

#include "Misc/CommandLine.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogAtlasReadOnlyExtraction);

namespace
{
	/** The one running server of this module; null unless the operator opted in. */
	FAtlasReadOnlyExtractionServer* GReadOnlyTransportServer = nullptr;
}

void FAtlasReadOnlyExtractionModule::StartupModule()
{
	UE_LOG(
		LogAtlasReadOnlyExtraction,
		Log,
		TEXT("Atlas read-only extraction plugin starting up (observation only: no fixture "
			 "provisioning, no write operation, no verification authority)"));

	FString ConfiguredPipeName;
	const bool bConfigEnabled = AtlasReadOnlyExtraction::ReadOptInConfiguration(ConfiguredPipeName);
	const AtlasReadOnlyExtraction::Startup::FDecision Decision =
		AtlasReadOnlyExtraction::Startup::Evaluate(FCommandLine::Get(), bConfigEnabled, ConfiguredPipeName);

	if (!Decision.bStartTransport)
	{
		UE_LOG(
			LogAtlasReadOnlyExtraction,
			Log,
			TEXT("Read-only transport NOT started: %s"),
			*Decision.Reason);
		return;
	}

	GReadOnlyTransportServer = new FAtlasReadOnlyExtractionServer(Decision.PipeName);
	if (!GReadOnlyTransportServer->StartServer())
	{
		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("Failed to start the read-only transport server"));
		delete GReadOnlyTransportServer;
		GReadOnlyTransportServer = nullptr;
		return;
	}

	UE_LOG(
		LogAtlasReadOnlyExtraction,
		Log,
		TEXT("Read-only transport started on %s (opt-in: %s)"),
		*Decision.PipeName,
		*Decision.Reason);
}

void FAtlasReadOnlyExtractionModule::ShutdownModule()
{
	UE_LOG(LogAtlasReadOnlyExtraction, Log, TEXT("Atlas read-only extraction plugin shutting down"));

	if (GReadOnlyTransportServer)
	{
		GReadOnlyTransportServer->StopServer();
		delete GReadOnlyTransportServer;
		GReadOnlyTransportServer = nullptr;
	}

	UE_LOG(LogAtlasReadOnlyExtraction, Log, TEXT("Atlas read-only extraction plugin shutdown complete"));
}

namespace AtlasReadOnlyExtraction
{
	bool IsTransportRunning()
	{
		return GReadOnlyTransportServer != nullptr && GReadOnlyTransportServer->IsRunning();
	}

	FString GetRunningPipeName()
	{
		return GReadOnlyTransportServer != nullptr
			? GReadOnlyTransportServer->GetPipeName()
			: FString();
	}

	FString GetRunningSessionId()
	{
		return GReadOnlyTransportServer != nullptr
			? GReadOnlyTransportServer->GetEditorSessionId().ToString(EGuidFormats::DigitsWithHyphens)
			: FString();
	}
}

IMPLEMENT_MODULE(FAtlasReadOnlyExtractionModule, AtlasReadOnlyExtraction)
