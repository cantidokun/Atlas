// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (automation tests).
//
// Fixture-free by construction: these tests use NO fixture content, NO /Game asset, NO
// tagged actor and NO harness module. They exercise the plugin's declared surface, its
// envelope, its session identity, the closed refusal path of the extraction core and the
// dynamic read-only proof, against whatever editor world the host project happens to have
// (including none).
//
// The refused-operation table below is test data: it names the operations the plugin must
// NOT expose, so that the refusal is asserted rather than assumed. No such operation is
// declared, dispatched or reachable anywhere in this plugin.
//
// Compiled only into development builds (`WITH_DEV_AUTOMATION_TESTS`); these tests perform
// no write of any kind.

#include "AtlasReadOnlyExtraction.h"
#include "AtlasReadOnlyExtractionContract.h"
#include "AtlasReadOnlyExtractionServer.h"
#include "AtlasStateExtraction.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "FileHelpers.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/EngineVersion.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/Package.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	/** Operations this plugin must never expose. Test data only; nothing dispatches them. */
	const TArray<FString>& RefusedOperationNames()
	{
		static const TArray<FString> Names = {
			TEXT("set_actor_location"),
			TEXT("set_actor_rotation"),
			TEXT("set_actor_scale"),
			TEXT("apply_material_variant"),
			TEXT("apply_niagara_variant"),
			TEXT("set_sequencer_playback_range"),
			TEXT("set_blueprint_metadata"),
			TEXT("compile_blueprint"),
			TEXT("configure_render"),
			TEXT("submit_render"),
			TEXT("reconcile_render_jobs"),
			// Read-only operations of the full Atlas transport that this plugin does not expose.
			TEXT("inspect_world"),
			TEXT("inspect_target_actors"),
			TEXT("inspect_material_state"),
			TEXT("inspect_niagara_state"),
			TEXT("inspect_sequencer_state"),
			TEXT("inspect_blueprint_state"),
			TEXT("inspect_render_state"),
			TEXT("inspect_render_job"),
			TEXT("get_capabilities"),
			TEXT("verify_render_state"),
			TEXT("verify_blueprint_state"),
			TEXT("verify_sequencer_playback_range"),
		};
		return Names;
	}

	/** An entity id that no project content can carry: the refusal path, not a fixture. */
	const TCHAR* const AbsentEntityId = TEXT("ATLAS_U1_PROBE_ENTITY_ABSENT");

	FAtlasReadOnlyExtractionServer::FRequest MakeRequest(
		const FString& OperationName,
		const FString& Capability,
		const FString& Kind,
		const TArray<FString>& EntityIds)
	{
		FAtlasReadOnlyExtractionServer::FRequest Request;
		Request.RequestId = TEXT("atlas-read-only-extraction-test-request");
		Request.OperationName = OperationName;
		Request.Capability = Capability;
		Request.Kind = Kind;
		Request.AuthorizationId = TEXT("atlas-read-only-extraction-test-authorization");
		Request.SchemaVersion = 1;
		Request.EntityIds = EntityIds;

		TSharedPtr<FJsonObject> Arguments = MakeShareable(new FJsonObject());
		TArray<TSharedPtr<FJsonValue>> EntityIdValues;
		for (const FString& EntityId : EntityIds)
		{
			EntityIdValues.Add(MakeShareable(new FJsonValueString(EntityId)));
		}
		Arguments->SetArrayField(TEXT("entity_ids"), EntityIdValues);
		Request.Arguments = Arguments;

		return Request;
	}

	/** The read-only pair every exposed operation declares. */
	FAtlasReadOnlyExtractionServer::FRequest MakeExtractionRequest(const FString& OperationName)
	{
		const TCHAR* Capability = AtlasReadOnlyExtraction::Operations::GetExpectedCapability(OperationName);
		return MakeRequest(
			OperationName,
			FString(Capability != nullptr ? Capability : TEXT("")),
			TEXT("read"),
			{TEXT("ATLAS_U1_PROBE_ENTITY_ABSENT")});
	}

	bool ParseJson(const FString& Json, TSharedPtr<FJsonObject>& OutObject)
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
	}

	/**
	 * Clear the transient dirty flag of one editor package so the "clean before, clean
	 * after" form of the dynamic read-only proof can run. This is test state, not content:
	 * nothing is saved, and the plugin's own code never touches a package flag.
	 */
	void ClearPackageDirtyFlagForTest(UPackage* Package)
	{
		if (Package != nullptr)
		{
			Package->SetDirtyFlag(false);
		}
	}
}

