// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (transport server).
//
// Envelope, wire framing, wire bound and error codes are the existing Atlas transport
// contract. The dispatch table is closed on the two extraction operations, and the
// extraction core is called through a one-way seam: it receives entity ids and returns
// either a value tree or one code from its closed error vocabulary, and it never calls
// back into this server.
//
// Read-only properties preserved here, by construction:
//   * no write, render, blueprint, material, Niagara, sequencer-edit, fixture or journal
//     operation exists anywhere in this translation unit;
//   * nothing is loaded, created, renamed, saved or dirtied;
//   * the response is untrusted evidence: it carries observations and a session identity,
//     never a verification decision, and never an Atlas semantic expectation.

#include "AtlasReadOnlyExtractionServer.h"

#include "AtlasReadOnlyExtraction.h"
#include "AtlasReadOnlyExtractionContract.h"
#include "AtlasStateExtraction.h"

#include "Dom/JsonValue.h"
#include "HAL/PlatformProcess.h"
#include "Misc/DateTime.h"
#include "Misc/EngineVersion.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <windows.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

namespace
{
	/** How long a request may occupy the game thread before the pipe thread gives up. */
	constexpr int32 OperationTimeoutMilliseconds = 5000;

	/** The extraction error code of the game-thread task, per request. */
	FString S_ExtractionErrorCode;
}

FAtlasReadOnlyExtractionServer::FAtlasReadOnlyExtractionServer(const FString& InPipeName)
	: Thread(nullptr)
	, bStopRequested(false)
	, PipeHandle(nullptr)
	, PipeName(InPipeName.IsEmpty()
			? FString(AtlasReadOnlyExtraction::Transport::DefaultPipeName)
			: InPipeName)
	, ProcessId(0)
{
	InitializeProcessIdentity();
}

FAtlasReadOnlyExtractionServer::~FAtlasReadOnlyExtractionServer()
{
	StopServer();
}

void FAtlasReadOnlyExtractionServer::InitializeProcessIdentity()
{
	EditorSessionId = FGuid::NewGuid();
	ProcessId = FPlatformProcess::GetCurrentProcessId();
	ServerStartTimeUtc = FDateTime::UtcNow().ToIso8601();
	ProjectIdentity = FPaths::GetProjectFilePath();

	// The engine identity is sourced, never hard-coded: this plugin must report the engine
	// it was actually built into, on any engine version, without branching on it.
	EngineVersion = FEngineVersion::Current().ToString();

	// Acquire the true OS creation timestamp on Windows.
	ProcessCreationTimeUtc = ServerStartTimeUtc;
#if PLATFORM_WINDOWS
	HANDLE hProcess = GetCurrentProcess();
	FILETIME ftCreation, ftExit, ftKernel, ftUser;
	if (GetProcessTimes(hProcess, &ftCreation, &ftExit, &ftKernel, &ftUser))
	{
		SYSTEMTIME stUTC;
		if (FileTimeToSystemTime(&ftCreation, &stUTC))
		{
			FDateTime CreationDateTime(
				stUTC.wYear,
				stUTC.wMonth,
				stUTC.wDay,
				stUTC.wHour,
				stUTC.wMinute,
				stUTC.wSecond,
				stUTC.wMilliseconds);
			ProcessCreationTimeUtc = CreationDateTime.ToIso8601();
		}
	}
#endif
}

bool FAtlasReadOnlyExtractionServer::StartServer()
{
	if (Thread)
	{
		UE_LOG(LogAtlasReadOnlyExtraction, Warning, TEXT("Read-only transport server already running"));
		return false;
	}

	bStopRequested = false;
	Thread = FRunnableThread::Create(this, TEXT("AtlasReadOnlyExtractionServer"), 0, TPri_Normal);

	if (Thread == nullptr)
	{
		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("Failed to create the read-only transport thread"));
		return false;
	}

	return true;
}

void FAtlasReadOnlyExtractionServer::StopServer()
{
	if (Thread)
	{
		bStopRequested = true;
		CloseNamedPipe();
		Thread->WaitForCompletion();
		delete Thread;
		Thread = nullptr;
	}
}

bool FAtlasReadOnlyExtractionServer::Init()
{
	UE_LOG(LogAtlasReadOnlyExtraction, Log, TEXT("Read-only transport thread initialising on pipe %s"), *PipeName);
	return true;
}

