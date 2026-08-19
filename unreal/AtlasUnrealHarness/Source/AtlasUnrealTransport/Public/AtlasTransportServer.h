#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "HAL/Event.h"
#include "Dom/JsonObject.h"

class FAtlasTransportServer : public FRunnable
{
public:
    FAtlasTransportServer();
    virtual ~FAtlasTransportServer();

    bool StartServer();
    void StopServer();

    // FRunnable interface
    virtual bool Init() override;
    virtual uint32 Run() override;
    virtual void Stop() override;
    virtual void Exit() override;

private:
    static const FString PipeName;
    static const int32 MaxMessageSize;

    FRunnableThread* Thread;
    FThreadSafeBool bStopRequested;
    void* PipeHandle;

    struct FTransportRequest
    {
        FString RequestId;
        FString OperationName;
        FString Capability;
        FString Kind;
        TSharedPtr<FJsonObject> Arguments;
        TArray<FString> EntityIds;
        FString AuthorizationId;
    };

    struct FTransportResponse
    {
        FString RequestId;
        FString OperationName;
        TArray<FString> EntityIds;
        bool bSuccess;
        TSharedPtr<FJsonObject> ObservedState;
        FString Error;
        FString Source;
    };

    // Shared state for game thread execution
    struct FGameThreadExecutionState
    {
        FTransportRequest Request;
        FTransportResponse Response;
        FString Error;
        TSharedPtr<FJsonObject> ObservedState;
        FThreadSafeBool bCompleted;
        FThreadSafeBool bSuccess;
        FEvent* CompletionEvent;

        FGameThreadExecutionState()
            : bCompleted(false)
            , bSuccess(false)
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

    bool CreateNamedPipe();
    void CloseNamedPipe();
    bool WaitForClient();
    bool ReadRequest(FString& OutJsonRequest);
    bool WriteResponse(const FString& JsonResponse);
    
    bool ParseRequest(const FString& JsonString, FTransportRequest& OutRequest);
    FString SerializeResponse(const FTransportResponse& Response);
    
    bool ValidateRequest(const FTransportRequest& Request, FString& OutError);
    bool ExecuteRequest(const FTransportRequest& Request, FTransportResponse& OutResponse);
    
    static void ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState);
    static bool InspectTargetActors(const TArray<FString>& EntityIds, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError);
    static AActor* FindActorByEntityId(const FString& EntityId);
};