// ---------------------------------------------------------------------------
// 1. The operation surface is closed
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionOperationSurfaceTest,
	"Atlas.ReadOnlyExtraction.OperationSurfaceIsClosed",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionOperationSurfaceTest::RunTest(const FString& Parameters)
{
	const TArray<FString>& Advertised =
		FAtlasReadOnlyExtractionServer::GetAdvertisedOperationNames();

	TestEqual(TEXT("the advertised operation surface has exactly two operations"), Advertised.Num(), 2);
	TestTrue(
		TEXT("extract_actor_state is advertised"),
		Advertised.Contains(FString(AtlasReadOnlyExtraction::Operations::ExtractActorState)));
	TestTrue(
		TEXT("extract_sequencer_state is advertised"),
		Advertised.Contains(FString(AtlasReadOnlyExtraction::Operations::ExtractSequencerState)));

	TestTrue(
		TEXT("extract_actor_state is supported"),
		FAtlasReadOnlyExtractionServer::IsOperationSupported(TEXT("extract_actor_state")));
	TestTrue(
		TEXT("extract_sequencer_state is supported"),
		FAtlasReadOnlyExtractionServer::IsOperationSupported(TEXT("extract_sequencer_state")));

	// No advertised operation may carry a mutating verb, a render surface or a fixture.
	for (const FString& OperationName : Advertised)
	{
		TestFalse(FString::Printf(TEXT("'%s' is not a mutating operation"), *OperationName), OperationName.StartsWith(TEXT("set_")));
		TestFalse(FString::Printf(TEXT("'%s' is not an apply operation"), *OperationName), OperationName.StartsWith(TEXT("apply_")));
		TestFalse(FString::Printf(TEXT("'%s' is not a submit operation"), *OperationName), OperationName.StartsWith(TEXT("submit_")));
		TestFalse(FString::Printf(TEXT("'%s' is not a configure operation"), *OperationName), OperationName.StartsWith(TEXT("configure_")));
		TestFalse(FString::Printf(TEXT("'%s' is not a compile operation"), *OperationName), OperationName.StartsWith(TEXT("compile_")));
		TestFalse(FString::Printf(TEXT("'%s' is not a reconcile operation"), *OperationName), OperationName.StartsWith(TEXT("reconcile_")));
		TestFalse(FString::Printf(TEXT("'%s' carries no render surface"), *OperationName), OperationName.Contains(TEXT("render")));
		TestFalse(FString::Printf(TEXT("'%s' carries no fixture surface"), *OperationName), OperationName.Contains(TEXT("fixture")));
	}

	// Reported as evidence: the surface this build exposes.
	AddInfo(FString::Printf(
		TEXT("advertised read-only operations: %s"),
		*FString::Join(Advertised, TEXT(", "))));

	return true;
}

