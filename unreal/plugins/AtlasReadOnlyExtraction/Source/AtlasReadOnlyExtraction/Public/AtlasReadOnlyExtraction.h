// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (module interface).
//
// This module is an *observation* mechanism. It carries the Atlas state-extraction core
// (AtlasStateExtraction.h/.cpp, byte-identical to the version in the Atlas validation
// harness) behind a closed, read-only transport that exposes exactly two operations:
//
//     extract_actor_state
//     extract_sequencer_state
//
// It declares no write, render, fixture, blueprint, material or Niagara operation, it
// provisions nothing, and it holds no verification authority: the extraction response is
// untrusted evidence for Atlas, never a normative decision.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleInterface.h"

DECLARE_LOG_CATEGORY_EXTERN(LogAtlasReadOnlyExtraction, Log, All);

class FAtlasReadOnlyExtractionServer;

class ATLASREADONLYEXTRACTION_API FAtlasReadOnlyExtractionModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};

namespace AtlasReadOnlyExtraction
{
	/** True only while the read-only transport server is actually running in this process. */
	bool IsTransportRunning();

	/** The pipe the running transport listens on; empty when the transport is not running. */
	FString GetRunningPipeName();

	/** The editor session id of the running transport; empty when it is not running. */
	FString GetRunningSessionId();
}
