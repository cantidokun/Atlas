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
    struct FTransportRequest { FString RequestId; FString OperationName; FString Capability; FString Kind; TSharedPtr<FJsonObject> Arguments; TArray<FString> EntityIds; FString AuthorizationId; };
    struct FTransportResponse { FString RequestId; FString OperationName; TArray<FString> EntityIds; bool bSuccess; TSharedPtr<FJsonObject> ObservedState; FString Error; FString Source; };
    struct FGameThreadExecutionState {
        FTransportRequest Request; FTransportResponse Response; FString Error; TSharedPtr<FJsonObject> ObservedState; FThreadSafeBool bCompleted; FThreadSafeBool bSuccess; FThreadSafeBool bCancelled; FEvent* CompletionEvent;
        FGameThreadExecutionState() : bCompleted(false), bSuccess(false), bCancelled(false), CompletionEvent(FPlatformProcess::GetSynchEventFromPool(false)) {}
        ~FGameThreadExecutionState() { if (CompletionEvent) FPlatformProcess::ReturnSynchEventToPool(CompletionEvent); }
    };
    bool CreatePipeHandle(); void CloseNamedPipe(); bool WaitForClient(); bool ReadRequest(FString& OutJsonRequest); bool WriteResponse(const FString& JsonResponse); bool ParseRequest(const FString& JsonString,FTransportRequest& OutRequest); FString SerializeResponse(const FTransportResponse& Response); bool ValidateRequest(const FTransportRequest& Request,FString& OutError); bool ExecuteRequest(const FTransportRequest& Request,FTransportResponse& OutResponse);
    static void ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState);
    static bool InspectTargetActors(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool SetActorLocation(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool SetActorRotation(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool SetActorScale(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool InspectMaterialState(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool ApplyMaterialVariant(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool BuildMaterialVariantState(AActor* Actor,TSharedPtr<FJsonObject>& OutMaterialState,FString& OutError);
    static bool InspectNiagaraState(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool ApplyNiagaraVariant(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool BuildNiagaraVariantState(AActor* Actor,TSharedPtr<FJsonObject>& OutNiagaraState,FString& OutError);
    static bool InspectSequencerState(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool SetSequencerPlaybackRange(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool FindSequencerPlaybackRange(int32& OutStartFrame, int32& OutEndFrame, FString& OutError);
    static bool InspectBlueprintState(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool BuildBlueprintState(const FString& AssetPath,TSharedPtr<FJsonObject>& OutBlueprintState,FString& OutError);
    static bool InspectRenderState(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool ConfigureRender(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool BuildRenderState(TSharedPtr<FJsonObject>& OutRenderState,FString& OutError);
    static AActor* FindActorByEntityId(const FString& EntityId);
};