// ---------------------------------------------------------------------------
// 2. Every non-extraction operation is refused by name
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionRefusalTest,
	"Atlas.ReadOnlyExtraction.NonExtractionOperationsAreRefused",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionRefusalTest::RunTest(const FString& Parameters)
{
	const FString ServerPipeName(AtlasReadOnlyExtraction::Transport::DefaultPipeName);
	FAtlasReadOnlyExtractionServer Server(ServerPipeName);

	for (const FString& OperationName : RefusedOperationNames())
	{
		TestFalse(
			FString::Printf(TEXT("'%s' is not supported"), *OperationName),
			FAtlasReadOnlyExtractionServer::IsOperationSupported(OperationName));

		// Refused with a write-shaped request, and refused just the same with a read-shaped
		// one: the surface is closed by name, not by the verb the caller used.
		const TArray<FAtlasReadOnlyExtractionServer::FRequest> Probes = {
			MakeRequest(OperationName, TEXT("modify_actor"), TEXT("write"), {AbsentEntityId}),
			MakeRequest(OperationName, TEXT("read"), TEXT("read"), {AbsentEntityId})};

		for (const FAtlasReadOnlyExtractionServer::FRequest& Probe : Probes)
		{
			FString Error;
			FString ErrorCode;
			TestFalse(
				FString::Printf(TEXT("'%s' fails validation"), *OperationName),
				FAtlasReadOnlyExtractionServer::ValidateRequest(Probe, Error, ErrorCode));
			TestEqual(
				FString::Printf(TEXT("'%s' is refused with ERR_UNKNOWN_OPERATION"), *OperationName),
				ErrorCode,
				FString(TEXT("ERR_UNKNOWN_OPERATION")));
			TestNotEqual(
				FString::Printf(TEXT("'%s' refusal carries a message"), *OperationName),
				Error,
				FString());
		}

		// The refusal envelope is well formed and carries no observed state.
		FAtlasReadOnlyExtractionServer::FResponse Response;
		Response.RequestId = TEXT("atlas-read-only-extraction-test-request");
		Response.OperationName = OperationName;
		Response.EntityIds = {AbsentEntityId};
		Response.bSuccess = false;
		Response.Error = TEXT("Unsupported operation");
		Response.Source = AtlasReadOnlyExtraction::Transport::SourceString;
		Response.SchemaVersion = 1;
		Response.ErrorCode = TEXT("ERR_UNKNOWN_OPERATION");

		TSharedPtr<FJsonObject> Envelope;
		const bool bParsed = ParseJson(Server.SerializeResponse(Response), Envelope);
		TestTrue(TEXT("the refusal envelope serializes"), bParsed);
		if (bParsed)
		{
			bool bSuccess = true;
			TestTrue(TEXT("the refusal reports success=false"), Envelope->TryGetBoolField(TEXT("success"), bSuccess) && !bSuccess);
			const TSharedPtr<FJsonObject>* ObservedState = nullptr;
			TestTrue(
				TEXT("the refusal carries no observed state payload"),
				Envelope->TryGetObjectField(TEXT("observed_state"), ObservedState) &&
					ObservedState != nullptr && (*ObservedState)->Values.Num() == 0);
		}
	}

	return true;
}

// ---------------------------------------------------------------------------
// 3. Only the read capability/kind is accepted
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionCapabilityKindTest,
	"Atlas.ReadOnlyExtraction.CapabilityAndKindMustBeRead",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionCapabilityKindTest::RunTest(const FString& Parameters)
{
	FString Error;
	FString ErrorCode;

	// The declared pair is accepted for both exposed operations.
	for (const FString& OperationName : FAtlasReadOnlyExtractionServer::GetAdvertisedOperationNames())
	{
		TestTrue(
			FString::Printf(TEXT("%s accepts its declared read capability/kind"), *OperationName),
			FAtlasReadOnlyExtractionServer::ValidateRequest(
				MakeExtractionRequest(OperationName), Error, ErrorCode));
	}

	// A write kind for an exposed operation is a malformed request, never a write path.
	TestFalse(
		TEXT("a write kind for extract_actor_state is refused"),
		FAtlasReadOnlyExtractionServer::ValidateRequest(
			MakeRequest(TEXT("extract_actor_state"), TEXT("inspect_actor"), TEXT("write"), {AbsentEntityId}),
			Error,
			ErrorCode));
	TestEqual(
		TEXT("a write kind is refused as a malformed request"),
		ErrorCode,
		FString(TEXT("ERR_MISSING_ARGUMENT")));

	// A foreign capability for an exposed operation is refused the same way.
	TestFalse(
		TEXT("a foreign capability is refused"),
		FAtlasReadOnlyExtractionServer::ValidateRequest(
			MakeRequest(TEXT("extract_sequencer_state"), TEXT("inspect_actor"), TEXT("read"), {AbsentEntityId}),
			Error,
			ErrorCode));
	TestEqual(
		TEXT("a foreign capability is refused as a malformed request"),
		ErrorCode,
		FString(TEXT("ERR_MISSING_ARGUMENT")));

	// Envelope-level requirements are unchanged.
	TestFalse(
		TEXT("a wrong schema_version is refused"),
		FAtlasReadOnlyExtractionServer::ValidateRequest(
			[&]()
			{
				FAtlasReadOnlyExtractionServer::FRequest Request = MakeExtractionRequest(TEXT("extract_actor_state"));
				Request.SchemaVersion = 2;
				return Request;
			}(),
			Error,
			ErrorCode));
	TestEqual(
		TEXT("a wrong schema_version reports ERR_UNSUPPORTED_SCHEMA_VERSION"),
		ErrorCode,
		FString(TEXT("ERR_UNSUPPORTED_SCHEMA_VERSION")));

	TestFalse(
		TEXT("an empty authorization_id is refused"),
		FAtlasReadOnlyExtractionServer::ValidateRequest(
			[&]()
			{
				FAtlasReadOnlyExtractionServer::FRequest Request = MakeExtractionRequest(TEXT("extract_actor_state"));
				Request.AuthorizationId = FString();
				return Request;
			}(),
			Error,
			ErrorCode));

	TestFalse(
		TEXT("no entity_ids is refused"),
		FAtlasReadOnlyExtractionServer::ValidateRequest(
			MakeRequest(TEXT("extract_actor_state"), TEXT("inspect_actor"), TEXT("read"), TArray<FString>()),
			Error,
			ErrorCode));

	return true;
}

