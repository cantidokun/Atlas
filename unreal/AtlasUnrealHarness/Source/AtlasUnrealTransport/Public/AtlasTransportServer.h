#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/ThreadSafeBool.h"
#include "HAL/Event.h"
#include "Dom/JsonObject.h"

class UMoviePipelineExecutorBase;
class UMoviePipelineExecutorJob;

class FAtlasUE56RenderJobBoundaryTest;
class FAtlasUE56SessionIdentityPurityTest;
class FAtlasUE56SubmitRenderDuplicateSuppressionTest;
class FAtlasUE56SubmitRenderConflictRejectionTest;
class FAtlasUE56WitnessJournalAcceptedBeforeDispatchTest;
class FAtlasUE56WitnessJournalFinishedWithHashAttestationTest;
class FAtlasUE56ReconcileCatalogReportingTest;

class FAtlasTransportServer : public FRunnable
{
    friend class FAtlasUE56RenderJobBoundaryTest;
    friend class FAtlasUE56SessionIdentityPurityTest;
    friend class FAtlasUE56SubmitRenderDuplicateSuppressionTest;
    friend class FAtlasUE56SubmitRenderConflictRejectionTest;
    friend class FAtlasUE56WitnessJournalAcceptedBeforeDispatchTest;
    friend class FAtlasUE56WitnessJournalFinishedWithHashAttestationTest;
    friend class FAtlasUE56ReconcileCatalogReportingTest;
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

    // Process incarnation identity
    FGuid EditorSessionId;
    uint32 ProcessId;
    FString ProcessCreationTimeUtc;
    FString ServerStartTimeUtc;
    FString EngineVersion;
    FString ProjectIdentity;

    struct FTransportRequest {
        FString RequestId;
        FString OperationName;
        FString Capability;
        FString Kind;
        TSharedPtr<FJsonObject> Arguments;
        TArray<FString> EntityIds;
        FString AuthorizationId;
        int32 SchemaVersion;
    };
    struct FTransportResponse {
        FString RequestId;
        FString OperationName;
        TArray<FString> EntityIds;
        bool bSuccess;
        TSharedPtr<FJsonObject> ObservedState;
        FString Error;
        FString Source;
        int32 SchemaVersion;
        FString ErrorCode;
    };
    struct FOutputManifestEntry
    {
        FString Path;
        int64 Size;
        FString Sha256;
    };
    struct FRenderJobState
    {
        FString JobId;
        FString AtlasJobId;
        FString AuthorizationId;
        FString SequenceAssetPath;
        FString ConfigDigest;
        FString OperationName;
        FString Status;
        FString StatusMessage;
        double Progress;
        FString OutputDirectory;
        FString OutputFormat;
        TArray<FString> OutputFiles;
        TArray<FOutputManifestEntry> OutputManifest;
        bool bSuccess;
        bool bFinished;
        bool bFailed;
        TWeakObjectPtr<UMoviePipelineExecutorBase> Executor;
        TWeakObjectPtr<UMoviePipelineExecutorJob> Job;

        FRenderJobState()
            : Progress(0.0)
            , bSuccess(false)
            , bFinished(false)
            , bFailed(false)
        {
        }
    };
    struct FGameThreadExecutionState {
        FTransportRequest Request; FTransportResponse Response; FString Error; TSharedPtr<FJsonObject> ObservedState; FThreadSafeBool bCompleted; FThreadSafeBool bSuccess; FThreadSafeBool bCancelled; FEvent* CompletionEvent;
        FGameThreadExecutionState() : bCompleted(false), bSuccess(false), bCancelled(false), CompletionEvent(FPlatformProcess::GetSynchEventFromPool(false)) {}
        ~FGameThreadExecutionState() { if (CompletionEvent) FPlatformProcess::ReturnSynchEventToPool(CompletionEvent); }
    };
    bool CreatePipeHandle(); void CloseNamedPipe(); bool WaitForClient(); bool ReadRequest(FString& OutJsonRequest); bool WriteResponse(const FString& JsonResponse); bool ParseRequest(const FString& JsonString,FTransportRequest& OutRequest); FString SerializeResponse(const FTransportResponse& Response); bool ValidateRequest(const FTransportRequest& Request,FString& OutError); bool ExecuteRequest(const FTransportRequest& Request,FTransportResponse& OutResponse);
    static void ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState);
    static bool InspectWorld(TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
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
    static bool SetBlueprintMetadata(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool InspectRenderState(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool ConfigureRender(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool SubmitRender(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool InspectRenderJob(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool ReconcileRenderJobs(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool GetCapabilities(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);
    static bool BuildBlueprintState(const FString& AssetPath,TSharedPtr<FJsonObject>& OutBlueprintState,FString& OutError);
    static void FinalizeRenderJobState(
        const TSharedPtr<FRenderJobState>& JobState,
        bool bReportedSuccess,
        const TArray<FString>& DiscoveredFiles,
        const FString& FailureReason = FString());
    static AActor* FindActorByEntityId(const FString& EntityId);

    // Witness Journal & Manifest helpers
    static FString GetJournalDirectory();
    static bool AtomicWriteFile(const FString& TargetFilePath, const FString& FileContents, FString& OutError);
    static bool WriteJournalEntry(
        const FString& AtlasJobId,
        const FString& UnrealJobId,
        const FString& Phase,
        const TSharedPtr<FRenderJobState>& JobState,
        FString& OutError);
    static bool ComputeFileSha256(const FString& FilePath, FString& OutSha256, int64& OutFileSize);
    static void CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject);

    static FCriticalSection RenderJobRegistryMutex;
    static TMap<FString,TSharedPtr<FRenderJobState>> RenderJobRegistry;

    // Active server instance pointer for static handlers
    static FAtlasTransportServer* ActiveInstance;
};
