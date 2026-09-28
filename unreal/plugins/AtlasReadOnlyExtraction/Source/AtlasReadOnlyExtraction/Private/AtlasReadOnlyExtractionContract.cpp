// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (contract implementation).

#include "AtlasReadOnlyExtractionContract.h"

#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Parse.h"

namespace AtlasReadOnlyExtraction
{
	namespace Operations
	{
		const TCHAR* const ExtractActorState = TEXT("extract_actor_state");
		const TCHAR* const ExtractSequencerState = TEXT("extract_sequencer_state");

		const TArray<FString>& GetSupportedOperationNames()
		{
			static const TArray<FString> Names = {
				FString(ExtractActorState),
				FString(ExtractSequencerState)};
			return Names;
		}

		bool IsSupportedOperation(const FString& OperationName)
		{
			return OperationName == ExtractActorState || OperationName == ExtractSequencerState;
		}

		const TCHAR* GetExpectedCapability(const FString& OperationName)
		{
			if (OperationName == ExtractActorState)
			{
				return TEXT("inspect_actor");
			}
			if (OperationName == ExtractSequencerState)
			{
				return TEXT("sequencer");
			}
			return nullptr;
		}

		const TCHAR* GetExpectedKind(const FString& OperationName)
		{
			return IsSupportedOperation(OperationName) ? TEXT("read") : nullptr;
		}

		bool IsReadOnlyRequest(
			const FString& OperationName,
			const FString& Capability,
			const FString& Kind,
			FString& OutError)
		{
			const TCHAR* ExpectedCapability = GetExpectedCapability(OperationName);
			const TCHAR* ExpectedKind = GetExpectedKind(OperationName);

			if (ExpectedCapability == nullptr || ExpectedKind == nullptr)
			{
				OutError = FString::Printf(
					TEXT("unsupported operation: %s"), *OperationName);
				return false;
			}

			if (Capability != ExpectedCapability || Kind != ExpectedKind)
			{
				OutError = FString::Printf(
					TEXT("%s requires %s/%s"),
					*OperationName,
					ExpectedCapability,
					ExpectedKind);
				return false;
			}

			return true;
		}
	}

	namespace Transport
	{
		const TCHAR* const DefaultPipeName = TEXT("\\\\.\\pipe\\AtlasReadOnlyExtraction");
		const TCHAR* const SourceString = TEXT("unreal-editor-atlas-read-only-extraction");
		const TCHAR* const OptInSwitch = TEXT("AtlasReadOnlyTransport");
		const TCHAR* const PipeNameSwitch = TEXT("AtlasReadOnlyTransportPipe");
		const TCHAR* const ConfigSection = TEXT("AtlasReadOnlyExtraction");
		const TCHAR* const ConfigEnableKey = TEXT("bReadOnlyTransportEnabled");
		const TCHAR* const ConfigPipeNameKey = TEXT("ReadOnlyTransportPipeName");

		/** The existing Atlas transport bound (1 MiB). No new cap, no second authority. */
		int32 GetMessageSizeLimit()
		{
			return 1024 * 1024;
		}

		bool IsOptInSwitchPresent(const FString& CommandLine)
		{
			return FParse::Param(*CommandLine, OptInSwitch);
		}

		FString ResolvePipeName(const FString& CommandLine, const FString& ConfiguredPipeName)
		{
			FString SwitchPipeName;
			if (FParse::Value(*CommandLine, TEXT("AtlasReadOnlyTransportPipe="), SwitchPipeName))
			{
				SwitchPipeName.TrimStartAndEndInline();
				if (!SwitchPipeName.IsEmpty())
				{
					return SwitchPipeName;
				}
			}

			FString ConfigPipeName = ConfiguredPipeName;
			ConfigPipeName.TrimStartAndEndInline();
			if (!ConfigPipeName.IsEmpty())
			{
				return ConfigPipeName;
			}

			return FString(DefaultPipeName);
		}
	}

	namespace Startup
	{
		FDecision Evaluate(const FString& CommandLine, bool bConfigEnabled, const FString& ConfiguredPipeName)
		{
			FDecision Decision;
			Decision.PipeName = Transport::ResolvePipeName(CommandLine, ConfiguredPipeName);

			if (Transport::IsOptInSwitchPresent(CommandLine))
			{
				Decision.bStartTransport = true;
				Decision.Reason = FString::Printf(TEXT("command-line opt-in -%s"), Transport::OptInSwitch);
			}
			else if (bConfigEnabled)
			{
				Decision.bStartTransport = true;
				Decision.Reason = FString::Printf(
					TEXT("configuration opt-in [%s] %s"),
					Transport::ConfigSection,
					Transport::ConfigEnableKey);
			}
			else
			{
				Decision.bStartTransport = false;
				Decision.Reason = FString::Printf(
					TEXT("no explicit opt-in (no -%s switch and %s is not set): the read-only transport stays down"),
					Transport::OptInSwitch,
					Transport::ConfigEnableKey);
			}

			return Decision;
		}
	}

	bool ReadOptInConfiguration(FString& OutConfiguredPipeName)
	{
		OutConfiguredPipeName.Empty();

		bool bEnabled = false;
		if (GConfig != nullptr)
		{
			GConfig->GetBool(
				Transport::ConfigSection,
				Transport::ConfigEnableKey,
				bEnabled,
				GEngineIni);

			GConfig->GetString(
				Transport::ConfigSection,
				Transport::ConfigPipeNameKey,
				OutConfiguredPipeName,
				GEngineIni);
		}

		return bEnabled;
	}
}