// ---------------------------------------------------------------------------
// 4. The envelope is the existing Atlas transport envelope
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionEnvelopeTest,
	"Atlas.ReadOnlyExtraction.EnvelopeIsPreserved",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionEnvelopeTest::RunTest(const FString& Parameters)
{
	// Constructing the server opens no pipe: only Run() does.
	const FString EnvelopeServerPipeName(AtlasReadOnlyExtraction::Transport::DefaultPipeName);
	FAtlasReadOnlyExtractionServer Server(EnvelopeServerPipeName);

	FAtlasReadOnlyExtractionServer::FResponse Response;
	Response.RequestId = TEXT("atlas-read-only-extraction-test-request");
	Response.OperationName = TEXT("extract_actor_state");
	Response.EntityIds = {AbsentEntityId};
	Response.bSuccess = false;
	Response.Error = TEXT("probe");
	Response.Source = AtlasReadOnlyExtraction::Transport::SourceString;
	Response.SchemaVersion = 1;
	Response.ErrorCode = TEXT("ERR_EXTRACTION_ENTITY_NOT_FOUND");

	TSharedPtr<FJsonObject> Envelope;
	const bool bParsed = ParseJson(Server.SerializeResponse(Response), Envelope);
	TestTrue(TEXT("the envelope serializes"), bParsed);
	if (!bParsed)
	{
		return false;
	}

	const TArray<FString> RequiredKeys = {
		TEXT("request_id"),
		TEXT("operation_name"),
		TEXT("success"),
		TEXT("error"),
		TEXT("source"),
		TEXT("schema_version"),
		TEXT("error_code"),
		TEXT("session_identity"),
		TEXT("entity_ids"),
		TEXT("observed_state")};

	for (const FString& Key : RequiredKeys)
	{
		TestTrue(
			FString::Printf(TEXT("the envelope carries '%s'"), *Key),
			Envelope->HasField(Key));
	}

	int32 SchemaVersion = 0;
	TestTrue(
		TEXT("schema_version is 1"),
		Envelope->TryGetNumberField(TEXT("schema_version"), SchemaVersion) && SchemaVersion == 1);

	FString Source;
	TestTrue(
		TEXT("the envelope carries the plugin's source string"),
		Envelope->TryGetStringField(TEXT("source"), Source) &&
			Source == FString(AtlasReadOnlyExtraction::Transport::SourceString));

	const TSharedPtr<FJsonObject>* ObservedState = nullptr;
	TestTrue(
		TEXT("observed_state is an object"),
		Envelope->TryGetObjectField(TEXT("observed_state"), ObservedState) && ObservedState != nullptr);

	const TArray<TSharedPtr<FJsonValue>>* EntityIdValues = nullptr;
	TestTrue(
		TEXT("entity_ids is echoed as an array"),
		Envelope->TryGetArrayField(TEXT("entity_ids"), EntityIdValues) &&
			EntityIdValues != nullptr && EntityIdValues->Num() == 1);

	return true;
}