uint32 FAtlasReadOnlyExtractionServer::Run()
{
	UE_LOG(LogAtlasReadOnlyExtraction, Log, TEXT("Read-only transport thread started on pipe %s"), *PipeName);

	while (!bStopRequested)
	{
		if (!CreatePipeHandle())
		{
			UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("Failed to create the read-only named pipe %s"), *PipeName);
			FPlatformProcess::Sleep(1.0f);
			continue;
		}

		if (!WaitForClient())
		{
			CloseNamedPipe();
			if (!bStopRequested)
			{
				UE_LOG(LogAtlasReadOnlyExtraction, Warning, TEXT("Read-only transport client connection failed"));
				FPlatformProcess::Sleep(0.1f);
			}
			continue;
		}

		if (bStopRequested)
		{
			CloseNamedPipe();
			break;
		}

		FString JsonRequest;
		if (ReadRequest(JsonRequest))
		{
			if (bStopRequested)
			{
				CloseNamedPipe();
				break;
			}

			FRequest Request;
			if (ParseRequest(JsonRequest, Request))
			{
				FString ValidationError;
				FString ValidationErrorCode;
				if (ValidateRequest(Request, ValidationError, ValidationErrorCode))
				{
					FResponse Response;
					ExecuteRequest(Request, Response);
					WriteResponse(SerializeCheckedResponse(Response));
				}
				else
				{
					FResponse ErrorResponse;
					ErrorResponse.RequestId = Request.RequestId;
					ErrorResponse.OperationName = Request.OperationName;
					ErrorResponse.EntityIds = Request.EntityIds;
					ErrorResponse.bSuccess = false;
					ErrorResponse.Error = ValidationError;
					ErrorResponse.Source = AtlasReadOnlyExtraction::Transport::SourceString;
					ErrorResponse.SchemaVersion = 1;
					ErrorResponse.ErrorCode = ValidationErrorCode;
					WriteResponse(SerializeResponse(ErrorResponse));
				}
			}
			else
			{
				UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("Failed to parse the request JSON envelope"));
			}
		}
		else
		{
			UE_LOG(LogAtlasReadOnlyExtraction, Warning, TEXT("Failed to read a request from the pipe"));
		}

		CloseNamedPipe();
	}

	UE_LOG(LogAtlasReadOnlyExtraction, Log, TEXT("Read-only transport thread exiting"));
	return 0;
}

void FAtlasReadOnlyExtractionServer::Stop()
{
	bStopRequested = true;
}

void FAtlasReadOnlyExtractionServer::Exit()
{
	CloseNamedPipe();
}

bool FAtlasReadOnlyExtractionServer::CreatePipeHandle()
{
#if PLATFORM_WINDOWS
	const int32 MessageSize = GetTransportMessageSizeLimit();
	HANDLE hPipe = CreateNamedPipeA(
		TCHAR_TO_ANSI(*PipeName),
		PIPE_ACCESS_DUPLEX,
		PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
		1,
		MessageSize,
		MessageSize,
		0,
		nullptr);

	if (hPipe == INVALID_HANDLE_VALUE)
	{
		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("CreateNamedPipe failed with error: %d"), GetLastError());
		return false;
	}

	PipeHandle = hPipe;
	return true;
#else
	return false;
#endif
}

void FAtlasReadOnlyExtractionServer::CloseNamedPipe()
{
#if PLATFORM_WINDOWS
	if (PipeHandle && PipeHandle != INVALID_HANDLE_VALUE)
	{
		CloseHandle((HANDLE)PipeHandle);
		PipeHandle = nullptr;
	}
#endif
}

bool FAtlasReadOnlyExtractionServer::WaitForClient()
{
#if PLATFORM_WINDOWS
	if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
	{
		return false;
	}

	BOOL bConnected = ConnectNamedPipe((HANDLE)PipeHandle, nullptr);
	if (!bConnected)
	{
		const DWORD Error = GetLastError();
		if (Error == ERROR_PIPE_CONNECTED)
		{
			return true;
		}

		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("ConnectNamedPipe failed with error: %d"), Error);
		return false;
	}

	return true;
#else
	return false;
#endif
}

