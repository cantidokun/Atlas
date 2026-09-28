// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (transport server declarations).
//
// The server is a reduced, read-only restatement of the Atlas transport contract:
// the request/response envelope, the wire bound and the closed error codes are the ones
// the existing Atlas transport already uses, and the dispatch table contains exactly the
// two extraction operations. There is no write, render, blueprint, material, Niagara,
// fixture or journal surface here, and no engine-verifiable authorization token: the
// request's `authorization_id` is the Atlas contract field it always was, never a token
// this plugin validates.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "HAL/Event.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"

class FAtlasReadOnlyExtractionServer : public FRunnable
{
public:
	/** The transport envelope. Field set is the existing Atlas transport contract. */
	struct FRequest
	{
		FString RequestId;
		FString OperationName;
		FString Capability;
		FString Kind;
		FString AuthorizationId;
		TSharedPtr<FJsonObject> Arguments;
		TArray<FString> EntityIds;
		int32 SchemaVersion = 0;
	};

	struct FResponse
	{
		FString RequestId;
		FString OperationName;
		TArray<FString> EntityIds;
		bool bSuccess = false;
		TSharedPtr<FJsonObject> ObservedState;
		FString Error;
		FString Source;
		int32 SchemaVersion = 1;
		FString ErrorCode;
	};

	explicit FAtlasReadOnlyExtractionServer(const FString& InPipeName);
	virtual ~FAtlasReadOnlyExtractionServer();

	bool StartServer();
	void StopServer();

	bool IsRunning() const { return Thread != nullptr; }
	const FString& GetPipeName() const { return PipeName; }
	const FGuid& GetEditorSessionId() const { return EditorSessionId; }

	// FRunnable
	virtual bool Init() override;
	virtual uint32 Run() override;
	virtual void Stop() override;
	virtual void Exit() override;

	// --- contract surface (pure; no pipe, no engine, safe to call from tests) ---------

	/** The closed operation surface this server will dispatch. */
	static const TArray<FString>& GetAdvertisedOperationNames();

	/** True only for the two extraction operations. */
	static bool IsOperationSupported(const FString& OperationName);

	/** The wire bound enforced on the response path. */
	static int32 GetTransportMessageSizeLimit();

	/** True when the serialized response would not fit the wire bound. */
	static bool ExceedsTransportBound(const FString& SerializedResponse, int32& OutWireBytes);

	/**
	 * The whole request gate, with the closed error-code mapping the Atlas transport uses:
	 *   ERR_UNSUPPORTED_SCHEMA_VERSION  wrong schema_version
	 *   ERR_UNKNOWN_OPERATION           any operation outside the two extraction operations
	 *   ERR_MISSING_ARGUMENT            every other malformed request (including a request
	 *                                   that asks for a write kind or a foreign capability)
	 */
	static bool ValidateRequest(const FRequest& Request, FString& OutError, FString& OutErrorCode);

	/** Parse a wire request into the envelope; false when the envelope itself is malformed. */
	static bool ParseRequest(const FString& JsonString, FRequest& OutRequest);

	/** Serialize the response envelope (including this incarnation's session identity). */
	FString SerializeResponse(const FResponse& Response) const;

	/** Serialize the response, failing closed when an extraction response cannot fit the wire. */
	FString SerializeCheckedResponse(FResponse& Response) const;

	/** The six session identity fields, as the Atlas transport contract declares them. */
	void CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject) const;

private:
	/**
	 * One request executed on the game thread. The observed state is produced there and
	 * handed back to the pipe thread; nothing else crosses the seam.
	 */
	struct FGameThreadExecutionState
	{
		FRequest Request;
		FResponse Response;
		FString Error;
		FString ErrorCode;
		TSharedPtr<FJsonObject> ObservedState;
		FThreadSafeBool bCompleted;
		FThreadSafeBool bSuccess;
		FThreadSafeBool bCancelled;
		FEvent* CompletionEvent;

		FGameThreadExecutionState()
			: bCompleted(false)
			, bSuccess(false)
			, bCancelled(false)
			, CompletionEvent(FPlatformProcess::GetSynchEventFromPool(false))
		{
		}

		~FGameThreadExecutionState()
		{
			if (CompletionEvent)
			{
				FPlatformProcess::ReturnSynchEventToPool(CompletionEvent);
			}
		}
	};

	bool CreatePipeHandle();
	void CloseNamedPipe();
	bool WaitForClient();
	bool ReadRequest(FString& OutJsonRequest);
	bool WriteResponse(const FString& JsonResponse);
	bool ExecuteRequest(const FRequest& Request, FResponse& OutResponse);
	static void ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState);
	void InitializeProcessIdentity();

	FRunnableThread* Thread;
	FThreadSafeBool bStopRequested;
	void* PipeHandle;
	FString PipeName;

	// Process incarnation identity (declared in initialization order).
	FGuid EditorSessionId;
	uint32 ProcessId;
	FString ProcessCreationTimeUtc;
	FString ServerStartTimeUtc;
	FString EngineVersion;
	FString ProjectIdentity;
};