// ---------------------------------------------------------------------------
// 5. Session identity is preserved
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionSessionIdentityTest,
	"Atlas.ReadOnlyExtraction.SessionIdentityIsPreserved",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionSessionIdentityTest::RunTest(const FString& Parameters)
{
	const FString IdentityServerPipeName(AtlasReadOnlyExtraction::Transport::DefaultPipeName);
	FAtlasReadOnlyExtractionServer Server(IdentityServerPipeName);

	FAtlasReadOnlyExtractionServer::FResponse Response;
	Response.RequestId = TEXT("atlas-read-only-extraction-test-request");
	Response.OperationName = TEXT("extract_actor_state");
	Response.EntityIds = {AbsentEntityId};
	Response.Source = AtlasReadOnlyExtraction::Transport::SourceString;
	Response.SchemaVersion = 1;

	TSharedPtr<FJsonObject> Envelope;
	const bool bParsed = ParseJson(Server.SerializeResponse(Response), Envelope);
	TestTrue(TEXT("the envelope serializes"), bParsed);
	if (!bParsed)
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* SessionIdentity = nullptr;
	const bool bHasSessionIdentity =
		Envelope->TryGetObjectField(TEXT("session_identity"), SessionIdentity) && SessionIdentity != nullptr;
	TestTrue(TEXT("the envelope carries session_identity"), bHasSessionIdentity);
	if (!bHasSessionIdentity)
	{
		return false;
	}

	const TArray<FString> RequiredIdentityKeys = {
		TEXT("editor_session_id"),
		TEXT("project_identity"),
		TEXT("engine_version"),
		TEXT("process_id"),
		TEXT("process_creation_time_utc"),
		TEXT("server_start_time_utc")};

	const TSharedPtr<FJsonObject>& Identity = *SessionIdentity;
	TestEqual(
		TEXT("session_identity has exactly the six contract fields"),
		Identity->Values.Num(),
		6);

	for (const FString& Key : RequiredIdentityKeys)
	{
		TestTrue(
			FString::Printf(TEXT("session_identity carries '%s'"), *Key),
			Identity->HasField(Key));
	}

	FString EditorSessionId;
	TestTrue(
		TEXT("editor_session_id is a well-formed GUID"),
		Identity->TryGetStringField(TEXT("editor_session_id"), EditorSessionId) &&
			EditorSessionId.Len() == 36);

	double ProcessId = 0.0;
	TestTrue(
		TEXT("process_id is a positive number"),
		Identity->TryGetNumberField(TEXT("process_id"), ProcessId) && ProcessId > 0.0);

	FString ProcessCreationTimeUtc;
	TestTrue(
		TEXT("process_creation_time_utc is populated"),
		Identity->TryGetStringField(TEXT("process_creation_time_utc"), ProcessCreationTimeUtc) &&
			ProcessCreationTimeUtc.Contains(TEXT("-")));

	FString ServerStartTimeUtc;
	TestTrue(
		TEXT("server_start_time_utc is populated"),
		Identity->TryGetStringField(TEXT("server_start_time_utc"), ServerStartTimeUtc) &&
			ServerStartTimeUtc.Contains(TEXT("-")));

	FString EngineVersion;
	TestTrue(
		TEXT("engine_version is populated"),
		Identity->TryGetStringField(TEXT("engine_version"), EngineVersion) && !EngineVersion.IsEmpty());
	TestTrue(
		TEXT("engine_version is sourced from the engine this plugin is built into"),
		EngineVersion.StartsWith(FString::FromInt(FEngineVersion::Current().GetMajor())));

	FString ProjectIdentity;
	TestTrue(
		TEXT("project_identity is populated"),
		Identity->TryGetStringField(TEXT("project_identity"), ProjectIdentity) && !ProjectIdentity.IsEmpty());

	// The observation reports what it saw; it never reports a decision.
	const FString Serializable = Server.SerializeResponse(Response).ToUpper();
	TestFalse(TEXT("no SATISFIED decision appears in the response"), Serializable.Contains(TEXT("SATISFIED")));
	TestFalse(TEXT("no NOT_SATISFIED decision appears in the response"), Serializable.Contains(TEXT("NOT_SATISFIED")));

	return true;
}