bool FAtlasReadOnlyExtractionServer::ReadRequest(FString& OutJsonRequest)
{
#if PLATFORM_WINDOWS
	if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
	{
		return false;
	}

	const int32 MessageSize = GetTransportMessageSizeLimit();
	TArray<uint8> Buffer;
	Buffer.SetNum(MessageSize);
	DWORD BytesRead = 0;

	const BOOL bRead = ReadFile((HANDLE)PipeHandle, Buffer.GetData(), MessageSize, &BytesRead, nullptr);
	if (!bRead)
	{
		const DWORD Error = GetLastError();
		if (Error == ERROR_MORE_DATA)
		{
			UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("Message exceeds the wire bound of %d bytes"), MessageSize);
			return false;
		}

		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("ReadFile failed with error: %d"), Error);
		return false;
	}

	if (BytesRead == 0)
	{
		return false;
	}

	Buffer.SetNum(BytesRead + 1);
	Buffer[BytesRead] = 0;
	OutJsonRequest = FString(UTF8_TO_TCHAR(reinterpret_cast<const char*>(Buffer.GetData())));
	return true;
#else
	return false;
#endif
}

bool FAtlasReadOnlyExtractionServer::WriteResponse(const FString& JsonResponse)
{
#if PLATFORM_WINDOWS
	if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
	{
		return false;
	}

	FTCHARToUTF8 UTF8String(*JsonResponse);
	const DWORD BytesToWrite = UTF8String.Length();
	DWORD BytesWritten = 0;

	const BOOL bWritten = WriteFile((HANDLE)PipeHandle, UTF8String.Get(), BytesToWrite, &BytesWritten, nullptr);
	if (!bWritten || BytesWritten != BytesToWrite)
	{
		UE_LOG(LogAtlasReadOnlyExtraction, Error, TEXT("WriteFile failed with error: %d"), GetLastError());
		return false;
	}

	FlushFileBuffers((HANDLE)PipeHandle);
	return true;
#else
	return false;
#endif
}

const TArray<FString>& FAtlasReadOnlyExtractionServer::GetAdvertisedOperationNames()
{
	return AtlasReadOnlyExtraction::Operations::GetSupportedOperationNames();
}

bool FAtlasReadOnlyExtractionServer::IsOperationSupported(const FString& OperationName)
{
	return AtlasReadOnlyExtraction::Operations::IsSupportedOperation(OperationName);
}

int32 FAtlasReadOnlyExtractionServer::GetTransportMessageSizeLimit()
{
	return AtlasReadOnlyExtraction::Transport::GetMessageSizeLimit();
}

bool FAtlasReadOnlyExtractionServer::ExceedsTransportBound(const FString& SerializedResponse, int32& OutWireBytes)
{
	// The wire form is exactly this conversion: WriteResponse writes FTCHARToUTF8 bytes.
	OutWireBytes = FTCHARToUTF8(*SerializedResponse).Length();
	return OutWireBytes > GetTransportMessageSizeLimit();
}

bool FAtlasReadOnlyExtractionServer::ParseRequest(const FString& JsonString, FRequest& OutRequest)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		return false;
	}

	if (!JsonObject->TryGetStringField(TEXT("request_id"), OutRequest.RequestId) ||
		!JsonObject->TryGetStringField(TEXT("operation_name"), OutRequest.OperationName) ||
		!JsonObject->TryGetStringField(TEXT("capability"), OutRequest.Capability) ||
		!JsonObject->TryGetStringField(TEXT("kind"), OutRequest.Kind) ||
		!JsonObject->TryGetStringField(TEXT("authorization_id"), OutRequest.AuthorizationId))
	{
		return false;
	}

	if (!JsonObject->TryGetStringArrayField(TEXT("entity_ids"), OutRequest.EntityIds))
	{
		return false;
	}

	// Fail closed on an unversioned request, exactly as the Atlas transport does.
	int32 SchemaVersion = 0;
	if (JsonObject->TryGetNumberField(TEXT("schema_version"), SchemaVersion))
	{
		OutRequest.SchemaVersion = SchemaVersion;
	}
	else
	{
		OutRequest.SchemaVersion = 0;
	}

	const TSharedPtr<FJsonObject>* ArgumentsObject = nullptr;
	if (JsonObject->TryGetObjectField(TEXT("arguments"), ArgumentsObject))
	{
		OutRequest.Arguments = *ArgumentsObject;
	}

	return true;
}

