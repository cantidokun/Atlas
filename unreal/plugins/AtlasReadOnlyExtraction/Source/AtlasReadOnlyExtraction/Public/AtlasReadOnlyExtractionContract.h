// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (declared contract).
//
// This header is the single declaration of what the plugin exposes:
//
//   * Operations   — the CLOSED read-only operation surface (exactly two operations);
//   * Transport    — the envelope constants (pipe name, source string, wire bound);
//   * Startup      — the explicit opt-in policy (pure; no engine state, no side effects).
//
// Nothing here is authority. The values are transport plumbing and a declaration of the
// observation surface; no semantic expectation, target value or registry authority is
// accepted from, or produced by, this plugin.

#pragma once

#include "CoreMinimal.h"

namespace AtlasReadOnlyExtraction
{
	namespace Operations
	{
		/** The only two operations this plugin ever dispatches. */
		extern const TCHAR* const ExtractActorState;      // "extract_actor_state"
		extern const TCHAR* const ExtractSequencerState;  // "extract_sequencer_state"

		/** The closed surface, in declaration order. */
		const TArray<FString>& GetSupportedOperationNames();

		/** True only for the two operations above; false for every other name. */
		bool IsSupportedOperation(const FString& OperationName);

		/** The capability the operation requires, or nullptr when the name is not supported. */
		const TCHAR* GetExpectedCapability(const FString& OperationName);

		/** The kind the operation requires ("read"), or nullptr when the name is not supported. */
		const TCHAR* GetExpectedKind(const FString& OperationName);

		/** True when the request names a supported operation with its declared read capability/kind. */
		bool IsReadOnlyRequest(
			const FString& OperationName,
			const FString& Capability,
			const FString& Kind,
			FString& OutError);
	}

	namespace Transport
	{
		/**
		 * The plugin's own default pipe. It is deliberately NOT the harness pipe
		 * (\\.\pipe\AtlasUnrealTransport): the two servers must never contend for one pipe
		 * name, and an evidence run must be able to say which mechanism answered it.
		 */
		extern const TCHAR* const DefaultPipeName;

		/** The response `source` string of this plugin (provenance, never authority). */
		extern const TCHAR* const SourceString;

		/** Command-line opt-ins: -AtlasReadOnlyTransport and -AtlasReadOnlyTransportPipe=<name>. */
		extern const TCHAR* const OptInSwitch;
		extern const TCHAR* const PipeNameSwitch;

		/** Engine.ini section/keys read by ReadOptInConfiguration(). */
		extern const TCHAR* const ConfigSection;
		extern const TCHAR* const ConfigEnableKey;
		extern const TCHAR* const ConfigPipeNameKey;

		/** The wire bound the response path enforces (the existing Atlas transport bound). */
		int32 GetMessageSizeLimit();

		/** Flag > configuration > default. Never returns an empty name. */
		FString ResolvePipeName(const FString& CommandLine, const FString& ConfiguredPipeName);

		/** True when the command line carries the opt-in switch. */
		bool IsOptInSwitchPresent(const FString& CommandLine);
	}

	namespace Startup
	{
		/** The opt-in decision for one launch. Pure data: no side effects. */
		struct FDecision
		{
			bool bStartTransport = false;
			FString Reason;
			FString PipeName;
		};

		/**
		 * The whole startup policy, as a pure function:
		 * the transport starts only when the operator opted in, either with
		 * -AtlasReadOnlyTransport or with the Engine.ini setting. Loading the module alone
		 * never starts it.
		 */
		FDecision Evaluate(const FString& CommandLine, bool bConfigEnabled, const FString& ConfiguredPipeName);
	}

	/** Read the plugin's Engine.ini opt-in; also returns the configured pipe name. */
	bool ReadOptInConfiguration(FString& OutConfiguredPipeName);
}