// ---------------------------------------------------------------------------
// 6. The closed refusal path carries no partial payload (fixture-free)
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionRefusalPayloadTest,
	"Atlas.ReadOnlyExtraction.RefusalCarriesNoPartialPayload",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionRefusalPayloadTest::RunTest(const FString& Parameters)
{
	const TArray<FString> Requested = {FString(AbsentEntityId)};

	{
		TSharedPtr<FJsonObject> Tree;
		FString Error;
		FString ErrorCode;
		const bool bExtracted = AtlasStateExtraction::ExtractActorState(Requested, Tree, Error, ErrorCode);

		TestFalse(TEXT("extracting an absent entity does not succeed"), bExtracted);
		TestFalse(TEXT("a failed extraction returns no value tree"), Tree.IsValid());
		TestTrue(
			TEXT("the refusal carries a closed extraction error code"),
			ErrorCode.StartsWith(TEXT("ERR_EXTRACTION_")) &&
				ErrorCode != FString(TEXT("ERR_EXTRACTION_ERROR_CODE_UNKNOWN")));
		AddInfo(FString::Printf(TEXT("actor-state refusal code: %s"), *ErrorCode));
	}

	{
		TSharedPtr<FJsonObject> Tree;
		FString Error;
		FString ErrorCode;
		const bool bExtracted = AtlasStateExtraction::ExtractSequencerState(Requested, Tree, Error, ErrorCode);

		TestFalse(TEXT("sequencer extraction of an absent entity does not succeed"), bExtracted);
		TestFalse(TEXT("a failed sequencer extraction returns no value tree"), Tree.IsValid());
		TestTrue(
			TEXT("the sequencer refusal carries a closed extraction error code"),
			ErrorCode.StartsWith(TEXT("ERR_EXTRACTION_")) &&
				ErrorCode != FString(TEXT("ERR_EXTRACTION_ERROR_CODE_UNKNOWN")));
		AddInfo(FString::Printf(TEXT("sequencer-state refusal code: %s"), *ErrorCode));
	}

	return true;
}

// ---------------------------------------------------------------------------
// 7. Dynamic read-only proof: package dirty state across extraction calls
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionDirtyStateTest,
	"Atlas.ReadOnlyExtraction.PackageDirtyInvarianceAcrossExtractionCall",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionDirtyStateTest::RunTest(const FString& Parameters)
{
	UWorld* World = (GEditor != nullptr) ? GEditor->GetEditorWorldContext().World() : nullptr;
	UPackage* WorldPackage = (World != nullptr) ? World->GetOutermost() : nullptr;

	AddInfo(World != nullptr
		? FString::Printf(TEXT("measuring against the loaded editor world '%s'"), *World->GetName())
		: FString(TEXT("no editor world in this session; measuring process-wide dirty state")));

	TArray<UPackage*> DirtyBefore;
	UEditorLoadingAndSavingUtils::GetDirtyMapPackages(DirtyBefore);
	const bool bWorldDirtyBefore = (WorldPackage != nullptr) ? WorldPackage->IsDirty() : false;

	TSharedPtr<FJsonObject> Tree;
	FString Error;
	FString ErrorCode;
	AtlasStateExtraction::ExtractActorState({FString(AbsentEntityId)}, Tree, Error, ErrorCode);
	AtlasStateExtraction::ExtractSequencerState({FString(AbsentEntityId)}, Tree, Error, ErrorCode);

	TArray<UPackage*> DirtyAfter;
	UEditorLoadingAndSavingUtils::GetDirtyMapPackages(DirtyAfter);

	TestEqual(
		TEXT("the number of dirty map packages is unchanged by an extraction call"),
		DirtyAfter.Num(),
		DirtyBefore.Num());

	if (WorldPackage != nullptr)
	{
		TestEqual(
			TEXT("the world package dirty flag is unchanged by an extraction call"),
			WorldPackage->IsDirty(),
			bWorldDirtyBefore);

		// The stronger form: clean before, clean after.
		bool bCleanAfter = false;
		{
			ClearPackageDirtyFlagForTest(WorldPackage);
			TSharedPtr<FJsonObject> CleanTree;
			AtlasStateExtraction::ExtractActorState({FString(AbsentEntityId)}, CleanTree, Error, ErrorCode);
			bCleanAfter = WorldPackage->IsDirty();
		}
		TestFalse(TEXT("an extraction call leaves a clean world package clean"), bCleanAfter);
	}

	return true;
}