bool FAtlasReadOnlyExtractionServer::ValidateRequest(const FRequest& Request, FString& OutError, FString& OutErrorCode)
{
	OutError.Empty();
	OutErrorCode.Empty();

	if (Request.SchemaVersion != 1)
	{
		OutError = FString::Printf(TEXT("Unsupported schema_version: %d (expected 1)"), Request.SchemaVersion);
		OutErrorCode = TEXT("ERR_UNSUPPORTED_SCHEMA_VERSION");
		return false;
	}

	if (Request.RequestId.IsEmpty())
	{
		OutError = TEXT("request_id cannot be empty");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	// authorization_id remains the Atlas contract field it always was. This plugin does
	// not treat it as an engine-verifiable token, and it does not invent one.
	if (Request.AuthorizationId.IsEmpty() || Request.AuthorizationId.TrimStartAndEnd().IsEmpty())
	{
		OutError = TEXT("authorization_id cannot be empty");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	// The closed surface: anything that is not one of the two extraction operations is
	// refused by name, before any arguments are looked at.
	if (!IsOperationSupported(Request.OperationName))
	{
		OutError = FString::Printf(TEXT("Unsupported operation: %s"), *Request.OperationName);
		OutErrorCode = TEXT("ERR_UNKNOWN_OPERATION");
		return false;
	}

	// Only the declared read capability/kind is accepted for an exposed operation: a
	// request that asks for a write kind is a malformed request, not a write operation.
	FString PairError;
	if (!AtlasReadOnlyExtraction::Operations::IsReadOnlyRequest(
			Request.OperationName,
			Request.Capability,
			Request.Kind,
			PairError))
	{
		OutError = PairError;
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	if (Request.EntityIds.Num() == 0)
	{
		OutError = TEXT("entity_ids cannot be empty");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	for (const FString& EntityId : Request.EntityIds)
	{
		if (EntityId.IsEmpty() || EntityId.TrimStartAndEnd().IsEmpty())
		{
			OutError = TEXT("entity_ids cannot contain empty strings");
			OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
			return false;
		}
	}

	if (!Request.Arguments.IsValid())
	{
		OutError = TEXT("arguments cannot be null");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	TArray<FString> ArgumentEntityIds;
	if (!Request.Arguments->TryGetStringArrayField(TEXT("entity_ids"), ArgumentEntityIds))
	{
		OutError = TEXT("arguments.entity_ids must be an array of strings");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	if (ArgumentEntityIds.Num() != Request.EntityIds.Num())
	{
		OutError = TEXT("arguments.entity_ids must match entity_ids");
		OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
		return false;
	}

	for (int32 Index = 0; Index < Request.EntityIds.Num(); ++Index)
	{
		if (ArgumentEntityIds[Index] != Request.EntityIds[Index])
		{
			OutError = TEXT("arguments.entity_ids must match entity_ids");
			OutErrorCode = TEXT("ERR_MISSING_ARGUMENT");
			return false;
		}
	}

	return true;
}

void FAtlasReadOnlyExtractionServer::CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject) const
{
	if (!OutSessionObject.IsValid())
	{
		OutSessionObject = MakeShareable(new FJsonObject());
	}

	OutSessionObject->SetStringField(TEXT("editor_session_id"), EditorSessionId.ToString(EGuidFormats::DigitsWithHyphens));
	OutSessionObject->SetNumberField(TEXT("process_id"), (double)ProcessId);
	OutSessionObject->SetStringField(TEXT("process_creation_time_utc"), ProcessCreationTimeUtc);
	OutSessionObject->SetStringField(TEXT("server_start_time_utc"), ServerStartTimeUtc);
	OutSessionObject->SetStringField(TEXT("engine_version"), EngineVersion);
	OutSessionObject->SetStringField(TEXT("project_identity"), ProjectIdentity);
}

FString FAtlasReadOnlyExtractionServer::SerializeResponse(const FResponse& Response) const
{
	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject());
	JsonObject->SetStringField(TEXT("request_id"), Response.RequestId);
	JsonObject->SetStringField(TEXT("operation_name"), Response.OperationName);
	JsonObject->SetBoolField(TEXT("success"), Response.bSuccess);
	JsonObject->SetStringField(TEXT("error"), Response.Error);
	JsonObject->SetStringField(TEXT("source"), Response.Source);
	JsonObject->SetNumberField(TEXT("schema_version"), Response.SchemaVersion > 0 ? Response.SchemaVersion : 1);
	JsonObject->SetStringField(TEXT("error_code"), Response.ErrorCode);

	TSharedPtr<FJsonObject> SessionObject = MakeShareable(new FJsonObject());
	CollectSessionIdentity(SessionObject);
	JsonObject->SetObjectField(TEXT("session_identity"), SessionObject);

	TArray<TSharedPtr<FJsonValue>> EntityIdsArray;
	for (const FString& EntityId : Response.EntityIds)
	{
		EntityIdsArray.Add(MakeShareable(new FJsonValueString(EntityId)));
	}
	JsonObject->SetArrayField(TEXT("entity_ids"), EntityIdsArray);

	if (Response.ObservedState.IsValid())
	{
		JsonObject->SetObjectField(TEXT("observed_state"), Response.ObservedState);
	}
	else
	{
		JsonObject->SetObjectField(TEXT("observed_state"), MakeShareable(new FJsonObject()));
	}

	FString OutputString;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
	return OutputString;
}

FString FAtlasReadOnlyExtractionServer::SerializeCheckedResponse(FResponse& Response) const
{
	FString Payload = SerializeResponse(Response);

	// The extraction design §9 item 3 requirement, unchanged: an extraction response that
	// would not fit the wire bound fails closed, and is never truncated or chunked.
	int32 WireBytes = 0;
	if (!ExceedsTransportBound(Payload, WireBytes))
	{
		return Payload;
	}

	UE_LOG(
		LogAtlasReadOnlyExtraction,
		Error,
		TEXT("Extraction response of %d bytes exceeds the wire bound of %d bytes; failing closed before writing"),
		WireBytes,
		GetTransportMessageSizeLimit());

	Response.bSuccess = false;
	Response.ObservedState.Reset();
	Response.Error = FString::Printf(
		TEXT("the extraction response would not fit the transport bound (%d bytes > %d bytes)"),
		WireBytes,
		GetTransportMessageSizeLimit());
	Response.ErrorCode = TEXT("ERR_EXTRACTION_PAYLOAD_TOO_LARGE");
	return SerializeResponse(Response);
}

bool FAtlasReadOnlyExtractionServer::ExecuteRequest(const FRequest& Request, FResponse& OutResponse)
{
	OutResponse.RequestId = Request.RequestId;
	OutResponse.OperationName = Request.OperationName;
	OutResponse.EntityIds = Request.EntityIds;
	OutResponse.Source = AtlasReadOnlyExtraction::Transport::SourceString;
	OutResponse.SchemaVersion = 1;
	OutResponse.ErrorCode = TEXT("");

	// Defence in depth: the dispatch table is closed here as well as in ValidateRequest, so
	// no path can reach any operation that is not one of the two extraction operations.
	if (!IsOperationSupported(Request.OperationName))
	{
		OutResponse.bSuccess = false;
		OutResponse.Error = FString::Printf(TEXT("Unsupported operation: %s"), *Request.OperationName);
		OutResponse.ErrorCode = TEXT("ERR_UNKNOWN_OPERATION");
		return false;
	}

	TSharedPtr<FGameThreadExecutionState> SharedState = MakeShareable(new FGameThreadExecutionState());
	SharedState->Request = Request;
	SharedState->Response.RequestId = Request.RequestId;
	SharedState->Response.OperationName = Request.OperationName;
	SharedState->Response.EntityIds = Request.EntityIds;
	SharedState->Response.Source = AtlasReadOnlyExtraction::Transport::SourceString;
	SharedState->Response.SchemaVersion = 1;

	AsyncTask(ENamedThreads::GameThread, [SharedState]()
	{
		FAtlasReadOnlyExtractionServer::ExecuteOnGameThread(SharedState);
	});

	const bool bEventTriggered = SharedState->CompletionEvent->Wait(OperationTimeoutMilliseconds);
	if (bStopRequested)
	{
		SharedState->bCancelled = true;
		OutResponse.bSuccess = false;
		OutResponse.Error = TEXT("Operation cancelled during shutdown");
		OutResponse.ErrorCode = TEXT("ERR_OPERATION_CANCELLED");
		return false;
	}

	if (!bEventTriggered)
	{
		SharedState->bCancelled = true;
		OutResponse.bSuccess = false;
		OutResponse.Error = TEXT("Operation timed out");
		OutResponse.ErrorCode = TEXT("ERR_OPERATION_TIMED_OUT");
		return false;
	}

	OutResponse = SharedState->Response;
	return SharedState->bSuccess;
}

void FAtlasReadOnlyExtractionServer::ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> S)
{
	if (S->bCancelled)
	{
		S->Response.bSuccess = false;
		S->Response.Error = TEXT("Operation cancelled before execution");
		S->bSuccess = false;
		S->bCompleted = true;
		S->CompletionEvent->Trigger();
		return;
	}

	if (!IsInGameThread())
	{
		S->Response.bSuccess = false;
		S->Response.Error = TEXT("ExecuteOnGameThread must be called on the game thread");
		S->bSuccess = false;
		S->bCompleted = true;
		S->CompletionEvent->Trigger();
		return;
	}

	if (!GEngine || IsEngineExitRequested())
	{
		S->Response.bSuccess = false;
		S->Response.Error = TEXT("Engine shutting down");
		S->bSuccess = false;
		S->bCompleted = true;
		S->CompletionEvent->Trigger();
		return;
	}

	bool bTaskSuccess = false;
	S_ExtractionErrorCode.Empty();

	// The single one-way seam (extraction design §10.2 item 2): the extractor receives the
	// request's entity ids and returns either a value tree or one code from the closed
	// error vocabulary. The dispatcher wraps the tree; the extractor never calls back.
	if (S->Request.OperationName == AtlasReadOnlyExtraction::Operations::ExtractActorState)
	{
		TSharedPtr<FJsonObject> ValueTree;
		bTaskSuccess = AtlasStateExtraction::ExtractActorState(
			S->Request.EntityIds,
			ValueTree,
			S->Error,
			S_ExtractionErrorCode);

		if (bTaskSuccess)
		{
			TSharedPtr<FJsonObject> ExtractionNode = MakeShareable(new FJsonObject());
			ExtractionNode->SetObjectField(TEXT("unreal_state_extraction"), ValueTree);
			S->ObservedState = ExtractionNode;
		}
	}
	else if (S->Request.OperationName == AtlasReadOnlyExtraction::Operations::ExtractSequencerState)
	{
		TSharedPtr<FJsonObject> ValueTree;
		bTaskSuccess = AtlasStateExtraction::ExtractSequencerState(
			S->Request.EntityIds,
			ValueTree,
			S->Error,
			S_ExtractionErrorCode);

		if (bTaskSuccess)
		{
			TSharedPtr<FJsonObject> ExtractionNode = MakeShareable(new FJsonObject());
			ExtractionNode->SetObjectField(TEXT("unreal_state_extraction"), ValueTree);
			S->ObservedState = ExtractionNode;
		}
	}
	else
	{
		// Unreachable through the dispatcher; present so the table stays closed at runtime.
		S->Error = FString::Printf(TEXT("Unsupported operation: %s"), *S->Request.OperationName);
		S->Response.ErrorCode = TEXT("ERR_UNKNOWN_OPERATION");
	}

	if (bTaskSuccess && S->Error.IsEmpty())
	{
		S->Response.bSuccess = true;
		S->Response.ObservedState = S->ObservedState;
		S->Response.ErrorCode = TEXT("");
		S->bSuccess = true;
	}
	else
	{
		S->Response.bSuccess = false;
		S->Response.Error = S->Error.IsEmpty() ? TEXT("Unknown error during extraction") : S->Error;
		if (!S_ExtractionErrorCode.IsEmpty())
		{
			S->Response.ErrorCode = S_ExtractionErrorCode;
		}
		else if (S->Response.ErrorCode.IsEmpty())
		{
			S->Response.ErrorCode = TEXT("ERR_OPERATION_FAILED");
		}
		S->bSuccess = false;
	}

	S->bCompleted = true;
	S->CompletionEvent->Trigger();
}