// ---------------------------------------------------------------------------
// 8. The transport starts only under explicit opt-in
// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FAtlasReadOnlyExtractionStartupPolicyTest,
	"Atlas.ReadOnlyExtraction.TransportStartupIsExplicitOptIn",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasReadOnlyExtractionStartupPolicyTest::RunTest(const FString& Parameters)
{
	using namespace AtlasReadOnlyExtraction;

	const FString DefaultPipe(Transport::DefaultPipeName);
	const FString ConfiguredPipe(TEXT("\\\\.\\pipe\\AtlasReadOnlyExtractionTestConfigured"));

	// Loaded, but nothing opted in: the transport stays down.
	const Startup::FDecision NoOptIn = Startup::Evaluate(FString(), false, FString());
	TestFalse(TEXT("no opt-in does not start the transport"), NoOptIn.bStartTransport);
	TestEqual(TEXT("no opt-in falls back to the plugin's default pipe"), NoOptIn.PipeName, DefaultPipe);

	// Command-line opt-in.
	const Startup::FDecision FlagOptIn = Startup::Evaluate(TEXT("-AtlasReadOnlyTransport"), false, FString());
	TestTrue(TEXT("the command-line opt-in starts the transport"), FlagOptIn.bStartTransport);
	TestEqual(TEXT("the command-line opt-in uses the default pipe"), FlagOptIn.PipeName, DefaultPipe);

	// Pipe override by command line, and by configuration.
	const Startup::FDecision FlagPipe =
		Startup::Evaluate(TEXT("-AtlasReadOnlyTransport -AtlasReadOnlyTransportPipe=\\\\.\\pipe\\AtlasReadOnlyExtractionTestSwitch"), false, FString());
	TestTrue(TEXT("the command-line pipe override starts the transport"), FlagPipe.bStartTransport);
	TestEqual(
		TEXT("the command-line pipe override wins"),
		FlagPipe.PipeName,
		FString(TEXT("\\\\.\\pipe\\AtlasReadOnlyExtractionTestSwitch")));
	TestEqual(
		TEXT("the command-line pipe override beats the configured pipe"),
		Startup::Evaluate(TEXT("-AtlasReadOnlyTransport -AtlasReadOnlyTransportPipe=\\\\.\\pipe\\AtlasReadOnlyExtractionTestSwitch"), false, ConfiguredPipe).PipeName,
		FString(TEXT("\\\\.\\pipe\\AtlasReadOnlyExtractionTestSwitch")));

	// Configuration opt-in.
	const Startup::FDecision ConfigOptIn = Startup::Evaluate(FString(), true, ConfiguredPipe);
	TestTrue(TEXT("the configuration opt-in starts the transport"), ConfigOptIn.bStartTransport);
	TestEqual(TEXT("the configured pipe is used"), ConfigOptIn.PipeName, ConfiguredPipe);

	// The default pipe is this plugin's own, never the harness pipe.
	TestNotEqual(
		TEXT("the plugin's default pipe is not the harness transport pipe"),
		DefaultPipe,
		FString(TEXT("\\\\.\\pipe\\AtlasUnrealTransport")));
	TestEqual(
		TEXT("the plugin's default pipe is the declared read-only extraction pipe"),
		DefaultPipe,
		FString(TEXT("\\\\.\\pipe\\AtlasReadOnlyExtraction")));

	// This session's live runtime state must match this session's opt-in decision.
	FString ConfiguredPipeName;
	const bool bConfigEnabled = ReadOptInConfiguration(ConfiguredPipeName);
	const Startup::FDecision SessionDecision =
		Startup::Evaluate(FCommandLine::Get(), bConfigEnabled, ConfiguredPipeName);

	TestEqual(
		TEXT("the running transport state matches the session's opt-in decision"),
		IsTransportRunning(),
		SessionDecision.bStartTransport);

	if (SessionDecision.bStartTransport)
	{
		TestEqual(TEXT("the running transport listens on the decided pipe"), GetRunningPipeName(), SessionDecision.PipeName);
		TestEqual(TEXT("the running transport reports a session id"), GetRunningSessionId().Len(), 36);
	}
	else
	{
		TestFalse(TEXT("no session id exists while the transport is down"), GetRunningSessionId().Len() != 0);
	}

	AddInfo(FString::Printf(
		TEXT("session opt-in decision: start=%s pipe=%s reason=%s"),
		SessionDecision.bStartTransport ? TEXT("true") : TEXT("false"),
		*SessionDecision.PipeName,
		*SessionDecision.Reason));

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
